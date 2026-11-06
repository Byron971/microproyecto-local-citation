"""Modelo y revision fijados (sin torch ni red)."""
import re

MODEL_ID = "allenai/scibert_scivocab_uncased"
# SHA de 40 hex obtenido con `python -m recuperacion_densa.descarga_modelo --resolver`.
# Resuelto el 2026-11-05 con --resolver (HEAD de `main` en ese momento); no usar `main`.
REVISION_SCIBERT: str | None = "24f92d32b1bfb0bcaf9ab193ff3ad01e87732fc1"
_SHA = re.compile(r"[0-9a-f]{40}")


def validar_revision(revision: str | None) -> str:
    if not revision or not _SHA.fullmatch(revision):
        raise ValueError("La revision del modelo debe ser un SHA de commit de 40 caracteres hex "
                         "(use descarga_modelo --resolver); `main` no es reproducible.")
    return revision
