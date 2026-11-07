import pytest

from clasificacion_funcion import dominio, servicio
from recuperacion_densa.cache_embeddings import CacheMemoria

from chunks_falsos import (CodificadorFalso, crear_integrar, fragmentar_falso, parrafos,
                           preparar_cache)
from fuentes_falsas import FuentesFalsas

CITADOS = ["A", "B", "C", "D", "E", "F", "G", "H"]


@pytest.fixture
def entorno(tmp_path):
    f = FuentesFalsas()
    r = servicio.cargar_conjuntos(f)
    papers = {c: {} for c in CITADOS}
    integrar = crear_integrar({c: parrafos(c) for c in CITADOS})
    return f, r["conjuntos"], papers, integrar, tmp_path / "cache"


def armar(entorno, **cache_kw):
    f, conjuntos, papers, integrar, cache = entorno
    preparar_cache(cache, CITADOS, **cache_kw)
    return servicio.construir_casos_split(conjuntos, f.ctx, papers, cache, integrar, fragmentar_falso)


def test_casos_sin_restriccion_de_split(entorno):
    casos, excluidos = armar(entorno)
    assert excluidos == []
    assert {n: [c["context_id"] for c in v] for n, v in casos.items()} == {
        "train": ["t1", "t2", "t4"], "val": [], "eval_2015": ["e1", "e3"],
        "gold_v2": ["e1", "e3", "e5"]}
    c = casos["eval_2015"][0]
    assert len(c["chunks"]) == 4 and c["cited_title"] == "titulo A" and len(c["sha256_ocl_citado"]) == 64
    assert c["etiqueta"] == "Basis"  # conserva los campos del caso original
    dominio.validar_casos_chunks(casos["train"])


def test_motivos_de_exclusion(entorno):
    f, conjuntos, papers, integrar, cache = entorno
    casos, excluidos = armar(entorno, ausentes=("B",), no_encontrados=("A",))
    motivos = {(e["conjunto"], e["context_id"]): e["motivo"] for e in excluidos}
    assert motivos[("train", "t2")] == "sin_descargar"          # B sin archivo
    assert motivos[("train", "t1")] == "ocl_404" and motivos[("eval_2015", "e1")] == "ocl_404"


def test_parrafo_largo_y_error_de_integracion(tmp_path):
    f = FuentesFalsas()
    conjuntos = servicio.cargar_conjuntos(f)["conjuntos"]
    cache = tmp_path / "c"
    preparar_cache(cache, CITADOS)
    integrar = crear_integrar({**{c: parrafos(c) for c in CITADOS}, "B": parrafos("B", largo=True)})
    casos, excluidos = servicio.construir_casos_split(
        conjuntos, f.ctx, {c: {} for c in CITADOS if c != "E"}, cache, integrar, fragmentar_falso)
    motivos = {(e["conjunto"], e["context_id"]): e["motivo"] for e in excluidos}
    assert motivos[("train", "t2")] == "parrafo_largo"
    assert motivos[("eval_2015", "e3")] == "ValueError"  # E no esta en papers
    assert ("train", "t1") not in motivos


def test_autocita_se_excluye(entorno):
    f, conjuntos, papers, integrar, cache = entorno
    preparar_cache(cache, CITADOS)
    f.ctx["t1"]["citing_id"] = "A"
    casos, excluidos = servicio.construir_casos_split(conjuntos, f.ctx, papers, cache, integrar,
                                                      fragmentar_falso)
    assert {"conjunto": "train", "context_id": "t1", "motivo": "autocita"} in excluidos


def test_fragmenta_una_vez_por_citado(entorno):
    f, conjuntos, papers, integrar, cache = entorno
    preparar_cache(cache, CITADOS)
    llamadas = []
    servicio.construir_casos_split(conjuntos, f.ctx, papers, cache, integrar,
                                   lambda p: llamadas.append(1) or fragmentar_falso(p))
    assert len(llamadas) == 4  # citados con casos: A, B, E, G (no uno por contexto)


# ---- Top-3
def test_top3_cumple_la_regla_de_a1(entorno):
    casos, _ = armar(entorno)
    cod, cache = CodificadorFalso(), CacheMemoria()
    res = servicio.recuperar_top3(casos["train"], cod, cache)
    assert sorted(res["top3"]) == ["t1", "t2", "t4"]
    for ctx, top in res["top3"].items():
        assert [r["posicion"] for r in top] == [1, 2, 3]
        sims = [r["similitud_coseno"] for r in top]
        assert sims == sorted(sims, reverse=True)
        assert all(r["cited_id"] in ("A", "B") and r["seccion"] and r["paragraph_indices"] for r in top)
    assert res["articulos"] == 2 and res["huella"]


def test_top3_determinista_y_usa_la_cache(entorno):
    casos, _ = armar(entorno)
    cache = CacheMemoria()
    a = servicio.recuperar_top3(casos["train"], CodificadorFalso(), cache)
    cod2 = CodificadorFalso()
    b = servicio.recuperar_top3(list(reversed(casos["train"])), cod2, cache)
    assert a["huella"] == b["huella"] and a["top3"] == b["top3"]
    assert b["chunks_en_cache"] == 8  # 2 articulos x 4 chunks
    assert cod2.llamadas == 3  # solo las consultas (una por contexto)


def test_top3_menos_de_3_chunks_devuelve_los_que_hay(entorno):
    f, conjuntos, papers, _, cache = entorno
    preparar_cache(cache, CITADOS)
    integrar = crear_integrar({c: parrafos(c, n=2) for c in CITADOS})
    casos, _ = servicio.construir_casos_split(conjuntos, f.ctx, papers, cache, integrar, fragmentar_falso)
    res = servicio.recuperar_top3(casos["train"], CodificadorFalso(), CacheMemoria())
    assert all(len(v) == 2 for v in res["top3"].values())


def test_validar_casos_chunks_rechaza_estructuras_invalidas(entorno):
    casos, _ = armar(entorno)
    base = casos["train"]
    malos = [
        {**base[0], "citation_context": "sin marca"},
        {**base[0], "chunks": []},
        {**base[0], "chunks": [base[0]["chunks"][0], base[0]["chunks"][0]]},
        {**base[0], "chunks": [{**base[0]["chunks"][0], "texto": " "}]},
        {**base[0], "citing_id": base[0]["cited_id"]},
    ]
    for malo in malos:
        with pytest.raises(ValueError):
            dominio.validar_casos_chunks([malo])
    with pytest.raises(ValueError, match="duplicado"):
        dominio.validar_casos_chunks([base[0], base[0]])
    distinto = {**base[1], "cited_id": base[0]["cited_id"],
                "chunks": [{**base[0]["chunks"][0], "texto": "otro"}, *base[0]["chunks"][1:]]}
    with pytest.raises(ValueError, match="inconsistentes"):
        dominio.validar_casos_chunks([base[0], distinto])


# ---- regresion contra A1
def filas_a1(top3, ctx_extra=None, cambiar=None):
    filas = []
    for ctx, top in top3.items():
        for r in top:
            cid = cambiar if cambiar and r["posicion"] == 1 and ctx == "t1" else r["chunk_id"]
            filas.append({"context_id": ctx, "metodo": "scibert", "posicion": str(r["posicion"]),
                          "chunk_id": cid, "puntaje": str(r["similitud_coseno"])})
            filas.append({"context_id": ctx, "metodo": "bm25", "posicion": "1",
                          "chunk_id": "zzz", "puntaje": "1"})
    return filas


def test_regresion_a1(entorno):
    casos, _ = armar(entorno)
    top3 = servicio.recuperar_top3(casos["train"], CodificadorFalso(), CacheMemoria())["top3"]
    ok = servicio.regresion_top3(top3, filas_a1(top3))
    assert ok["contextos_comparados"] == 3 and ok["coinciden"] == 3 and ok["discrepancias"] == []
    mal = servicio.regresion_top3(top3, filas_a1(top3, cambiar="p99999"))
    assert mal["discrepancias"] == ["t1"] and mal["coinciden"] == 2
    parcial = servicio.regresion_top3({"t1": top3["t1"]}, filas_a1(top3))
    assert parcial["contextos_a1"] == 3 and parcial["contextos_comparados"] == 1
    desviado = filas_a1(top3)
    desviado[0]["puntaje"] = str(float(desviado[0]["puntaje"]) + 0.5)
    assert servicio.regresion_top3(top3, desviado)["discrepancias"][0].startswith("similitud_max_dif")
