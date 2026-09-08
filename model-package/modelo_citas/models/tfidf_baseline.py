"""Recuperador TF-IDF: primera etapa que propone candidatos por similitud coseno."""

import re
from collections.abc import Sequence
from typing import Any

import numpy as np
from scipy import sparse
from sklearn.feature_extraction.text import TfidfVectorizer

# Marcadores que el dataset inserta para señalar dónde iba la cita.
CITATION_MARKERS = re.compile(r"\b(TARGETCIT|OTHERCIT)\b")


def build_paper_text(paper: dict[str, Any]) -> str:
    """Combina título y resumen en el texto que se vectoriza."""
    title = paper.get("title") or ""
    abstract = paper.get("abstract") or ""

    return f"{title} {abstract}".strip()


def clean_context_text(text: str) -> str:
    """Elimina los marcadores de cita del contexto."""
    return CITATION_MARKERS.sub(" ", text or "").strip()


class TfidfBaseline:
    """Ordena artículos por similitud coseno TF-IDF con el contexto."""

    def __init__(
        self,
        max_features: int | None = 50_000,
        ngram_range: tuple[int, int] = (1, 1),
        min_df: int = 2,
        stop_words: str | None = "english",
    ) -> None:
        self.max_features = max_features
        self.ngram_range = ngram_range
        self.min_df = min_df
        self.stop_words = stop_words

        self.vectorizer: TfidfVectorizer | None = None
        self.paper_ids: list[str] = []
        self._paper_matrix: sparse.csr_matrix | None = None

    def fit(self, papers: dict[str, dict[str, Any]]) -> "TfidfBaseline":
        """Ajusta el vocabulario sobre título+resumen de los artículos."""
        if not papers:
            raise ValueError("papers no puede estar vacío.")

        # El orden fija la correspondencia entre filas de la matriz e IDs.
        self.paper_ids = list(papers.keys())
        texts = [build_paper_text(papers[paper_id]) for paper_id in self.paper_ids]

        self.vectorizer = TfidfVectorizer(
            max_features=self.max_features,
            ngram_range=self.ngram_range,
            min_df=self.min_df,
            stop_words=self.stop_words,
        )
        self._paper_matrix = self.vectorizer.fit_transform(texts)

        return self

    @property
    def paper_matrix(self) -> sparse.csr_matrix:
        """Matriz TF-IDF de los artículos, en el orden de ``paper_ids``."""
        if self._paper_matrix is None:
            raise RuntimeError("Debe llamarse fit() antes de usar paper_matrix.")

        return self._paper_matrix

    def rank_with_scores(
        self,
        context: str,
        top_k: int = 100,
    ) -> list[tuple[str, float]]:
        """Devuelve los ``top_k`` artículos más similares a un contexto, con su puntaje."""
        if self.vectorizer is None or self._paper_matrix is None:
            raise RuntimeError("Debe llamarse fit() antes de rank_with_scores().")
        if top_k <= 0:
            raise ValueError("top_k debe ser un entero positivo.")

        cleaned = clean_context_text(context)

        if not cleaned:
            return []

        query_vector = self.vectorizer.transform([cleaned])
        similarities = (query_vector @ self._paper_matrix.T).toarray()[0]
        effective_k = min(top_k, len(self.paper_ids))

        # argpartition evita ordenar los ~20.000 artículos para quedarse con K.
        top_indices = np.argpartition(-similarities, effective_k - 1)[:effective_k]
        top_indices = top_indices[np.argsort(-similarities[top_indices])]

        return [
            (self.paper_ids[index], float(similarities[index])) for index in top_indices
        ]

    def rank(
        self,
        contexts: Sequence[str],
        top_k: int = 10,
        batch_size: int = 256,
    ) -> list[list[str]]:
        """Devuelve los ``top_k`` artículos más similares para cada contexto."""
        if self.vectorizer is None or self._paper_matrix is None:
            raise RuntimeError("Debe llamarse fit() antes de rank().")
        if top_k <= 0:
            raise ValueError("top_k debe ser un entero positivo.")

        effective_k = min(top_k, len(self.paper_ids))
        cleaned = [clean_context_text(text) for text in contexts]
        rankings: list[list[str]] = []

        for start in range(0, len(cleaned), batch_size):
            batch = cleaned[start : start + batch_size]
            query_matrix = self.vectorizer.transform(batch)

            # Ambas matrices están normalizadas en L2: el producto es el coseno.
            similarities = (query_matrix @ self._paper_matrix.T).toarray()

            top_unsorted = np.argpartition(-similarities, effective_k - 1, axis=1)
            top_unsorted = top_unsorted[:, :effective_k]

            for row_index in range(similarities.shape[0]):
                candidate_indices = top_unsorted[row_index]
                ordered = candidate_indices[
                    np.argsort(-similarities[row_index, candidate_indices])
                ]
                rankings.append([self.paper_ids[i] for i in ordered])

        return rankings
