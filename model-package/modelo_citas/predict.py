"""API pública del paquete: cargar el modelo y pedir recomendaciones."""

from typing import Any

from modelo_citas import __version__
from modelo_citas.models.citation_model import CitationArtifact
from modelo_citas.processing.data_manager import load_artifact
from modelo_citas.processing.validation import validate_input

_artifact: CitationArtifact | None = None


def load_model(force: bool = False) -> CitationArtifact:
    """Carga el artefacto empaquetado y lo deja en memoria.

    A diferencia de cargarlo al importar el módulo, esto deja que la aplicación
    decida cuándo pagar el costo: el artefacto pesa decenas de MB.
    """
    global _artifact

    if _artifact is None or force:
        _artifact = load_artifact()

    return _artifact


def make_prediction(*, context: str, top_k: int = 10) -> dict[str, Any]:
    """Recomienda artículos para citar en un contexto académico."""
    validated, errors = validate_input(context=context, top_k=top_k)

    if validated is None:
        return {"predictions": None, "version": __version__, "errors": errors}

    predictions = load_model().recommend(validated.context, top_k=validated.top_k)

    return {"predictions": predictions, "version": __version__, "errors": None}


def describe() -> dict[str, Any]:
    """Ficha técnica del modelo empaquetado."""
    return {**load_model().describe(), "version": __version__}
