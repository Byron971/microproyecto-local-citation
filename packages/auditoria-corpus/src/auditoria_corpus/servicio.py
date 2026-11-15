"""Orquestacion de la auditoria a traves de puertos (sin red)."""
from __future__ import annotations

import random
from dataclasses import dataclass
from pathlib import Path

from . import dominio
from .puertos import Fragmentador, IndiceSplits, Integrador
from .reglas import ReglasChunk

ERRORES_ESPERADOS = (KeyError, TypeError, ValueError, OSError)


@dataclass
class Auditoria:
    filas: list[dict]
    citados: list[dict]
    filas_chunks: list[dict]
    muestras: list[dict]
    resumen: dict


def _estado_cache(cited_id: str, cache: Path) -> str:
    if (cache / f"{cited_id}.json").is_file():
        return "json"
    if (cache / f"{cited_id}.404").is_file():
        return "404"
    return "ausente"


def auditar_contexto(
    context_id: str, indice: IndiceSplits, papers: dict, cache: Path,
    integrar: Integrador, fragmentar: Fragmentador, reglas: ReglasChunk,
    memo: dict[str, dict],
) -> tuple[dict, dict | None]:
    """Devuelve (fila_contexto, resultado_citado_o_None). `memo` evita repetir por citado."""
    ctx = indice.contexts[context_id]
    cited_id = ctx.get("refid")
    fila = {
        "context_id": context_id, "split": indice.by_context[context_id],
        "cited_id": cited_id, "estado": "ok", "causa": "",
    }

    def fallo(causa: str):
        fila.update(estado="error", causa=causa)
        return fila, None

    estado = _estado_cache(cited_id, cache)
    if estado == "404":
        return fallo("citado_404")
    if estado == "ausente":
        return fallo("citado_no_descargado")

    try:
        registro = integrar(context_id, indice.contexts, papers, cache)
        parrafos = registro["paragraphs"]
    except ERRORES_ESPERADOS as exc:
        return fallo(dominio.clasificar_error(exc))

    if cited_id in memo:
        if memo[cited_id]["estado"] != "ok":
            fila.update(estado="error", causa=memo[cited_id]["causa"])
        return fila, memo[cited_id]

    resultado = {"cited_id": cited_id, "estado": "ok", "causa": "", "chunks": [],
                 "violaciones": [], "metricas": {}, "reproducible": True, "perfiles": [],
                 "parrafos": parrafos}
    try:
        chunks = fragmentar(parrafos)
        otra = fragmentar(parrafos)
    except ERRORES_ESPERADOS as exc:
        resultado.update(estado="error", causa=dominio.clasificar_error(exc, parrafos, reglas))
        memo[cited_id] = resultado
        fila.update(estado="error", causa=resultado["causa"])
        return fila, resultado
    violaciones, metricas = dominio.verificar_chunks(chunks, parrafos, reglas)
    resultado.update(
        chunks=chunks, violaciones=violaciones, metricas=metricas,
        reproducible=dominio.huella_chunks(chunks) == dominio.huella_chunks(otra),
        perfiles=[dominio.perfil_seccion(c["seccion"]) for c in chunks],
    )
    memo[cited_id] = resultado
    return fila, resultado


def auditar_corpus(
    indice: IndiceSplits, papers: dict, cache: Path, integrar: Integrador,
    fragmentar: Fragmentador, reglas: ReglasChunk, excluidos: set[str],
    n_muestras: int = 20, semilla: int = 101,
) -> Auditoria:
    memo: dict[str, dict] = {}
    filas: list[dict] = []
    # Para citados sin intento (fallos previos a fragmentar) se registra su causa una vez.
    fallidos: dict[str, dict] = {}
    for cid in sorted(indice.by_context):
        fila, _ = auditar_contexto(cid, indice, papers, cache, integrar, fragmentar, reglas, memo)
        filas.append(fila)
        if fila["estado"] == "error" and fila["cited_id"] not in memo:
            fallidos.setdefault(fila["cited_id"], {
                "cited_id": fila["cited_id"], "estado": "error", "causa": fila["causa"],
                "chunks": [], "violaciones": [], "metricas": {}, "reproducible": True, "perfiles": [],
            })
    citados = []
    for cited_id in sorted({f["cited_id"] for f in filas}):
        if cited_id in memo:
            citados.append(memo[cited_id])
        elif cited_id in fallidos:
            citados.append(fallidos[cited_id])

    filas_chunks = [
        {"cited_id": c["cited_id"], "chunk_id": ch["chunk_id"], "seccion": ch["seccion"],
         "perfil_seccion": dominio.perfil_seccion(ch["seccion"]), "palabras": ch["palabras"],
         "n_parrafos": len(ch["paragraph_indices"])}
        for c in citados if c["estado"] == "ok" for ch in c["chunks"]
    ]

    candidatos = [
        {"context_id": f["context_id"], "split": f["split"], "cited_id": f["cited_id"]}
        for f in filas if f["estado"] == "ok"
    ]
    elegidos = dominio.seleccionar_muestras(candidatos, excluidos, n_muestras, semilla)
    muestras = []
    for e in elegidos:
        res = memo[e["cited_id"]]
        chunk = random.Random(f"{semilla}:{e['context_id']}").choice(res["chunks"])
        ctx = indice.contexts[e["context_id"]]
        muestras.append({
            "context_id": e["context_id"], "cited_id": e["cited_id"],
            "citation_context": ctx.get("masked_text", ""),
            "cited_title": papers.get(e["cited_id"], {}).get("title", ""),
            "chunk_id": chunk["chunk_id"], "seccion": chunk["seccion"],
            "palabras": chunk["palabras"], "texto": chunk["texto"],
            "verificado_por": "", "texto_ok": "", "seccion_ok": "", "chunk_ok": "", "nota": "",
        })
    resumen = dominio.resumir(filas, citados)
    resumen["muestras"] = {"n": len(muestras), "semilla": semilla, "solo_split": "train",
                           "ids_excluidos_suministrados": len(excluidos)}
    return Auditoria(filas, citados, filas_chunks, muestras, resumen)
