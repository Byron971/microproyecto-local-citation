"""Métricas de evaluación para rankings de recomendación de citas."""

from collections.abc import Iterable, Sequence


def recall_at_k(
    ranked_ids: Sequence[str],
    relevant_ids: set[str],
    k: int,
) -> float:
    """Calcula Recall@K para un ranking.

    Recall@K representa la proporción de elementos relevantes
    recuperados dentro de las primeras K posiciones del ranking.
    """
    if not relevant_ids:
        return 0.0

    top_k = ranked_ids[:k]
    hits = sum(item_id in relevant_ids for item_id in top_k)

    return hits / len(relevant_ids)


def mean_reciprocal_rank(
    rankings: Iterable[tuple[Sequence[str], set[str]]],
) -> float:
    """Calcula Mean Reciprocal Rank (MRR) para múltiples rankings.

    Para cada consulta se utiliza la posición del primer elemento
    relevante encontrado. Si no se encuentra ninguno, su aporte es 0.
    """
    reciprocal_ranks = []

    for ranked_ids, relevant_ids in rankings:
        reciprocal_rank = 0.0

        for rank, item_id in enumerate(ranked_ids, start=1):
            if item_id in relevant_ids:
                reciprocal_rank = 1.0 / rank
                break

        reciprocal_ranks.append(reciprocal_rank)

    if not reciprocal_ranks:
        return 0.0

    return sum(reciprocal_ranks) / len(reciprocal_ranks)
