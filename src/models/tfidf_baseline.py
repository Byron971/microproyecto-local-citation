"""Línea base de recomendación de citas con TF-IDF y similitud coseno.

Es el punto de comparación más simple del proyecto: representa cada artículo
candidato y cada contexto de cita como vectores TF-IDF y ordena los artículos
por similitud coseno con el contexto. No aprende de los ejemplos etiquetados,
solo mide coincidencia léxica.

La exploración de datos de la Entrega 1 justificó este enfoque: en el 90,1 % de
las consultas el artículo realmente citado obtuvo mayor similitud TF-IDF que un
artículo aleatorio. Este módulo convierte esa señal en un ranking evaluable.
"""

import re
from collections.abc import Sequence
from typing import Any

import numpy as np
from scipy import sparse
from sklearn.feature_extraction.text import TfidfVectorizer

# Marcadores que el conjunto de datos inserta en los contextos para señalar
# dónde iba la cita objetivo (TARGETCIT) y otras citas del mismo pasaje
# (OTHERCIT). Se eliminan porque no son contenido del texto: aparecen en todos
# los contextos y solo aportan ruido a la representación.
CITATION_MARKERS = re.compile(r"\b(TARGETCIT|OTHERCIT)\b")


def build_paper_text(paper: dict[str, Any]) -> str:
    """Combina título y resumen de un artículo en un solo texto.

    Se concatenan porque el título aporta los términos más discriminantes y el
    resumen la cobertura temática; usar solo uno pierde señal.

    Parameters
    ----------
    paper:
        Registro del artículo, con claves ``title`` y ``abstract``.

    Returns
    -------
    str
        Texto combinado, listo para vectorizar.
    """
    title = paper.get("title") or ""
    abstract = paper.get("abstract") or ""

    return f"{title} {abstract}".strip()


def clean_context_text(text: str) -> str:
    """Elimina los marcadores de cita del contexto.

    Parameters
    ----------
    text:
        Texto del contexto tal como viene en ``contexts.json``.

    Returns
    -------
    str
        Texto sin los marcadores ``TARGETCIT`` ni ``OTHERCIT``.
    """
    return CITATION_MARKERS.sub(" ", text or "").strip()


class TfidfBaseline:
    """Recomendador de citas basado en similitud coseno sobre TF-IDF.

    Parameters
    ----------
    max_features:
        Tamaño máximo del vocabulario. Limitarlo acota la memoria sin perder
        los términos más informativos, porque TF-IDF conserva los de mayor
        frecuencia ponderada.
    ngram_range:
        Rango de n-gramas a considerar.
    min_df:
        Frecuencia documental mínima para incluir un término. Descarta
        errores de tipeo y términos que aparecen en un solo artículo.
    stop_words:
        Lista de palabras vacías. El corpus está en inglés.
    """

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
        """Ajusta el vocabulario TF-IDF sobre los artículos candidatos.

        El vectorizador se entrena solo con los artículos, no con los
        contextos: los artículos son el corpus que se va a recuperar, y usar
        también los contextos sesgaría el IDF hacia el vocabulario de las
        consultas.

        Parameters
        ----------
        papers:
            Diccionario ``paper_id -> {title, abstract}``.

        Returns
        -------
        TfidfBaseline
            La misma instancia, ya ajustada.
        """
        if not papers:
            raise ValueError("papers no puede estar vacío.")

        # El orden de los identificadores debe quedar fijo: las filas de la
        # matriz se corresponden posicionalmente con esta lista.
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
        """Matriz TF-IDF de los artículos, en el mismo orden que ``paper_ids``.

        Se expone para permitir análisis que necesitan los valores de similitud
        y no solo el ranking, como el diagnóstico de muestreo de negativos.
        ``rank()`` devuelve identificadores ordenados pero descarta los puntajes,
        y hay preguntas -por ejemplo, qué tan parecido es un negativo concreto a
        su consulta- que no se pueden responder sin ellos.

        Returns
        -------
        scipy.sparse.csr_matrix
            Matriz dispersa de forma ``(n_articulos, n_terminos)``.
        """
        if self._paper_matrix is None:
            raise RuntimeError("Debe llamarse fit() antes de usar paper_matrix.")

        return self._paper_matrix

    def rank(
        self,
        contexts: Sequence[str],
        top_k: int = 10,
        batch_size: int = 256,
    ) -> list[list[str]]:
        """Devuelve los ``top_k`` artículos más similares para cada contexto.

        Procesa las consultas por lotes porque la matriz completa de
        similitudes (consultas × artículos) no cabe en memoria: con 9.381
        consultas de validación y 19.776 artículos serían más de 1 GB en
        denso. Por lote solo se conservan las K mejores posiciones.

        Parameters
        ----------
        contexts:
            Textos de los contextos de cita.
        top_k:
            Número de artículos a devolver por consulta.
        batch_size:
            Cantidad de consultas procesadas simultáneamente.

        Returns
        -------
        list[list[str]]
            Para cada contexto, la lista ordenada de identificadores de
            artículo, del más al menos similar.
        """
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

            # Ambas matrices están normalizadas en norma L2 por TfidfVectorizer,
            # así que el producto punto ya es la similitud coseno.
            similarities = (query_matrix @ self._paper_matrix.T).toarray()

            # argpartition encuentra las K mejores sin ordenar todo el arreglo;
            # después solo se ordenan esas K, que es mucho más barato que
            # ordenar los ~20.000 artículos por consulta.
            top_unsorted = np.argpartition(-similarities, effective_k - 1, axis=1)
            top_unsorted = top_unsorted[:, :effective_k]

            for row_index in range(similarities.shape[0]):
                candidate_indices = top_unsorted[row_index]
                ordered = candidate_indices[
                    np.argsort(-similarities[row_index, candidate_indices])
                ]
                rankings.append([self.paper_ids[i] for i in ordered])

        return rankings
