"""Seguimiento en MLflow y evaluación del experimento supervisado.

El ajuste del modelo no se repite aquí: lo hace ``modelo_citas.train_pipeline``,
el mismo código que congela el artefacto que sirve el tablero. Este módulo
aporta lo que es propio del repositorio y no cabe en un paquete instalable: el
registro en MLflow, la evaluación en val/test y el artefacto por run.
"""

import json
from pathlib import Path

import joblib
import mlflow
import yaml
from modelo_citas.models.citation_model import CitationArtifact
from modelo_citas.train_pipeline import data_hashes, file_hash, fit_artifact

from src.config import ExperimentConfig
from src.data.load_data import load_json
from src.evaluation.evaluate_reranker import evaluate_model
from src.tracking.mlflow_setup import configure_mlflow, log_ranking_metrics, start_run

# Archivos cuya huella se guarda al entrenar: los tres del ajuste más ``val``,
# porque la evaluación posterior debe poder comprobar que no cambiaron.
HASHED_FILES = ("papers", "contexts", "train", "val")


def log_evaluation(summary: dict, k: int) -> None:
    metrics = summary["reranker_metrics"]
    log_ranking_metrics(metrics[f"recall_at_{k}"], metrics[f"mrr_at_{k}"], k)
    mlflow.log_metrics(metrics)
    mlflow.log_metrics(
        {f"baseline_{key}": value for key, value in summary["baseline_metrics"].items()}
    )
    mlflow.log_metrics(summary["timings"])
    mlflow.log_dict(summary, "evaluation/summary.json")


def train(config: ExperimentConfig) -> Path:
    """Entrena en train, evalúa en val y guarda un artefacto por run."""
    raw = config.resolve_path(config.data_dir)
    contexts = load_json(raw / "contexts.json")
    split = load_json(raw / "train.json")
    validation = load_json(raw / "val.json")
    if not split or not validation:
        raise ValueError("train y val deben contener consultas.")
    hashes = data_hashes(raw, HASHED_FILES)
    configure_mlflow()
    params = config.model_dump(mode="json")
    params["C"] = params.pop("c")
    with start_run("regresion-logistica", config.negative_strategy, params) as run:
        mlflow.set_tags({"stage": "train", "split": "val"})
        model = fit_artifact(
            papers=load_json(raw / "papers.json"),
            contexts=contexts,
            split=split,
            settings=config,
            metadata={"run_id": run.info.run_id, "hashes_datos": hashes},
        )
        # El ajuste ya midió sus tiempos y dejó los coeficientes en la traza del
        # artefacto; aquí solo se traducen a las claves con que MLflow los viene
        # registrando, para no romper la comparación con los runs anteriores.
        trace = model.metadata
        feature_names = list(model.extractor.feature_names)
        mlflow.log_metrics(
            {
                "train_feature_seconds": trace["segundos_caracteristicas"],
                "training_seconds": trace["segundos_entrenamiento"],
            }
        )
        print("Evaluando en val...", flush=True)
        summary = evaluate_model(model, contexts, validation)
        summary.update(
            {
                "feature_names": feature_names,
                "coefficients": trace["coeficientes"],
                "intercept": trace["intercepto"],
                "data_hashes": hashes,
            }
        )
        mlflow.log_params(
            {
                "n_train_queries": trace["n_consultas_entrenamiento"],
                "n_val_queries": len(validation),
                "n_training_pairs": trace["n_pares_entrenamiento"],
                # Se deriva de la configuración en vez de fijarse a mano: con
                # un literal, las corridas con metadatos seguían anunciándose
                # como v1 y la evidencia en MLflow quedaba engañosa.
                "feature_version": (
                    "pair_features_v2"
                    if config.include_metadata
                    else "pair_features_v1"
                ),
                "n_features": len(feature_names),
                "candidate_policy": "top_n_excluding_citing_paper",
            }
        )
        log_evaluation(summary, config.k)
        output = config.resolve_path(config.output_dir) / run.info.run_id
        output.mkdir(parents=True, exist_ok=False)
        model_path = output / "model.joblib"
        joblib.dump(model, model_path)
        (output / "config.yaml").write_text(
            yaml.safe_dump(config.model_dump(mode="json"), sort_keys=False),
            encoding="utf-8",
        )
        (output / "validation.json").write_text(
            json.dumps(summary, indent=2), encoding="utf-8"
        )
        mlflow.log_artifacts(str(output), artifact_path="model")
        print(json.dumps(summary["reranker_metrics"], indent=2))
        print(f"Modelo guardado: {model_path}")
        return model_path


def evaluate_saved(model_path: Path, split_name: str) -> dict:
    """Usa la configuración guardada; nunca vuelve a ajustar el modelo."""
    if split_name not in {"val", "test"}:
        raise ValueError("Solo se permite evaluar val o test.")
    model: CitationArtifact = joblib.load(model_path)
    config = ExperimentConfig.model_validate(model.settings)
    hashes_datos = model.metadata.get("hashes_datos", {})
    raw = config.resolve_path(config.data_dir)
    for name in ("papers", "contexts", split_name):
        expected = hashes_datos.get(name)
        if expected and file_hash(raw / f"{name}.json") != expected:
            raise ValueError(f"Los datos de {name} cambiaron desde el entrenamiento.")
    contexts = load_json(raw / "contexts.json")
    split = load_json(raw / f"{split_name}.json")
    configure_mlflow()
    with start_run(
        "regresion-logistica",
        config.negative_strategy,
        {
            "source_run_id": model.metadata.get("run_id"),
            "split": split_name,
            "top_n": config.top_n,
            "n_eval_queries": len(split),
        },
    ):
        mlflow.set_tags({"stage": "evaluate", "split": split_name})
        summary = evaluate_model(model, contexts, split)
        summary["split_sha256"] = file_hash(raw / f"{split_name}.json")
        log_evaluation(summary, config.k)
        print(json.dumps(summary, indent=2))
        return summary
