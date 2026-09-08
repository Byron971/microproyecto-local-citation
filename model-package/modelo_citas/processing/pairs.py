"""Construcción de pares contexto-artículo para el entrenamiento."""

import random
from collections.abc import Collection, Mapping, Sequence
from typing import Any


def build_pairs(
    split: Sequence[dict],
    paper_ids: Sequence[str],
    negatives_per_positive: int = 1,
    random_state: int = 42,
    excluded_paper_ids: Mapping[str, Collection[str]] | None = None,
) -> list[dict]:
    """Positivos etiquetados y negativos muestreados al azar del corpus."""
    if negatives_per_positive < 0:
        raise ValueError("negatives_per_positive debe ser mayor o igual a 0.")

    rng = random.Random(random_state)
    all_paper_ids = list(paper_ids)
    pairs = []

    for row in split:
        context_id = row["context_id"]
        positive_ids = list(row["positive_ids"])
        positive_set = set(positive_ids)
        excluded_set = set((excluded_paper_ids or {}).get(context_id, ()))

        for paper_id in positive_ids:
            pairs.append({"context_id": context_id, "paper_id": paper_id, "label": 1})

        negative_candidates = [
            paper_id
            for paper_id in all_paper_ids
            if paper_id not in positive_set and paper_id not in excluded_set
        ]
        number_of_negatives = negatives_per_positive * len(positive_ids)

        if number_of_negatives > len(negative_candidates):
            raise ValueError(
                "No existen suficientes artículos candidatos "
                "para generar los negativos solicitados."
            )

        for paper_id in rng.sample(negative_candidates, k=number_of_negatives):
            pairs.append({"context_id": context_id, "paper_id": paper_id, "label": 0})

    return pairs


def hard_negatives_from_ranking(
    ranking: Sequence[str],
    positive_ids: Collection[str],
    n_hard: int | None = None,
) -> list[str]:
    """Toma del ranking los mejor posicionados que no son citas correctas."""
    if n_hard is not None and n_hard < 0:
        raise ValueError("n_hard debe ser mayor o igual a 0.")

    positive_set = set(positive_ids)
    hard = [paper_id for paper_id in ranking if paper_id not in positive_set]

    return hard if n_hard is None else hard[:n_hard]


def build_hard_pairs(
    candidate_records: Sequence[dict[str, Any]],
    negatives_per_positive: int = 2,
    contexts: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Negativos tomados del ranking TF-IDF; sin muestreo, es reproducible."""
    if negatives_per_positive < 0:
        raise ValueError("negatives_per_positive debe ser mayor o igual a 0.")

    pairs: list[dict[str, Any]] = []

    for record in candidate_records:
        context_id = record["context_id"]
        positive_ids = list(record["positive_ids"])
        ranking = list(record["candidate_ids"])

        if contexts is not None:
            if context_id not in contexts:
                raise KeyError(f"Contexto no encontrado: {context_id}")
            citing_id = contexts[context_id].get("citing_id")
            ranking = [paper_id for paper_id in ranking if paper_id != citing_id]

        for paper_id in positive_ids:
            pairs.append({"context_id": context_id, "paper_id": paper_id, "label": 1})

        number_of_negatives = negatives_per_positive * len(positive_ids)
        hard_ids = hard_negatives_from_ranking(
            ranking, set(positive_ids), n_hard=number_of_negatives
        )

        if len(hard_ids) < number_of_negatives:
            raise ValueError(
                f"No existen suficientes negativos difíciles para {context_id}: "
                f"se solicitaron {number_of_negatives} y hay {len(hard_ids)}."
            )

        pairs.extend(
            {"context_id": context_id, "paper_id": paper_id, "label": 0}
            for paper_id in hard_ids
        )

    return pairs


def retrieve_candidates(
    retriever: Any,
    contexts: dict[str, dict[str, Any]],
    split: Sequence[dict],
    top_n: int,
) -> list[dict[str, Any]]:
    """Recupera candidatos por consulta, excluyendo el artículo citante."""
    rankings = retriever.rank(
        [contexts[row["context_id"]]["masked_text"] for row in split],
        top_k=top_n + 1,
    )

    return [
        {
            "context_id": row["context_id"],
            "positive_ids": row["positive_ids"],
            "candidate_ids": [
                paper_id
                for paper_id in ranking
                if paper_id != contexts[row["context_id"]].get("citing_id")
            ][:top_n],
        }
        for row, ranking in zip(split, rankings, strict=True)
    ]
