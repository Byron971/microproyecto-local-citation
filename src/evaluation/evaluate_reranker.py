"""Métricas de ranking y evaluación sin ajustar el modelo."""

from collections.abc import Sequence
from time import perf_counter

import numpy as np

from src.evaluation.ranking_metrics import mean_reciprocal_rank, recall_at_k
from src.models.citation_model import CitationModel

DEFAULT_KS = (1, 5, 10, 20, 50, 100)


def evaluate_rankings(
    rankings: Sequence[Sequence[str]],
    relevant_sets: Sequence[set[str]],
    ks: Sequence[int] = DEFAULT_KS,
) -> dict[str, float]:
    if len(rankings) != len(relevant_sets):
        raise ValueError("rankings y relevant_sets deben tener la misma longitud.")
    if not rankings:
        raise ValueError("Se requiere al menos un ranking para evaluar.")
    metrics = {}
    for k in ks:
        if k <= 0:
            raise ValueError("Todos los valores de k deben ser positivos.")
        metrics[f"recall_at_{k}"] = float(
            np.mean(
                [
                    recall_at_k(ranked_ids=ranking, relevant_ids=relevant, k=k)
                    for ranking, relevant in zip(rankings, relevant_sets, strict=True)
                ]
            )
        )
        metrics[f"mrr_at_{k}"] = mean_reciprocal_rank(
            [
                (list(ranking[:k]), relevant)
                for ranking, relevant in zip(rankings, relevant_sets, strict=True)
            ]
        )
    return metrics


def evaluate_model(model: CitationModel, contexts: dict, split: list[dict]) -> dict:
    """Baseline y reordenador comparten exactamente los mismos candidatos."""
    if not split:
        raise ValueError("La partición de evaluación está vacía.")
    start = perf_counter()
    records = model.candidates(contexts, split)
    retrieval_seconds = perf_counter() - start
    start = perf_counter()
    rankings = model.rank(records, contexts)
    inference_seconds = perf_counter() - start
    relevant = [set(row["positive_ids"]) for row in records]
    config = model.config
    ks = sorted({k for k in DEFAULT_KS if k <= config.top_n} | {config.k, config.top_n})
    return {
        "baseline_metrics": evaluate_rankings(
            [row["candidate_ids"] for row in records], relevant, ks
        ),
        "reranker_metrics": evaluate_rankings(rankings, relevant, ks),
        "timings": {
            "retrieval_seconds": retrieval_seconds,
            "reranking_seconds": inference_seconds,
            "inference_ms_per_query": 1000 * inference_seconds / len(split),
        },
    }
