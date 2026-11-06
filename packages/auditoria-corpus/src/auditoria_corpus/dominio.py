"""Dominio PURO de la auditoria: sin I/O ni imports del proyecto."""
from __future__ import annotations

import hashlib
import json
import random
import unicodedata
from collections import Counter, defaultdict
from statistics import median

from .reglas import ReglasChunk

SPLITS = ("train", "val", "test")


def _sin_acentos(texto: str) -> str:
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().lower()


def causa_parrafo_largo(parrafos: list[dict], reglas: ReglasChunk) -> str:
    """Distingue si el parrafo excede por palabras o por caracteres."""
    for p in parrafos:
        if len(p["texto"].split()) > reglas.max_palabras:
            return "parrafo_supera_palabras"
    for p in parrafos:
        if len(p["texto"]) > reglas.max_caracteres:
            return "parrafo_supera_caracteres"
    return "parrafo_largo_indeterminado"


def clasificar_error(
    exc: Exception, parrafos: list[dict] | None = None, reglas: ReglasChunk | None = None
) -> str:
    """Causa estable de un fallo de integracion/fragmentacion."""
    if isinstance(exc, json.JSONDecodeError):
        return "archivo_invalido"
    msg = _sin_acentos(str(exc))
    if isinstance(exc, FileNotFoundError):
        return "citado_no_descargado"
    if "cita objetivo unica" in msg:
        return "targetcit_no_unico"
    if "no existe en acl-200" in msg:
        return "citado_no_en_papers"
    if "id incorrecto" in msg:
        return "id_incorrecto"
    if "no contiene parrafos" in msg or "sin parrafos" in msg or "sin fragmentos" in msg:
        return "sin_parrafos"
    if "demasiado largo" in msg:
        if parrafos is not None and reglas is not None:
            return causa_parrafo_largo(parrafos, reglas)
        return "parrafo_largo_indeterminado"
    if "indice de parrafo" in msg:
        return "indice_invalido"
    return f"otro_{type(exc).__name__}"


def verificar_chunks(chunks: list[dict], parrafos: list[dict], reglas: ReglasChunk):
    """Comprueba los chunks de forma independiente a `fragmentar`.

    Devuelve (violaciones, metricas)."""
    violaciones: list[str] = []
    por_numero = {p["numero"]: p for p in parrafos}
    vistos: list[int] = []
    palabras: list[int] = []
    dos_parrafos = sin_seccion = 0

    for c in chunks:
        cid = c.get("chunk_id")
        idx = list(c.get("paragraph_indices", []))
        if not 1 <= len(idx) <= reglas.max_parrafos:
            violaciones.append(f"{cid}: {len(idx)} parrafos")
        if len(idx) == 2:
            dos_parrafos += 1
        if any(i not in por_numero for i in idx):
            violaciones.append(f"{cid}: indice inexistente en el articulo")
            continue
        if idx != list(range(idx[0], idx[0] + len(idx))):
            violaciones.append(f"{cid}: indices no contiguos")
        if cid != f"p{idx[0]:05d}-p{idx[-1]:05d}":
            violaciones.append(f"{cid}: chunk_id incoherente con paragraph_indices")
        secciones = {por_numero[i]["seccion"] for i in idx}
        if len(secciones) != 1:
            violaciones.append(f"{cid}: mezcla secciones")
        elif c.get("seccion") not in secciones:
            violaciones.append(f"{cid}: seccion del chunk distinta a la del parrafo")
        if not c.get("seccion"):
            sin_seccion += 1
        esperado = "\n".join(por_numero[i]["texto"] for i in idx)
        if c.get("texto") != esperado:
            violaciones.append(f"{cid}: texto no reconstruye los parrafos")
        n = len(esperado.split())
        palabras.append(n)
        if n > reglas.max_palabras:
            violaciones.append(f"{cid}: {n} palabras")
        if c.get("palabras") != n:
            violaciones.append(f"{cid}: campo palabras incoherente")
        if any(len(por_numero[i]["texto"]) > reglas.max_caracteres for i in idx):
            violaciones.append(f"{cid}: parrafo supera caracteres")
        vistos.extend(idx)

    esperados = [p["numero"] for p in parrafos]
    if vistos != esperados:
        perdidos = sorted(set(esperados) - set(vistos))
        duplicados = sorted(i for i, k in Counter(vistos).items() if k > 1)
        violaciones.append(f"cobertura de parrafos: perdidos={perdidos} duplicados={duplicados}")

    numeros = sorted(esperados)
    huecos = sum(1 for a, b in zip(numeros, numeros[1:]) if b != a + 1)
    metricas = {
        "chunks": len(chunks),
        "parrafos": len(parrafos),
        "palabras": palabras,
        "chunks_2_parrafos": dos_parrafos,
        "chunks_sin_seccion": sin_seccion,
        "huecos_indice": huecos,
    }
    return violaciones, metricas


def huella_chunks(chunks: list[dict]) -> str:
    canon = json.dumps(chunks, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


_HEURISTICA = (
    ("introduction", ("introduc", "motivation")),
    ("related_work", ("related", "background", "prior work", "previous work")),
    ("conclusion", ("conclusion", "future work", "summary", "discussion")),
    ("results", ("result", "experiment", "evaluation", "analysis", "finding")),
    ("method", ("method", "approach", "model", "system", "algorithm", "framework", "data", "corpus", "task")),
)


def perfil_seccion(nombre: str | None) -> str:
    """Mapeo HEURISTICO por palabras clave; no es una etiqueta retorica validada."""
    if not nombre or not nombre.strip():
        return "vacia"
    n = _sin_acentos(nombre)
    for perfil, claves in _HEURISTICA:
        if any(k in n for k in claves):
            return perfil
    return "otra"


def _pct(a: int, b: int) -> float | None:
    return round(100 * a / b, 2) if b else None


def resumir(filas: list[dict], citados: list[dict]) -> dict:
    """Agrega resultados.

    filas: una por contexto {split, cited_id, estado, causa}.
    citados: una por articulo citado auditado {cited_id, estado, causa, chunks,
             violaciones, metricas, reproducible, perfiles}."""
    por_split = {}
    for s in SPLITS:
        fs = [f for f in filas if f["split"] == s]
        ok = sum(f["estado"] == "ok" for f in fs)
        unicos = {f["cited_id"] for f in fs}
        ok_u = {f["cited_id"] for f in fs if f["estado"] == "ok"}
        por_split[s] = {
            "contextos": len(fs), "contextos_ok": ok, "cobertura_contextos_pct": _pct(ok, len(fs)),
            "citados_unicos": len(unicos), "citados_ok": len(ok_u),
            "cobertura_citados_pct": _pct(len(ok_u), len(unicos)),
        }
    estados = Counter(c["estado"] for c in citados)
    unicos_total = {f["cited_id"] for f in filas}
    resueltos = sum(1 for c in citados if c["causa"] not in ("citado_no_descargado",))
    ok_citados = [c for c in citados if c["estado"] == "ok"]
    errores = Counter(c["causa"] for c in citados if c["estado"] != "ok")
    errores_ctx = Counter(f["causa"] for f in filas if f["estado"] != "ok")

    palabras = sorted(p for c in ok_citados for p in c["metricas"]["palabras"])
    total_chunks = len(palabras)
    n = lambda k: sum(c["metricas"][k] for c in ok_citados)  # noqa: E731
    viol = [(c["cited_id"], v) for c in ok_citados for v in c["violaciones"]]
    perfiles = Counter(p for c in ok_citados for p in c["perfiles"])

    ids = defaultdict(set)
    for c in ok_citados:
        for ch in c["chunks"]:
            ids[ch["chunk_id"]].add(c["cited_id"])
    pares = [(c["cited_id"], ch["chunk_id"]) for c in ok_citados for ch in c["chunks"]]

    return {
        "alcance": "SOBRE LA CACHE LOCAL: solo citados presentes (o marcados 404) en cache_ocl; no es cobertura de ACL-200 completo.",
        "cobertura_por_split": por_split,
        "citados_unicos_total": len(unicos_total),
        "citados_estado": dict(sorted(estados.items())),
        "citados_resueltos_en_cache": resueltos,
        "citados_ok": len(ok_citados),
        "cobertura_citados_sobre_cache_pct": _pct(len(ok_citados), resueltos),
        "cobertura_citados_sobre_acl200_pct": _pct(len(ok_citados), len(unicos_total)),
        "errores_por_causa_citados": dict(sorted(errores.items())),
        "errores_por_causa_contextos": dict(sorted(errores_ctx.items())),
        "chunks": {
            "total": total_chunks,
            "palabras_min": palabras[0] if palabras else None,
            "palabras_mediana": median(palabras) if palabras else None,
            "palabras_max": palabras[-1] if palabras else None,
            "pct_2_parrafos": _pct(n("chunks_2_parrafos"), total_chunks),
            "chunks_sin_seccion": n("chunks_sin_seccion"),
            "pct_sin_seccion": _pct(n("chunks_sin_seccion"), total_chunks),
            "huecos_indice_total": n("huecos_indice"),
            "articulos_con_huecos": sum(c["metricas"]["huecos_indice"] > 0 for c in ok_citados),
            "perfil_seccion_heuristico": dict(sorted(perfiles.items())),
        },
        "violaciones_total": len(viol),
        "violaciones_ejemplos": [f"{a}: {v}" for a, v in viol[:20]],
        "ids": {
            "chunk_id_distintos": len(ids),
            "chunk_id_en_varios_articulos": sum(len(v) > 1 for v in ids.values()),
            "pares_citado_chunk": len(pares),
            "pares_citado_chunk_unicos": len(set(pares)),
        },
        "reproducibilidad": {
            "articulos_verificados": len(ok_citados),
            "huellas_distintas": sum(not c["reproducible"] for c in ok_citados),
        },
    }


def seleccionar_muestras(
    candidatos: list[dict], excluidos: set[str], n: int = 20, semilla: int = 101
) -> list[dict]:
    """Solo train, sin IDs excluidos, un caso por articulo citado, determinista."""
    elegibles = sorted(
        (c for c in candidatos if c["split"] == "train" and c["context_id"] not in excluidos),
        key=lambda c: (c["cited_id"], c["context_id"]),
    )
    vistos, unicos = set(), []
    for c in elegibles:
        if c["cited_id"] not in vistos:
            vistos.add(c["cited_id"])
            unicos.append(c)
    rng = random.Random(semilla)
    return sorted(rng.sample(unicos, min(n, len(unicos))), key=lambda c: c["context_id"])
