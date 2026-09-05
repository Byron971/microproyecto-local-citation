"""Entrenamiento, persistencia y evaluación del experimento supervisado."""

import hashlib
import json
from pathlib import Path
from time import perf_counter

import joblib
import mlflow
import numpy as np
import yaml

from src.config import ModelConfig
from src.data.build_hard_pairs import build_hard_pairs
from src.data.build_pairs import build_pairs
from src.data.load_data import load_json
from src.evaluation.evaluate_reranker import evaluate_model
from src.features.pair_features import PairFeatureExtractor
from src.models.citation_model import CitationModel, retrieve_candidates
from src.models.linear_reranker import LinearReranker
from src.models.tfidf_baseline import TfidfBaseline
from src.tracking.mlflow_setup import configure_mlflow, log_ranking_metrics, start_run


def file_hash(path: Path) -> str:
    with path.open("rb") as file:
        return hashlib.file_digest(file, "sha256").hexdigest()


def labels_from_pairs(pairs: list[dict]) -> np.ndarray:
    return np.asarray([int(pair["label"]) for pair in pairs], dtype=int)


def training_pairs(
    config: ModelConfig,
    retriever: TfidfBaseline,
    papers: dict,
    contexts: dict,
    split: list[dict],
) -> list[dict]:
    if config.negative_strategy == "hard":
        return build_hard_pairs(
            retrieve_candidates(retriever, contexts, split, config.top_n),
            config.negatives_per_positive,
            contexts,
        )
    return build_pairs(
        split,
        list(papers),
        config.negatives_per_positive,
        config.seed,
        excluded_paper_ids={
            row["context_id"]: {contexts[row["context_id"]].get("citing_id")}
            for row in split
        },
    )


def log_evaluation(summary: dict, k: int) -> None:
    metrics = summary["reranker_metrics"]
    log_ranking_metrics(metrics[f"recall_at_{k}"], metrics[f"mrr_at_{k}"], k)
    mlflow.log_metrics(metrics)
    mlflow.log_metrics(
        {f"baseline_{key}": value for key, value in summary["baseline_metrics"].items()}
    )
    mlflow.log_metrics(summary["timings"])
    mlflow.log_dict(summary, "evaluation/summary.json")


def train(config: ModelConfig) -> Path:
    """Entrena en train, evalúa en val y guarda un artefacto por run."""
    raw = config.resolve_path(config.data_dir)
    papers = load_json(raw / "papers.json")
    contexts = load_json(raw / "contexts.json")
    split = load_json(raw / "train.json")
    validation = load_json(raw / "val.json")
    if not split or not validation:
        raise ValueError("train y val deben contener consultas.")
    hashes = {
        name: file_hash(raw / f"{name}.json")
        for name in ("papers", "contexts", "train", "val")
    }
    configure_mlflow()
    params = config.model_dump(mode="json")
    params["C"] = params.pop("c")
    with start_run("regresion-logistica", config.negative_strategy, params) as run:
        mlflow.set_tags({"stage": "train", "split": "val"})
        print("Ajustando TF-IDF y preparando pares de entrenamiento...", flush=True)
        start = perf_counter()
        retriever = TfidfBaseline(
            max_features=config.max_features, min_df=config.min_df
        ).fit(papers)
        extractor = PairFeatureExtractor(
            max_features=config.max_features, min_df=config.min_df
        ).fit(papers)
        pairs = training_pairs(config, retriever, papers, contexts, split)
        features = extractor.transform(pairs, contexts)
        mlflow.log_metric("train_feature_seconds", perf_counter() - start)
        start = perf_counter()
        reranker = LinearReranker(c=config.c, random_state=config.seed).fit(
            features, labels_from_pairs(pairs)
        )
        mlflow.log_metric("training_seconds", perf_counter() - start)
        model = CitationModel(
            config, retriever, extractor, reranker, hashes, run.info.run_id
        )
        print("Evaluando en val...", flush=True)
        summary = evaluate_model(model, contexts, validation)
        classifier = reranker.pipeline.named_steps["classifier"]
        summary.update(
            {
                "feature_names": list(extractor.feature_names),
                "coefficients": dict(
                    zip(
                        extractor.feature_names,
                        classifier.coef_[0].tolist(),
                        strict=True,
                    )
                ),
                "intercept": float(classifier.intercept_[0]),
                "data_hashes": hashes,
            }
        )
        mlflow.log_params(
            {
                "n_train_queries": len(split),
                "n_val_queries": len(validation),
                "n_training_pairs": len(pairs),
                "feature_version": "pair_features_v1",
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
    model: CitationModel = joblib.load(model_path)
    config = model.config
    raw = config.resolve_path(config.data_dir)
    for name in ("papers", "contexts", split_name):
        expected = model.data_hashes.get(name)
        if expected and file_hash(raw / f"{name}.json") != expected:
            raise ValueError(f"Los datos de {name} cambiaron desde el entrenamiento.")
    contexts = load_json(raw / "contexts.json")
    split = load_json(raw / f"{split_name}.json")
    configure_mlflow()
    with start_run(
        "regresion-logistica",
        config.negative_strategy,
        {
            "source_run_id": model.training_run_id,
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
