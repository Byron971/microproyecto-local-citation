"""Reordenador lineal de candidatos basado en regresión logística."""

from collections.abc import Sequence
from typing import Any, Self

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


class LinearReranker:
    """Clasificador lineal cuya probabilidad positiva se usa como puntaje."""

    def __init__(
        self,
        c: float = 1.0,
        random_state: int = 42,
    ) -> None:
        if c <= 0:
            raise ValueError("c debe ser mayor que 0.")

        self.pipeline = Pipeline(
            [
                ("scaler", StandardScaler()),
                (
                    "classifier",
                    LogisticRegression(
                        C=c,
                        max_iter=1_000,
                        random_state=random_state,
                    ),
                ),
            ]
        )
        self._is_fitted = False

    def fit(self, features: np.ndarray, labels: Sequence[int]) -> Self:
        """Ajusta escalador y regresión logística en una sola operación."""
        if len(features) != len(labels):
            raise ValueError("features y labels deben tener la misma longitud.")
        if len(features) == 0:
            raise ValueError("Se requiere al menos un ejemplo de entrenamiento.")
        if len(set(labels)) < 2:
            raise ValueError("El entrenamiento requiere ejemplos de ambas clases.")

        self.pipeline.fit(features, labels)
        self._is_fitted = True
        return self

    def predict_scores(self, features: np.ndarray) -> np.ndarray:
        """Devuelve la probabilidad de relevancia para cada par."""
        if not self._is_fitted:
            raise RuntimeError("Debe llamarse fit() antes de predict_scores().")
        return self.pipeline.predict_proba(features)[:, 1]


def rerank_candidate_records(
    candidate_records: Sequence[dict[str, Any]],
    scores: Sequence[float],
) -> list[list[str]]:
    """Agrupa puntajes planos y reordena cada lista de candidatos."""
    expected = sum(len(record["candidate_ids"]) for record in candidate_records)
    if len(scores) != expected:
        raise ValueError(
            f"Se esperaban {expected} puntajes para los candidatos y llegaron {len(scores)}."
        )

    rankings: list[list[str]] = []
    offset = 0

    for record in candidate_records:
        candidate_ids = list(record["candidate_ids"])
        local_scores = scores[offset : offset + len(candidate_ids)]
        ordered = sorted(
            zip(candidate_ids, local_scores, strict=True),
            key=lambda item: item[1],
            reverse=True,
        )
        rankings.append([paper_id for paper_id, _score in ordered])
        offset += len(candidate_ids)

    return rankings
