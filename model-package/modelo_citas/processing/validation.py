"""Validación de las consultas que llegan al modelo."""

from pydantic import BaseModel, Field, ValidationError


class QueryInput(BaseModel):
    """Una consulta: el contexto de cita y cuántos artículos devolver."""

    context: str = Field(min_length=1)
    top_k: int = Field(default=10, ge=1, le=100)


def validate_input(context: str, top_k: int) -> tuple[QueryInput | None, str | None]:
    """Devuelve la consulta validada, o los errores en formato JSON."""
    try:
        return QueryInput(context=context, top_k=top_k), None
    except ValidationError as error:
        return None, error.json()
