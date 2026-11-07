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
