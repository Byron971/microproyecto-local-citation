"""Servicio de recomendación que envuelve el paquete ``modelo_citas``.

El tablero ya no ajusta el modelo al arrancar ni lee ``data/raw``: consume el
artefacto entrenado que viaja dentro de la librería instalada, que recupera
candidatos con TF-IDF y los reordena con el modelo lineal supervisado.
"""

from typing import Any

import modelo_citas
from modelo_citas.models.citation_model import CitationArtifact


class Recommender:
    """Recomendador de citas listo para servir peticiones HTTP."""

    def __init__(self) -> None:
        self.model: CitationArtifact | None = None

    def load(self) -> "Recommender":
        """Carga el artefacto empaquetado.

        Se invoca una vez durante el arranque del servidor, no en el
        constructor, para que el costo quede explícito en el ciclo de vida de
        la aplicación.
        """
        self.model = modelo_citas.load_model()

        return self

    @property
    def is_ready(self) -> bool:
        """Indica si el modelo ya está cargado y puede responder consultas."""
        return self.model is not None

    def describe(self) -> dict[str, Any]:
        """Devuelve la ficha técnica del modelo que se está sirviendo."""
        self._require_loaded()

        return modelo_citas.describe()

    def recommend(self, context: str, top_k: int = 10) -> list[dict[str, Any]]:
        """Devuelve los artículos mejor puntuados por el reordenador.

        Parameters
        ----------
        context:
            Texto académico en inglés donde haría falta la cita.
        top_k:
            Cantidad de artículos a devolver.

        Returns
        -------
        list[dict]
            Recomendaciones ordenadas de mayor a menor puntaje, cada una con
            posición, identificador, título, extracto del resumen y puntaje.
        """
        self._require_loaded()

        if top_k <= 0:
            raise ValueError("top_k debe ser un entero positivo.")

        resultado = modelo_citas.make_prediction(context=context, top_k=top_k)

        # Un contexto vacío o un top_k fuera de rango los rechaza la validación
        # del paquete; aquí se traduce a la misma lista vacía de antes.
        if resultado["errors"] is not None:
            return []

        return resultado["predictions"]

    def _require_loaded(self) -> None:
        """Falla con un mensaje claro si el arranque no llamó a ``load()``."""
        if self.model is None:
            raise RuntimeError("Debe llamarse load() antes de usar el recomendador.")
