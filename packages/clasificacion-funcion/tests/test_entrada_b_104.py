"""Controles de fuga de la Entrada B (#104) con fixtures pequenos: sin archivos, sin torch."""
import json
import re
from pathlib import Path

import pytest

from clasificacion_funcion import dominio, entrada_b_104 as eb, seleccion_datos as sd

NOTEBOOK_06 = Path(__file__).resolve().parents[3] / "notebooks/06_experimentos_104_entrada_b.ipynb"

CLASES = dominio.CATEGORIAS


def _ctx(citing, cited, texto="texto TARGETCIT fin"):
    return {"citing_id": citing, "refid": cited, "masked_text": texto}


def _fila(cid, clase="Background"):
    return {"context_id": cid, "etiqueta_entrenamiento": clase}


def fuentes():
    """t2 cita a VCIT (citante de V), t3 a GCIT (citante del gold), t4 a XCIT (citante excluido)."""
    contextos = {
        "t1": _ctx("P1", "A"), "t2": _ctx("P2", "VCIT"), "t3": _ctx("P3", "GCIT"),
        "t4": _ctx("P4", "XCIT"), "t5": _ctx("P5", "A"),
        "v1": _ctx("VCIT", "A"), "v2": _ctx("P6", "A"),
        "g1": _ctx("GCIT", "A"), "x1": _ctx("XCIT", "A"),
    }
    return sd.Fuentes(qlora={}, jurado={}, haiku={}, haiku_train=set(), haiku_val=set(), gpt={},
                      contextos=contextos, ids_gold={"g1"}, ids_excluidos={"x1"})


V = [{"context_id": "v1", "citing_id": "VCIT"}, {"context_id": "v2", "citing_id": "P6"}]


# ---------------------------------------------------------------- L2 / L3
def test_citantes_evaluacion_une_v_gold_y_excluidos():
    f = fuentes()
    assert eb.citantes_evaluacion(f, V) == {"VCIT", "P6", "GCIT", "XCIT"}
    assert eb.citantes_gold(f) == {"GCIT"}


def test_l2_quita_las_citas_a_citantes_y_cuenta_por_clase():
    f = fuentes()
    filas = [_fila("t1"), _fila("t2", "Gap"), _fila("t3", "Gap"), _fila("t4", "Basis"), _fila("t5")]
    limpias, quitadas = eb.excluir_citas_a_citantes(filas, f.contextos, eb.citantes_evaluacion(f, V))
    assert [x["context_id"] for x in limpias] == ["t1", "t5"]
    assert quitadas == {"Basis": 1, "Gap": 2}
    sin_citantes, nada = eb.excluir_citas_a_citantes(filas, f.contextos, set())
    assert sin_citantes == filas and nada == {}


def test_l2_contexto_ausente_falla_cerrado():
    with pytest.raises(ValueError, match="Contexto ausente"):
        eb.excluir_citas_a_citantes([_fila("zzz")], fuentes().contextos, {"A"})


def test_l3_levanta_si_v_cita_un_citante_del_gold():
    f = fuentes()
    assert eb.verificar_citados_v(V, f.contextos, eb.citantes_gold(f)) == {
        "citas_v_a_citantes_gold": 0, "citas_v": 2}
    v_mala = [*V, {"context_id": "t3", "citing_id": "P3"}]  # t3 cita a GCIT, citante del gold
    with pytest.raises(ValueError, match="citan un citante del Gold"):
        eb.verificar_citados_v(v_mala, f.contextos, eb.citantes_gold(f))


# ---------------------------------------------------------------- L4
CONTEXTO = ("we adopt the maximum entropy tagger of TARGETCIT because it handles unknown words "
            "better than the earlier OTHERCIT systems on noisy text")


def _chunk(texto, cid="t1", cited="A", chunk="p00001"):
    return {"context_id": cid, "cited_id": cited, "chunk_id": chunk, "texto": texto}


def test_shingles_cortan_en_los_marcadores_y_normalizan():
    assert eb.shingles("uno dos tres", k=4) == set()
    assert eb.shingles("A b C d", k=4) == eb.shingles("a, B; c: D!", k=4)
    # un k-grama no puede cruzar TARGETCIT: "a b c TARGETCIT d e f" no tiene 4 palabras seguidas
    assert eb.shingles("a b c TARGETCIT d e f", k=4) == set()
    assert len(eb.shingles("a b c d TARGETCIT d e f g", k=4)) == 2


def test_l4_detecta_un_contexto_copiado_aunque_el_marcador_sea_una_referencia():
    copia = CONTEXTO.replace("TARGETCIT", "(Smith et al., 2010)").replace("OTHERCIT", "(Jones, 2008)")
    parrafo = f"in this section we describe the setup. {copia} all experiments use the same split."
    r = eb.solapes_texto({"train": [_chunk(parrafo)]}, {"V": {"v1": CONTEXTO}})
    par = r["pares"]["train~V"]
    assert r["total_violaciones"] == 1 and par["max_solape"] >= 0.9
    assert par["detalle"][0]["contexto_eval"] == "v1" and par["detalle"][0]["chunk_id"] == "p00001"
    assert par["conjunto"] == "train" and par["objetivo"] == "V"
    with pytest.raises(ValueError, match="evaluacion"):
        eb.exigir_sin_solapes(r)


def test_l4_ignora_texto_no_relacionado_y_reporta_el_histograma():
    ajeno = "the corpus contains news articles that were collected during two thousand and nine " * 3
    r = eb.solapes_texto({"train": [_chunk(ajeno)]}, {"V": {"v1": CONTEXTO}, "gold": {"g1": CONTEXTO}})
    assert r["total_violaciones"] == 0 and eb.exigir_sin_solapes(r) is r
    assert set(r["pares"]) == {"train~V", "train~gold"}
    assert r["pares"]["train~V"]["histograma"] == {"0": 1} and r["pares"]["train~V"]["max_solape"] == 0.0


def test_l4_citados_con_solape_es_por_articulo_y_conjunto():
    copia = f"intro. {CONTEXTO.replace('TARGETCIT', '(Smith, 2010)').replace('OTHERCIT', '(Jones, 2008)')} fin."
    ajeno = "the corpus contains news articles that were collected during two thousand and nine " * 3
    chunks = {"train": [_chunk(copia, cid="t1", cited="DUP", chunk="p1"), _chunk(ajeno, cid="t1", cited="DUP", chunk="p2"),
                        _chunk(ajeno, cid="t5", cited="LIMPIO", chunk="p1")],
              "V": [_chunk(ajeno, cid="v2", cited="OTRO", chunk="p9")]}
    r = eb.solapes_texto(chunks, {"V": {"v1": CONTEXTO}, "gold": {"g1": CONTEXTO}})
    assert eb.citados_con_solape(r, "train") == {"DUP"}  # todo el citado, no solo el chunk copiado
    assert eb.citados_con_solape(r, "V") == set()
    f = fuentes()
    filas = [_fila("t1", "Gap"), _fila("t5")]
    f.contextos["t1"]["refid"], f.contextos["t5"]["refid"] = "DUP", "LIMPIO"
    limpias, quitadas = eb.excluir_citas_a_citantes(filas, f.contextos, eb.citados_con_solape(r, "train"))
    assert [x["context_id"] for x in limpias] == ["t5"] and quitadas == {"Gap": 1}


def test_l4_el_umbral_separa_un_solape_parcial_de_uno_casi_completo():
    palabras = [f"w{i}" for i in range(30)]  # 23 shingles de 8 palabras
    contexto = " ".join(palabras)
    relleno = " ".join(f"otra{i}" for i in range(40))
    corto = eb.solapes_texto({"train": [_chunk(f"{' '.join(palabras[:16])} {relleno}")]}, {"V": {"v1": contexto}})
    largo = eb.solapes_texto({"train": [_chunk(f"{' '.join(palabras[:22])} {relleno}")]}, {"V": {"v1": contexto}})
    assert corto["pares"]["train~V"]["max_solape"] == pytest.approx(9 / 23, abs=1e-3)
    assert corto["total_violaciones"] == 0
    assert largo["pares"]["train~V"]["max_solape"] == pytest.approx(15 / 23, abs=1e-3)
    assert largo["total_violaciones"] == 1


def test_l4_no_compara_un_conjunto_consigo_mismo_y_deduplica_chunks():
    chunks = [_chunk(CONTEXTO), _chunk(CONTEXTO, cid="t9")]  # el mismo chunk citado por dos citas
    r = eb.solapes_texto({"V": chunks}, {"V": {"v1": CONTEXTO}, "gold": {"g1": CONTEXTO}})
    assert list(r["pares"]) == ["V~gold"]
    assert r["pares"]["V~gold"]["chunks_unicos"] == 1 and r["total_violaciones"] == 1


# ---------------------------------------------------------------- casos y entradas
def test_casos_para_chunks_tiene_la_forma_de_servicio_caso_y_pone_indice_solo_con_etiqueta():
    f = fuentes()
    con = eb.casos_para_chunks([_fila("t1", "Gap")], f.contextos)
    sin = eb.casos_para_chunks([{"context_id": "t1"}], f.contextos)
    assert con == [{"context_id": "t1", "citing_id": "P1", "cited_id": "A",
                    "citation_context": "texto TARGETCIT fin", "indice": 1}]
    assert "indice" not in sin[0]
    with pytest.raises(ValueError, match="ausente"):
        eb.casos_para_chunks([{"context_id": "no"}], f.contextos)


def _entrada(cid, *chunks):
    return {"context_id": cid, "top3": [{"chunk_id": c, "perfil": "method", "seccion": "S", "texto": c}
                                        for c in chunks]}


def test_entradas_por_contexto_une_y_detecta_top3_distinto():
    a, b = _entrada("t1", "p1", "p2", "p3"), _entrada("t1", "p1", "p2", "p3")
    union = eb.entradas_por_contexto({"train_M": [a], "train_S": [b, _entrada("t2", "p4")]})
    assert union.keys() == {"t1", "t2"}
    with pytest.raises(ValueError, match="Top-3 distinto"):
        eb.entradas_por_contexto({"train_M": [a], "train_S": [_entrada("t1", "p9", "p2", "p3")]})


def test_l5_mismos_ids_en_a_y_b():
    a = [{"context_id": "t1"}, {"context_id": "t2"}]
    assert eb.verificar_mismos_ids("train", a, list(reversed(a))) == dominio.sha_ids(["t1", "t2"])
    with pytest.raises(ValueError, match="difieren en train"):
        eb.verificar_mismos_ids("train", a, a[:1])


# ---------------------------------------------------------------- L7
def test_l7_el_notebook_06_nunca_carga_el_test_gold_anotado():
    """Por construccion: del Gold solo se leen ids (manifiestos). `servicio.cargar_conjuntos` y
    `filas_test_gold` cargan TEST_GOLD_2700_ANOTADO.csv (con etiquetas), asi que no pueden aparecer."""
    if not NOTEBOOK_06.is_file():
        pytest.skip("notebook 06 ausente")
    nb = json.loads(NOTEBOOK_06.read_text(encoding="utf-8"))
    codigo = "\n".join("".join(c["source"]) for c in nb["cells"] if c["cell_type"] == "code")
    for prohibido in ("filas_test_gold", "cargar_conjuntos", "TEST_GOLD_2700_ANOTADO", "gold_eval_2015"):
        assert prohibido not in codigo, f"el notebook 06 no debe usar {prohibido}"
    assert not re.search(r"ad\.TEST_GOLD\b(?!_MANIFIESTO)", codigo)
    assert "ids_gold_v2()" in codigo  # lo unico que lee del Gold v2


# ---------------------------------------------------------------- dev, chunks al azar, L10
def _contextos_dev(n=400):
    return {f"c{i}": _ctx(f"P{i // 4}", "A") for i in range(n)}


def test_separar_dev_agrupa_por_citante_es_determinista_y_no_depende_del_orden():
    ctx = _contextos_dev()
    filas = [_fila(c) for c in ctx]
    train, dev = eb.separar_dev(filas, ctx)
    assert len(train) + len(dev) == len(filas)
    citantes_dev = {ctx[x["context_id"]]["citing_id"] for x in dev}
    assert not citantes_dev & {ctx[x["context_id"]]["citing_id"] for x in train}
    assert (train, dev) == eb.separar_dev(filas, ctx)
    t2, d2 = eb.separar_dev(list(reversed(filas)), ctx)
    assert {x["context_id"] for x in d2} == {x["context_id"] for x in dev}
    assert 0.05 < len(citantes_dev) / 100 < 0.30  # 100 citantes, fraccion 0.15
    assert {x["context_id"] for x in eb.separar_dev(filas, ctx, sal="otra")[1]} != {x["context_id"] for x in dev}
    with pytest.raises(ValueError):
        eb.separar_dev(filas, ctx, fraccion=1.5)


def _caso_chunks(cid, cited, n=5):
    return {"context_id": cid, "cited_id": cited,
            "chunks": [{"chunk_id": f"{cited}-p{i}", "texto": f"texto {i} de {cited}",
                        "seccion": "Results" if i % 2 else "Method"} for i in range(n)]}


def _perfil(seccion):
    return (seccion or "vacia").lower()


def _b(cid, cited, chunks=(0, 1, 2)):
    return {"context_id": cid, "cited_id": cited, "titulo": "t", "abstract": "a",
            "top3": [{"chunk_id": f"{cited}-p{i}", "texto": f"texto {i} de {cited}",
                      "perfil": _perfil("Results" if i % 2 else "Method"),
                      "seccion": "Results" if i % 2 else "Method"} for i in chunks]}


def test_entradas_aleatorias_deterministas_del_mismo_citado_y_con_los_mismos_campos():
    casos = {"train_M": [_caso_chunks("t1", "R1"), _caso_chunks("t2", "R2", 8)], "V": [_caso_chunks("v1", "R1")]}
    entradas = {"t1": _b("t1", "R1"), "t2": _b("t2", "R2"), "v1": _b("v1", "R1")}
    al = eb.entradas_aleatorias(casos, entradas, _perfil)
    assert al == eb.entradas_aleatorias(casos, entradas, _perfil)
    assert al != eb.entradas_aleatorias(casos, entradas, _perfil, sal="otra")
    for cid, e in al.items():
        ids = [c["chunk_id"] for c in e["top3"]]
        assert len(set(ids)) == 3 and all(i.startswith(entradas[cid]["cited_id"] + "-") for i in ids)
        assert all(set(c) == {"chunk_id", "texto", "perfil"} for c in e["top3"])
        assert {k: v for k, v in e.items() if k != "top3"} == {k: v for k, v in entradas[cid].items() if k != "top3"}
        top3 = {c["chunk_id"]: c["perfil"] for c in entradas[cid]["top3"]}
        assert all(c["perfil"] == top3[c["chunk_id"]] for c in e["top3"] if c["chunk_id"] in top3)


def test_entradas_aleatorias_fallan_con_menos_de_tres_chunks():
    with pytest.raises(ValueError, match="menos de 3"):
        eb.entradas_aleatorias({"t": [_caso_chunks("t1", "R1", 2)]}, {"t1": _b("t1", "R1", (0, 1, 1))}, _perfil)
    with pytest.raises(ValueError, match="sin chunks"):
        eb.entradas_aleatorias({"t": []}, {"t1": _b("t1", "R1")}, _perfil)


def test_resumen_aleatorias():
    entradas = {"t1": _b("t1", "R1"), "t2": _b("t2", "R2")}
    al = {"t1": _b("t1", "R1"), "t2": _b("t2", "R2", (2, 3, 4))}
    assert eb.resumen_aleatorias(al, entradas) == {"contextos": 2, "solape_medio": (1 + 1 / 3) / 2,
                                                   "frac_identicos": 0.5}
    assert eb.resumen_aleatorias({}, entradas)["solape_medio"] is None


def test_l10_detecta_un_contexto_gemelo_y_respeta_el_umbral():
    gemelo = CONTEXTO.replace("noisy text", "noisy web text")
    ajeno = "the corpus contains news articles that were collected during two thousand and nine"
    r = eb.contextos_casi_duplicados({"train": {"t1": gemelo, "t2": ajeno}, "dev": {"d1": ajeno + " again"},
                                      "V": {"v1": CONTEXTO}}, citantes={"t1": "P1", "v1": "Q1"})
    assert list(r["pares"]) == ["train~dev", "train~V", "dev~V"]
    assert [(p["a"], p["b"]) for p in r["pares"]["train~V"]["detalle"]] == [("t1", "v1")]
    assert r["pares"]["train~V"]["detalle"][0]["citante_b"] == "Q1"
    assert [(p["a"], p["b"]) for p in r["pares"]["train~dev"]["detalle"]] == [("t2", "d1")]
    assert r["total_pares"] == 2
    assert eb.contextos_casi_duplicados({"train": {"t1": gemelo}, "V": {"v1": CONTEXTO}}, umbral=1.01)["total_pares"] == 0


def test_chunks_de_citados_trae_todos_los_chunks_de_cada_citado_una_vez():
    f = fuentes()
    casos = {"train": [_caso_chunks("t1", "A", 4)], "V": [_caso_chunks("v1", "VCIT", 2)]}
    salida = eb.chunks_de_citados(casos, [_fila("t5"), _fila("t1")], f.contextos)
    assert [c["chunk_id"] for c in salida] == [f"A-p{i}" for i in range(4)]
    assert {c["context_id"] for c in salida} == {"t1"} and set(salida[0]) == {"context_id", "cited_id", "chunk_id", "texto"}
    with pytest.raises(ValueError, match="sin chunks"):
        eb.chunks_de_citados(casos, [_fila("t3")], f.contextos)
