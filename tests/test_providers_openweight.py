from types import SimpleNamespace

import pytest

from src.evaluation.commercial.providers_openweight import (
    OpenWeightClient,
    OpenWeightProviderNotConfiguredError,
    build_client,
)


class _FakeCompletions:
    def create(self, **kwargs):
        assert kwargs["temperature"] == 0
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content="[0.9, 0, 0, 0, 0, 0, 0, 0, 0]"
                    )
                )
            ],
            usage=SimpleNamespace(prompt_tokens=11, completion_tokens=9),
        )


class _FakeClient:
    def __init__(self):
        self.chat = SimpleNamespace(completions=_FakeCompletions())


def test_build_client_uses_openweight_provider():
    client = build_client()
    assert client.provider == "openweight"
    assert client.base_url


def test_client_requires_model(monkeypatch):
    monkeypatch.delenv("OPENWEIGHT_MODEL", raising=False)
    client = OpenWeightClient(model="")
    with pytest.raises(OpenWeightProviderNotConfiguredError):
        client.generate("prompt")


def test_generate_returns_provider_response():
    client = OpenWeightClient(model="local-test-model")
    client._client = _FakeClient()

    result = client.generate("prompt")

    assert result.text.startswith("[0.9")
    assert result.input_tokens == 11
    assert result.output_tokens == 9
