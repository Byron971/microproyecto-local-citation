"""Encoders y revisiones fijados (sin torch ni red).

SciBERT reutiliza la revision de A1 (mismo recuperador y mismo encoder de clasificacion).
SPECTER se fija con `python -m clasificacion_funcion.descarga_modelo --encoder specter --resolver`."""
from recuperacion_densa.revision import MODEL_ID as MODEL_ID_SCIBERT
from recuperacion_densa.revision import REVISION_SCIBERT, validar_revision

MODEL_ID_SPECTER = "allenai/specter"
# SHA de 40 hex obtenido con --resolver el 2026-11-06 (HEAD de `main` en ese momento);
# no usar `main`: no es reproducible.
REVISION_SPECTER: str | None = "81cbfb43d4fc2e728d5b4201ce14987db8d0854c"

MODELOS: dict[str, dict] = {
    "scibert": {"model_id": MODEL_ID_SCIBERT, "revision": REVISION_SCIBERT},
    "specter": {"model_id": MODEL_ID_SPECTER, "revision": REVISION_SPECTER},
}
ENCODERS = tuple(MODELOS)


def modelo(encoder: str) -> tuple[str, str]:
    """(model_id, revision validada) del encoder; lanza ValueError si falta o es invalida."""
    if encoder not in MODELOS:
        raise ValueError(f"Encoder desconocido: {encoder!r} (validos: {', '.join(ENCODERS)})")
    espec = MODELOS[encoder]
    return espec["model_id"], validar_revision(espec["revision"])
