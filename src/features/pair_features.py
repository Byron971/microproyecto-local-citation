"""Características numéricas para pares contexto-artículo.

El reordenador lineal no consume texto directamente. Este módulo transforma
cada par en señales interpretables: similitud TF-IDF con el título y con el
resumen, y las longitudes de los tres textos. El vocabulario se ajusta una sola
vez sobre título+resumen de los artículos, igual que en la línea base.
"""

from collections.abc import Sequence
from typing import Any, Self

import numpy as np
from scipy import sparse
from sklearn.feature_extraction.text import TfidfVectorizer

from src.models.tfidf_baseline import build_paper_text, clean_context_text

FEATURE_NAMES = (
    "similarity_title",
    "similarity_abstract",
    "context_length",
    "title_length",
    "abstract_length",
)


def word_count(text: str | None) -> int:
    """Cuenta tokens separados por espacios, tolerando valores ausentes."""
    return len((text or "").split())


class PairFeatureExtractor:
    """Construye características para pares identificados por sus IDs.

    Parameters
    ----------
    max_features, ngram_range, min_df, stop_words:
        Configuración del espacio TF-IDF compartido por contextos, títulos y
        resúmenes.
    batch_size:
        Cantidad de pares procesados a la vez al calcular productos dispersos.
    """

    def __init__(
        self,
        max_features: int | None = 50_000,
        ngram_range: tuple[int, int] = (1, 1),
        min_df: int = 2,
        stop_words: str | None = "english",
        batch_size: int = 4096,
    ) -> None:
        self.max_features = max_features
        self.ngram_range = ngram_range
        self.min_df = min_df
        self.stop_words = stop_words
        self.batch_size = batch_size

        self.vectorizer: TfidfVectorizer | None = None
        self.paper_ids: list[str] = []
        self._paper_row: dict[str, int] = {}
        self._title_matrix: sparse.csr_matrix | None = None
        self._abstract_matrix: sparse.csr_matrix | None = None
        self._title_lengths: np.ndarray | None = None
        self._abstract_lengths: np.ndarray | None = None

    @property
    def feature_names(self) -> tuple[str, ...]:
        """Nombres de columnas, en el mismo orden producido por transform."""
        return FEATURE_NAMES

    def fit(self, papers: dict[str, dict[str, Any]]) -> Self:
        """Ajusta el vocabulario y precalcula matrices de todos los artículos."""
        if not papers:
            raise ValueError("papers no puede estar vacío.")
        if self.batch_size <= 0:
            raise ValueError("batch_size debe ser un entero positivo.")

        self.paper_ids = list(papers)
        self._paper_row = {
            paper_id: index for index, paper_id in enumerate(self.paper_ids)
        }

        titles = [(papers[paper_id].get("title") or "") for paper_id in self.paper_ids]
        abstracts = [
            (papers[paper_id].get("abstract") or "") for paper_id in self.paper_ids
        ]
        combined = [build_paper_text(papers[paper_id]) for paper_id in self.paper_ids]

        self.vectorizer = TfidfVectorizer(
            max_features=self.max_features,
            ngram_range=self.ngram_range,
            min_df=self.min_df,
            stop_words=self.stop_words,
        )
        self.vectorizer.fit(combined)
        self._title_matrix = self.vectorizer.transform(titles).tocsr()
        self._abstract_matrix = self.vectorizer.transform(abstracts).tocsr()
        self._title_lengths = np.asarray(
            [word_count(text) for text in titles], dtype=float
        )
        self._abstract_lengths = np.asarray(
            [word_count(text) for text in abstracts], dtype=float
        )
        return self

    def _require_fitted(self) -> None:
        if (
            self.vectorizer is None
            or self._title_matrix is None
            or self._abstract_matrix is None
            or self._title_lengths is None
            or self._abstract_lengths is None
        ):
            raise RuntimeError("Debe llamarse fit() antes de transform().")

    def transform(
        self,
        pairs: Sequence[dict[str, Any]],
        contexts: dict[str, dict[str, Any]],
    ) -> np.ndarray:
        """Transforma pares ``context_id``/``paper_id`` en una matriz densa.

        Los contextos únicos se vectorizan una sola vez. Luego se seleccionan
        sus filas para cada par y se calcula el producto elemento a elemento
        contra el título y el resumen correspondientes. Como los vectores están
        normalizados en L2, la suma de ese producto es la similitud coseno.
        """
        self._require_fitted()

        if not pairs:
            return np.empty((0, len(FEATURE_NAMES)), dtype=float)

        context_ids = list(dict.fromkeys(pair["context_id"] for pair in pairs))
        missing_contexts = [
            context_id for context_id in context_ids if context_id not in contexts
        ]
        if missing_contexts:
            raise KeyError(f"Contextos no encontrados: {missing_contexts[:3]}")

        missing_papers = [
            pair["paper_id"]
            for pair in pairs
            if pair["paper_id"] not in self._paper_row
        ]
        if missing_papers:
            raise KeyError(f"Artículos no encontrados: {missing_papers[:3]}")

        context_row = {
            context_id: index for index, context_id in enumerate(context_ids)
        }
        cleaned_contexts = [
            clean_context_text(contexts[context_id].get("masked_text", ""))
            for context_id in context_ids
        ]
        context_matrix = self.vectorizer.transform(cleaned_contexts).tocsr()
        context_lengths = np.asarray(
            [word_count(text) for text in cleaned_contexts], dtype=float
        )

        features = np.empty((len(pairs), len(FEATURE_NAMES)), dtype=float)

        for start in range(0, len(pairs), self.batch_size):
            end = min(start + self.batch_size, len(pairs))
            batch = pairs[start:end]
            context_indices = np.asarray(
                [context_row[pair["context_id"]] for pair in batch]
            )
            paper_indices = np.asarray(
                [self._paper_row[pair["paper_id"]] for pair in batch]
            )

            query_rows = context_matrix[context_indices]
            title_rows = self._title_matrix[paper_indices]
            abstract_rows = self._abstract_matrix[paper_indices]

            title_similarity = np.asarray(
                query_rows.multiply(title_rows).sum(axis=1)
            ).ravel()
            abstract_similarity = np.asarray(
                query_rows.multiply(abstract_rows).sum(axis=1)
            ).ravel()

            features[start:end] = np.column_stack(
                [
                    title_similarity,
                    abstract_similarity,
                    context_lengths[context_indices],
                    self._title_lengths[paper_indices],
                    self._abstract_lengths[paper_indices],
                ]
            )

        return features

    def fit_transform(
        self,
        papers: dict[str, dict[str, Any]],
        pairs: Sequence[dict[str, Any]],
        contexts: dict[str, dict[str, Any]],
    ) -> np.ndarray:
        """Ajusta sobre artículos y transforma los pares indicados."""
        return self.fit(papers).transform(pairs, contexts)
