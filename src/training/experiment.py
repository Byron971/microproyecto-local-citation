"""Entrenamiento, persistencia y evaluación del experimento supervisado."""

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

import joblib
import mlflow
import numpy as np
import yaml
from modelo_citas.models.citation_model import CitationArtifact
from modelo_citas.models.linear_reranker import LinearReranker
from modelo_citas.models.tfidf_baseline import TfidfBaseline
from modelo_citas.processing.data_manager import paper_metadata
from modelo_citas.processing.features import PairFeatureExtractor
from modelo_citas.processing.pairs import build_hard_pairs, build_pairs, retrieve_candidates

from src.config import ModelConfig
from src.data.load_data import load_json
from src.evaluation.evaluate_reranker import evaluate_model
from src.tracking.mlflow_setup import configure_mlflow, log_ranking_metrics, start_run


def file_hash(path: Path) -> str:
    with path.open("rb") as file:
        return hashlib.file_digest(file, "sha256").hexdigest()


def current_git_sha() -> str | None:
    """Commit desde el que se entrenó, o ``None`` fuera de un repositorio git."""
    try:
        return (
            subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True,
                check=True,
                text=True,
            )
            .stdout.strip()
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def citation_counts_from_split(split: list[dict]) -> dict[str, int]:
    """Cuenta cuántas veces se cita cada artículo dentro de un split.

    Alimenta la característica ``citation_prior``. Se le pasa **siempre** el
    split de entrenamiento: contarlo sobre validación le filtraría al modelo la
    respuesta que después se le pregunta, y el resultado se vería mejor de lo
    que es.
    """
    counts: dict[str, int] = {}

    for record in split:
        for paper_id in record.get("positive_ids", ()):
            counts[paper_id] = counts.get(paper_id, 0) + 1

    return counts


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
            max_features=config.max_features,
            min_df=config.min_df,
            include_metadata=config.include_metadata,
            citation_counts=citation_counts_from_split(split),
        ).fit(papers)
        pairs = training_pairs(config, retriever, papers, contexts, split)
        features = extractor.transform(pairs, contexts)
        mlflow.log_metric("train_feature_seconds", perf_counter() - start)
        start = perf_counter()
        reranker = LinearReranker(c=config.c, random_state=config.seed).fit(
            features, labels_from_pairs(pairs)
        )
        mlflow.log_metric("training_seconds", perf_counter() - start)
        classifier = reranker.pipeline.named_steps["classifier"]
        model = CitationArtifact(
            retriever=retriever,
            extractor=extractor,
            reranker=reranker,
            papers=paper_metadata(papers),
            settings=config.model_dump(mode="json"),
            metadata={
                "run_id": run.info.run_id,
                "git_sha": current_git_sha(),
                "hashes_datos": hashes,
                "entrenado_en": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "coeficientes": dict(
                    zip(
                        extractor.feature_names,
                        classifier.coef_[0].tolist(),
                        strict=True,
                    )
                ),
                "intercepto": float(classifier.intercept_[0]),
            },
        )
        print("Evaluando en val...", flush=True)
        summary = evaluate_model(model, contexts, validation)
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
                # Se deriva de la configuración en vez de fijarse a mano: con
                # un literal, las corridas con metadatos seguían anunciándose
                # como v1 y la evidencia en MLflow quedaba engañosa.
                "feature_version": (
                    "pair_features_v2"
                    if config.include_metadata
                    else "pair_features_v1"
                ),
                "n_features": len(extractor.feature_names),
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
    config = ModelConfig.model_validate(model.settings)
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
