"""Cliente de OpenAI para las pruebas de estabilidad del issue #43.

Implementa el contrato `CommercialModelClient` (ver `providers.py`) usando el
SDK oficial de OpenAI. La API key se lee de la variable de entorno
`OPENAI_API_KEY`; nunca se versiona ni se hardcodea en este archivo. Ver
"Decision pendiente" en docs/prompts_estabilidad.md para el contexto de esta
decision (modelo gpt-4o-mini, via variable de entorno).
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

_TRANSIENT_ERRORS = (RateLimitError, APITimeoutError, APIConnectionError, InternalServerError)


class OpenAIProviderNotConfiguredError(RuntimeError):
    """Se lanza si falta la variable de entorno OPENAI_API_KEY."""


class OpenAIClient:
    provider = "openai"

    def __init__(self, model: str = DEFAULT_MODEL) -> None:
        self.model = model
        self._client: OpenAI | None = None

    def _get_client(self) -> OpenAI:
        if self._client is None:
            api_key = os.environ.get("OPENAI_API_KEY")
            if not api_key:
                raise OpenAIProviderNotConfiguredError(
                    "Falta la variable de entorno OPENAI_API_KEY. Configura tu "
                    "API key de OpenAI antes de ejecutar corridas reales."
                )
            # max_retries=0: los reintentos ya los controla run_evaluation
            # (--max-retries), no queremos que el SDK reintente por su cuenta.
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
            # Puede pasar con respuestas filtradas por moderacion de
            # contenido (finish_reason="content_filter" sin choices). No es
            # un error de proveedor transitorio: reintentar no lo arregla.
            raise ProviderCallError("respuesta sin choices (posible filtro de contenido)", transient=False)

        text = response.choices[0].message.content or ""
        usage = response.usage
        return ProviderResponse(
            text=text,
            input_tokens=usage.prompt_tokens if usage else None,
            output_tokens=usage.completion_tokens if usage else None,
        )


def build_client() -> OpenAIClient:
    return OpenAIClient()
