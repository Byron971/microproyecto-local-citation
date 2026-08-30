"""Entrena y evalúa la línea base TF-IDF, registrando el run en MLflow.

Uso:
    python -m src.training.run_tfidf_baseline
    python -m src.training.run_tfidf_baseline --k 5 --max-features 20000

Requiere los datos en ``data/raw/`` (ver la sección "Obtener los datos" del
README, o ``dvc pull`` si se tiene acceso al remoto S3).
"""

import argparse
from pathlib import Path
from typing import Any

from src.data.load_data import load_json
from src.evaluation.ranking_metrics import mean_reciprocal_rank, recall_at_k
from src.models.tfidf_baseline import TfidfBaseline
from src.tracking.mlflow_setup import (
    configure_mlflow,
    log_ranking_metrics,
    start_run,
)

DEFAULT_DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "raw"


def evaluate_baseline(
    baseline: TfidfBaseline,
    contexts: dict[str, dict[str, Any]],
    split: list[dict[str, Any]],
    k: int,
) -> tuple[float, float]:
    """Evalúa la línea base sobre un split y devuelve (Recall@K, MRR@K).

    Ambas métricas van truncadas a K: el ranking se corta en las K primeras
    posiciones antes de evaluarlo, que es la convención en recuperación de
    información. Su valor depende de K, así que solo son comparables entre
    corridas que usen el mismo K.

    Parameters
    ----------
    baseline:
        Modelo ya ajustado.
    contexts:
        Diccionario ``context_id -> {masked_text, ...}``.
    split:
        Registros del split, con ``context_id`` y ``positive_ids``.
    k:
        Profundidad del ranking a evaluar.

    Returns
    -------
    tuple[float, float]
        Recall@K promedio y MRR@K sobre todas las consultas del split.
    """
    query_texts = [contexts[row["context_id"]]["masked_text"] for row in split]
    relevant_sets = [set(row["positive_ids"]) for row in split]

    rankings = baseline.rank(query_texts, top_k=k)

    # Recall@K se promedia por consulta: cada una aporta la fracción de sus
    # artículos relevantes que quedaron en el top-K.
    recall_scores = [
        recall_at_k(ranked_ids=ranked, relevant_ids=relevant, k=k)
        for ranked, relevant in zip(rankings, relevant_sets, strict=True)
    ]
    mean_recall = sum(recall_scores) / len(recall_scores)

    mrr = mean_reciprocal_rank(zip(rankings, relevant_sets, strict=True))

    return mean_recall, mrr


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=DEFAULT_DATA_DIR,
        help="Carpeta con los archivos JSON del conjunto de datos.",
    )
    parser.add_argument(
        "--split",
        default="val",
        choices=["val", "test"],
        help="Partición sobre la que se evalúa.",
    )
    parser.add_argument("--k", type=int, default=10, help="Profundidad del ranking.")
    parser.add_argument(
        "--max-features",
        type=int,
        default=50_000,
        help="Tamaño máximo del vocabulario TF-IDF.",
    )
    parser.add_argument(
        "--min-df",
        type=int,
        default=2,
        help="Frecuencia documental mínima de un término.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Evaluar solo las primeras N consultas (útil para pruebas rápidas).",
    )
    args = parser.parse_args()

    print("Cargando datos...")
    papers = load_json(args.data_dir / "papers.json")
    contexts = load_json(args.data_dir / "contexts.json")
    split = load_json(args.data_dir / f"{args.split}.json")

    if args.limit:
        split = split[: args.limit]

    print(f"  {len(papers)} artículos | {len(split)} consultas de {args.split}")

    print("Ajustando TF-IDF sobre los artículos...")
    baseline = TfidfBaseline(
        max_features=args.max_features,
        min_df=args.min_df,
    ).fit(papers)

    print(f"  vocabulario: {len(baseline.vectorizer.vocabulary_)} términos")

    print(f"Evaluando Recall@{args.k} y MRR@{args.k}...")
    mean_recall, mrr = evaluate_baseline(baseline, contexts, split, args.k)

    print(f"\n  Recall@{args.k}: {mean_recall:.4f}")
    print(f"  MRR@{args.k}:{'':<6} {mrr:.4f}")

    # El run se registra al final, cuando ya hay métricas: así no quedan runs
    # vacíos en MLflow si la evaluación falla a mitad de camino.
    configure_mlflow()

    with start_run(
        "tfidf",
        params={
            "max_features": args.max_features,
            "min_df": args.min_df,
            "ngram_range": "(1, 1)",
            "split": args.split,
            "n_queries": len(split),
            "n_papers": len(papers),
        },
    ):
        log_ranking_metrics(recall_at_k=mean_recall, mrr=mrr, k=args.k)

    print("\nRun registrado en MLflow.")


if __name__ == "__main__":
    main()
