"""Inferencia SciBERT base, opt-in, usando el MISMO codificador/ranking del A1.

No carga Torch/HuggingFace al importar FastAPI. En startup, cuando se activa,
requiere un snapshot fijado por commit y manifiesto de hashes válido.
NO es un encoder fine-tuned ni un clasificador de funciones de cita.
"""
from __future__ import annotations

from importlib import import_module
import hashlib
import json
import math
import threading
from collections import OrderedDict
from pathlib import Path
from typing import Any, Protocol


class DenseEncoder(Protocol):
    def encode(self, textos: list[str]) -> list[tuple[float, ...]]: ...


class SciBERTRuntime:
    """Adapter para contexto y chunks de un único cited paper."""

    model = "SciBERT_base_mean_pooling"
    method = "scibert_base_mean_pooling_cosine"

    def __init__(self, encoder: DenseEncoder, *, revision: str, domain: Any,
                 max_chunks: int = 500, max_characters: int = 600000,
                 max_cached_papers: int = 8):
        if not revision or len(revision) != 40:
            raise ValueError("La revisión SciBERT debe ser un commit fijado.")
        if not (3 <= max_chunks <= 2000 and 1000 <= max_characters <= 2000000
                and 1 <= max_cached_papers <= 64):
            raise ValueError("Límites de recursos científicos inválidos.")
        self.encoder, self.revision, self.domain = encoder, revision, domain
        self.max_chunks, self.max_characters = max_chunks, max_characters
        self.max_cached_papers = max_cached_papers
        self._lock = threading.RLock()  # serializa inferencia GPU/CPU por worker
        self._embeddings: OrderedDict[str, tuple[tuple[float, ...], ...]] = OrderedDict()
        self._hits = self._misses = 0

    @classmethod
    def load(cls, manifest: Path, device: str = "cpu", *,
             max_chunks: int = 500, max_characters: int = 600000,
             max_cached_papers: int = 8) -> "SciBERTRuntime":
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
        return cls(encoder, revision=revision.REVISION_SCIBERT, domain=domain,
                   max_chunks=max_chunks, max_characters=max_characters,
                   max_cached_papers=max_cached_papers)

    def cache_stats(self) -> dict:
        """Métricas operativas sin contenidos ni IDs de artículos."""
        with self._lock:
            n = sum(len(v) for v in self._embeddings.values())
            size = sum(sum(len(vec) * 8 for vec in vectors)
                       for vectors in self._embeddings.values())
            return {"papers": len(self._embeddings), "vectors": n,
                    "bytes_estimated": size, "hits": self._hits, "misses": self._misses,
                    "max_papers": self.max_cached_papers,
                    "max_chunks_per_request": self.max_chunks}

    def _cache_key(self, document_key: str, chunks: list[dict]) -> str:
        """Incluye revisión + configuración + TODOS los bytes del contenido."""
        identity = {
            "revision": self.revision, "encoder": getattr(self.encoder, "model_id", self.model),
            "environment": getattr(self.encoder, "huella_entorno", ""),
            "document_key": document_key,
            "chunks": [(c["chunk_id"], c["texto"], c.get("seccion"),
                        c.get("paragraph_indices")) for c in chunks],
        }
        return hashlib.sha256(
            json.dumps(identity, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest()

    def top3(self, contexto: str, chunks: list[dict[str, Any]], *,
             document_key: str | None = None) -> list[dict[str, Any]]:
        if not chunks:
            raise ValueError("El artículo citado no tiene chunks.")
        if len(chunks) > self.max_chunks:
            raise ValueError("Demasiados chunks para el límite configurado de inferencia.")
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
        if len(contexto) + sum(len(t) for t in textos) > self.max_characters:
            raise ValueError("Entrada científica supera el máximo de caracteres.")
        if document_key is not None and (not isinstance(document_key, str) or not document_key):
            raise ValueError("Clave del artículo inválida.")

        # El caché es SOLO para corpus TRAIN autorizado. Nunca guardar párrafos
        # manuales de usuarios. Una clave incluye el contenido, no solo cited_id.
        with self._lock:
            key = self._cache_key(document_key, chunks) if document_key else None
            vectors = self._embeddings.get(key) if key is not None else None
            if vectors is not None:
                self._hits += 1
                self._embeddings.move_to_end(key)
            else:
                self._misses += 1
                encoded = self.encoder.encode(textos)
                if len(encoded) != len(textos):
                    raise RuntimeError("SciBERT produjo cantidad incorrecta de embeddings.")
                vectors = tuple(tuple(float(x) for x in row) for row in encoded)
                if any(not row or any(not math.isfinite(v) for v in row) for row in vectors):
                    raise RuntimeError("SciBERT produjo vectores vacíos o no finitos.")
                if key is not None:
                    self._embeddings[key] = vectors
                    self._embeddings.move_to_end(key)
                    while len(self._embeddings) > self.max_cached_papers:
                        self._embeddings.popitem(last=False)
            query = self.encoder.encode([consulta])[0]
            scored = self.domain.ordenar_top3(query, chunks, vectors)
        by_id = {c["chunk_id"]: c for c in chunks}
        return [{
            "posicion": row["posicion"], "chunk_id": row["chunk_id"],
            "texto": by_id[row["chunk_id"]]["texto"],
            "seccion": by_id[row["chunk_id"]].get("seccion"),
            **({"paragraph_indices": list(by_id[row["chunk_id"]]["paragraph_indices"])}
               if "paragraph_indices" in by_id[row["chunk_id"]] else {}),
            "similitud_coseno": row["similitud_coseno"],
        } for row in scored]
