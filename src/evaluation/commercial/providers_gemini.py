"""Cliente de Gemini mediante la capa oficial de compatibilidad con OpenAI.

La API key se lee de GEMINI_API_KEY y el modelo de GEMINI_MODEL. El endpoint
se configura con la URL de compatibilidad documentada por Google.
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

GEMINI_OPENAI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"

_TRANSIENT_ERRORS = (
    RateLimitError,
    APITimeoutError,
    APIConnectionError,
    InternalServerError,
)


class GeminiProviderNotConfiguredError(RuntimeError):
    pass


class GeminiClient:
    provider = "gemini"

    def __init__(self, model: str | None = None) -> None:
        self.model = model or os.environ.get("GEMINI_MODEL", "")
        self._client: OpenAI | None = None

    def _get_client(self) -> OpenAI:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise GeminiProviderNotConfiguredError(
                "Falta GEMINI_API_KEY para ejecutar corridas reales de Gemini."
            )
        if not self.model:
            raise GeminiProviderNotConfiguredError(
                "Falta GEMINI_MODEL. Define el identificador de modelo Gemini "
                "que se usará en la evaluación."
            )
        if self._client is None:
            self._client = OpenAI(
                api_key=api_key,
                base_url=GEMINI_OPENAI_BASE_URL,
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
                "respuesta sin choices del proveedor Gemini",
                transient=False,
            )

        text = response.choices[0].message.content or ""
        usage = response.usage
        return ProviderResponse(
            text=text,
            input_tokens=usage.prompt_tokens if usage else None,
            output_tokens=usage.completion_tokens if usage else None,
        )


def build_client() -> GeminiClient:
    return GeminiClient()
