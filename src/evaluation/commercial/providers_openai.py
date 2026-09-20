"""Cliente de OpenAI para la evaluación de función de cita.

Implementa el contrato CommercialModelClient usando el SDK oficial de OpenAI.
La API key se lee de OPENAI_API_KEY y el modelo puede seleccionarse con
OPENAI_MODEL. Ninguna credencial se versiona en el repositorio.
"""
from __future__ import annotations

import os

from openai import (
    APIConnectionError,
    APITimeoutError,
    InternalServerError,
    OpenAI,
    OpenAIError,
    RateLimitError,
)

from .providers import ProviderCallError
from .schema import ProviderResponse

DEFAULT_MODEL = "gpt-4o-mini"

_TRANSIENT_ERRORS = (
    RateLimitError,
    APITimeoutError,
    APIConnectionError,
    InternalServerError,
)


class OpenAIProviderNotConfiguredError(RuntimeError):
    """Se lanza si falta la variable de entorno OPENAI_API_KEY."""


class OpenAIClient:
    provider = "openai"

    def __init__(self, model: str | None = None) -> None:
        self.model = model or os.environ.get("OPENAI_MODEL", DEFAULT_MODEL)
        self._client: OpenAI | None = None

    def _get_client(self) -> OpenAI:
        if self._client is None:
            api_key = os.environ.get("OPENAI_API_KEY")
            if not api_key:
                raise OpenAIProviderNotConfiguredError(
                    "Falta la variable de entorno OPENAI_API_KEY. Configura tu "
                    "API key de OpenAI antes de ejecutar corridas reales."
                )
            self._client = OpenAI(api_key=api_key, max_retries=0)
        return self._client

    def generate(self, prompt: str) -> ProviderResponse:
        client = self._get_client()
        try:
            response = client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
            )
        except _TRANSIENT_ERRORS as exc:
            raise ProviderCallError(str(exc), transient=True) from exc
        except OpenAIError as exc:
            raise ProviderCallError(str(exc), transient=False) from exc

        if not response.choices:
            raise ProviderCallError(
                "respuesta sin choices (posible filtro de contenido)",
                transient=False,
            )

        text = response.choices[0].message.content or ""
        usage = response.usage
        return ProviderResponse(
            text=text,
            input_tokens=usage.prompt_tokens if usage else None,
            output_tokens=usage.completion_tokens if usage else None,
        )


def build_client() -> OpenAIClient:
    return OpenAIClient()
