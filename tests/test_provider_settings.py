"""Pruebas de timeout/URL de proveedores sin enviar llamadas reales."""
from types import SimpleNamespace

import pytest

from src.evaluation.commercial.provider_settings import (
    request_timeout_seconds, validate_openweight_url,
)


def test_timeout_default_and_configurable():
    assert request_timeout_seconds({}) == 60.0
    assert request_timeout_seconds({"CITATION_PROVIDER_TIMEOUT_SECONDS": "2.5"}) == 2.5


@pytest.mark.parametrize("raw", ["0", "0.5", "601", "-1", "nan", "inf", "nonsense", ""])
def test_invalid_timeout_rejected(raw):
    with pytest.raises(ValueError, match="CITATION_PROVIDER_TIMEOUT_SECONDS"):
        request_timeout_seconds({"CITATION_PROVIDER_TIMEOUT_SECONDS": raw})


@pytest.mark.parametrize("url", [
    "file:///etc/passwd",
    "ftp://localhost",
    "https://u:pass@private.example/v1",
    "http://localhost:abc/v1",
    "http://localhost:99999/v1",
    "https://server.example/v1?secret=s",
    "https://server.example/v1#fragment",
    "",
])
def test_invalid_openweight_endpoints_rejected(url):
    with pytest.raises(ValueError, match="OPENWEIGHT_BASE_URL"):
        validate_openweight_url(url)


def test_valid_local_and_https_openweight_urls():
    assert validate_openweight_url("http://localhost:11434/v1").startswith("http")
    assert validate_openweight_url("https://server.example/v1").startswith("https")


@pytest.mark.parametrize("provider_module,api_key_env", [
    ("src.evaluation.commercial.providers_openai", "OPENAI_API_KEY"),
    ("src.evaluation.commercial.providers_gemini", "GEMINI_API_KEY"),
    ("src.evaluation.commercial.providers_cohere", "COHERE_API_KEY"),
    ("src.evaluation.commercial.providers_openweight", "OPENWEIGHT_API_KEY"),
])
def test_timeout_reaches_actual_sdk_constructor(monkeypatch, provider_module, api_key_env):
    import importlib

    m = importlib.import_module(provider_module)
    seen = {}

    def fake_openai(**kwargs):
        seen.update(kwargs)
        return SimpleNamespace()

    monkeypatch.setenv("CITATION_PROVIDER_TIMEOUT_SECONDS", "3.25")
    monkeypatch.setenv(api_key_env, "fake-test-key")
    monkeypatch.setenv("GEMINI_MODEL", "fake-gemini")
    monkeypatch.setenv("OPENWEIGHT_MODEL", "fake-local")
    monkeypatch.setattr(m, "OpenAI", fake_openai)

    if provider_module.endswith("providers_openai"):
        c = m.OpenAIClient()
    elif provider_module.endswith("providers_gemini"):
        c = m.GeminiClient()
    elif provider_module.endswith("providers_cohere"):
        c = m.CohereClient()
    else:
        c = m.OpenWeightClient(base_url="http://localhost:11434/v1")
    c._get_client()
    assert seen["timeout"] == pytest.approx(3.25)
    assert seen["max_retries"] == 0
