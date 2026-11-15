"""Puertos: lo que el dominio y el servicio necesitan del exterior."""
from pathlib import Path
from typing import Callable, Protocol


class Codificador(Protocol):
    model_id: str
    revision: str

    def encode(self, textos: list[str]) -> list[tuple[float, ...]]: ...

    def info(self) -> dict: ...


class RecuperadorLexico(Protocol):
    def __call__(self, contexto: str, chunks: list[dict]) -> list[dict]: ...


class CacheEmbeddings(Protocol):
    def get(self, clave: str) -> tuple[float, ...] | None: ...

    def put(self, clave: str, vector: tuple[float, ...]) -> None: ...


class PerfilSeccion(Protocol):
    def __call__(self, seccion: str | None) -> str: ...


class Reloj(Protocol):
    def __call__(self) -> float: ...


class PuntuarGold(Protocol):
    def __call__(self, ranking: list[str], gold: set[str]) -> dict | None: ...


class Fragmentador(Protocol):
    def __call__(self, parrafos: list[dict]) -> list[dict]: ...


class Integrador(Protocol):
    def __call__(
        self, context_id: str, contextos: dict, papers: dict, cache_dir: Path
    ) -> dict: ...


class IndiceSplits(Protocol):
    by_context: dict[str, str]
    contexts: dict[str, dict]


Perfil = Callable[[str | None], str]
