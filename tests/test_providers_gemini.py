from types import SimpleNamespace

import pytest

from src.evaluation.commercial.providers_gemini import (
    GEMINI_OPENAI_BASE_URL,
    GeminiClient,
    GeminiProviderNotConfiguredError,
    build_client,
)


class _FakeCompletions:
    def create(self, **kwargs):
        assert kwargs["model"] == "gemini-test"
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content="[0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.9, 0.0, 0.0]"
                    )
                )
            ],
            usage=SimpleNamespace(prompt_tokens=12, completion_tokens=9),
        )


class _FakeClient:
    def __init__(self):
        self.chat = SimpleNamespace(completions=_FakeCompletions())


def test_build_client_reads_model_from_environment(monkeypatch):
    monkeypatch.setenv("GEMINI_MODEL", "gemini-test")
    client = build_client()
    assert client.provider == "gemini"
    assert client.model == "gemini-test"


def test_client_requires_api_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("GEMINI_MODEL", "gemini-test")
    client = GeminiClient()
    with pytest.raises(GeminiProviderNotConfiguredError):
        client.generate("prompt")


def test_client_requires_model(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "fake")
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    client = GeminiClient()
    with pytest.raises(GeminiProviderNotConfiguredError):
        client.generate("prompt")


def test_generate_returns_provider_response(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "fake")
    client = GeminiClient(model="gemini-test")
    client._client = _FakeClient()

    result = client.generate("prompt")

    assert result.text.startswith("[0.0")
    assert result.input_tokens == 12
    assert result.output_tokens == 9


def test_base_url_points_to_google_openai_compatibility_endpoint():
    assert GEMINI_OPENAI_BASE_URL.startswith(
        "https://generativelanguage.googleapis.com/"
    )
