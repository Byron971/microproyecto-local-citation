"""Registro en MLflow con una base SQLite temporal (nunca toca `mlflow.db` de la raiz)."""
import json

import pytest

pytest.importorskip("mlflow")
pytest.importorskip("pandas")
pytest.importorskip("matplotlib")

import mlflow  # noqa: E402

from clasificacion_funcion import dominio, registro_mlflow as rm  # noqa: E402


@pytest.fixture(autouse=True)
def mlflow_temporal(tmp_path, monkeypatch):
    monkeypatch.delenv("MLFLOW_TRACKING_URI", raising=False)
    rm.configurar("prueba-104", db_path=tmp_path / "m.db", artifacts_dir=tmp_path / "art")
    yield
    mlflow.end_run()


def _metricas():
    return dominio.metricas([0, 1, 2, 3], [0, 1, 2, 2])


def test_sha_config_estable_y_sensible():
    assert rm.sha_config({"a": 1, "b": 2}) == rm.sha_config({"b": 2, "a": 1})
    assert rm.sha_config({"a": 1}) != rm.sha_config({"a": 2})


def test_run_registra_tags_params_metricas_y_se_reanuda():
    config = {"variante": "d1", "semilla": 42}
    with rm.abrir_corrida("scibert-d1", config, {"x": "y"}, {"gpu": "g"}) as run:
        assert run is not None
        rm.log_epoca({"epoca": 1, "loss_train": 0.5, "f1_macro_val": 0.4, "accuracy_val": 0.6, "segundos": 1.0})
        rm.log_metricas("val", _metricas())
        rm.log_dataset("train", ["a", "b"], ["Gap", "Basis"], "training")
        rm.log_matriz_confusion(_metricas(), "val")
    datos = mlflow.get_run(run.info.run_id)
    assert datos.info.status == "FINISHED"
    assert datos.data.tags["issue"] == "104" and datos.data.tags["hw_gpu"] == "g"
    assert datos.data.tags["config_sha"] == rm.sha_config(config)
    assert datos.data.params["semilla"] == "42"
    assert "val_f1_macro" in datos.data.metrics and "val_f1_Gap" in datos.data.metrics
    assert datos.inputs.dataset_inputs
    with rm.abrir_corrida("scibert-d1", config) as segundo:
        assert segundo is None  # reanudable: no repite un run FINISHED


def test_una_falla_deja_el_run_failed_y_no_cuenta_como_terminado():
    config = {"variante": "falla"}
    with pytest.raises(RuntimeError):
        with rm.abrir_corrida("falla", config) as run:
            raise RuntimeError("boom")
    assert rm.corrida_terminada(rm.sha_config(config)) is None


def test_backfill_a4_idempotente(tmp_path):
    carpeta = tmp_path / "corridas" / "scibert_A_42"
    carpeta.mkdir(parents=True)
    val = {k: v for k, v in _metricas().items()}
    (carpeta / "metricas_val.json").write_text(json.dumps(val), encoding="utf-8")
    (carpeta / "manifiesto_entrenamiento.json").write_text(json.dumps({
        "experiment_id": "scibert_A_42", "checkpoint_sha256": "abc", "encoder": "scibert", "entrada": "A",
        "semilla": 42, "model_version": "r", "git": {"head": "h"}, "training_labels": "Haiku",
        "hiperparametros": {"lr": 2e-5}, "segundos_entrenamiento": 80.1, "hardware": {"gpu": "g"},
        "historial": [{"epoca": 1, "loss_train": 1.0, "f1_macro_val": 0.3, "accuracy_val": 0.5, "segundos": 2.0}],
    }), encoding="utf-8")
    kw = {"db_path": tmp_path / "m.db", "artifacts_dir": tmp_path / "art"}
    assert len(rm.registrar_corridas_a4(tmp_path / "corridas", "prueba-104", **kw)) == 1
    assert rm.registrar_corridas_a4(tmp_path / "corridas", "prueba-104", **kw) == []
    df = rm.exportar_manifiesto(tmp_path / "ev", "prueba-104")
    assert len(df) == 1 and (tmp_path / "ev/manifiesto_experimentos.csv").is_file()
