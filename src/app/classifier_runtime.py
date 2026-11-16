"""Inferencia A4 (A/B) sobre checkpoints autenticos de nueve funciones.

Importable SIN torch. El modo B reutiliza la receta de entrenamiento y
convierte secciones a perfiles con auditoria_corpus; nunca utiliza Gold.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from importlib import import_module
from pathlib import Path
from typing import Any, Callable

HEX64 = re.compile(r"[0-9a-f]{64}\Z")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(b)
    return digest.hexdigest()


def validate_evidence(run: Path, manifest: Path, *, entrada: str | None = None) -> dict:
    """Verificación ANTES de importar Torch o cargar pesos."""
    weight = run / "model.safetensors"
    if not run.is_dir() or run.is_symlink():
        raise RuntimeError("Falta directorio A4 legítimo.")
    for p in (manifest, weight):
        if not p.is_file() or p.is_symlink():
            raise RuntimeError("Faltan pesos A4 o manifiesto; no se crean checkpoints.")
    evidence = json.loads(manifest.read_text(encoding="utf-8"))
    sha = evidence.get("checkpoint_sha256")
    if not isinstance(sha, str) or HEX64.fullmatch(sha) is None:
        raise RuntimeError("El SHA-256 esperado del checkpoint es inválido.")
    if evidence.get("experiment_id") != run.name:
        raise RuntimeError("Nombre de corrida A4 diferente del manifiesto.")
    if evidence.get("encoder") not in ("scibert", "specter") or evidence.get("entrada") not in ("A", "B"):
        raise RuntimeError("El servicio solo admite SciBERT o SPECTER A/B históricos.")
    if entrada is not None and evidence["entrada"] != entrada:
        raise RuntimeError("La entrada A/B solicitada no coincide con los pesos.")
    if evidence.get("training_labels") != "Haiku" or evidence.get("data_use") != "provisional_only":
        raise RuntimeError("La corrida no es entrenamiento Haiku provisional registrado.")
    if not isinstance(evidence.get("semilla"), int):
        raise RuntimeError("Semilla A4 ausente.")
    if evidence.get("hiperparametros", {}).get("max_len") != 512:
        raise RuntimeError("El modelo debe conservar max_len=512 del entrenamiento.")
    if sha256_file(weight) != sha:
        raise RuntimeError("El checkpoint A4 difiere del SHA-256 archivado.")
    return evidence


def verify_historical_identity(
    run: Path, evidence_manifest: Path, *,
    registry: Path | None = None, repo: Path | None = None,
) -> dict:
    """Ancla pesos y evidencias a los SHA del registro, no a JSON arbitrario.

    Validar solamente contra un manifiesto suministrado por el solicitante
    permitiría sustituir EN PAREJA los pesos y su SHA. Este gate impide que
    una corrida ajena se presente como uno de los cuatro checkpoints A4.
    """
    from src.app.checkpoint_gate import REPO, REGISTRY, _relative

    root = REPO if repo is None else Path(repo)
    source = REGISTRY if registry is None else Path(registry)
    evidence = validate_evidence(Path(run), Path(evidence_manifest))
    if source.is_symlink() or not source.is_file():
        raise RuntimeError("Registro histórico A4 no disponible.")
    manifest_registry = json.loads(source.read_text(encoding="utf-8"))
    if manifest_registry.get("version") != 1:
        raise RuntimeError("Versión del registro histórico A4 incompatible.")
    matches = [
        row for row in manifest_registry.get("models", [])
        if isinstance(row, dict) and row.get("id") == evidence["experiment_id"]
    ]
    if len(matches) != 1:
        raise RuntimeError("Corrida A4 ausente o duplicada en el registro histórico.")
    expected = matches[0]
    for manifest_key, evidence_key in (
        ("encoder", "encoder"), ("entrada", "entrada"),
        ("semilla", "semilla"), ("expected_sha256", "checkpoint_sha256"),
    ):
        if expected.get(manifest_key) != evidence.get(evidence_key):
            raise RuntimeError("Identidad/SHA A4 incompatible con registro histórico.")
    if (expected.get("training_labels") != "Haiku" or
            expected.get("validation") != "provisional_not_gold"):
        raise RuntimeError("Procedencia científica histórica no verificable.")
    expected_manifest = root / _relative(expected.get("source_manifest"))
    actual_manifest = Path(evidence_manifest)
    if (actual_manifest.is_symlink() or expected_manifest.is_symlink() or
            actual_manifest.resolve() != expected_manifest.resolve()):
        raise RuntimeError("Solo se acepta el manifiesto A4 histórico versionado.")
    relative_weights = _relative(expected.get("checkpoint"))
    if relative_weights.name != "model.safetensors" or relative_weights.parent.name != run.name:
        raise RuntimeError("Ruta de checkpoint no coincide con el registro A4.")
    return evidence


class A4Classifier:
    """Representa una corrida A o B; nunca cambia pesos en peticiones."""

    def __init__(self, model: Any, tokenizer: Any, ct: Any, domain: Any, device: Any,
                 evidence: dict, profiler: Callable[[str | None], str] | None = None):
        self.model, self.tokenizer, self.ct, self.domain, self.device = (
            model, tokenizer, ct, domain, device
        )
        self.evidence = evidence
        self.model_id = evidence["experiment_id"]
        self.entrada = evidence.get("entrada", "A")
        self.categories = tuple(domain.CATEGORIAS)
        if len(self.categories) != 9 or len(set(self.categories)) != 9:
            raise ValueError("La taxonomía A4 debe tener nueve categorías únicas.")
        self.profiler = profiler
        if self.entrada == "B" and profiler is None:
            raise ValueError("La entrada B exige perfil_seccion original de auditoria_corpus.")

    @classmethod
    def load(cls, run: Path, evidence_manifest: Path, encoder_manifest: Path,
             device: str = "cpu", *, entrada: str | None = None) -> "A4Classifier":
        if device not in ("cpu", "cuda", "auto"):
            raise ValueError("APP_A4_DEVICE: use cpu, cuda o auto.")
        evidence = verify_historical_identity(run, evidence_manifest)
        if entrada is not None and evidence["entrada"] != entrada:
            raise RuntimeError("La entrada A/B solicitada no coincide con los pesos.")
        if not encoder_manifest.is_file() or encoder_manifest.is_symlink():
            raise RuntimeError("Falta manifiesto firmado del encoder SciBERT.")
        try:
            ct = import_module("clasificacion_funcion.clasificador_torch")
            domain = import_module("clasificacion_funcion.dominio")
            rev = import_module("clasificacion_funcion.revision")
            profile = import_module("auditoria_corpus.dominio").perfil_seccion
        except ImportError as exc:
            raise RuntimeError("Faltan dependencias científicas del servicio (torch y paquetes A4).") from exc
        if rev.modelo(evidence["encoder"])[1] != evidence.get("model_version"):
            raise RuntimeError("Revisión del encoder no corresponde a la corrida histórica A4.")
        spec = domain.especificacion_entrada(evidence["entrada"], evidence["hiperparametros"]["max_len"])
        if domain.sha_especificacion(spec) != evidence.get("input_spec_sha256"):
            raise RuntimeError("El contrato de entrada no es el entrenado.")
        encoder_path = ct.resolver_encoder(evidence["encoder"], encoder_manifest)
        tokenizer = ct.TokenizadorHF(encoder_path)
        if tokenizer.info() != evidence.get("tokenizer"):
            raise RuntimeError("Tokenizador distinto al del entrenamiento.")
        if device == "auto":
            device = "cuda" if ct.torch.cuda.is_available() else "cpu"
        if device == "cuda" and not ct.torch.cuda.is_available():
            raise RuntimeError("CUDA solicitado, pero no disponible.")
        target = ct.torch.device(device)
        model = ct.ClasificadorCLS(
            encoder_path, evidence["semilla"], evidence["hiperparametros"]["dropout"]
        )
        ct.cargar_checkpoint(model, run / "model.safetensors", evidence["checkpoint_sha256"])
        model.to(target).eval()
        return cls(model, tokenizer, ct, domain, target, evidence, profile)

    def classify(self, context: str, title: str | None = None,
                 abstract: str | None = None, top3: list[dict] | None = None) -> dict:
        if not isinstance(context, str) or context.count("TARGETCIT") != 1:
            raise ValueError("El contexto requiere exactamente un TARGETCIT.")
        entry = {"context_id": "solicitud_de_desarrollo", "citation_context": context}
        if self.entrada == "A":
            if not title or not title.strip() or not abstract or not abstract.strip():
                raise ValueError("Entrada A exige título y abstract reales.")
            entry.update({"titulo": title, "abstract": abstract})
        else:
            if not isinstance(top3, list) or len(top3) != 3:
                raise ValueError("Entrada B exige exactamente tres chunks del artículo citado.")
            ids = [c.get("chunk_id") for c in top3]
            if any(not isinstance(x, str) or not x for x in ids) or len(set(ids)) != 3:
                raise ValueError("Chunks B con identificadores ausentes o duplicados.")
            entry["top3"] = []
            for c in top3:
                if not isinstance(c.get("texto"), str) or not c["texto"].strip():
                    raise ValueError("Chunk B vacío.")
                entry["top3"].append({
                    "chunk_id": c["chunk_id"],
                    "texto": c["texto"],
                    "perfil": self.profiler(c.get("seccion")),
                })
        rows = self.ct.preparar_ejemplos(
            [entry], self.entrada, self.tokenizer, self.evidence["hiperparametros"]["max_len"]
        )
        probabilities, latencies = self.ct.predecir_probabilidades(
            self.model, rows, self.tokenizer.pad_id, self.device, batch_size=1
        )
        if not probabilities or not latencies:
            raise RuntimeError("El modelo A4 no devolvió salidas de inferencia.")
        scores = probabilities[0]
        if len(scores) != len(self.categories):
            raise RuntimeError("El modelo A4 devolvió un número incorrecto de categorías.")
        if (any(not isinstance(s, (int, float)) or isinstance(s, bool)
                or not math.isfinite(s) or s < 0 or s > 1 for s in scores)
                or not math.isclose(sum(scores), 1.0, rel_tol=1e-3, abs_tol=1e-3)):
            raise RuntimeError("Softmax A4 inválido: probabilidades no finitas o no normalizadas.")
        if (not isinstance(latencies[0], (int, float)) or
                not math.isfinite(latencies[0]) or latencies[0] < 0):
            raise RuntimeError("Latencia A4 inválida.")
        pos = max(range(9), key=lambda i: (scores[i], -i))
        return {
            "modelo": self.model_id, "encoder": self.evidence.get("encoder", "scibert"),
            "entrada": self.entrada,
            "clase": self.categories[pos], "indice_clase": pos,
            "puntuaciones_softmax": [
                {"categoria": cat, "score": round(float(score), 6)}
                for cat, score in zip(self.categories, scores)
            ],
            "latencia_modelo_ms": round(float(latencies[0]), 3),
            "training_labels": "Haiku", "validacion": "provisional_no_gold_humano",
            "advertencia": (
                "Softmax no calibrado, entrenamiento con Haiku y sin validación "
                "sobre Gold humano. No representa relevancia científica certificada."
            ),
        }
