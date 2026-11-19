"""Inferencia científica M/S: SciBERT Top-3 -> entrada AB -> clasificación 9 clases.

No usa Gold ni retrena. Reusa la tokenización, perfiles y sesgos del notebook 10.
Los candidatos y metadatos deben provenir del MISMO artículo citado.
"""
from __future__ import annotations

import hashlib
import json
import threading
import unicodedata
from pathlib import Path
from typing import Any

import torch
from torch import nn
from transformers import AutoModel, AutoTokenizer
from huggingface_hub import snapshot_download
from safetensors.torch import load_file

from src.app.scibert_runtime import SciBERTRuntime

ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS = ROOT / "proyecto_de_grado/artifacts/experimentos_10"
MANIFEST_SCIBERT = ROOT / "proyecto_de_grado/docs/evidencias_recuperacion_densa_a1/manifiesto_modelo.json"
REVISION = "24f92d32b1bfb0bcaf9ab193ff3ad01e87732fc1"
CLASES = (
    "Background", "Gap", "Basis", "Comparison", "Application",
    "Improvement / Modification", "Evidence",
    "Identification of the Originator", "Further Reading",
)
MAX_LEN, TOPE_CONTEXTO, TOPE_TITULO = 512, 192, 48
HEURISTICA = (
    ("introduction", ("introduc", "motivation")),
    ("related_work", ("related", "background", "prior work", "previous work")),
    ("conclusion", ("conclusion", "future work", "summary", "discussion")),
    ("results", ("result", "experiment", "evaluation", "analysis", "finding")),
    ("method", ("method", "approach", "model", "system", "algorithm", "framework", "data", "corpus", "task")),
)


def perfil_seccion(nombre: str | None) -> str:
    if not nombre or not nombre.strip():
        return "vacia"
    normal = unicodedata.normalize("NFKD", nombre).encode("ascii", "ignore").decode().lower()
    for perfil, palabras in HEURISTICA:
        if any(p in normal for p in palabras):
            return perfil
    return "otra"


def limpio(s: str) -> str:
    return " ".join(s.split())


def reparto_water_filling(longitudes: list[int], presupuesto: int) -> list[int]:
    asignado = [0] * len(longitudes)
    pendientes = sorted(range(len(longitudes)), key=lambda i: (longitudes[i], i))
    restante = presupuesto
    while pendientes:
        parte = restante // len(pendientes)
        i = pendientes[0]
        if longitudes[i] <= parte:
            asignado[i] = longitudes[i]
            restante -= longitudes[i]
            pendientes.pop(0)
            continue
        for j in pendientes:
            asignado[j] = parte
        restante -= parte * len(pendientes)
        for j in sorted(pendientes):
            if restante and asignado[j] < longitudes[j]:
                asignado[j] += 1
                restante -= 1
        break
    return asignado


def ventana_contexto(ids: list[int], centro: tuple[int, int], tope: int) -> list[int]:
    if len(ids) <= tope:
        return ids
    medio = (centro[0] + centro[1]) // 2
    inicio = min(max(medio - tope // 2, 0), len(ids) - tope)
    if centro[0] < inicio:
        inicio = centro[0]
    return ids[inicio:inicio + tope]


def preparar_entrada_ab(contexto: str, titulo: str, abstract: str, top3: list[dict], tokenizador: Any) -> list[int]:
    """Mismo ensamblado AB notebook 10: CLS, contexto centrado, título, abstract, Top-3."""
    contexto = limpio(contexto)
    if contexto.count("TARGETCIT") != 1 or len(top3) != 3:
        raise ValueError("Se requiere TARGETCIT una vez y exactamente 3 chunks")

    def ids(texto: str) -> list[int]:
        return tokenizador(texto, add_special_tokens=False)["input_ids"]

    antes, despues = contexto.split("TARGETCIT")
    a, m, z = ids(antes), ids("TARGETCIT"), ids(despues)
    segs = [
        {"nombre": "contexto", "ids": a + m + z, "centro": (len(a), len(a) + len(m))},
        {"nombre": "titulo", "ids": ids(limpio(titulo))},
        {"nombre": "abstract", "ids": ids(limpio(abstract))},
    ]
    for i, chunk in enumerate(top3, 1):
        texto = f'{perfil_seccion(chunk.get("seccion"))} : {limpio(chunk["texto"])}'
        segs.append({"nombre": f"chunk_{i}", "ids": ids(texto)})
    ctx, resto = segs[0], segs[1:]
    presupuesto = MAX_LEN - 2 - len(resto)
    ventana = ventana_contexto(ctx["ids"], ctx["centro"], min(TOPE_CONTEXTO, presupuesto))
    libre = presupuesto - len(ventana)
    titulo_seg, abstract_seg = resto[:2]
    t = min(len(titulo_seg["ids"]), TOPE_TITULO, libre)
    a = min(len(abstract_seg["ids"]), libre - t)
    asignado = {"titulo": t, "abstract": a}
    libre -= t + a
    chunks = resto[2:]
    asignado.update({s["nombre"]: n for s, n in zip(chunks, reparto_water_filling([len(s["ids"]) for s in chunks], libre))})
    out = [tokenizador.cls_token_id, *ventana, tokenizador.sep_token_id]
    for s in resto:
        out += [*s["ids"][:asignado[s["nombre"]]], tokenizador.sep_token_id]
    assert len(out) <= MAX_LEN
    return out


class ClasificadorCLS(nn.Module):
    def __init__(self, snapshot: str, semilla: int):
        super().__init__()
        self.encoder = AutoModel.from_pretrained(snapshot, attn_implementation="eager", local_files_only=True)
        torch.manual_seed(semilla)
        self.dropout = nn.Dropout(0.1)
        self.cabeza = nn.Linear(self.encoder.config.hidden_size, len(CLASES))

    def forward(self, input_ids: torch.Tensor, attention_mask: torch.Tensor) -> torch.Tensor:
        cls = self.encoder(input_ids=input_ids, attention_mask=attention_mask).last_hidden_state[:, 0]
        return self.cabeza(self.dropout(cls))


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda: f.read(1024 * 1024), b""):
            h.update(b)
    return h.hexdigest()


class ServicioMS:
    def __init__(self):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        if not MANIFEST_SCIBERT.is_file():
            raise FileNotFoundError("Falta el manifiesto de recuperación SciBERT")
        self.recuperador = SciBERTRuntime.load(MANIFEST_SCIBERT, device=self.device.type)
        self.snapshot = snapshot_download("allenai/scibert_scivocab_uncased", revision=REVISION, local_files_only=True)
        self.tokenizador = AutoTokenizer.from_pretrained(self.snapshot, local_files_only=True)
        self.tokenizador.model_max_length = int(1e9)
        self.modelos: dict[str, nn.Module] = {}
        self.manifiestos: dict[str, dict] = {}
        for pista in ("M", "S"):
            carpeta = ARTIFACTS / pista
            pesos = carpeta / "model.safetensors"
            manifiesto = carpeta / "manifiesto_entrenamiento.json"
            if not pesos.is_file() or not manifiesto.is_file():
                raise FileNotFoundError(f"Falta checkpoint/manifiesto de {pista}")
            config = json.loads(manifiesto.read_text(encoding="utf-8-sig"))
            sha_esperado = config.get("sha256_model_safetensors")
            if not sha_esperado or _sha256(pesos) != sha_esperado.lower():
                raise RuntimeError(f"Hash SHA256 incorrecto en checkpoint {pista}")
            if config.get("scibert_snapshot") != REVISION:
                raise RuntimeError(f"Revision SciBERT no coincide para {pista}")
            if config["config"].get("entrada") != "AB":
                raise RuntimeError(f"El checkpoint {pista} no es AB")
            modelo = ClasificadorCLS(self.snapshot, int(config["config"]["semilla"]))
            modelo.load_state_dict(load_file(str(pesos)), strict=True)
            self.modelos[pista] = modelo.to(self.device).eval()
            self.manifiestos[pista] = config

    @torch.inference_mode()
    def analizar(self, contexto: str, titulo: str, abstract: str, candidatos: list[dict]) -> dict:
        ranking = self.recuperador.top3(contexto, candidatos)
        if len(ranking) != 3:
            raise ValueError("SciBERT no devolvio tres fragmentos")
        tokens = preparar_entrada_ab(contexto, titulo, abstract, ranking, self.tokenizador)
        entrada = torch.tensor([tokens], dtype=torch.long, device=self.device)
        resultados = {}
        for pista, modelo in self.modelos.items():
            logits = modelo(input_ids=entrada, attention_mask=torch.ones_like(entrada)).float()
            scores = torch.log_softmax(logits, dim=-1)
            sesgos = self.manifiestos[pista].get("sesgos_ph")
            if sesgos is not None:
                if len(sesgos) != len(CLASES):
                    raise RuntimeError(f"Sesgos PH incorrectos en {pista}")
                scores = scores + torch.tensor(sesgos, device=self.device, dtype=scores.dtype)
            prob = torch.softmax(scores, dim=-1)[0].cpu().tolist()
            idx = max(range(len(prob)), key=lambda i: prob[i])
            resultados[pista] = {
                "clase": CLASES[idx], "indice": idx, "probabilidad": round(prob[idx], 6),
                "ajuste_ph": sesgos is not None,
                "probabilidades": [{"clase": etiqueta, "probabilidad": round(p, 6)} for etiqueta, p in zip(CLASES, prob)],
            }
        return {
            "modelo_recuperacion": self.recuperador.method,
            "revision_scibert": REVISION,
            "dispositivo": self.device.type,
            "tokens_ab": len(tokens),
            "top3": [{**r, "perfil": perfil_seccion(r.get("seccion"))} for r in ranking],
            "clasificadores": resultados,
            "aviso": "Prueba de inferencia; las similitudes no son relevancia Gold y las probabilidades no validan precisión.",
        }


_INSTANCIA: ServicioMS | None = None
_LOCK = threading.RLock()


def obtener_servicio() -> ServicioMS:
    global _INSTANCIA
    with _LOCK:
        if _INSTANCIA is None:
            _INSTANCIA = ServicioMS()
        return _INSTANCIA


def analizar_seguro(contexto: str, titulo: str, abstract: str, candidatos: list[dict]) -> dict:
    """Serializa peticiones para no solapar inferencias grandes sobre VRAM 8 GB."""
    with _LOCK:
        return obtener_servicio().analizar(contexto, titulo, abstract, candidatos)
