import re

import pytest

import mlflow

from src.tracking.mlflow_setup import (
    DEFAULT_ARTIFACTS_DIR,
    DEFAULT_DB_NAME,
    EXPERIMENT_NAME,
    TRACKING_URI_ENV_VAR,
    build_run_name,
    configure_mlflow,
    get_artifacts_uri,
    get_tracking_uri,
    is_local_backend,
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

    # modelo-YYYYmmdd-HHMMSS
    assert re.fullmatch(r"tfidf-\d{8}-\d{6}", result)


def test_build_run_name_includes_variant_when_provided():
    result = build_run_name("regresion-logistica", variant="bigramas")

    assert re.fullmatch(r"regresion-logistica-bigramas-\d{8}-\d{6}", result)


def test_build_run_name_rejects_empty_model_name():
    with pytest.raises(ValueError):
        build_run_name("")


def test_is_local_backend_distinguishes_server_from_local_storage():
    assert is_local_backend("sqlite:///C:/repo/mlflow.db")
    assert is_local_backend("file:///C:/repo/mlruns")
    assert not is_local_backend("http://18.212.44.10:8050")
    assert not is_local_backend("https://mlflow.ejemplo.com")


def test_configure_mlflow_fixes_artifact_location_on_local_backend(tmp_path):
    # Con el backend local SI se fija la ubicacion: de lo contrario MLflow la
    # resolveria relativa al directorio de ejecucion.
    configure_mlflow(
        experiment_name="prueba-local",
        db_path=tmp_path / "mlflow.db",
        artifacts_dir=tmp_path / "mlartifacts",
    )

    experimento = mlflow.get_experiment_by_name("prueba-local")

    assert experimento is not None
    assert "mlartifacts" in experimento.artifact_location


def test_configure_mlflow_lets_remote_server_choose_artifact_location(
    monkeypatch, tmp_path
):
    # Contra un servidor remoto NO debe enviarse una ruta del disco local: se
    # grabaria de forma permanente en el experimento del servidor y apuntaria a
    # una carpeta que alli no existe. Este es el defecto que la prueba fija.
    llamadas = {}

    def create_experiment_espia(name, artifact_location=None, tags=None):
        llamadas["artifact_location"] = artifact_location
        return "id-falso"

    monkeypatch.setenv(TRACKING_URI_ENV_VAR, "http://servidor-mlflow:8050")
    monkeypatch.setattr(mlflow, "get_experiment_by_name", lambda _name: None)
    monkeypatch.setattr(mlflow, "create_experiment", create_experiment_espia)
    monkeypatch.setattr(mlflow, "set_tracking_uri", lambda _uri: None)
    monkeypatch.setattr(mlflow, "set_experiment", lambda _name: None)

    configure_mlflow(experiment_name="prueba-remota")

    assert llamadas["artifact_location"] is None


def test_experiment_name_is_shared_across_the_project():
    # La comparación entre modelos depende de que todos los runs queden bajo
    # el mismo experimento, así que el nombre es una constante, no un
    # parámetro que cada script defina por su cuenta.
    assert EXPERIMENT_NAME == "recomendacion-local-citas"
