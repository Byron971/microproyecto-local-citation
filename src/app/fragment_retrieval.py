"""Recuperación BM25 de fragmentos de UN artículo citado.

Baseline determinista y sin modelos entrenados. Los párrafos se reciben de la
API o, posteriormente, de un adaptador de corpus versionado. No representa
el ranking de artículos del MVP ni implica métricas de calidad de recuperación.
"""
from __future__ import annotations

from collections import Counter
from math import log
import re
from typing import Any

_K1 = 1.5
_B = 0.75
_TOKENS = re.compile(r"[^\W_]+", flags=re.UNICODE)
_IGNORAR = frozenset({
    "targetcit", "othercit", "a", "an", "the", "and", "or", "of", "to",
    "in", "for", "on", "with", "by", "from", "as", "at", "is", "are",
    "was", "were", "be", "been", "this", "that", "these", "those",
    "we", "our", "they", "their", "it", "its", "which", "using",
})


def tokens(texto: str) -> list[str]:
    """Tokenización léxica reproducible, sin usar marcadores como contenido."""
    return [
        token for token in _TOKENS.findall(texto.casefold())
        if token not in _IGNORAR and len(token) > 1
    ]


def recuperar_top3(contexto: str, parrafos: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """BM25 por artículo: recupera hasta tres fragmentos con señal léxica.

    No devuelve párrafos de otros artículos ni inventa coincidencias si
    todos los puntajes son cero. El puntaje BM25 no es una probabilidad.
    Ante empates, usa chunk_id para hacer el resultado determinista.
    """
    consulta = set(tokens(contexto))
    if not consulta or not parrafos:
        return []

    documentos = [Counter(tokens(p["texto"])) for p in parrafos]
    longitudes = [sum(doc.values()) for doc in documentos]
    total = len(parrafos)
    longitud_media = sum(longitudes) / total
    if longitud_media == 0:
        return []

    frecuencias = Counter(
        termino for doc in documentos for termino in doc.keys()
    )
    resultados = []
    for p, doc, longitud in zip(parrafos, documentos, longitudes):
        puntuacion = 0.0
        for termino in consulta:
            frecuencia = doc.get(termino, 0)
            if not frecuencia:
                continue
            frecuencia_documental = frecuencias[termino]
            idf = log(1 + (total - frecuencia_documental + 0.5)
                      / (frecuencia_documental + 0.5))
            denominador = frecuencia + _K1 * (
                1 - _B + _B * longitud / longitud_media
            )
            puntuacion += idf * frecuencia * (_K1 + 1) / denominador
        if puntuacion > 0:
            resultados.append({
                "chunk_id": p["chunk_id"],
                "texto": p["texto"],
                "seccion": p.get("seccion"),
                "puntaje_bm25": round(puntuacion, 6),
            })

    resultados.sort(key=lambda p: (-p["puntaje_bm25"], p["chunk_id"]))
    return [
        {"posicion": i, **registro}
        for i, registro in enumerate(resultados[:3], start=1)
    ]
