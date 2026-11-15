"""Inferencia SciBERT base, opt-in, usando el MISMO codificador/ranking del A1.

No carga Torch/HuggingFace al importar FastAPI. En startup, cuando se activa,
requiere un snapshot fijado por commit y manifiesto de hashes válido.
NO es un encoder fine-tuned ni un clasificador de funciones de cita.
"""
from __future__ import annotations

from importlib import import_module
from pathlib import Path
from typing import Any, Protocol


class DenseEncoder(Protocol):
    def encode(self, textos: list[str]) -> list[tuple[float, ...]]: ...


class SciBERTRuntime:
    """Adapter para contexto y chunks de un único cited paper."""

    model = "SciBERT_base_mean_pooling"
    method = "scibert_base_mean_pooling_cosine"

    def __init__(self, encoder: DenseEncoder, *, revision: str, domain: Any):
        if not revision or len(revision) != 40:
            raise ValueError("La revisión SciBERT debe ser un commit fijado.")
        self.encoder, self.revision, self.domain = encoder, revision, domain

    @classmethod
    def load(cls, manifest: Path, device: str = "cpu") -> "SciBERTRuntime":
        """Solo cargar pesos verificados; nunca usar un modelo desconocido de red."""
        if device not in ("cpu", "cuda", "auto"):
            raise ValueError("APP_SCIBERT_DEVICE debe ser cpu, cuda o auto.")
        if not manifest.is_file() or manifest.is_symlink():
            raise RuntimeError("SciBERT requiere manifiesto_modelo.json existente y confiable.")
        try:
            revision = import_module("recuperacion_densa.revision")
            module = import_module("recuperacion_densa.codificador_torch")
            domain = import_module("recuperacion_densa.dominio")
        except ImportError as exc:
            raise RuntimeError(
                "Falta paquete opcional recuperacion-densa con torch; "
                "instale el entorno de inferencia antes de activar SciBERT."
            ) from exc
        encoder = module.TorchSciBERTEncoder(
            revision.REVISION_SCIBERT,
            revision.MODEL_ID,
            device=device,
            manifiesto=manifest,
            local_files_only=True,
        )
        return cls(encoder, revision=revision.REVISION_SCIBERT, domain=domain)

    def top3(self, contexto: str, chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not chunks:
            return []
        if not isinstance(contexto, str) or not contexto.strip():
            raise ValueError("Contexto de cita vacío.")
        ids = [c.get("chunk_id") for c in chunks]
        if len(ids) != len(set(ids)) or any(not isinstance(x, str) or not x for x in ids):
            raise ValueError("IDs de chunks duplicados o vacíos.")
        consulta = self.domain.normalizar_contexto(contexto)
        if not consulta:
            raise ValueError("El contexto no contiene texto además de marcadores ACL.")
        textos = [c["texto"] for c in chunks]
        if any(not isinstance(t, str) or not t.strip() for t in textos):
            raise ValueError("Chunk sin texto.")
        query = self.encoder.encode([consulta])[0]
        embeddings = self.encoder.encode(textos)
        scored = self.domain.ordenar_top3(query, chunks, embeddings)
        by_id = {c["chunk_id"]: c for c in chunks}
        return [{
            "posicion": row["posicion"],
            "chunk_id": row["chunk_id"],
            "texto": by_id[row["chunk_id"]]["texto"],
            "seccion": by_id[row["chunk_id"]].get("seccion"),
            **({"paragraph_indices": list(by_id[row["chunk_id"]]["paragraph_indices"])}
               if "paragraph_indices" in by_id[row["chunk_id"]] else {}),
            "similitud_coseno": row["similitud_coseno"],
        } for row in scored]
