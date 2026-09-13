"""Características numéricas para pares contexto-artículo.

El reordenador lineal no consume texto directamente. Este módulo transforma
cada par en señales interpretables: similitud TF-IDF con el título y con el
resumen, y las longitudes de los tres textos. El vocabulario se ajusta una sola
vez sobre título+resumen de los artículos, igual que en la línea base.

Con ``include_metadata=True`` se añaden cinco señales derivadas de los metadatos
que codifica el identificador del ACL Anthology y del conjunto de entrenamiento.
La bandera existe para que la versión 1 del reordenador siga siendo exactamente
reproducible: la comparación entre versiones es un único parámetro.
"""

import re
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

# Señales que solo se calculan con include_metadata=True. Van después de las
# anteriores para que el orden de las cinco originales no cambie nunca.
METADATA_FEATURE_NAMES = (
    "year_diff",
    "is_future",
    "same_venue",
    "title_overlap",
    "citation_prior",
)

# Identificador del ACL Anthology: letra de tipo de publicación, año de dos
# dígitos y número. Por ejemplo W11-1305 es un taller de 2011. Los 19.776
# artículos del corpus lo cumplen.
ACL_ID = re.compile(r"^([A-Z])(\d{2})-")

# Las siglas del Anthology usan dos dígitos, así que hay que decidir el siglo.
# El corpus va de los años noventa a 2015, de modo que un valor por debajo del
# umbral pertenece a los dos mil.
SIGLO_XXI_ANTES_DE = 50


def parse_acl_id(paper_id: str | None) -> tuple[str | None, int | None]:
    """Extrae tipo de publicación y año de un identificador del ACL Anthology.

    Devuelve ``(None, None)`` si el identificador no sigue el formato, para que
    quien llame decida el valor neutro en lugar de recibir un dato inventado.

    Parameters
    ----------
    paper_id:
        Identificador como ``"W11-1305"``.

    Returns
    -------
    tuple[str | None, int | None]
        Letra del tipo de publicación y año de cuatro dígitos.
    """
    match = ACL_ID.match(paper_id or "")
    if match is None:
        return None, None

    venue, two_digit_year = match.group(1), int(match.group(2))
    year = (
        2000 + two_digit_year
        if two_digit_year < SIGLO_XXI_ANTES_DE
        else 1900 + two_digit_year
    )

    return venue, year


def word_count(text: str | None) -> int:
    """Cuenta tokens separados por espacios, tolerando valores ausentes."""
    return len((text or "").split())


def token_set(text: str | None) -> set[str]:
    """Conjunto de palabras en minúsculas, para medir solapamiento literal.

    Es deliberadamente más simple que el vectorizador: el solapamiento cuenta
    coincidencias exactas, mientras que el coseno TF-IDF las pondera por IDF y
    diluye las de términos frecuentes. Son señales distintas.
    """
    return {token for token in (text or "").lower().split() if token}


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
        include_metadata: bool = False,
        citation_counts: dict[str, int] | None = None,
    ) -> None:
        self.max_features = max_features
        self.ngram_range = ngram_range
        self.min_df = min_df
        self.stop_words = stop_words
        self.batch_size = batch_size
        self.include_metadata = include_metadata

        # Veces que cada artículo aparece como positivo en ENTRENAMIENTO. Debe
        # calcularse solo sobre train: contarlo sobre validación filtraría al
        # modelo la respuesta que se le va a preguntar.
        self.citation_counts = citation_counts or {}

        self.vectorizer: TfidfVectorizer | None = None
        self.paper_ids: list[str] = []
        self._paper_row: dict[str, int] = {}
        self._title_matrix: sparse.csr_matrix | None = None
        self._abstract_matrix: sparse.csr_matrix | None = None
        self._title_lengths: np.ndarray | None = None
        self._abstract_lengths: np.ndarray | None = None
        self._paper_years: np.ndarray | None = None
        self._paper_venues: list[str | None] = []
        self._title_tokens: list[set[str]] = []
        self._paper_prior: np.ndarray | None = None

    @property
    def feature_names(self) -> tuple[str, ...]:
        """Nombres de columnas, en el mismo orden producido por transform."""
        if self.include_metadata:
            return FEATURE_NAMES + METADATA_FEATURE_NAMES

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

        if self.include_metadata:
            self._fit_metadata(titles)

        return self

    def _fit_metadata(self, titles: list[str]) -> None:
        """Precalcula por artículo lo que no depende del contexto consultado.

        Año y tipo de publicación salen del identificador; el conjunto de
        palabras del título y el prior de popularidad se calculan una sola vez
        porque se reutilizan en cada par donde aparece el artículo.
        """
        metadata = [parse_acl_id(paper_id) for paper_id in self.paper_ids]

        self._paper_venues = [venue for venue, _ in metadata]
        # El año ausente se marca con 0 y quien lo consuma lo trata como
        # desconocido; usar NaN obligaría a imputar antes de la regresión.
        self._paper_years = np.asarray(
            [year or 0 for _, year in metadata], dtype=float
        )
        self._title_tokens = [token_set(title) for title in titles]

        # Logaritmo porque la distribución de citas tiene cola larga: sin él,
        # un puñado de artículos muy citados domina la escala de la columna.
        self._paper_prior = np.log1p(
            np.asarray(
                [self.citation_counts.get(pid, 0) for pid in self.paper_ids],
                dtype=float,
            )
        )

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
            return np.empty((0, len(self.feature_names)), dtype=float)

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

        if self.include_metadata:
            # El artículo que cita define la referencia temporal: nada publicado
            # después de él puede ser una cita suya.
            citing_metadata = [
                parse_acl_id(contexts[context_id].get("citing_id"))
                for context_id in context_ids
            ]
            citing_venues = [venue for venue, _ in citing_metadata]
            citing_years = np.asarray(
                [year or 0 for _, year in citing_metadata], dtype=float
            )
            context_tokens = [token_set(text) for text in cleaned_contexts]

        features = np.empty((len(pairs), len(self.feature_names)), dtype=float)

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

            columns = [
                title_similarity,
                abstract_similarity,
                context_lengths[context_indices],
                self._title_lengths[paper_indices],
                self._abstract_lengths[paper_indices],
            ]

            if self.include_metadata:
                columns.extend(
                    self._metadata_columns(
                        context_indices=context_indices,
                        paper_indices=paper_indices,
                        citing_years=citing_years,
                        citing_venues=citing_venues,
                        context_tokens=context_tokens,
                    )
                )

            features[start:end] = np.column_stack(columns)

        return features

    def _metadata_columns(
        self,
        context_indices: np.ndarray,
        paper_indices: np.ndarray,
        citing_years: np.ndarray,
        citing_venues: list[str | None],
        context_tokens: list[set[str]],
    ) -> list[np.ndarray]:
        """Calcula las cinco columnas de metadatos para un lote de pares."""
        anio_candidato = self._paper_years[paper_indices]
        anio_citante = citing_years[context_indices]

        # Un año en 0 significa identificador no reconocido. En ese caso las
        # tres señales temporales quedan en su valor neutro en vez de producir
        # diferencias absurdas de dos mil años.
        conocidos = (anio_candidato > 0) & (anio_citante > 0)

        year_diff = np.where(conocidos, anio_citante - anio_candidato, 0.0)
        is_future = np.where(conocidos & (anio_candidato > anio_citante), 1.0, 0.0)

        same_venue = np.asarray(
            [
                1.0
                if (
                    self._paper_venues[paper]
                    and self._paper_venues[paper] == citing_venues[context]
                )
                else 0.0
                for context, paper in zip(context_indices, paper_indices, strict=True)
            ],
            dtype=float,
        )

        # Se normaliza por el tamaño del título y no por el del contexto: mide
        # qué fracción del título aparece en el contexto, que es la señal
        # buscada, y evita que los contextos largos la diluyan.
        title_overlap = np.asarray(
            [
                len(context_tokens[context] & self._title_tokens[paper])
                / max(len(self._title_tokens[paper]), 1)
                for context, paper in zip(context_indices, paper_indices, strict=True)
            ],
            dtype=float,
        )

        return [
            year_diff,
            is_future,
            same_venue,
            title_overlap,
            self._paper_prior[paper_indices],
        ]

    def fit_transform(
        self,
        papers: dict[str, dict[str, Any]],
        pairs: Sequence[dict[str, Any]],
        contexts: dict[str, dict[str, Any]],
    ) -> np.ndarray:
        """Ajusta sobre artículos y transforma los pares indicados."""
        return self.fit(papers).transform(pairs, contexts)
