from types import SimpleNamespace

import httpx2
import openai
import pytest

from src.evaluation.commercial.providers import ProviderCallError
from src.evaluation.commercial.providers_openai import (
    OpenAIClient,
    OpenAIProviderNotConfiguredError,
    build_client,
)


def _fake_request() -> httpx2.Request:
    return httpx2.Request("POST", "https://api.openai.com/v1/chat/completions")


def _fake_completion(content: str, prompt_tokens: int = 10, completion_tokens: int = 5):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
        usage=SimpleNamespace(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens),
    )


class _FakeCompletions:
    def __init__(self, result=None, error=None):
        self._result = result
        self._error = error

    def create(self, **kwargs):
        if self._error is not None:
            raise self._error
        return self._result


class _FakeChat:
    def __init__(self, completions: _FakeCompletions):
        self.completions = completions


class _FakeOpenAI:
    def __init__(self, completions: _FakeCompletions):
        self.chat = _FakeChat(completions)


def test_build_client_returns_openai_client_with_default_model():
    client = build_client()
    assert isinstance(client, OpenAIClient)
    assert client.provider == "openai"
    assert client.model == "gpt-4o-mini"


def test_generate_raises_without_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    client = OpenAIClient()
    with pytest.raises(OpenAIProviderNotConfiguredError) as exc_info:
        client.generate("cualquier prompt")
    assert "openai_api_key" in str(exc_info.value).lower()


def test_generate_returns_provider_response_on_success(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "fake-key")
    client = OpenAIClient()
    fake_completion = _fake_completion(
        "[0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.9, 0.0, 0.0]",
        prompt_tokens=123,
        completion_tokens=45,
    )
    monkeypatch.setattr(
        client, "_get_client", lambda: _FakeOpenAI(_FakeCompletions(result=fake_completion))
    )

    response = client.generate("prompt de prueba")

    assert response.text == "[0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.9, 0.0, 0.0]"
    assert response.input_tokens == 123
    assert response.output_tokens == 45


def test_generate_wraps_rate_limit_error_as_transient(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "fake-key")
    client = OpenAIClient()
    request = _fake_request()
    response = httpx2.Response(429, request=request)
    error = openai.RateLimitError("rate limited", response=response, body=None)
    monkeypatch.setattr(
        client, "_get_client", lambda: _FakeOpenAI(_FakeCompletions(error=error))
    )

    with pytest.raises(ProviderCallError) as exc_info:
        client.generate("prompt de prueba")
    assert exc_info.value.transient is True


def test_generate_wraps_timeout_error_as_transient(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "fake-key")
    client = OpenAIClient()
    error = openai.APITimeoutError(request=_fake_request())
    monkeypatch.setattr(
        client, "_get_client", lambda: _FakeOpenAI(_FakeCompletions(error=error))
    )

    with pytest.raises(ProviderCallError) as exc_info:
        client.generate("prompt de prueba")
    assert exc_info.value.transient is True


def test_generate_wraps_connection_error_as_transient(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "fake-key")
    client = OpenAIClient()
    error = openai.APIConnectionError(request=_fake_request())
    monkeypatch.setattr(
        client, "_get_client", lambda: _FakeOpenAI(_FakeCompletions(error=error))
    )

    with pytest.raises(ProviderCallError) as exc_info:
        client.generate("prompt de prueba")
    assert exc_info.value.transient is True


def test_generate_wraps_authentication_error_as_non_transient(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "fake-key")
    client = OpenAIClient()
    request = _fake_request()
    response = httpx2.Response(401, request=request)
    error = openai.AuthenticationError("invalid api key", response=response, body=None)
    monkeypatch.setattr(
        client, "_get_client", lambda: _FakeOpenAI(_FakeCompletions(error=error))
    )

    with pytest.raises(ProviderCallError) as exc_info:
        client.generate("prompt de prueba")
    assert exc_info.value.transient is False


def test_generate_wraps_empty_choices_as_non_transient_error(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "fake-key")
    client = OpenAIClient()
    empty_completion = SimpleNamespace(choices=[], usage=None)
    monkeypatch.setattr(
        client, "_get_client", lambda: _FakeOpenAI(_FakeCompletions(result=empty_completion))
    )

    with pytest.raises(ProviderCallError) as exc_info:
        client.generate("prompt de prueba")
    assert exc_info.value.transient is False


def test_generate_uses_configured_model(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "fake-key")
    client = OpenAIClient(model="gpt-4o")
    captured_kwargs = {}

    class _CapturingCompletions:
        def create(self, **kwargs):
            captured_kwargs.update(kwargs)
            return _fake_completion("[0.0]*9")

    monkeypatch.setattr(
        client, "_get_client", lambda: _FakeOpenAI(_CapturingCompletions())
    )

    client.generate("hola")
    assert captured_kwargs["model"] == "gpt-4o"
    assert captured_kwargs["messages"] == [{"role": "user", "content": "hola"}]
