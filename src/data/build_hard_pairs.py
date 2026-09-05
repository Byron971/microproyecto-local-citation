"""Construcción reproducible de pares con negativos difíciles."""

from collections.abc import Sequence
from typing import Any

from src.evaluation.diagnose_negatives import hard_negatives_from_ranking


def build_hard_pairs(
    candidate_records: Sequence[dict[str, Any]],
    negatives_per_positive: int = 2,
    contexts: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Crea positivos y negativos desde rankings TF-IDF.

    Los negativos se toman en el orden del ranking, excluyendo todos los
    positivos y, cuando se proporcionan los contextos, el artículo citante.
    No hay muestreo aleatorio: la misma entrada produce los mismos pares.
    """
    if negatives_per_positive < 0:
        raise ValueError("negatives_per_positive debe ser mayor o igual a 0.")

    pairs: list[dict[str, Any]] = []

    for record in candidate_records:
        context_id = record["context_id"]
        positive_ids = list(record["positive_ids"])
        positive_set = set(positive_ids)
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
            ranking,
            positive_set,
            n_hard=number_of_negatives,
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


def build_candidate_pairs(
    candidate_records: Sequence[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Aplana candidatos para construir características de evaluación."""
    return [
        {
            "context_id": record["context_id"],
            "paper_id": paper_id,
            "label": int(paper_id in set(record["positive_ids"])),
        }
        for record in candidate_records
        for paper_id in record["candidate_ids"]
    ]
