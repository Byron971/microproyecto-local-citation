"""Puertos: lo que el dominio y el servicio necesitan del exterior."""
from pathlib import Path
from typing import Protocol


class Tokenizador(Protocol):
    cls_id: int
    sep_id: int

    def ids(self, texto: str) -> list[int]:
        """Ids de subpalabras sin tokens especiales."""
        ...

    def info(self) -> dict: ...


class Recuperador(Protocol):
    def __call__(self, contexto: str, chunks: list[dict]) -> list[dict]:
        """Devuelve los chunks ordenados por relevancia (Top-3 lo recorta el servicio)."""
        ...


class Entrenador(Protocol):
    def __call__(
        self, entrenamiento: list[dict], validacion: list[dict], semilla: int, salida: Path
    ) -> dict:
        """Entrena y devuelve el manifiesto de la corrida (checkpoint, metricas de val)."""
        ...


class Predictor(Protocol):
    def __call__(self, casos: list[dict]) -> list[dict]:
        """Devuelve, por caso, `pred_label`, `pred_index` y `scores_9`."""
        ...


class Reloj(Protocol):
    def __call__(self) -> float: ...


class Fuentes(Protocol):
    """Origen de los datos del proyecto de grado (lo implementa el adaptador)."""

    def indice(self) -> tuple[dict[str, str], dict[str, dict]]:
        """(context_id -> split ACL-200, context_id -> {citing_id, refid, masked_text})."""
        ...

    def filas_haiku(self) -> list[dict]:
        """Etiquetas Haiku de train/val: {context_id, etiqueta, titulo, abstract}."""
        ...

    def split_entrenamiento(self) -> dict[str, list[str]]:
        """{'train': [context_id], 'val': [context_id]} agrupado por citante."""
        ...

    def filas_test_gold(self) -> list[dict]:
        """Test Gold 2700 (etiquetas Haiku): {context_id, etiqueta, titulo, abstract, anio_citante}."""
        ...

    def ids_gold_v2(self) -> list[str]:
        """context_id del Gold v2 (ciego, sin etiquetas)."""
        ...

    def exclusiones(self) -> set[str]: ...

    def rutas(self) -> dict[str, Path]:
        """Archivos de entrada (para registrar su SHA en el manifiesto)."""
        ...
