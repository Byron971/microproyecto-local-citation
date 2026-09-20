from types import SimpleNamespace

import pytest

from src.evaluation.commercial.providers_cohere import (
    COHERE_OPENAI_BASE_URL,
    DEFAULT_MODEL,
    CohereClient,
    CohereProviderNotConfiguredError,
    build_client,
)


class _FakeCompletions:
    def create(self, **kwargs):
        assert kwargs["model"] == "cohere-test"
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content="[0.0, 0.0, 0.0, 0.0, 0.9, 0.0, 0.0, 0.0, 0.0]"
                    )
                )
            ],
            usage=SimpleNamespace(prompt_tokens=11, completion_tokens=9),
        )


class _FakeClient:
    def __init__(self):
        self.chat = SimpleNamespace(completions=_FakeCompletions())


def test_build_client_uses_default_model(monkeypatch):
    monkeypatch.delenv("COHERE_MODEL", raising=False)
    client = build_client()
    assert client.provider == "cohere"
    assert client.model == DEFAULT_MODEL


def test_build_client_reads_model_from_environment(monkeypatch):
    monkeypatch.setenv("COHERE_MODEL", "cohere-test")
    client = build_client()
    assert client.model == "cohere-test"


def test_client_requires_api_key(monkeypatch):
    monkeypatch.delenv("COHERE_API_KEY", raising=False)
    client = CohereClient(model="cohere-test")
    with pytest.raises(CohereProviderNotConfiguredError):
        client.generate("prompt")


def test_generate_returns_provider_response(monkeypatch):
    monkeypatch.setenv("COHERE_API_KEY", "fake")
    client = CohereClient(model="cohere-test")
    client._client = _FakeClient()

    result = client.generate("prompt")

    assert result.text.startswith("[0.0")
    assert result.input_tokens == 11
    assert result.output_tokens == 9


def test_base_url_points_to_cohere_compatibility_endpoint():
    assert COHERE_OPENAI_BASE_URL == "https://api.cohere.ai/compatibility/v1"
