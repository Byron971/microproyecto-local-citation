"""Dominio PURO de la evaluacion densa: solo stdlib, sin I/O ni imports del proyecto."""
from __future__ import annotations

import hashlib
import json
import math
from collections import Counter, defaultdict
from typing import Callable

TOP_K = 3
SIN_SECCION = "(sin seccion)"
ETIQUETA_GOLD = "calibracion_train_no_gold"
_CLAVES_RELEVANCIA = ("evidencia_top3", "fragmentos_relevantes_adjudicados", "relevantes", "gold")


# --------------------------------------------------------------- texto / vectores
def normalizar_contexto(contexto: str) -> str:
    """Los marcadores ACL-200 no son terminos cientificos (misma regla que BM25)."""
    return " ".join(contexto.replace("TARGETCIT", " ").replace("OTHERCIT", " ").split())


def ventanas(n: int, cap: int) -> list[tuple[int, int]]:
    """Intervalos contiguos [ini, fin) de a lo sumo `cap` tokens; no se trunca nada."""
    if cap < 1:
        raise ValueError("cap debe ser >= 1.")
    if n < 0:
        raise ValueError("n no puede ser negativo.")
    return [(i, min(i + cap, n)) for i in range(0, n, cap)]


def construir_lotes(ids_por_texto: list[list[int]], capacidad: int, cls: int, sep: int):
    """(secuencias `[CLS]+w+[SEP]`, indice_texto, pesos) con las ventanas de cada texto."""
    secuencias, indices, pesos = [], [], []
    for i, ids in enumerate(ids_por_texto):
        if not ids:
            raise ValueError("Tokenizer produjo secuencia vacia.")
        for ini, fin in ventanas(len(ids), capacidad):
            secuencias.append([cls, *ids[ini:fin], sep])
            indices.append(i)
            pesos.append(fin - ini)
    return secuencias, indices, pesos


def normalizar_vector(vector) -> tuple[float, ...]:
    if not len(vector) or not all(math.isfinite(float(v)) for v in vector):
        raise ValueError("Embedding vacio o no finito.")
    norma = math.sqrt(math.fsum(float(v) ** 2 for v in vector))
    if norma <= 0:
        raise ValueError("Embedding nulo.")
    return tuple(float(v) / norma for v in vector)


def media_ponderada(vectores: list, pesos: list[int]) -> tuple[float, ...]:
    if not vectores or len(vectores) != len(pesos) or any(p <= 0 for p in pesos):
        raise ValueError("Vectores y pesos inconsistentes.")
    dim = len(vectores[0])
    if any(len(v) != dim for v in vectores):
        raise ValueError("Dimensiones incompatibles.")
    total = sum(pesos)
    return tuple(math.fsum(float(v[i]) * p for v, p in zip(vectores, pesos)) / total
                 for i in range(dim))


def ordenar_top3(query, chunks: list[dict], vectores: list) -> list[dict]:
    """Coseno redondeado a 6 decimales; desempate por chunk_id."""
    if len(chunks) != len(vectores):
        raise ValueError("Numero de chunks y embeddings inconsistente.")
    q = normalizar_vector(query)
    res = []
    for c, vec in zip(chunks, vectores):
        v = normalizar_vector(vec)
        if len(v) != len(q):
            raise ValueError("Dimensiones de embeddings incompatibles.")
        res.append({"chunk_id": c["chunk_id"],
                    "similitud_coseno": round(math.fsum(x * y for x, y in zip(q, v)), 6)})
    res.sort(key=lambda r: (-r["similitud_coseno"], r["chunk_id"]))
    return [{"posicion": i, **r} for i, r in enumerate(res[:TOP_K], 1)]


# --------------------------------------------------------------- huellas
def _sha(obj) -> str:
    return hashlib.sha256(
        json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()


def huella_chunks(chunks: list[dict]) -> str:
    return _sha([(c["chunk_id"], c["texto"], c.get("seccion"), c.get("paragraph_indices"))
                 for c in chunks])


def huella_resultados(resultados: dict[str, list[dict]]) -> str:
    return _sha([(ctx, [(r.get("cited_id"), r["chunk_id"], r.get("similitud_coseno"))
                        for r in resultados[ctx]]) for ctx in sorted(resultados)])


def extracto(texto: str, limite: int = 240) -> str:
    t = " ".join(texto.split())
    return t if len(t) <= limite else t[: limite - 1].rstrip() + "…"


# --------------------------------------------------------------- validacion de casos
def deduplicar_chunks(chunks: list[dict]) -> tuple[list[dict], list[str]]:
    """Descarta chunks con texto repetido (normalizado: strip + espacios colapsados).

    Conserva el de menor chunk_id de cada grupo y mantiene el orden original.
    Devuelve (chunks_unicos, chunk_ids_descartados)."""
    mejor: dict[str, str] = {}
    for c in chunks:
        k = " ".join(c["texto"].split())
        if k not in mejor or c["chunk_id"] < mejor[k]:
            mejor[k] = c["chunk_id"]
    unicos = [c for c in chunks if mejor[" ".join(c["texto"].split())] == c["chunk_id"]]
    return unicos, sorted(c["chunk_id"] for c in chunks if c not in unicos)


def validar_casos(casos: list[dict], excluidos: set[str] | frozenset[str] = frozenset()) -> dict:
    """Bloquea fugas: solo train, contexto no excluido, un TARGETCIT, corpus consistente."""
    if not isinstance(casos, list) or not casos:
        raise ValueError("Se necesita una lista no vacia de casos train.")
    ids, articulos = set(), {}
    for caso in casos:
        if not isinstance(caso, dict) or caso.get("split") != "train":
            raise ValueError("Entrada no es exclusivamente train: operacion bloqueada.")
        cid, pid = caso.get("context_id"), caso.get("cited_id")
        if not isinstance(cid, str) or not cid or cid in ids:
            raise ValueError("context_id vacio o duplicado.")
        ids.add(cid)
        if cid in excluidos:
            raise ValueError(f"Contexto excluido: {cid}")
        if not isinstance(pid, str) or not pid:
            raise ValueError(f"cited_id invalido en {cid}")
        if caso.get("citing_id") == pid:
            raise ValueError(f"Autocita (citing_id == cited_id) en {cid}")
        ctx = caso.get("citation_context")
        if not isinstance(ctx, str) or ctx.count("TARGETCIT") != 1:
            raise ValueError(f"Contexto sin TARGETCIT unico en {cid}")
        if any(caso.get(k) is not None for k in _CLAVES_RELEVANCIA):
            raise ValueError("Caso con etiquetas de relevancia: solo exploracion train.")
        chunks = caso.get("chunks")
        if not isinstance(chunks, list) or not chunks:
            raise ValueError(f"Articulo sin chunks en {cid}")
        vistos, textos = set(), set()
        for c in chunks:
            if not isinstance(c, dict):
                raise ValueError(f"Chunk mal formado en {cid}")
            chid, texto = c.get("chunk_id"), c.get("texto")
            if not isinstance(chid, str) or not chid or chid in vistos:
                raise ValueError(f"chunk_id vacio/duplicado en {cid}")
            vistos.add(chid)
            if not isinstance(texto, str) or not texto.strip():
                raise ValueError(f"Texto de chunk vacio en {cid}")
            norm = " ".join(texto.split())
            if norm in textos:
                raise ValueError(f"Texto de chunk duplicado en el articulo de {cid}")
            textos.add(norm)
        h = huella_chunks(chunks)
        if articulos.setdefault(pid, (h, len(chunks)))[0] != h:
            raise ValueError(f"Chunks inconsistentes entre casos del mismo articulo: {pid}")
    return {"contextos": len(casos), "articulos": len(articulos),
            "chunks_unicos": sum(n for _, n in articulos.values())}


# --------------------------------------------------------------- enriquecimiento e integridad
def enriquecer(caso: dict, resultados: list[dict]) -> list[dict]:
    """Agrega cited_id, seccion, paragraph_indices y palabras (sin el texto)."""
    por_id = {c["chunk_id"]: c for c in caso["chunks"]}
    salida = []
    for r in resultados:
        c = por_id.get(r["chunk_id"])
        extra = ({"seccion": c.get("seccion"), "paragraph_indices": c.get("paragraph_indices"),
                  "palabras": c.get("palabras")} if c else {})
        salida.append({**r, "cited_id": caso["cited_id"], **extra})
    return salida


def verificar_integridad(casos: list[dict], resultados: dict[str, list[dict]],
                         metodo: str) -> list[str]:
    """Violaciones (lista vacia = integro). Aplica a SciBERT y a BM25."""
    indice: dict[tuple[str, str], dict] = {}
    for caso in casos:
        for c in caso["chunks"]:
            indice[(caso["cited_id"], c["chunk_id"])] = c
    por_ctx = {c["context_id"]: c for c in casos}
    v = []
    for ctx in sorted(set(resultados) - set(por_ctx)):
        v.append(f"{metodo}:{ctx}: contexto desconocido")
    for ctx, caso in por_ctx.items():
        res = resultados.get(ctx)
        if res is None:
            v.append(f"{metodo}:{ctx}: sin resultados")
            continue
        if len(res) > TOP_K:
            v.append(f"{metodo}:{ctx}: {len(res)} resultados > {TOP_K}")
        pares = [(r.get("cited_id"), r["chunk_id"]) for r in res]
        if len(pares) != len(set(pares)):
            v.append(f"{metodo}:{ctx}: resultados duplicados")
        for r in res:
            par = (r.get("cited_id"), r["chunk_id"])
            if r.get("cited_id") != caso["cited_id"] or par not in indice:
                v.append(f"{metodo}:{ctx}: {par} ajeno al articulo citado")
                continue
            ch = indice[par]
            if r.get("seccion") != ch.get("seccion"):
                v.append(f"{metodo}:{ctx}: seccion de {par} no coincide con el corpus")
            if r.get("paragraph_indices") != ch.get("paragraph_indices"):
                v.append(f"{metodo}:{ctx}: paragraph_indices de {par} no coinciden")
    return v


# --------------------------------------------------------------- comparacion
def comparar(ids_denso: list[str], ids_bm25: list[str]) -> dict:
    d, b = set(ids_denso), set(ids_bm25)
    inter, union = len(d & b), len(d | b)
    return {"interseccion": inter, "solape_3": inter / TOP_K,
            "jaccard": inter / union if union else 0.0,
            "mismo_top1": bool(ids_denso and ids_bm25 and ids_denso[0] == ids_bm25[0]),
            "abstencion_bm25": not ids_bm25}


def solape_esperado_azar(n: int, k: int = TOP_K) -> float:
    """E[|A∩B|] para dos subconjuntos aleatorios de tamano k de n chunks: k²/n."""
    if n < 1:
        raise ValueError("n debe ser >= 1.")
    k = min(k, n)
    return k * k / n


def _media(xs: list[float]) -> float | None:
    return math.fsum(xs) / len(xs) if xs else None


def agregar_comparacion(filas: list[dict]) -> dict:
    """filas: context_id, cited_id, n_chunks + salida de `comparar`. Micro y macro."""
    if not filas:
        raise ValueError("Sin filas que agregar.")
    claves = ("interseccion", "jaccard", "mismo_top1", "abstencion_bm25")

    def agg(grupo: list[dict]) -> dict:
        out = {k: _media([float(f[k]) for f in grupo]) for k in claves}
        out["solape_3"] = _media([f["interseccion"] / TOP_K for f in grupo])
        out["solape_esperado_azar"] = _media([solape_esperado_azar(f["n_chunks"]) / TOP_K
                                              for f in grupo])
        out["solape_esperado_azar_chunks"] = _media([solape_esperado_azar(f["n_chunks"])
                                                     for f in grupo])
        return out

    por_art: dict[str, list[dict]] = defaultdict(list)
    for f in filas:
        por_art[f["cited_id"]].append(f)
    medias = [agg(g) for _, g in sorted(por_art.items())]
    macro = {k: _media([m[k] for m in medias]) for k in medias[0]}
    return {"micro": {"n": len(filas), **agg(filas)},
            "macro": {"n": len(por_art), **macro}}


def resumir_latencias(valores: list[float]) -> dict:
    """n, media, p50, p95 y maximo; percentiles por rango mas cercano."""
    if not valores:
        return {"n": 0, "media": None, "p50": None, "p95": None, "max": None}
    s = sorted(valores)

    def pct(p: float) -> float:
        return s[max(1, math.ceil(p / 100 * len(s))) - 1]

    return {"n": len(s), "media": math.fsum(s) / len(s), "p50": pct(50), "p95": pct(95),
            "max": s[-1]}


# --------------------------------------------------------------- distribuciones
def _prop(c: Counter) -> dict[str, float]:
    t = sum(c.values())
    return {k: c[k] / t for k in sorted(c)} if t else {}


def distribucion_secciones(chunks_corpus: list[dict], tops_denso: list[list[dict]],
                           tops_bm25: list[list[dict]],
                           perfil: Callable[[str | None], str] | None = None) -> dict:
    f = perfil or (lambda s: s or SIN_SECCION)

    def cont(items):
        return Counter(f(i.get("seccion")) for i in items)

    return {"corpus": _prop(cont(chunks_corpus)),
            "denso": _prop(cont(x for t in tops_denso for x in t)),
            "bm25": _prop(cont(x for t in tops_bm25 for x in t))}


def diversidad_por_articulo(tops: dict[str, list[str]], cited: dict[str, str],
                            n_chunks: dict[str, int]) -> list[dict]:
    """Hubness/anisotropia: cuantos chunks distintos recupera un articulo entre sus contextos
    y que fraccion de los contextos comparte el chunk mas frecuente."""
    por_art: dict[str, list[str]] = defaultdict(list)
    for ctx, ids in tops.items():
        por_art[cited[ctx]].append(ctx)
    filas = []
    for art in sorted(por_art):
        ctxs = por_art[art]
        cuenta = Counter(i for c in ctxs for i in tops[c])
        top1 = Counter(tops[c][0] for c in ctxs if tops[c])
        filas.append({"cited_id": art, "contextos": len(ctxs), "n_chunks": n_chunks[art],
                      "chunks_distintos_top3": len(cuenta),
                      "cobertura": len(cuenta) / n_chunks[art],
                      "chunk_top1_mas_frecuente": max(top1.values()) / len(ctxs) if top1 else 0.0})
    return filas


def estadisticas_similitud(tops: dict[str, list[dict]]) -> dict:
    top1 = [r[0]["similitud_coseno"] for r in tops.values() if r]
    brecha = [r[0]["similitud_coseno"] - r[1]["similitud_coseno"] for r in tops.values()
              if len(r) > 1]
    f = lambda xs: ({"media": _media(xs), "min": min(xs), "max": max(xs)} if xs else None)
    return {"top1": f(top1), "brecha_top1_top2": f(brecha)}


# --------------------------------------------------------------- gold (calibracion, fail-closed)
def consenso(a: dict, b: dict, adj: dict, esperado: set) -> tuple[dict, list]:
    """Mismas reglas que top3_humano.evaluar_calibracion. Devuelve (consenso, discrepancias)."""
    if set(a) != esperado or set(b) != esperado or set(adj) != esperado:
        raise ValueError("Anotacion incompleta o ajena al corpus.")
    if any(a[k] not in (0, 1) or b[k] not in (0, 1) for k in esperado):
        raise ValueError("Etiqueta binaria incompleta/incorrecta.")
    disc = [k for k in sorted(esperado) if a[k] != b[k]]
    if any(adj[k] is None for k in disc):
        raise ValueError(f"Faltan {sum(adj[k] is None for k in disc)} adjudicaciones.")
    if any(adj[k] is not None and a[k] == b[k] and adj[k] != a[k] for k in esperado):
        raise ValueError("La adjudicacion contradice un acuerdo entre anotadores.")
    return {k: a[k] if a[k] == b[k] else adj[k] for k in esperado}, disc


def agregar_gold(casos: list[dict], cons: dict, rankings: dict[str, list[str]],
                 puntuar: Callable[[list[str], set[str]], dict | None]) -> dict:
    """Puntua rankings contra el consenso. `puntuar` se inyecta (top3_humano.puntajes_top3)."""
    por_caso = []
    for caso in casos:
        cid = caso["context_id"]
        validos = {c["chunk_id"] for c in caso["chunks"]}
        ranking = rankings[cid]
        if any(x not in validos for x in ranking):
            raise ValueError("Ranking incluye fragmentos ajenos al articulo citado.")
        rel = {ch for (ctx, ch), lab in cons.items() if ctx == cid and lab == 1}
        m = puntuar(ranking, rel)
        por_caso.append({"context_id": cid, "cited_id": caso["cited_id"],
                         "n_relevantes": len(rel),
                         "estado": "sin_relevantes_anotados" if m is None else "evaluable",
                         "metricas": m})
    el = [c["metricas"] for c in por_caso if c["metricas"] is not None]
    med = lambda k: round(_media([m[k] for m in el]), 6) if el else None
    return {"estado": ETIQUETA_GOLD, "total_casos": len(por_caso), "casos_elegibles": len(el),
            "casos_sin_relevantes": len(por_caso) - len(el),
            "hit_3": med("hit_3"), "recall_3": med("recall_3"), "mrr_3": med("rr_3"),
            "casos": por_caso}
