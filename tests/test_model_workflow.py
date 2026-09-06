"""Verifica YAML, persistencia y separación train/val/test con datos sintéticos."""

import json

import joblib
import mlflow
import pytest
import yaml
from pydantic import ValidationError

from src.config import load_config
from src.training.experiment import evaluate_saved, train


@pytest.fixture
def config_file(tmp_path, monkeypatch):
    raw = tmp_path / "data"
    raw.mkdir()
    papers = {
        "a": {"title": "neural translation", "abstract": "neural language translation"},
        "b": {"title": "protein folding", "abstract": "protein biological folding"},
        "c": {"title": "language models", "abstract": "language neural models"},
        "d": {"title": "cell biology", "abstract": "cell protein biology"},
    }
    contexts = {
        "q1": {"masked_text": "neural translation TARGETCIT", "citing_id": "c"},
        "q2": {"masked_text": "protein folding", "citing_id": "d"},
        "q3": {"masked_text": "neural language", "citing_id": "c"},
    }
    payloads = {
        "papers": papers,
        "contexts": contexts,
        "train": [
            {"context_id": "q1", "positive_ids": ["a"]},
            {"context_id": "q2", "positive_ids": ["b"]},
        ],
        "val": [{"context_id": "q3", "positive_ids": ["a"]}],
    }
    for name, value in payloads.items():
        (raw / f"{name}.json").write_text(json.dumps(value))
    settings = {
        "data_dir": str(raw),
        "output_dir": str(tmp_path / "models"),
        "seed": 42,
        "negative_strategy": "random",
        "negatives_per_positive": 1,
        "top_n": 3,
        "k": 1,
        "max_features": 100,
        "min_df": 1,
        "c": 1.0,
    }
    path = tmp_path / "model.yaml"
    path.write_text(yaml.safe_dump(settings))
    monkeypatch.setenv("MLFLOW_TRACKING_URI", f"sqlite:///{tmp_path / 'mlflow.db'}")
    # Aislar artefactos: el entorno de prueba no escribe en el almacén del usuario.
    mlflow.set_tracking_uri(f"sqlite:///{tmp_path / 'mlflow.db'}")
    mlflow.create_experiment(
        "recomendacion-local-citas", artifact_location=(tmp_path / "runs").as_uri()
    )
    return path


@pytest.mark.parametrize("strategy", ["random", "hard"])
def test_train_reload_evaluate_without_refit(config_file, monkeypatch, strategy):
    config = load_config(config_file).model_copy(update={"negative_strategy": strategy})
    path = train(config)  # test.json no existe: entrenar no puede depender de test.
    model = joblib.load(path)
    original = json.loads((path.parent / "validation.json").read_text())

    def forbidden_fit(*args, **kwargs):
        raise AssertionError("La evaluación no debe entrenar")

    monkeypatch.setattr(type(model.retriever), "fit", forbidden_fit)
    monkeypatch.setattr(type(model.extractor), "fit", forbidden_fit)
    monkeypatch.setattr(type(model.reranker), "fit", forbidden_fit)
    repeated = evaluate_saved(path, "val")
    assert repeated["reranker_metrics"] == original["reranker_metrics"]
    assert (
        repeated["baseline_metrics"]["recall_at_3"]
        == repeated["reranker_metrics"]["recall_at_3"]
    )
    raw = config.data_dir
    (raw / "test.json").write_text((raw / "val.json").read_text())
    assert (
        evaluate_saved(path, "test")["reranker_metrics"] == repeated["reranker_metrics"]
    )
    (raw / "contexts.json").write_text("{}")
    with pytest.raises(ValueError, match="cambiaron"):
        evaluate_saved(path, "val")


@pytest.mark.parametrize(
    "change",
    [
        {"k": 999},
        {"c": -1},
        {"negative_strategy": "typo"},
        {"unknown": 1},
        {"min_df": 0},
    ],
)
def test_invalid_yaml_is_rejected(config_file, change):
    data = yaml.safe_load(config_file.read_text())
    data.update(change)
    config_file.write_text(yaml.safe_dump(data))
    with pytest.raises(ValidationError):
        load_config(config_file)
