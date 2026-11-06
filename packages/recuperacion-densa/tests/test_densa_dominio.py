import math

import pytest

pytest.importorskip("recuperacion_densa")

from recuperacion_densa import dominio as d  # noqa: E402


def chunk(i, sec="Intro", texto=None, idx=None):
    return {"chunk_id": f"c{i}", "texto": texto or f"texto {i}", "seccion": sec,
            "paragraph_indices": idx or [i], "palabras": 2}


def caso(cid="x1", cited="A", n=4, ctx="mira TARGETCIT aqui", **kw):
    return {"context_id": cid, "split": "train", "cited_id": cited,
            "citation_context": ctx, "chunks": [chunk(i) for i in range(n)], **kw}


# ---- texto / vectores
def test_normalizar_contexto():
    assert d.normalizar_contexto("a  TARGETCIT b OTHERCIT c") == "a b c"


def test_ventanas_contiguas_sin_perdida():
    w = d.ventanas(10, 4)
    assert w == [(0, 4), (4, 8), (8, 10)]
    assert d.ventanas(0, 4) == [] and d.ventanas(4, 4) == [(0, 4)]
    with pytest.raises(ValueError):
        d.ventanas(5, 0)


def test_media_ponderada():
    assert d.media_ponderada([(1.0, 0.0), (0.0, 1.0)], [3, 1]) == (0.75, 0.25)
    with pytest.raises(ValueError):
        d.media_ponderada([(1.0,)], [1, 2])


@pytest.mark.parametrize("v", [(), (0.0, 0.0), (float("nan"), 1.0), (float("inf"), 1.0)])
def test_normalizar_vector_rechaza(v):
    with pytest.raises(ValueError):
        d.normalizar_vector(v)


def test_normalizar_vector_unitario():
    assert math.isclose(math.hypot(*d.normalizar_vector((3.0, 4.0))), 1.0)


def test_ordenar_top3_desempate_por_chunk_id_y_corte():
    chunks = [{"chunk_id": i} for i in ("b", "a", "c", "d")]
    vecs = [(1.0, 0.0)] * 3 + [(0.0, 1.0)]
    top = d.ordenar_top3((1.0, 0.0), chunks, vecs)
    assert [r["chunk_id"] for r in top] == ["a", "b", "c"]
    assert [r["posicion"] for r in top] == [1, 2, 3]


def test_ordenar_top3_nan_y_dimension():
    with pytest.raises(ValueError):
        d.ordenar_top3((1.0, 0.0), [{"chunk_id": "a"}], [(float("nan"), 1.0)])
    with pytest.raises(ValueError):
        d.ordenar_top3((1.0, 0.0), [{"chunk_id": "a"}], [(1.0, 0.0, 0.0)])
    with pytest.raises(ValueError):
        d.ordenar_top3((1.0, 0.0), [{"chunk_id": "a"}], [])


# ---- validar_casos
def test_validar_ok_y_conteos():
    r = d.validar_casos([caso("x1"), caso("x2"), caso("x3", cited="B", n=2)])
    assert r == {"contextos": 3, "articulos": 2, "chunks_unicos": 6}


@pytest.mark.parametrize("mut", [
    {"split": "val"}, {"citation_context": "sin marca"},
    {"citation_context": "TARGETCIT y TARGETCIT"}, {"chunks": []},
    {"gold": ["c1"]}, {"evidencia_top3": {"x": 1}},
])
def test_validar_rechaza(mut):
    with pytest.raises(ValueError):
        d.validar_casos([{**caso(), **mut}])


def test_validar_duplicados_excluidos_y_huella():
    with pytest.raises(ValueError):
        d.validar_casos([caso("x1"), caso("x1")])
    with pytest.raises(ValueError):
        d.validar_casos([caso("x1")], excluidos={"x1"})
    otro = caso("x2")
    otro["chunks"][0]["paragraph_indices"] = [99]
    with pytest.raises(ValueError, match="inconsistentes"):
        d.validar_casos([caso("x1"), otro])
    dup = caso("x3")
    dup["chunks"][1]["chunk_id"] = "c0"
    with pytest.raises(ValueError):
        d.validar_casos([dup])


def test_huella_incluye_paragraph_indices():
    a, b = [chunk(1)], [chunk(1, idx=[7])]
    assert d.huella_chunks(a) != d.huella_chunks(b)


# ---- integridad
def res(c, cited="A", **kw):
    ch = c["chunks"][0]
    return {"chunk_id": ch["chunk_id"], "cited_id": cited, "seccion": ch["seccion"],
            "paragraph_indices": ch["paragraph_indices"], **kw}


def test_enriquecer_sin_texto():
    c = caso()
    out = d.enriquecer(c, [{"chunk_id": "c1", "similitud_coseno": 0.5}])
    assert out[0]["cited_id"] == "A" and out[0]["paragraph_indices"] == [1]
    assert "texto" not in out[0]


def test_integridad_ok():
    c = caso()
    assert d.verificar_integridad([c], {"x1": [res(c)]}, "scibert") == []


def test_integridad_detecta_violaciones():
    c = caso()
    base = res(c)
    casos = {
        "ajeno": [{**base, "cited_id": "B"}],
        "seccion": [{**base, "seccion": "Otra"}],
        "indices": [{**base, "paragraph_indices": [9]}],
        "duplicado": [base, base],
        "exceso": [{**res(c), "chunk_id": f"c{i}", "paragraph_indices": [i]} for i in range(4)],
        "inexistente": [{**base, "chunk_id": "zz"}],
    }
    for nombre, r in casos.items():
        assert d.verificar_integridad([c], {"x1": r}, "bm25"), nombre
    assert d.verificar_integridad([c], {}, "bm25")
    assert d.verificar_integridad([c], {"x1": [], "y": []}, "bm25")


def test_integridad_mismo_chunk_id_en_otro_articulo_es_ajeno():
    a, b = caso("x1", "A"), caso("x2", "B", n=1)
    r = {"chunk_id": "c3", "cited_id": "A", "seccion": "Intro", "paragraph_indices": [3]}
    v = d.verificar_integridad([a, b], {"x1": [r], "x2": [r]}, "m")
    assert len(v) == 1 and "x2" in v[0]


# ---- comparacion
def test_comparar():
    assert d.comparar(["a", "b", "c"], ["a", "x", "c"]) == {
        "interseccion": 2, "solape_3": 2 / 3, "jaccard": 0.5, "mismo_top1": True,
        "abstencion_bm25": False}
    r = d.comparar(["a"], [])
    assert r["abstencion_bm25"] and not r["mismo_top1"] and r["interseccion"] == 0


def test_solape_azar():
    assert d.solape_esperado_azar(9) == 1.0
    assert d.solape_esperado_azar(2) == 2 * 2 / 2
    with pytest.raises(ValueError):
        d.solape_esperado_azar(0)


def fila(ctx, art, inter, n=9, top1=False, abst=False):
    return {"context_id": ctx, "cited_id": art, "n_chunks": n, "interseccion": inter,
            "jaccard": 0.0, "mismo_top1": top1, "abstencion_bm25": abst}


def test_agregar_micro_vs_macro():
    # A: 3 contextos con solape 3/3; B: 1 contexto con 0/3
    f = [fila(f"a{i}", "A", 3) for i in range(3)] + [fila("b", "B", 0)]
    r = d.agregar_comparacion(f)
    assert r["micro"]["n"] == 4 and r["macro"]["n"] == 2
    assert r["micro"]["solape_3"] == pytest.approx(0.75)
    assert r["macro"]["solape_3"] == pytest.approx(0.5)
    assert r["macro"]["solape_esperado_azar_chunks"] == pytest.approx(1.0)
    with pytest.raises(ValueError):
        d.agregar_comparacion([])


# ---- latencias
def test_percentiles_rango_mas_cercano():
    r = d.resumir_latencias([float(i) for i in range(1, 101)])
    assert (r["n"], r["p50"], r["p95"], r["max"]) == (100, 50.0, 95.0, 100.0)
    assert r["media"] == pytest.approx(50.5)
    assert d.resumir_latencias([2.0]) == {"n": 1, "media": 2.0, "p50": 2.0, "p95": 2.0, "max": 2.0}
    assert d.resumir_latencias([])["n"] == 0


# ---- distribuciones
def test_distribucion_secciones():
    corpus = [chunk(0, "A"), chunk(1, None), chunk(2, "A"), chunk(3, "B")]
    r = d.distribucion_secciones(corpus, [[{"seccion": "A"}]], [[{"seccion": None}]])
    assert r["corpus"] == {"(sin seccion)": 0.25, "A": 0.5, "B": 0.25}
    assert r["denso"] == {"A": 1.0} and r["bm25"] == {"(sin seccion)": 1.0}


def test_diversidad_y_similitud():
    tops = {"x1": ["c0", "c1", "c2"], "x2": ["c0", "c1", "c3"], "y": ["c5"]}
    cited = {"x1": "A", "x2": "A", "y": "B"}
    f = d.diversidad_por_articulo(tops, cited, {"A": 10, "B": 5})
    a = f[0]
    assert a["chunks_distintos_top3"] == 4 and a["chunk_top1_mas_frecuente"] == 1.0
    s = d.estadisticas_similitud({"x": [{"similitud_coseno": 0.9}, {"similitud_coseno": 0.6}],
                                  "y": [{"similitud_coseno": 0.5}]})
    assert s["top1"]["max"] == 0.9 and s["brecha_top1_top2"]["media"] == pytest.approx(0.3)


def test_extracto_y_huella_resultados():
    assert len(d.extracto("palabra " * 100)) <= 240
    assert d.extracto("a   b") == "a b"
    r1 = {"x": [{"cited_id": "A", "chunk_id": "c", "similitud_coseno": 0.1}]}
    r2 = {"x": [{"cited_id": "A", "chunk_id": "c", "similitud_coseno": 0.2}]}
    assert d.huella_resultados(r1) == d.huella_resultados(dict(r1)) != d.huella_resultados(r2)


# ---- consenso / gold
ESP = {("x1", "c0"), ("x1", "c1")}


def test_consenso_reglas_fail_closed():
    a = {("x1", "c0"): 1, ("x1", "c1"): 0}
    b = {("x1", "c0"): 1, ("x1", "c1"): 1}
    adj = {("x1", "c0"): None, ("x1", "c1"): 1}
    cons, disc = d.consenso(a, b, adj, ESP)
    assert cons == {("x1", "c0"): 1, ("x1", "c1"): 1} and disc == [("x1", "c1")]
    with pytest.raises(ValueError, match="Faltan"):
        d.consenso(a, b, {**adj, ("x1", "c1"): None}, ESP)
    with pytest.raises(ValueError, match="contradice"):
        d.consenso(a, b, {**adj, ("x1", "c0"): 0}, ESP)
    with pytest.raises(ValueError):
        d.consenso({("x1", "c0"): 1}, b, adj, ESP)
    with pytest.raises(ValueError):
        d.consenso({**a, ("x1", "c0"): None}, b, adj, ESP)


def puntuar(ranking, gold):
    if not gold:
        return None
    hit = [i for i, x in enumerate(ranking[:3], 1) if x in gold]
    return {"hit_3": float(bool(hit)), "recall_3": len(set(ranking[:3]) & gold) / len(gold),
            "rr_3": 1 / hit[0] if hit else 0.0}


def test_agregar_gold():
    c = caso("x1", n=3)
    cons = {("x1", "c0"): 0, ("x1", "c1"): 1, ("x1", "c2"): 1}
    r = d.agregar_gold([c], cons, {"x1": ["c1", "c0", "c2"]}, puntuar)
    assert r["estado"] == "calibracion_train_no_gold"
    assert (r["hit_3"], r["recall_3"], r["mrr_3"]) == (1.0, 1.0, 1.0)
    vacio = d.agregar_gold([c], {k: 0 for k in cons}, {"x1": ["c1"]}, puntuar)
    assert vacio["casos_sin_relevantes"] == 1 and vacio["recall_3"] is None
    with pytest.raises(ValueError):
        d.agregar_gold([c], cons, {"x1": ["zz"]}, puntuar)
