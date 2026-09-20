"""Cliente de Cohere mediante la capa oficial de compatibilidad con OpenAI.

La API key se lee de COHERE_API_KEY y el modelo de COHERE_MODEL. Si no se
define modelo, se usa Command A+ como valor por defecto. Ninguna credencial se
versiona en el repositorio.
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

COHERE_OPENAI_BASE_URL = "https://api.cohere.ai/compatibility/v1"
DEFAULT_MODEL = "command-a-plus-05-2026"

_TRANSIENT_ERRORS = (
    RateLimitError,
    APITimeoutError,
    APIConnectionError,
    InternalServerError,
)


class CohereProviderNotConfiguredError(RuntimeError):
    pass


class CohereClient:
    provider = "cohere"

    def __init__(self, model: str | None = None) -> None:
        self.model = model or os.environ.get("COHERE_MODEL", DEFAULT_MODEL)
        self._client: OpenAI | None = None

    def _get_client(self) -> OpenAI:
        api_key = os.environ.get("COHERE_API_KEY")
        if not api_key:
            raise CohereProviderNotConfiguredError(
                "Falta COHERE_API_KEY para ejecutar corridas reales de Cohere."
            )
        if self._client is None:
            self._client = OpenAI(
                api_key=api_key,
                base_url=COHERE_OPENAI_BASE_URL,
                max_retries=0,
            )
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
                "respuesta sin choices del proveedor Cohere",
                transient=False,
            )

        text = response.choices[0].message.content or ""
        usage = response.usage
        return ProviderResponse(
            text=text,
            input_tokens=usage.prompt_tokens if usage else None,
            output_tokens=usage.completion_tokens if usage else None,
        )


def build_client() -> CohereClient:
    return CohereClient()
