import re

import pytest

from src.tracking.mlflow_setup import (
    DEFAULT_ARTIFACTS_DIR,
    DEFAULT_DB_NAME,
    EXPERIMENT_NAME,
    TRACKING_URI_ENV_VAR,
    build_run_name,
    get_artifacts_uri,
    get_tracking_uri,
)


def test_get_tracking_uri_prefers_environment_variable(monkeypatch):
    monkeypatch.setenv(TRACKING_URI_ENV_VAR, "http://servidor-mlflow:5000")

    result = get_tracking_uri()

    assert result == "http://servidor-mlflow:5000"


def test_get_tracking_uri_falls_back_to_local_sqlite(monkeypatch, tmp_path):
    monkeypatch.delenv(TRACKING_URI_ENV_VAR, raising=False)

    result = get_tracking_uri(tmp_path / DEFAULT_DB_NAME)

    # MLflow 3.x rechaza el backend de archivos, así que el respaldo local
    # debe ser SQLite y no un URI ``file://``.
    assert result.startswith("sqlite:///")
    assert DEFAULT_DB_NAME in result


def test_get_tracking_uri_uses_forward_slashes(monkeypatch, tmp_path):
    monkeypatch.delenv(TRACKING_URI_ENV_VAR, raising=False)

    result = get_tracking_uri(tmp_path / DEFAULT_DB_NAME)

    # SQLAlchemy no acepta barras invertidas de Windows en el URI.
    assert "\\" not in result


def test_get_artifacts_uri_creates_directory(tmp_path):
    artifacts_dir = tmp_path / DEFAULT_ARTIFACTS_DIR

    result = get_artifacts_uri(artifacts_dir)

    assert artifacts_dir.is_dir()
    assert result.startswith("file://")


def test_build_run_name_follows_convention():
    result = build_run_name("tfidf")

    # modelo-YYYYmmdd-HHMM
    assert re.fullmatch(r"tfidf-\d{8}-\d{4}", result)


def test_build_run_name_includes_variant_when_provided():
    result = build_run_name("regresion-logistica", variant="bigramas")

    assert re.fullmatch(r"regresion-logistica-bigramas-\d{8}-\d{4}", result)


def test_build_run_name_rejects_empty_model_name():
    with pytest.raises(ValueError):
        build_run_name("")


def test_experiment_name_is_shared_across_the_project():
    # La comparación entre modelos depende de que todos los runs queden bajo
    # el mismo experimento, así que el nombre es una constante, no un
    # parámetro que cada script defina por su cuenta.
    assert EXPERIMENT_NAME == "recomendacion-local-citas"
