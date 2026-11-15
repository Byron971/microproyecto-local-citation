"""Clasificación A4 de nueve funciones, solo inferencia PROVISIONAL con Haiku.

No importa Torch al arrancar el módulo. Al habilitarlo requiere los pesos
originales A4, sus hashes y el snapshot del encoder verificado.
No entrena ni lee Test Gold. Soporta entrada A; B se integra por separado.
"""
from __future__ import annotations

import hashlib
import json
from importlib import import_module
from pathlib import Path
from typing import Any

from src.app.checkpoint_gate import HEX64

_9_FUNCTIONS = (
    "Background", "Gap", "Basis", "Comparison", "Application",
    "Improvement / Modification", "Evidence",
    "Identification of the Originator", "Further Reading",
)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


class A4Classifier:
    """Adaptador real a ClasificadorCLS/TokenizadorHF de la corrida SciBERT-A."""

    def __init__(self, model: Any, tokenizer: Any, ct: Any, domain: Any,
                 device: Any, evidence: dict):
        self.model, self.tokenizer = model, tokenizer
        self.ct, self.domain, self.device = ct, domain, device
        self.evidence = evidence
        self.model_id = evidence["experiment_id"]
        self.categories = tuple(domain.CATEGORIAS)
        if self.categories != _9_FUNCTIONS:
            raise ValueError("La taxonomía de nueve funciones no coincide con A4.")

    @classmethod
    def load(cls, run: Path, evidence_manifest: Path, encoder_manifest: Path,
             device: str = "cpu") -> "A4Classifier":
        if device not in ("cpu", "cuda", "auto"):
            raise ValueError("APP_A4_DEVICE inválido.")
        weight = run / "model.safetensors"
        for p in (evidence_manifest, encoder_manifest, weight):
            if not p.is_file() or p.is_symlink():
                raise RuntimeError("Faltan checkpoint y/o manifiestos A4 verificables.")
        evidence = json.loads(evidence_manifest.read_text(encoding="utf-8"))
        sha = evidence.get("checkpoint_sha256")
        if not isinstance(sha, str) or HEX64.fullmatch(sha) is None:
            raise RuntimeError("Manifiesto A4 sin checkpoint_sha256 válido.")
        if _sha256(weight) != sha:
            raise RuntimeError("Checkpoint A4 no coincide con SHA-256 histórico.")
        if evidence.get("encoder") != "scibert" or evidence.get("entrada") != "A":
            raise RuntimeError("Este endpoint admite únicamente SciBERT-A.")
        if evidence.get("training_labels") != "Haiku" or evidence.get("data_use") != "provisional_only":
            raise RuntimeError("Procedencia A4 no es entrenamiento Haiku provisional.")
        if evidence.get("experiment_id") != run.name:
            raise RuntimeError("El directorio no corresponde a la corrida A4 declarada.")
        try:
            ct = import_module("clasificacion_funcion.clasificador_torch")
            domain = import_module("clasificacion_funcion.dominio")
            rev = import_module("clasificacion_funcion.revision")
        except ImportError as exc:
            raise RuntimeError(
                "Instale clasificacion-funcion, recuperacion-densa y torch "
                "en el mismo entorno de la API para activar A4."
            ) from exc
        if rev.modelo("scibert")[1] != evidence.get("model_version"):
            raise RuntimeError("La revisión fijada de SciBERT difiere de la corrida A4.")
        max_len = evidence["hiperparametros"]["max_len"]
        spec = domain.especificacion_entrada("A", max_len)
        if domain.sha_especificacion(spec) != evidence.get("input_spec_sha256"):
            raise RuntimeError("La especificación A4 de entrada A difiere del manifiesto.")
        encoder = ct.resolver_encoder("scibert", encoder_manifest)
        tok = ct.TokenizadorHF(encoder)
        if tok.info() != evidence.get("tokenizer"):
            raise RuntimeError("El tokenizer no coincide con la corrida A4.")
        if device == "auto":
            device = "cuda" if ct.torch.cuda.is_available() else "cpu"
        if device == "cuda" and not ct.torch.cuda.is_available():
            raise RuntimeError("CUDA solicitado, pero no disponible.")
        target = ct.torch.device(device)
        model = ct.ClasificadorCLS(
            encoder, evidence["semilla"], evidence["hiperparametros"]["dropout"]
        )
        ct.cargar_checkpoint(model, weight, sha)
        model.to(target).eval()
        return cls(model, tok, ct, domain, target, evidence)

    def classify(self, context: str, title: str, abstract: str) -> dict:
        entry = {
            "context_id": "solicitud_de_desarrollo",
            "citation_context": context,
            "titulo": title,
            "abstract": abstract,
        }
        # Reutiliza EXACTAMENTE la receta del entrenamiento A4.
        rows = self.ct.preparar_ejemplos(
            [entry], "A", self.tokenizer,
            self.evidence["hiperparametros"]["max_len"],
        )
        probabilities, latencies = self.ct.predecir_probabilidades(
            self.model, rows, self.tokenizer.pad_id, self.device, batch_size=1
        )
        scores = probabilities[0]
        if len(scores) != 9:
            raise RuntimeError("La cabeza A4 no devolvió nueve puntuaciones.")
        pos = max(range(9), key=lambda i: scores[i])
        return {
            "modelo": self.model_id,
            "encoder": "scibert",
            "entrada": "A",
            "clase": self.categories[pos],
            "indice_clase": pos,
            "puntuaciones_softmax": [
                {"categoria": cat, "score": round(float(score), 6)}
                for cat, score in zip(self.categories, scores)
            ],
            "latencia_modelo_ms": round(float(latencies[0]), 3),
            "training_labels": "Haiku",
            "validacion": "provisional_no_gold_humano",
            "advertencia": (
                "Puntuaciones softmax no calibradas; resultado provisional con "
                "etiquetas Haiku, no validado sobre Test Gold humano."
            ),
        }
