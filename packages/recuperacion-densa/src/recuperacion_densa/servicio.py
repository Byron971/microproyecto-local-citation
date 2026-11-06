"""Orquestacion: constructor de casos multicontexto y evaluacion SciBERT vs BM25."""
from __future__ import annotations

import hashlib
import json
import random
from dataclasses import dataclass, field
from pathlib import Path

from . import dominio
from .cache_embeddings import clave_embedding
from .puertos import (CacheEmbeddings, Codificador, Fragmentador, IndiceSplits, Integrador,
                      PerfilSeccion, PuntuarGold, RecuperadorLexico, Reloj)

ERRORES_ESPERADOS = (KeyError, TypeError, ValueError, OSError)
TIPO = "muestra_desarrollo_train_no_gold"
VARIANTE = "multicontexto_por_citado"
RECONSTRUCCION = "contexto_acl200_original_sin_adjudicacion"


# ------------------------------------------------------------------ casos
def construir_casos(
    indice: IndiceSplits, papers: dict, cache: Path, integrar: Integrador,
    fragmentar: Fragmentador, excluidos: set[str] | frozenset[str], limite: int | None = None,
) -> tuple[list[dict], dict]:
    """Todos los contextos train utilizables, con esquema S2.2 (un caso por contexto).

    integrar + fragmentar se ejecutan UNA vez por cited_id (memo)."""
    if limite is not None and limite < 1:
        raise ValueError("limite debe ser positivo")
    memo: dict[str, dict | None] = {}
    casos: list[dict] = []
    motivos: dict[str, int] = {}

    def omitir(m: str) -> None:
        motivos[m] = motivos.get(m, 0) + 1

    for cid in sorted(indice.by_context):
        if limite is not None and len(casos) >= limite:
            break
        if indice.by_context[cid] != "train":
            continue
        if cid in excluidos:
            omitir("excluido")
            continue
        cited = indice.contexts[cid].get("refid")
        ruta = Path(cache) / f"{cited}.json"
        if not ruta.is_file():
            omitir("sin_cache_citado")
            continue
        try:
            registro = integrar(cid, indice.contexts, papers, Path(cache))
            if cited not in memo:
                memo[cited] = {
                    "chunks": fragmentar(registro["paragraphs"]),
                    "sha": hashlib.sha256(ruta.read_bytes()).hexdigest(),
                }
        except ERRORES_ESPERADOS as exc:
            memo.setdefault(cited, None)
            omitir(type(exc).__name__)
            continue
        info = memo[cited]
        if info is None:
            omitir("citado_fallido")
            continue
        if (registro["cited_id"] != registro["ocl_paper_id"]
                or registro["citation_context"].count("TARGETCIT") != 1):
            raise ValueError("Invariante de cita/articulo rota.")
        casos.append({
            "context_id": cid, "split": "train", "citing_id": registro["citing_id"],
            "cited_id": cited, "cited_title": registro["cited_title"],
            "citation_context": registro["citation_context"],
            "sha256_ocl_citado": info["sha"], "chunks": info["chunks"],
            "reconstruccion": RECONSTRUCCION,
        })
    meta = {
        "tipo": TIPO, "variante": VARIANTE, "total": len(casos),
        "articulos": len({c["cited_id"] for c in casos}), "limite": limite,
        "exclusiones_suministradas": len(excluidos),
        "motivos_no_seleccion": dict(sorted(motivos.items())),
        "nota": "No contiene etiquetas humanas ni relevancia Top3; no reportar metricas cientificas.",
    }
    return casos, meta


def exportar_casos(casos: list[dict], meta: dict) -> dict:
    """Documento S2.2 aceptado por top3_humano.leer_casos/preparar_hojas."""
    return {"version": 1, "resumen": meta, "casos": casos}


# ------------------------------------------------------------------ evaluacion
@dataclass
class Evaluacion:
    resumen: dict                      # determinista, sin tiempos
    denso: dict[str, list[dict]]       # context_id -> top3 enriquecido
    bm25: dict[str, list[dict]]
    comparacion: list[dict]            # una fila por contexto
    latencias: dict                    # NO determinista: va aparte del resumen
    ejemplos: list[dict] = field(default_factory=list)
    diversidad: list[dict] = field(default_factory=list)


def _embeddings_articulo(chunks, codificador, cache, params) -> tuple[list, int]:
    claves = [clave_embedding(codificador.model_id, codificador.revision, *params, c["texto"])
              for c in chunks]
    vectores = [cache.get(k) if cache else None for k in claves]
    faltan = [i for i, v in enumerate(vectores) if v is None]
    if faltan:
        nuevos = codificador.encode([chunks[i]["texto"] for i in faltan])
        if len(nuevos) != len(faltan):
            raise ValueError("El codificador devolvio un numero distinto de embeddings.")
        for i, v in zip(faltan, nuevos):
            vectores[i] = tuple(v)
            if cache:
                cache.put(claves[i], vectores[i])
    return vectores, len(chunks) - len(faltan)


def _bm25_limpio(res: list[dict]) -> list[dict]:
    return [{"chunk_id": r["chunk_id"], "puntaje_bm25": r["puntaje_bm25"]} for r in res]


def seleccionar_ejemplos(filas: list[dict], n: int, semilla: int) -> list[str]:
    """Estratificado por interseccion (0..3), round-robin, semilla fija."""
    rng = random.Random(semilla)
    estratos: dict[int, list[str]] = {}
    for f in sorted(filas, key=lambda f: f["context_id"]):
        estratos.setdefault(f["interseccion"], []).append(f["context_id"])
    for k in estratos:
        rng.shuffle(estratos[k])
    elegidos: list[str] = []
    while len(elegidos) < n and any(estratos.values()):
        for k in sorted(estratos):
            if estratos[k] and len(elegidos) < n:
                elegidos.append(estratos[k].pop())
    return elegidos


def evaluar(
    casos: list[dict], codificador: Codificador, lexico: RecuperadorLexico,
    cache: CacheEmbeddings | None, reloj: Reloj, perfil: PerfilSeccion,
    *, max_length: int = 512, pooling: str = "mean", n_ejemplos: int = 12, semilla: int = 102,
    excluidos: set[str] | frozenset[str] = frozenset(),
    gold: dict | None = None, puntuar: PuntuarGold | None = None,
) -> Evaluacion:
    validacion = dominio.validar_casos(casos, excluidos)
    casos = sorted(casos, key=lambda c: c["context_id"])

    t0 = reloj()
    codificador.encode(["warm-up"])
    warmup = reloj() - t0

    params = (max_length, pooling)
    articulos: dict[str, dict] = {}
    lat_art: list[float] = []
    ids_art: list[str] = []
    for c in casos:
        if c["cited_id"] in articulos:
            continue
        t0 = reloj()
        vecs, aciertos = _embeddings_articulo(c["chunks"], codificador, cache, params)
        lat_art.append(reloj() - t0)
        ids_art.append(c["cited_id"])
        articulos[c["cited_id"]] = {"vecs": vecs, "aciertos": aciertos}

    denso, bm25, filas, lat_denso, lat_bm25 = {}, {}, [], [], []
    for c in casos:
        ctx = c["context_id"]
        consulta = dominio.normalizar_contexto(c["citation_context"])
        if not consulta:
            raise ValueError(f"Consulta vacia tras retirar marcadores en {ctx}")
        t0 = reloj()
        q = codificador.encode([consulta])[0]
        top = dominio.ordenar_top3(q, c["chunks"], articulos[c["cited_id"]]["vecs"])
        lat_denso.append(reloj() - t0)
        t0 = reloj()
        lex = lexico(c["citation_context"], c["chunks"])
        lat_bm25.append(reloj() - t0)
        denso[ctx] = dominio.enriquecer(c, top)
        bm25[ctx] = dominio.enriquecer(c, _bm25_limpio(lex))

    violaciones = (dominio.verificar_integridad(casos, denso, "scibert")
                   + dominio.verificar_integridad(casos, bm25, "bm25"))
    if violaciones:
        raise ValueError("Integridad violada: " + "; ".join(violaciones[:5])
                         + (f" (+{len(violaciones) - 5})" if len(violaciones) > 5 else ""))

    for c in casos:
        ctx = c["context_id"]
        cmp_ = dominio.comparar([r["chunk_id"] for r in denso[ctx]],
                                [r["chunk_id"] for r in bm25[ctx]])
        filas.append({"context_id": ctx, "cited_id": c["cited_id"],
                      "n_chunks": len(c["chunks"]), **cmp_})

    unicos = {c["cited_id"]: c for c in casos}
    corpus = [{**ch, "cited_id": a} for a, c in sorted(unicos.items()) for ch in c["chunks"]]
    cited = {c["context_id"]: c["cited_id"] for c in casos}
    n_chunks = {a: len(c["chunks"]) for a, c in unicos.items()}
    div = dominio.diversidad_por_articulo(
        {k: [r["chunk_id"] for r in v] for k, v in denso.items()}, cited, n_chunks)
    multi = [d for d in div if d["contextos"] >= 2]
    resumen = {
        "estado": "comparacion_tecnica_train_sin_gold",
        "modelo": {"model_id": codificador.model_id, "revision": codificador.revision,
                   "max_length": max_length, "pooling": pooling},
        "validacion": validacion,
        "integridad": {"violaciones": 0, "metodos": ["scibert", "bm25"]},
        "comparacion": dominio.agregar_comparacion(filas),
        "secciones": dominio.distribucion_secciones(
            corpus, list(denso.values()), list(bm25.values()), perfil),
        "similitud": dominio.estadisticas_similitud(denso),
        "diversidad": {
            "articulos_con_2_o_mas_contextos": len(multi),
            "cobertura_media": (sum(d["cobertura"] for d in multi) / len(multi)) if multi else None,
            "top1_mas_frecuente_medio": (sum(d["chunk_top1_mas_frecuente"] for d in multi)
                                         / len(multi)) if multi else None,
        },
        "huella_denso": dominio.huella_resultados(denso),
        "huella_bm25": dominio.huella_resultados(bm25),
        "metricas_relevancia": "no calculadas: sin gold validado",
    }
    if gold is not None:
        if puntuar is None:
            raise ValueError("Se aporto gold sin funcion de puntuacion.")
        rk = lambda r: {k: [x["chunk_id"] for x in v] for k, v in r.items()}  # noqa: E731
        resumen["gold"] = {"denso": dominio.agregar_gold(casos, gold, rk(denso), puntuar),
                           "bm25": dominio.agregar_gold(casos, gold, rk(bm25), puntuar)}
        resumen["metricas_relevancia"] = dominio.ETIQUETA_GOLD

    por_ctx = {c["context_id"]: c for c in casos}
    ejemplos = []
    for ctx in seleccionar_ejemplos(filas, n_ejemplos, semilla):
        c = por_ctx[ctx]
        txt = {ch["chunk_id"]: ch["texto"] for ch in c["chunks"]}
        ejemplos.append({
            "context_id": ctx, "cited_id": c["cited_id"],
            "contexto": dominio.extracto(dominio.normalizar_contexto(c["citation_context"])),
            "interseccion": next(f["interseccion"] for f in filas if f["context_id"] == ctx),
            **{m: [{**{k: v for k, v in r.items() if k != "cited_id"},
                    "extracto": dominio.extracto(txt[r["chunk_id"]])} for r in tops[ctx]]
               for m, tops in (("denso", denso), ("bm25", bm25))},
        })
    latencias = {
        "warmup_s": warmup,
        "embedding_articulo": {**dominio.resumir_latencias(lat_art),
                               "chunks_en_cache": sum(a["aciertos"] for a in articulos.values())},
        "consulta_densa": dominio.resumir_latencias(lat_denso),
        "bm25": dominio.resumir_latencias(lat_bm25),
        "codificador": codificador.info(),
        "muestras": {"embedding_articulo": list(zip(ids_art, lat_art)),
                     "consulta_densa": list(zip([c["context_id"] for c in casos], lat_denso)),
                     "bm25": list(zip([c["context_id"] for c in casos], lat_bm25))},
    }
    return Evaluacion(resumen, denso, bm25, filas, latencias, ejemplos, div)


def resumen_json(ev: Evaluacion) -> str:
    return json.dumps(ev.resumen, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
