"""Construcción de pares contexto-artículo para entrenamiento supervisado."""

import random
from collections.abc import Collection, Mapping, Sequence


def build_pairs(
    split: Sequence[dict],
    paper_ids: Sequence[str],
    negatives_per_positive: int = 1,
    random_state: int = 42,
    excluded_paper_ids: Mapping[str, Collection[str]] | None = None,
) -> list[dict]:
    """Construye pares positivos y negativos para un split del dataset.

    Cada artículo presente en ``positive_ids`` se conserva como un ejemplo
    positivo con label 1. Los ejemplos negativos se seleccionan aleatoriamente
    entre los artículos que no pertenecen al conjunto de positivos del
    contexto.

    Parameters
    ----------
    split:
        Registros del split. Cada registro debe contener ``context_id`` y
        ``positive_ids``.
    paper_ids:
        Identificadores de todos los artículos candidatos.
    negatives_per_positive:
        Número de ejemplos negativos generados por cada ejemplo positivo.
    random_state:
        Semilla utilizada para garantizar reproducibilidad.
    excluded_paper_ids:
        Artículos adicionales que no pueden actuar como negativos para cada
        contexto. Permite excluir, por ejemplo, el artículo citante.

    Returns
    -------
    list[dict]
        Lista de pares con ``context_id``, ``paper_id`` y ``label``.
    """
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
            pairs.append(
                {
                    "context_id": context_id,
                    "paper_id": paper_id,
                    "label": 1,
                }
            )

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

        sampled_negatives = rng.sample(
            negative_candidates,
            k=number_of_negatives,
        )

        for paper_id in sampled_negatives:
            pairs.append(
                {
                    "context_id": context_id,
                    "paper_id": paper_id,
                    "label": 0,
                }
            )

    return pairs
