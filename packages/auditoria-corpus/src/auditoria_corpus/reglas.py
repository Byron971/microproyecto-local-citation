"""Reglas de chunking que se auditan (inyectadas, no copiadas)."""
from dataclasses import dataclass


@dataclass(frozen=True)
class ReglasChunk:
    max_palabras: int
    max_parrafos: int
    max_caracteres: int
