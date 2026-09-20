"""Cliente de proveedor placeholder para las pruebas de estabilidad del issue #43.

El equipo aun no ha decidido que modelo de prueba usar (Ollama local vs.
API comercial): ver "Decision pendiente" en docs/prompts_estabilidad.md.
Cuando se decida, solo este archivo cambia; el resto del pipeline
(prompts, datos piloto, analisis de estabilidad) no se modifica.
"""
from __future__ import annotations

from .schema import ProviderResponse


class LocalProviderNotConfiguredError(NotImplementedError):
    """Se lanza mientras el equipo no configure un proveedor real."""


class LocalPilotClient:
    provider = "pending"
    model = "pending"

    def generate(self, prompt: str) -> ProviderResponse:
        raise LocalProviderNotConfiguredError(
            "Configura el proveedor de prueba (Ollama local o API comercial) "
            "antes de ejecutar corridas reales. Ver 'Decision pendiente' en "
            "docs/prompts_estabilidad.md."
        )


def build_client() -> LocalPilotClient:
    return LocalPilotClient()
