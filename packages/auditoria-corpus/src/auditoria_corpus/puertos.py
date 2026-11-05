"""Puertos: lo que el dominio y el servicio necesitan del exterior."""
from pathlib import Path
from typing import Protocol


class Fragmentador(Protocol):
    def __call__(self, parrafos: list[dict]) -> list[dict]: ...


class Integrador(Protocol):
    def __call__(
        self, context_id: str, contextos: dict, papers: dict, cache_dir: Path
    ) -> dict: ...


class LectorOCL(Protocol):
    def __call__(self, acl_id: str, cache_dir: Path) -> dict | None: ...


class IndiceSplits(Protocol):
    by_context: dict[str, str]
    contexts: dict[str, dict]
