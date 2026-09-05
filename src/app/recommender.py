"""Servicio de recomendación que envuelve la línea base TF-IDF.

A diferencia de la maqueta, que devolvía un diccionario fijo de ejemplo, este
módulo carga el modelo real y ordena los 19.776 artículos del corpus para cada
consulta que llega por la API.

El modelo se ajusta una sola vez al arrancar el proceso y queda en memoria. Se
hace así porque ``fit`` tarda unos segundos y no depende de la consulta:
repetirlo en cada petición multiplicaría por mil el tiempo de respuesta sin
cambiar un solo resultado.
"""

from pathlib import Path
from typing import Any

import numpy as np

from sklearn.feature_extraction.text import TfidfVectorizer

from src.data.load_data import load_json
from src.models.tfidf_baseline import TfidfBaseline, clean_context_text

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RAW_DIR = PROJECT_ROOT / "data" / "raw"

# Longitud máxima del resumen que se envía al frontend. Los resúmenes completos
# llegan a superar las 400 palabras y el panel de detalle solo muestra un
# extracto; recortar aquí evita mandar megabytes por la red en cada consulta.
ABSTRACT_PREVIEW_CHARS = 600


class Recommender:
    """Recomendador de citas listo para servir peticiones HTTP.

    Parameters
    ----------
    raw_dir:
        Carpeta con ``papers.json``. Por omisión ``data/raw`` del repositorio.
    max_features:
        Tamaño máximo del vocabulario TF-IDF. El valor por defecto es el mismo
        con el que se obtuvieron las métricas reportadas, para que lo que sirve
        la API coincida con lo que muestra el tablero.
    min_df:
        Frecuencia documental mínima de un término.
    """

    def __init__(
        self,
        raw_dir: str | Path = DEFAULT_RAW_DIR,
        max_features: int = 50_000,
        min_df: int = 2,
    ) -> None:
        self.raw_dir = Path(raw_dir)
        self.max_features = max_features
        self.min_df = min_df

        self.papers: dict[str, dict[str, Any]] = {}
        self.baseline: TfidfBaseline | None = None

    def load(self) -> "Recommender":
        """Carga los artículos y ajusta el modelo.

        Se invoca una vez durante el arranque del servidor, no en el
        constructor, para que crear la instancia sea barato y el costo quede
        explícito en el ciclo de vida de la aplicación.

        Returns
        -------
        Recommender
            La misma instancia, ya lista para responder.
        """
        self.papers = load_json(self.raw_dir / "papers.json")
        self.baseline = TfidfBaseline(
            max_features=self.max_features,
            min_df=self.min_df,
        ).fit(self.papers)

        return self

    @property
    def is_ready(self) -> bool:
        """Indica si el modelo ya está ajustado y puede responder consultas."""
        return self.baseline is not None

    def describe(self) -> dict[str, Any]:
        """Devuelve la ficha técnica del modelo que se está sirviendo.

        El tablero la muestra para que quede explícito qué versión del modelo
        produjo las recomendaciones que el usuario está viendo.

        Returns
        -------
        dict
            Nombre del modelo, tamaño del corpus y parámetros del vectorizador.
        """
        baseline = self._ready_baseline()

        return {
            "modelo": "TF-IDF + similitud coseno",
            "articulos": len(baseline.paper_ids),
            "vocabulario": len(self._ready_vectorizer().vocabulary_),
            "max_features": self.max_features,
            "min_df": self.min_df,
        }

    def recommend(self, context: str, top_k: int = 10) -> list[dict[str, Any]]:
        """Ordena los artículos del corpus por similitud con el contexto.

        Se calcula la similitud directamente en vez de delegar en
        ``TfidfBaseline.rank()`` porque el tablero necesita mostrar el puntaje
        de cada recomendación, y ``rank()`` devuelve solo identificadores
        ordenados. La matriz de artículos se expone justamente para este caso.

        Parameters
        ----------
        context:
            Texto académico en inglés donde haría falta la cita.
        top_k:
            Cantidad de artículos a devolver.

        Returns
        -------
        list[dict]
            Recomendaciones ordenadas de mayor a menor similitud, cada una con
            posición, identificador, título, extracto del resumen y puntaje.
        """
        baseline = self._ready_baseline()

        if top_k <= 0:
            raise ValueError("top_k debe ser un entero positivo.")

        cleaned = clean_context_text(context)

        # Un contexto vacío produciría un vector nulo y un ranking arbitrario
        # entre artículos todos con similitud cero. Es preferible no devolver
        # nada a devolver ruido presentado como recomendación.
        if not cleaned:
            return []

        query_vector = self._ready_vectorizer().transform([cleaned])
        similarities = (query_vector @ baseline.paper_matrix.T).toarray()[0]

        effective_k = min(top_k, len(baseline.paper_ids))

        # Mismo criterio que en la línea base: argpartition evita ordenar los
        # casi 20.000 artículos cuando solo se necesitan los primeros.
        top_indices = np.argpartition(-similarities, effective_k - 1)[:effective_k]
        top_indices = top_indices[np.argsort(-similarities[top_indices])]

        return [
            self._build_recommendation(int(index), position, float(similarities[index]))
            for position, index in enumerate(top_indices, start=1)
        ]

    def _build_recommendation(
        self,
        index: int,
        position: int,
        score: float,
    ) -> dict[str, Any]:
        """Arma el registro de una recomendación a partir de su fila."""
        paper_id = self._ready_baseline().paper_ids[index]
        paper = self.papers[paper_id]

        abstract = (paper.get("abstract") or "").strip()
        truncated = len(abstract) > ABSTRACT_PREVIEW_CHARS

        return {
            "posicion": position,
            "paper_id": paper_id,
            "titulo": (paper.get("title") or "").strip(),
            "resumen": abstract[:ABSTRACT_PREVIEW_CHARS] + ("…" if truncated else ""),
            "similitud": round(score, 4),
        }

    def _ready_vectorizer(self) -> TfidfVectorizer:
        """Devuelve el vectorizador ajustado del modelo.

        ``TfidfBaseline`` lo deja en ``None`` hasta que se llama ``fit``, así
        que se valida aquí por la misma razón que el modelo mismo.
        """
        vectorizer = self._ready_baseline().vectorizer

        if vectorizer is None:
            raise RuntimeError("Debe llamarse load() antes de usar el recomendador.")

        return vectorizer

    def _ready_baseline(self) -> TfidfBaseline:
        """Devuelve el modelo ya ajustado, o falla con un mensaje claro.

        Devuelve la instancia en vez de solo comprobarla para que quien la use
        trabaje sobre un valor que no es ``None``, tanto en ejecución como para
        el verificador de tipos.
        """
        if self.baseline is None:
            raise RuntimeError("Debe llamarse load() antes de usar el recomendador.")

        return self.baseline
