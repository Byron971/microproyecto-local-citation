from __future__ import annotations

from typing import Protocol

from .schema import ProviderResponse


class ProviderCallError(RuntimeError):
    def __init__(self, message: str, *, transient: bool) -> None:
        super().__init__(message)
        self.transient = transient


class CommercialModelClient(Protocol):
    provider: str
    model: str

    def generate(self, prompt: str) -> ProviderResponse:
        ...
