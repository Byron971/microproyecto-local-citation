"""Pruebas sin red ni pesos para validar configuración y no exponer secretos."""
from pathlib import Path

import pytest

from src.app.settings import ROOT, get_app_settings


def test_defaults_are_supported_and_local_only():
    cfg = get_app_settings({})
    assert cfg.environment == "development"
    assert cfg.host == "127.0.0.1"
    assert cfg.port == 8000
    assert cfg.log_level == "info"
    assert cfg.top3_backend == "bm25_lexical"
    assert cfg.recommender_backend == "packaged_tfidf_linear"
    assert cfg.model_device == "cpu"
    assert cfg.insights_path == ROOT / "data/processed/dashboard_insights.json"


def test_supported_environment_and_runtime_overrides():
    cfg = get_app_settings({
        "APP_ENV": "production",
        "APP_HOST": "0.0.0.0",
        "APP_PORT": "8081",
        "APP_LOG_LEVEL": "warning",
        "APP_INSIGHTS_PATH": "data/processed/other.json",
        "TOP3_CORPUS_PATH": "proyecto_de_grado/artifacts/test.json",
    })
    assert cfg.port == 8081
    assert cfg.environment == "production"
    assert cfg.insights_path == ROOT / "data/processed/other.json"
    assert cfg.top3_corpus_path == ROOT / "proyecto_de_grado/artifacts/test.json"


@pytest.mark.parametrize(("env", "match"), [
    ({"APP_ENV": "qa"}, "APP_ENV"),
    ({"APP_HOST": "http://0.0.0.0:8000"}, "APP_HOST"),
    ({"APP_PORT": "0"}, "APP_PORT"),
    ({"APP_PORT": "65536"}, "APP_PORT"),
    ({"APP_PORT": "abc"}, "APP_PORT"),
    ({"APP_LOG_LEVEL": "verbose"}, "APP_LOG_LEVEL"),
    ({"APP_MODEL_DEVICE": "cuda"}, "APP_MODEL_DEVICE"),
    ({"APP_RECOMMENDER_BACKEND": "scibert"}, "APP_RECOMMENDER_BACKEND"),
    ({"APP_TOP3_BACKEND": "scibert"}, "APP_TOP3_BACKEND"),
    ({"APP_INSIGHTS_PATH": ""}, "APP_INSIGHTS_PATH"),
    ({"TOP3_CORPUS_PATH": "  "}, "TOP3_CORPUS_PATH"),
])
def test_invalid_or_unimplemented_configuration_fails_closed(env, match):
    with pytest.raises(ValueError, match=match):
        get_app_settings(env)


def test_public_configuration_excludes_paths_and_credentials():
    cfg = get_app_settings({
        "APP_ENV": "test",
        "TOP3_CORPUS_PATH": "/private/top3.json",
        "OPENAI_API_KEY": "TOP-SECRET-CANARY",
    })
    safe = str(cfg.public_info())
    assert "TOP-SECRET-CANARY" not in safe
    assert "/private" not in safe
    assert "top3" in safe


def test_top3_corpus_adapter_uses_validated_root_relative_path(monkeypatch):
    from src.app.corpus_adapter import ruta_corpus

    monkeypatch.setenv("TOP3_CORPUS_PATH", "proyecto_de_grado/artifacts/sample.json")
    assert ruta_corpus() == ROOT / "proyecto_de_grado/artifacts/sample.json"


def test_run_backend_uses_explicit_validated_uvicorn_arguments(monkeypatch):
    import uvicorn
    from src.app.main import app, run_backend

    calls = []
    monkeypatch.setenv("APP_PORT", "8123")
    monkeypatch.setenv("APP_HOST", "127.0.0.1")
    monkeypatch.setenv("APP_LOG_LEVEL", "error")
    monkeypatch.setattr(uvicorn, "run", lambda *args, **kwargs: calls.append((args, kwargs)))
    run_backend()
    assert calls == [((app,), {
        "host": "127.0.0.1", "port": 8123, "log_level": "error",
    })]


def test_lifespan_refuses_unsupported_backend_before_loading_model(monkeypatch):
    from fastapi.testclient import TestClient
    from src.app.main import app

    monkeypatch.setenv("APP_TOP3_BACKEND", "scibert_not_integrated")
    with pytest.raises(ValueError, match="APP_TOP3_BACKEND"):
        with TestClient(app):
            pass
