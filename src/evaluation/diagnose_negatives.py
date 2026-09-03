"""Diagnóstico del muestreo de negativos: aleatorios frente a negativos duros.

Los pares supervisados de ``data/processed`` toman sus negativos por muestreo
uniforme sobre todo el corpus (``src/data/build_pairs.py``). En producción, en
cambio, el reordenador solo recibe los Top-N candidatos que devuelve TF-IDF, y
esos candidatos son todos temáticamente cercanos a la consulta. Entrenar contra
negativos aleatorios y evaluar contra ellos mide, por tanto, una tarea más fácil
que la real.

Este módulo cuantifica esa brecha para que la decisión de usar negativos duros
quede sustentada en evidencia y no en intuición. No entrena nada: solo compara
las distribuciones de similitud coseno de tres poblaciones (positivos, negativos
aleatorios y negativos duros) sobre las mismas consultas.

Uso:
    python -m src.evaluation.diagnose_negatives
    python -m src.evaluation.diagnose_negatives --n-queries 800 --top-n 100

Requiere ``data/raw/`` y ``data/processed/`` (ver el README, o ``dvc pull``).
"""

import argparse
import random
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.metrics import roc_auc_score

from src.data.load_data import load_json
from src.models.tfidf_baseline import TfidfBaseline, clean_context_text

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RAW_DIR = REPO_ROOT / "data" / "raw"
DEFAULT_PROCESSED_DIR = REPO_ROOT / "data" / "processed"


def hard_negatives_from_ranking(
    ranking: Sequence[str],
    positive_ids: Iterable[str],
    n_hard: int | None = None,
) -> list[str]:
    """Extrae negativos duros de un ranking ya calculado.

    Un negativo duro es un artículo que la primera etapa colocó arriba pero que
    no es una cita correcta: justamente el tipo de candidato que el reordenador
    tendrá que descartar en producción. Se obtienen recorriendo el ranking en
    orden y descartando los positivos, de modo que conserven la posición
    relativa que TF-IDF les asignó.

    Parameters
    ----------
    ranking:
        Identificadores de artículo ordenados de mayor a menor similitud, tal
        como los devuelve ``TfidfBaseline.rank()``.
    positive_ids:
        Identificadores que sí son citas correctas para esa consulta.
    n_hard:
        Cantidad máxima de negativos a devolver. ``None`` devuelve todos los
        del ranking que no sean positivos.

    Returns
    -------
    list[str]
        Negativos duros, del más al menos similar a la consulta.
    """
    if n_hard is not None and n_hard < 0:
        raise ValueError("n_hard debe ser mayor o igual a 0.")

    # Se convierte a conjunto una sola vez: la pertenencia se consulta una vez
    # por elemento del ranking, y con listas eso sería cuadrático.
    positives = set(positive_ids)

    negatives = [paper_id for paper_id in ranking if paper_id not in positives]

    return negatives if n_hard is None else negatives[:n_hard]


def separability_auc(
    positive_scores: Sequence[float],
    negative_scores: Sequence[float],
) -> float:
    """Área bajo la curva ROC usando el puntaje como único predictor.

    Responde a la pregunta de si basta la similitud coseno para separar las dos
    poblaciones. Un valor cercano a 1 indica que la tarea se resuelve sin modelo
    alguno, y por tanto que un clasificador entrenado sobre ella reportará
    métricas altas sin haber aprendido nada útil.

    Parameters
    ----------
    positive_scores:
        Puntajes de los ejemplos de la clase positiva.
    negative_scores:
        Puntajes de los ejemplos de la clase negativa.

    Returns
    -------
    float
        AUC en el rango [0, 1].
    """
    if len(positive_scores) == 0 or len(negative_scores) == 0:
        raise ValueError("Ambas poblaciones deben tener al menos un elemento.")

    # roc_auc_score espera etiquetas y puntajes en un solo arreglo, así que se
    # concatenan las dos poblaciones marcando su clase de origen.
    labels = np.concatenate(
        [np.ones(len(positive_scores)), np.zeros(len(negative_scores))]
    )
    scores = np.concatenate([np.asarray(positive_scores), np.asarray(negative_scores)])

    return float(roc_auc_score(labels, scores))


def random_negatives_by_context(pairs: list[dict[str, Any]]) -> dict[str, list[str]]:
    """Agrupa por contexto los negativos que el pipeline actual asignó.

    Se leen de los pares ya generados en vez de volver a muestrearlos, para que
    el diagnóstico describa los datos que el equipo realmente tiene en
    ``data/processed`` y no una réplica aproximada.

    Parameters
    ----------
    pairs:
        Registros ``{context_id, paper_id, label}``.

    Returns
    -------
    dict[str, list[str]]
        ``context_id -> [paper_id, ...]``, solo con los de etiqueta 0.
    """
    negatives: dict[str, list[str]] = {}

    for pair in pairs:
        if pair["label"] == 0:
            negatives.setdefault(pair["context_id"], []).append(pair["paper_id"])

    return negatives


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    parser.add_argument("--processed-dir", type=Path, default=DEFAULT_PROCESSED_DIR)
    parser.add_argument("--split", default="val", choices=["val", "test"])
    parser.add_argument(
        "--n-queries",
        type=int,
        default=400,
        help="Consultas muestreadas. Basta una muestra: se comparan "
        "distribuciones, no se optimiza nada.",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=100,
        help="Profundidad de recuperación que simula el escenario de servicio.",
    )
    parser.add_argument("--seed", type=int, default=42, help="Semilla del muestreo.")
    parser.add_argument("--max-features", type=int, default=50_000)
    parser.add_argument("--min-df", type=int, default=2)
    args = parser.parse_args()

    print("Cargando datos...")
    papers = load_json(args.raw_dir / "papers.json")
    contexts = load_json(args.raw_dir / "contexts.json")
    split = load_json(args.raw_dir / f"{args.split}.json")
    pairs = load_json(args.processed_dir / f"{args.split}_pairs.json")

    random_negatives = random_negatives_by_context(pairs)

    print(f"  {len(papers)} artículos | {len(split)} consultas de {args.split}")

    print("Ajustando TF-IDF sobre los artículos...")
    baseline = TfidfBaseline(
        max_features=args.max_features,
        min_df=args.min_df,
    ).fit(papers)

    # Posición de cada artículo en la matriz: permite recuperar la similitud de
    # un identificador concreto sin volver a buscarlo en la lista.
    row_of = {paper_id: i for i, paper_id in enumerate(baseline.paper_ids)}

    rng = random.Random(args.seed)
    sample = rng.sample(split, min(args.n_queries, len(split)))

    query_texts = [
        clean_context_text(contexts[row["context_id"]]["masked_text"]) for row in sample
    ]

    # Se calcula la matriz completa de similitudes de la muestra: con unos
    # cientos de consultas cabe en memoria, y aquí sí hacen falta todos los
    # puntajes, no solo el top-K.
    query_matrix = baseline.vectorizer.transform(query_texts)
    similarities = (query_matrix @ baseline.paper_matrix.T).toarray()

    rankings = baseline.rank(query_texts, top_k=args.top_n)

    positive_scores: list[float] = []
    random_scores: list[float] = []
    hard_scores: list[float] = []

    for row_index, record in enumerate(sample):
        scores = similarities[row_index]
        positive_ids = set(record["positive_ids"])

        positive_scores.extend(
            scores[row_of[paper_id]] for paper_id in positive_ids if paper_id in row_of
        )

        random_scores.extend(
            scores[row_of[paper_id]]
            for paper_id in random_negatives.get(record["context_id"], [])
            if paper_id in row_of
        )

        hard_scores.extend(
            scores[row_of[paper_id]]
            for paper_id in hard_negatives_from_ranking(
                rankings[row_index], positive_ids
            )
        )

    positives = np.array(positive_scores)
    randoms = np.array(random_scores)
    hards = np.array(hard_scores)

    print(f"\nSimilitud coseno media ({len(sample)} consultas)")
    print(f"  positivos (artículo citado)     : {positives.mean():.4f}")
    print(f"  negativos aleatorios (pipeline) : {randoms.mean():.4f}")
    print(f"  negativos duros (Top-{args.top_n})      : {hards.mean():.4f}")

    print("\nAUC con la similitud coseno como único predictor")
    print(f"  positivos vs aleatorios: {separability_auc(positives, randoms):.4f}")
    print(f"  positivos vs duros     : {separability_auc(positives, hards):.4f}")

    # Dos lecturas complementarias que hacen tangible por qué el muestreo
    # aleatorio produce una tarea artificialmente fácil.
    print(
        "\nNegativos aleatorios sin un solo término en común con la consulta: "
        f"{float((randoms == 0).mean()):.1%}"
    )
    print(
        "Negativos aleatorios por debajo de la similitud media de un positivo: "
        f"{float((randoms < positives.mean()).mean()):.1%}"
    )


if __name__ == "__main__":
    main()
