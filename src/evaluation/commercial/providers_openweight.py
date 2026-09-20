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

_TRANSIENT_ERRORS = (
    RateLimitError,
    APITimeoutError,
    APIConnectionError,
    InternalServerError,
)


class OpenWeightProviderNotConfiguredError(RuntimeError):
    pass


class OpenWeightClient:
    provider = "openweight"

    def __init__(
        self,
        *,
        base_url: str | None = None,
        model: str | None = None,
        api_key: str | None = None,
    ) -> None:
        self.base_url = base_url or os.environ.get(
            "OPENWEIGHT_BASE_URL", "http://localhost:11434/v1"
        )
        self.model = model or os.environ.get("OPENWEIGHT_MODEL", "")
        self.api_key = api_key or os.environ.get("OPENWEIGHT_API_KEY", "local")
        self._client: OpenAI | None = None

    def _get_client(self) -> OpenAI:
        if not self.model:
            raise OpenWeightProviderNotConfiguredError(
                "Falta OPENWEIGHT_MODEL. Define el identificador del modelo "
                "servido por tu endpoint local OpenAI-compatible."
            )
        if self._client is None:
            self._client = OpenAI(
                base_url=self.base_url,
                api_key=self.api_key,
                max_retries=0,
            )
        return self._client

    def generate(self, prompt: str) -> ProviderResponse:
        client = self._get_client()
        try:
            response = client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
            )
        except _TRANSIENT_ERRORS as exc:
            raise ProviderCallError(str(exc), transient=True) from exc
        except OpenAIError as exc:
            raise ProviderCallError(str(exc), transient=False) from exc

        if not response.choices:
            raise ProviderCallError(
                "respuesta sin choices del endpoint open-weight",
                transient=False,
            )

        text = response.choices[0].message.content or ""
        usage = response.usage
        return ProviderResponse(
            text=text,
            input_tokens=usage.prompt_tokens if usage else None,
            output_tokens=usage.completion_tokens if usage else None,
        )


def build_client() -> OpenWeightClient:
    return OpenWeightClient()
