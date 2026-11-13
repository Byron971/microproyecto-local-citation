"""Clasificador de la funcion de la cita: encoder + dropout + Linear(hidden, 9) sobre [CLS].

Importa torch: solo lo cargan `cli_modelo` y los tests con `importorskip`. La misma
estrategia (cabeza sobre [CLS]) se usa en SciBERT y SPECTER; es la nativa de SPECTER."""
import hashlib
import json
import math
import os
import platform
import random
import time
import warnings
from dataclasses import asdict, dataclass
from pathlib import Path

import torch
import transformers
from huggingface_hub import snapshot_download
from recuperacion_densa.descarga_modelo import hash_manifiesto, manifiesto_de
from safetensors.torch import load_file, save_file
from torch import nn
from torch.utils.data import DataLoader
from transformers import AutoModel, AutoTokenizer, get_linear_schedule_with_warmup

from . import dominio, exportar, revision

# Debe fijarse antes de la primera operacion CUDA para que los matmul sean deterministas.
os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
# Menos fragmentacion de memoria en corridas largas (tambien antes de la primera operacion CUDA).
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")


@dataclass(frozen=True)
class Hiperparametros:
    """Identicos en ambos encoders y fijados antes de mirar el eval."""
    max_len: int = 512
    lr: float = 2e-5
    weight_decay: float = 0.01
    warmup: float = 0.1
    batch_size: int = 8
    acumulacion: int = 2
    epocas: int = 6
    paciencia: int = 2
    clip: float = 1.0
    dropout: float = 0.1
    pesos_clase: bool = True


# ---------------------------------------------------------------- determinismo y carga
def fijar_determinismo(semilla: int) -> None:
    random.seed(semilla)
    torch.manual_seed(semilla)
    torch.cuda.manual_seed_all(semilla)
    torch.use_deterministic_algorithms(True, warn_only=True)
    torch.backends.cudnn.benchmark = False


def resolver_encoder(encoder: str, manifiesto: Path) -> Path:
    """Snapshot local (sin red) del encoder, verificado contra su manifiesto SHA."""
    model_id, rev = revision.modelo(encoder)
    ruta = Path(snapshot_download(model_id, revision=rev, local_files_only=True))
    if ruta.name != rev:
        raise RuntimeError(f"El commit resuelto ({ruta.name}) no coincide con la revision ({rev}).")
    if not Path(manifiesto).is_file():
        raise FileNotFoundError(f"Falta {manifiesto}: ejecute descarga_modelo --encoder {encoder}.")
    previo = json.loads(Path(manifiesto).read_text(encoding="utf-8"))
    if hash_manifiesto(manifiesto_de(ruta, model_id, rev)) != previo.get("sha256_manifiesto"):
        raise RuntimeError(f"El snapshot de {encoder} no coincide con {manifiesto}.")
    return ruta


class TokenizadorHF:
    """Cumple el puerto `Tokenizador`: ids de subpalabras sin tokens especiales."""

    def __init__(self, ruta: Path):
        self.tokenizer = AutoTokenizer.from_pretrained(ruta, trust_remote_code=False)
        self.tokenizer.model_max_length = int(1e9)  # el recorte lo hace `ensamblar`
        self.cls_id = self.tokenizer.cls_token_id
        self.sep_id = self.tokenizer.sep_token_id
        self.pad_id = self.tokenizer.pad_token_id
        vocab = Path(ruta) / "vocab.txt"
        self._vocab_sha = hashlib.sha256(vocab.read_bytes()).hexdigest() if vocab.is_file() else None

    def ids(self, texto: str) -> list[int]:
        return self.tokenizer.encode(texto, add_special_tokens=False, truncation=False)

    def info(self) -> dict:
        """Huella del tokenizer: SciBERT y SPECTER NO comparten vocab.txt."""
        return {"clase": type(self.tokenizer).__name__, "vocab_size": len(self.tokenizer),
                "vocab_sha256": self._vocab_sha,
                "do_lower_case": getattr(self.tokenizer, "do_lower_case", None)}


class ClasificadorCLS(nn.Module):
    def __init__(self, ruta: Path, semilla: int, dropout: float = 0.1):
        super().__init__()
        # atencion "eager": SDPA (flash/mem-efficient) tiene retroceso no determinista en CUDA
        self.encoder = AutoModel.from_pretrained(ruta, trust_remote_code=False,
                                                 attn_implementation="eager")
        torch.manual_seed(semilla)  # la cabeza se inicializa con la semilla de la corrida
        self.dropout = nn.Dropout(dropout)
        self.cabeza = nn.Linear(self.encoder.config.hidden_size, dominio.N_CLASES)

    def forward(self, input_ids, attention_mask):
        cls = self.encoder(input_ids=input_ids, attention_mask=attention_mask).last_hidden_state[:, 0]
        return self.cabeza(self.dropout(cls))


# ---------------------------------------------------------------- ejemplos y lotes
def preparar_ejemplos(entradas: list[dict], tipo: str, tokenizador, max_len: int) -> list[dict]:
    ejemplos = []
    for e in entradas:
        segmentos = dominio.tokenizar_segmentos(dominio.construir_segmentos(e, tipo), tokenizador)
        r = dominio.ensamblar(segmentos, max_len, tokenizador.cls_id, tokenizador.sep_id)
        ejemplo = {"context_id": e["context_id"], "input_ids": r["input_ids"],
                   "truncados": r["truncados"], "indice": e.get("indice")}
        for campo in ("objetivo", "peso"):  # perdidas kd / ponderado: no deben perderse aqui
            if e.get(campo) is not None:
                ejemplo[campo] = e[campo]
        ejemplos.append(ejemplo)
    return ejemplos


def resumen_truncamiento(ejemplos: list[dict]) -> dict:
    if not ejemplos:
        return {}
    nombres = sorted({k for e in ejemplos for k in e["truncados"]})
    n = len(ejemplos)
    salida = {"casos": n, "longitud_media": sum(len(e["input_ids"]) for e in ejemplos) / n,
              "segmentos": {}}
    for k in nombres:
        v = [e["truncados"].get(k, 0) for e in ejemplos]
        salida["segmentos"][k] = {"frac_truncado": sum(1 for x in v if x) / n,
                                  "tokens_truncados_media": sum(v) / n, "tokens_truncados_max": max(v)}
    return salida


def _lote(ejemplos: list[dict], pad_id: int, dispositivo) -> tuple:
    largo = max(len(e["input_ids"]) for e in ejemplos)
    ids = torch.full((len(ejemplos), largo), pad_id, dtype=torch.long)
    mask = torch.zeros((len(ejemplos), largo), dtype=torch.long)
    for i, e in enumerate(ejemplos):
        ids[i, :len(e["input_ids"])] = torch.tensor(e["input_ids"])
        mask[i, :len(e["input_ids"])] = 1
    etiquetas = None
    if all(e.get("indice") is not None for e in ejemplos):
        etiquetas = torch.tensor([e["indice"] for e in ejemplos], dtype=torch.long)
    return ids.to(dispositivo), mask.to(dispositivo), (etiquetas.to(dispositivo) if etiquetas is not None else None)


def _extras(ejemplos: list[dict], dispositivo) -> tuple:
    """(objetivo, peso) del lote; None cuando los ejemplos no traen el campo opcional."""
    objetivo = peso = None
    if all(e.get("objetivo") is not None for e in ejemplos):
        objetivo = torch.tensor([e["objetivo"] for e in ejemplos], dtype=torch.float32).to(dispositivo)
    if all(e.get("peso") is not None for e in ejemplos):
        peso = torch.tensor([e["peso"] for e in ejemplos], dtype=torch.float32).to(dispositivo)
    return objetivo, peso


def calcular_perdida(logits, y, pesos_clase=None, objetivo=None, peso=None):
    """Entropia cruzada media ponderada. Con `objetivo` (distribucion de 9 clases) usa etiquetas
    suaves; `peso` pondera cada muestra. Sin campos opcionales == CrossEntropyLoss(weight)."""
    logp = torch.log_softmax(logits.float(), dim=-1)
    if objetivo is not None:
        por_muestra = -(objetivo * logp).sum(-1)
        w = (objetivo * pesos_clase).sum(-1) if pesos_clase is not None else torch.ones_like(por_muestra)
    else:
        por_muestra = nn.functional.nll_loss(logp, y, reduction="none")
        w = pesos_clase[y] if pesos_clase is not None else torch.ones_like(por_muestra)
    if peso is not None:
        w = w * peso
    return (por_muestra * w).sum() / w.sum()


def _autocast(dispositivo):
    return torch.autocast(device_type=dispositivo.type, dtype=torch.bfloat16,
                          enabled=dispositivo.type == "cuda")


@torch.inference_mode()
def predecir_probabilidades(modelo, ejemplos: list[dict], pad_id: int, dispositivo,
                            batch_size: int = 16) -> tuple[list[list[float]], list[float]]:
    """(probabilidades softmax por caso, latencia en ms por caso = tiempo del lote / n)."""
    modelo.eval()
    probs, latencias = [], []
    for ini in range(0, len(ejemplos), batch_size):
        lote = ejemplos[ini:ini + batch_size]
        ids, mask, _ = _lote(lote, pad_id, dispositivo)
        t0 = time.perf_counter()
        with _autocast(dispositivo):
            logits = modelo(ids, mask)
        p = torch.softmax(logits.float(), dim=-1).cpu()
        if dispositivo.type == "cuda":
            torch.cuda.synchronize()
        dt = (time.perf_counter() - t0) * 1000 / len(lote)
        probs += [[float(x) for x in fila] for fila in p.tolist()]
        latencias += [dt] * len(lote)
    return probs, latencias


def _f1_val(modelo, ejemplos, pad_id, dispositivo, batch_size) -> dict:
    probs, _ = predecir_probabilidades(modelo, ejemplos, pad_id, dispositivo, batch_size)
    pred = [max(range(dominio.N_CLASES), key=lambda i: (p[i], -i)) for p in probs]
    return dominio.metricas([e["indice"] for e in ejemplos], pred)


def _sha_archivo(ruta: Path) -> str:
    h = hashlib.sha256()
    with Path(ruta).open("rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def guardar_checkpoint(modelo, ruta: Path) -> str:
    save_file({k: v.detach().cpu().contiguous().clone() for k, v in modelo.state_dict().items()},
              str(ruta))
    return _sha_archivo(ruta)


def cargar_checkpoint(modelo, ruta: Path, sha_esperado: str | None = None) -> None:
    if sha_esperado is not None and _sha_archivo(ruta) != sha_esperado:
        raise RuntimeError(f"El checkpoint {ruta} no coincide con checkpoint_sha256.")
    modelo.load_state_dict(load_file(str(ruta)))


def hardware() -> dict:
    gpu = torch.cuda.get_device_name(0) if torch.cuda.is_available() else None
    return {"gpu": gpu, "torch": torch.__version__, "cuda": torch.version.cuda,
            "transformers": transformers.__version__, "python": platform.python_version()}


# ---------------------------------------------------------------- entrenamiento
def entrenar(modelo: ClasificadorCLS, train: list[dict], val: list[dict], pad_id: int,
             semilla: int, hp: Hiperparametros, salida: Path, dispositivo,
             al_terminar_epoca=None) -> dict:
    """Entrena con early stopping sobre macro-F1 de val y guarda el MEJOR checkpoint.

    `train`/`val`: ejemplos de `preparar_ejemplos` con `indice`. Devuelve el manifiesto de
    entrenamiento (historial, mejor epoca, metricas de val, SHA del checkpoint).

    Campos opcionales de los ejemplos de `train`: `objetivo` (distribucion de 9 clases, perdida
    de etiquetas suaves) y `peso` (ponderacion por muestra). `al_terminar_epoca(registro)` se
    llama tras cada epoca con el registro del historial."""
    if not train or not val:
        raise ValueError("Se necesitan ejemplos de train y val.")
    if any(e["indice"] is None for e in (*train, *val)):
        raise ValueError("train y val deben tener etiquetas.")
    fijar_determinismo(semilla)
    if dispositivo.type == "cuda":
        torch.cuda.reset_peak_memory_stats(dispositivo)
    modelo.to(dispositivo)
    salida.mkdir(parents=True, exist_ok=True)
    sin_decay = ("bias", "LayerNorm.weight")
    grupos = [
        {"params": [p for n, p in modelo.named_parameters() if not any(k in n for k in sin_decay)],
         "weight_decay": hp.weight_decay},
        {"params": [p for n, p in modelo.named_parameters() if any(k in n for k in sin_decay)],
         "weight_decay": 0.0},
    ]
    optimizador = torch.optim.AdamW(grupos, lr=hp.lr)
    lotes_por_epoca = math.ceil(len(train) / hp.batch_size)
    pasos_por_epoca = math.ceil(lotes_por_epoca / hp.acumulacion)
    total = pasos_por_epoca * hp.epocas
    plan = get_linear_schedule_with_warmup(optimizador, round(hp.warmup * total), total)
    pesos = (torch.tensor(dominio.pesos_clase([e["indice"] for e in train]), dtype=torch.float32)
             if hp.pesos_clase else None)
    pesos = pesos.to(dispositivo) if pesos is not None else None
    generador = torch.Generator().manual_seed(semilla)
    cargador = DataLoader(train, batch_size=hp.batch_size, shuffle=True, generator=generador,
                          collate_fn=lambda b: b)
    ruta_ckpt = salida / "model.safetensors"
    historial, mejor, mejor_epoca, sin_mejora = [], None, 0, 0
    t_inicio = time.perf_counter()
    for epoca in range(1, hp.epocas + 1):
        modelo.train()
        t0 = time.perf_counter()
        acumulado, n_lotes = 0.0, 0
        optimizador.zero_grad(set_to_none=True)
        for i, lote in enumerate(cargador, 1):
            ids, mask, y = _lote(lote, pad_id, dispositivo)
            with _autocast(dispositivo):
                logits = modelo(ids, mask)
            objetivo, peso = _extras(lote, dispositivo)
            valor = calcular_perdida(logits, y, pesos, objetivo, peso)
            (valor / hp.acumulacion).backward()
            acumulado += float(valor.detach())
            n_lotes += 1
            if i % hp.acumulacion == 0 or i == lotes_por_epoca:
                torch.nn.utils.clip_grad_norm_(modelo.parameters(), hp.clip)
                optimizador.step()
                plan.step()
                optimizador.zero_grad(set_to_none=True)
        m_val = _f1_val(modelo, val, pad_id, dispositivo, hp.batch_size * 2)
        historial.append({"epoca": epoca, "loss_train": acumulado / n_lotes,
                          "f1_macro_val": m_val["f1_macro"], "accuracy_val": m_val["accuracy"],
                          "segundos": round(time.perf_counter() - t0, 1)})
        if al_terminar_epoca is not None:
            al_terminar_epoca(historial[-1])
        if mejor is None or m_val["f1_macro"] > mejor["f1_macro"]:
            mejor, mejor_epoca, sin_mejora = m_val, epoca, 0
            sha = guardar_checkpoint(modelo, ruta_ckpt)
        else:
            sin_mejora += 1
            if sin_mejora >= hp.paciencia:
                break
    if not math.isfinite(historial[-1]["loss_train"]):
        warnings.warn("La perdida de entrenamiento no es finita.", RuntimeWarning, stacklevel=2)
    return {
        "semilla": semilla, "hiperparametros": asdict(hp),
        "pesos_clase": dominio.pesos_clase([e["indice"] for e in train]) if hp.pesos_clase else None,
        "casos": {"train": len(train), "val": len(val)},
        "epocas_ejecutadas": len(historial), "mejor_epoca": mejor_epoca,
        "parada_temprana": len(historial) < hp.epocas,
        "historial": historial, "metricas_val": mejor, "checkpoint_sha256": sha,
        "segundos_entrenamiento": round(time.perf_counter() - t_inicio, 1),
        "gpu_mem_pico_gb": (round(torch.cuda.max_memory_allocated(dispositivo) / 1024 ** 3, 3)
                            if dispositivo.type == "cuda" else None),
        "hardware": hardware(),
    }


def filas_prediccion(ejemplos: list[dict], probs: list[list[float]], latencias: list[float], *,
                     model_id: str, model_version: str, experiment_id: str,
                     gold_manifest_sha256: str | None) -> list[dict]:
    return [exportar.fila_prediccion(e["context_id"], p, model_id=model_id,
                                     model_version=model_version, experiment_id=experiment_id,
                                     latency_ms=lat, gold_manifest_sha256=gold_manifest_sha256)
            for e, p, lat in zip(ejemplos, probs, latencias)]
