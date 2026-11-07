"""Casos de uso: orquesta dominio y puertos (sin torch, sin red)."""
import hashlib
from pathlib import Path

from recuperacion_densa import dominio as densa
from recuperacion_densa.cache_embeddings import clave_embedding

from . import dominio

ERRORES_ESPERADOS = (KeyError, TypeError, ValueError, OSError)

FUENTES_ETIQUETAS = ("haiku", "jurado")
ESTADO = "provisional_etiquetas_haiku_no_gold_humano"
ANIO_EVAL = "2015"


def _caso(cid: str, contextos: dict, fila: dict | None = None) -> dict:
    ctx = contextos.get(cid)
    if not isinstance(ctx, dict):
        raise ValueError(f"Contexto ausente del indice: {cid}")
    caso = {"context_id": cid, "citing_id": ctx["citing_id"], "cited_id": ctx["refid"],
            "citation_context": ctx["masked_text"]}
    if fila is not None:
        caso.update({"titulo": fila["titulo"], "abstract": fila["abstract"],
                     "etiqueta": fila["etiqueta"]})
    return caso


def _evaluables(filas: list[dict], conjunto: str) -> tuple[list[dict], list[dict]]:
    """(filas evaluables con `indice`, abstenciones [{conjunto, context_id, motivo}])."""
    evaluables, abstenciones = [], []
    for fila in filas:
        indice = dominio.normalizar_etiqueta(fila["etiqueta"])
        if indice is None:
            abstenciones.append({"conjunto": conjunto, "context_id": fila["context_id"],
                                 "motivo": dominio.motivo_abstencion(fila["etiqueta"])})
        else:
            evaluables.append({**fila, "indice": indice})
    return evaluables, abstenciones


def _unicos(filas: list[dict], nombre: str) -> None:
    ids = [f["context_id"] for f in filas]
    if len(set(ids)) != len(ids):
        raise ValueError(f"context_id duplicado en {nombre}.")


def cargar_conjuntos(fuentes, fuente_etiquetas: str = "haiku", limite: int | None = None) -> dict:
    """Construye train/val/eval_2015 (etiquetados) y Gold v2 (ciego) y verifica fugas.

    - train/val: Haiku Evaluable con el split agrupado por citante (qlora_split_v2).
    - eval_2015 (PROVISIONAL): Test Gold 2700 de 2015, Evaluable, sin exclusiones,
      con pertenencia al split `test` comprobada.
    - gold_v2: IDs ciegos (sin etiquetas)."""
    if fuente_etiquetas not in FUENTES_ETIQUETAS:
        raise ValueError(f"Fuente de etiquetas desconocida: {fuente_etiquetas!r}")
    if fuente_etiquetas == "jurado":
        raise NotImplementedError("Etiquetas del Jurado no disponibles (DVC sin descargar).")
    if limite is not None and limite < 1:
        raise ValueError("--limite debe ser positivo.")
    por_split, contextos = fuentes.indice()
    excluidos = set(fuentes.exclusiones())

    # ---- train / val
    haiku = fuentes.filas_haiku()
    _unicos(haiku, "Haiku")
    pertenece = fuentes.split_entrenamiento()
    ids_split = {n: set(pertenece[n]) for n in ("train", "val")}
    if ids_split["train"] & ids_split["val"]:
        raise ValueError("El split de entrenamiento comparte contextos entre train y val.")
    por_id = {f["context_id"]: f for f in haiku}
    if set(por_id) != ids_split["train"] | ids_split["val"]:
        raise ValueError("Las filas Haiku no coinciden con el split train/val.")
    abstenciones, conjuntos, etiquetados = [], {}, {}
    for nombre in ("train", "val"):
        filas = [por_id[c] for c in pertenece[nombre]]
        for f in filas:
            if por_split.get(f["context_id"]) != "train":
                raise ValueError(f"{f['context_id']} no pertenece al split train de ACL-200.")
        evaluables, abst = _evaluables(filas, nombre)
        abstenciones += abst
        etiquetados[nombre] = evaluables
    # ---- eval provisional
    test_gold = fuentes.filas_test_gold()
    _unicos(test_gold, "Test Gold")
    excluidos_prep = []
    candidatos = []
    for f in test_gold:
        if f["anio_citante"] != ANIO_EVAL:
            continue
        if por_split.get(f["context_id"]) != "test":
            raise ValueError(f"{f['context_id']} (2015) no pertenece al split test de ACL-200.")
        if f["context_id"] in excluidos:
            excluidos_prep.append({"conjunto": "eval_2015", "context_id": f["context_id"],
                                   "motivo": "excluido_test_gold"})
            continue
        candidatos.append(f)
    evaluables, abst = _evaluables(candidatos, "eval_2015")
    abstenciones += abst
    etiquetados["eval_2015"] = evaluables
    # ---- gold v2 ciego
    ids_gold = fuentes.ids_gold_v2()
    if len(set(ids_gold)) != len(ids_gold) or not ids_gold:
        raise ValueError("IDs del Gold v2 vacios o duplicados.")
    for cid in ids_gold:
        if por_split.get(cid) != "test":
            raise ValueError(f"{cid} (Gold v2) no pertenece al split test de ACL-200.")

    for nombre, filas in etiquetados.items():
        filas.sort(key=lambda f: f["context_id"])
        conjuntos[nombre] = [{**_caso(f["context_id"], contextos, f), "indice": f["indice"]}
                             for f in (filas[:limite] if limite else filas)]
    gold = sorted(ids_gold)
    conjuntos["gold_v2"] = [_caso(c, contextos) for c in (gold[:limite] if limite else gold)]

    # ---- fugas (el Gold v2 solapa con eval_2015 por construccion: ambos son test 2015)
    principal = dominio.verificar_fugas(
        {n: conjuntos[n] for n in ("train", "val", "eval_2015")}, excluidos)
    con_gold = dominio.verificar_fugas(
        {n: conjuntos[n] for n in ("train", "val", "gold_v2")}, excluidos)
    fugas = {"principal": principal, "gold_v2": con_gold,
             "total_fugas": principal["total_fugas"] + con_gold["total_fugas"]}
    citados = sorted({c["cited_id"] for casos in conjuntos.values() for c in casos})
    return {"conjuntos": conjuntos, "abstenciones": abstenciones, "excluidos": excluidos_prep,
            "fugas": fugas, "citados_requeridos": citados, "fuente_etiquetas": fuente_etiquetas,
            "estado": ESTADO}


# ---------------------------------------------------------------- chunks y Top-3
def _motivo(exc: Exception) -> str:
    if isinstance(exc, ValueError) and "demasiado largo" in str(exc):
        return "parrafo_largo"
    return type(exc).__name__


def construir_casos_split(
    conjuntos: dict[str, list[dict]], contextos: dict, papers: dict, cache: Path,
    integrar, fragmentar,
) -> tuple[dict[str, list[dict]], list[dict]]:
    """Variante de `construir_casos` de A1 sin la restriccion de split.

    Por cada caso agrega los chunks del citado (regla de A1, sin cambios). Devuelve
    (casos utilizables por conjunto, excluidos [{conjunto, context_id, motivo}]).
    integrar + fragmentar se ejecutan una vez por cited_id (memo)."""
    memo: dict[str, dict | tuple] = {}
    salida: dict[str, list[dict]] = {}
    excluidos: list[dict] = []
    for nombre, casos in conjuntos.items():
        salida[nombre] = []
        for caso in casos:
            cid, cited = caso["context_id"], caso["cited_id"]

            def omitir(motivo: str, cid=cid, nombre=nombre) -> None:
                excluidos.append({"conjunto": nombre, "context_id": cid, "motivo": motivo})

            ruta = Path(cache) / f"{cited}.json"
            if not ruta.is_file():
                omitir("ocl_404" if (Path(cache) / f"{cited}.404").exists() else "sin_descargar")
                continue
            try:
                registro = integrar(cid, contextos, papers, Path(cache))
            except ERRORES_ESPERADOS as exc:
                omitir(_motivo(exc))
                continue
            if registro.get("citing_id") == cited:
                omitir("autocita")
                continue
            if cited not in memo:
                try:
                    chunks, descartados = densa.deduplicar_chunks(fragmentar(registro["paragraphs"]))
                    memo[cited] = {"chunks": chunks, "descartados": descartados,
                                   "sha": hashlib.sha256(ruta.read_bytes()).hexdigest()}
                except ERRORES_ESPERADOS as exc:
                    memo[cited] = (_motivo(exc),)
            info = memo[cited]
            if isinstance(info, tuple):
                omitir(info[0])
                continue
            if (registro["cited_id"] != registro["ocl_paper_id"]
                    or registro["citation_context"].count(dominio.MARCA_TARGET) != 1):
                raise ValueError("Invariante de cita/articulo rota.")
            salida[nombre].append({
                **caso, "cited_title": registro["cited_title"],
                "sha256_ocl_citado": info["sha"], "chunks": info["chunks"],
            })
    return salida, excluidos


def _embeddings_articulo(chunks, codificador, cache, params) -> tuple[list, int]:
    device = getattr(codificador, "device", "cpu")
    entorno = getattr(codificador, "huella_entorno", "")
    claves = [clave_embedding(codificador.model_id, codificador.revision, *params, c["texto"],
                              device, entorno) for c in chunks]
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


def recuperar_top3(
    casos: list[dict], codificador, cache, *, max_length: int = 512, pooling: str = "mean",
) -> dict:
    """Top-3 denso por contexto con la regla de A1 (coseno sobre embeddings de chunk, mean
    pooling, desempate por chunk_id). Un recuperador unico para ambos encoders.

    Devuelve {top3: {context_id: [{posicion, chunk_id, similitud_coseno, cited_id, seccion,
    paragraph_indices, palabras}]}, huella, articulos, chunks_en_cache}."""
    dominio.validar_casos_chunks(casos)
    casos = sorted(casos, key=lambda c: c["context_id"])
    params = (max_length, pooling)
    articulos: dict[str, list] = {}
    aciertos = 0
    for c in casos:
        if c["cited_id"] not in articulos:
            vecs, n = _embeddings_articulo(c["chunks"], codificador, cache, params)
            articulos[c["cited_id"]] = vecs
            aciertos += n
    top3 = {}
    for c in casos:
        consulta = densa.normalizar_contexto(c["citation_context"])
        if not consulta:
            raise ValueError(f"Consulta vacia tras retirar marcadores en {c['context_id']}")
        q = codificador.encode([consulta])[0]
        top3[c["context_id"]] = densa.enriquecer(
            c, densa.ordenar_top3(q, c["chunks"], articulos[c["cited_id"]]))
    violaciones = densa.verificar_integridad(casos, top3, "scibert")
    if violaciones:
        raise ValueError("Integridad violada: " + "; ".join(violaciones[:5]))
    return {"top3": top3, "huella": densa.huella_resultados(top3),
            "articulos": len(articulos), "chunks_en_cache": aciertos}


def regresion_top3(top3: dict[str, list[dict]], filas_a1: list[dict], tolerancia: float = 1e-4) -> dict:
    """Los chunk_id (y su orden) deben coincidir con el top3.csv de A1 en los contextos
    compartidos. Solo se consideran las filas `scibert` de A1."""
    a1: dict[str, list[tuple[int, str, float]]] = {}
    for f in filas_a1:
        if f.get("metodo", "scibert") == "scibert":
            a1.setdefault(f["context_id"], []).append(
                (int(f["posicion"]), f["chunk_id"], float(f["puntaje"])))
    comunes = sorted(set(a1) & set(top3))
    discrepancias, max_dif = [], 0.0
    for ctx in comunes:
        ref = sorted(a1[ctx])
        propio = [(r["posicion"], r["chunk_id"], r["similitud_coseno"]) for r in top3[ctx]]
        if [x[:2] for x in ref] != [x[:2] for x in propio]:
            discrepancias.append(ctx)
            continue
        max_dif = max(max_dif, *(abs(a[2] - b[2]) for a, b in zip(ref, propio)))
    if max_dif > tolerancia:
        discrepancias.append(f"similitud_max_dif={max_dif}")
    return {"contextos_a1": len(a1), "contextos_comparados": len(comunes),
            "coinciden": len(comunes) - len([d for d in discrepancias if not d.startswith("similitud")]),
            "max_dif_similitud": max_dif, "discrepancias": discrepancias}
