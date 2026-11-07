import math

import pytest

from clasificacion_funcion import dominio as d


def caso(cid, citing, cited, ctx=None):
    return {"context_id": cid, "citing_id": citing, "cited_id": cited,
            "citation_context": ctx or f"texto unico {cid} TARGETCIT fin"}


# ---- taxonomia
def test_nueve_categorias_unicas():
    assert len(d.CATEGORIAS) == 9 == len(set(d.CATEGORIAS))


@pytest.mark.parametrize("texto,indice", [
    ("Background", 0), ("  gap ", 1), ("IMPROVEMENT/MODIFICATION", 5),
    ("Improvement / Modification", 5), ("identification  of the originator", 7),
    ("Further Reading", 8),
])
def test_normalizar_etiqueta(texto, indice):
    assert d.normalizar_etiqueta(texto) == indice


def test_normalizar_acepta_indice_y_rechaza_invalidos():
    assert d.normalizar_etiqueta(4) == 4
    for malo in ("desconocida", 9, -1, True, None, 1.5):
        with pytest.raises(ValueError):
            d.normalizar_etiqueta(malo)


def test_abstenciones_no_son_clase():
    assert d.normalizar_etiqueta("Ambiguo") is None
    assert d.normalizar_etiqueta(" no  evaluable ") is None
    assert d.motivo_abstencion("Ambiguo") == "Ambiguo"
    assert d.motivo_abstencion("No evaluable") == "No evaluable"
    assert d.motivo_abstencion("Gap") is None


def test_separar_abstenciones_cuenta_y_conserva_evaluables():
    filas = [{"id": "a", "etiqueta": "Gap"}, {"id": "b", "etiqueta": "Ambiguo"},
             {"id": "c", "etiqueta": "No evaluable"}, {"id": "d", "etiqueta": "Ambiguo"}]
    evaluables, abst = d.separar_abstenciones(filas)
    assert [f["id"] for f in evaluables] == ["a"] and evaluables[0]["indice"] == 1
    assert abst == {"Ambiguo": 2, "No evaluable": 1}


# ---- hashes
def test_sha_ids_independiente_del_orden_y_rechaza_duplicados():
    assert d.sha_ids(["b", "a"]) == d.sha_ids(["a", "b"])
    assert d.sha_ids(["a"]) != d.sha_ids(["a", "b"])
    with pytest.raises(ValueError):
        d.sha_ids(["a", "a"])


def test_sha_etiquetas_sensible_a_etiqueta_no_a_orden():
    assert d.sha_etiquetas({"a": 1, "b": 2}) == d.sha_etiquetas({"b": 2, "a": 1})
    assert d.sha_etiquetas({"a": 1}) != d.sha_etiquetas({"a": 2})
    with pytest.raises(ValueError):
        d.sha_etiquetas({"a": 9})


# ---- metricas calculadas a mano
def test_metricas_a_mano():
    # verdad:   0 0 1 1 2 ; predicho: 0 1 1 1 0
    m = d.metricas([0, 0, 1, 1, 2], [0, 1, 1, 1, 0])
    assert m["n"] == 5 and m["accuracy"] == pytest.approx(3 / 5)
    c0, c1, c2 = m["per_class"][:3]
    assert (c0["precision"], c0["recall"]) == (pytest.approx(1 / 2), pytest.approx(1 / 2))
    assert (c1["precision"], c1["recall"]) == (pytest.approx(2 / 3), pytest.approx(1.0))
    assert c1["f1"] == pytest.approx(0.8)
    assert (c2["precision"], c2["recall"], c2["f1"], c2["support"]) == (0.0, 0.0, 0.0, 1)
    # macro sobre las 9 clases (las 6 sin soporte aportan 0)
    assert m["f1_macro"] == pytest.approx((0.5 + 0.8 + 0.0) / 9)
    assert m["f1_micro"] == m["precision_micro"] == m["recall_micro"] == pytest.approx(0.6)
    assert m["f1_weighted"] == pytest.approx((0.5 * 2 + 0.8 * 2 + 0.0 * 1) / 5)
    assert m["confusion_matrix"][0][:2] == [1, 1] and m["confusion_matrix"][2][0] == 1
    assert len(m["confusion_matrix"]) == 9 and all(len(f) == 9 for f in m["confusion_matrix"])
    assert sum(sum(f) for f in m["confusion_matrix"]) == 5


def test_metricas_validaciones():
    with pytest.raises(ValueError):
        d.metricas([0], [0, 1])
    with pytest.raises(ValueError):
        d.metricas([], [])
    with pytest.raises(ValueError):
        d.metricas([0], [9])


def test_pesos_clase_inversos_a_frecuencia():
    w = d.pesos_clase([0, 0, 0, 1])
    assert w[0] == pytest.approx(4 / (9 * 3)) and w[1] == pytest.approx(4 / 9)
    assert w[2:] == [0.0] * 7
    assert w[0] < w[1]
    with pytest.raises(ValueError):
        d.pesos_clase([])


def test_agregar_semillas_media_y_desviacion_muestral():
    m1 = d.metricas([0, 1], [0, 1])
    m2 = d.metricas([0, 1], [0, 0])
    agg = d.agregar_semillas([m1, m2])
    assert agg["semillas"] == 2
    assert agg["accuracy"]["media"] == pytest.approx(0.75)
    assert agg["accuracy"]["desv"] == pytest.approx(math.sqrt(0.125))
    assert len(agg["f1_por_clase"]) == 9
    assert d.agregar_semillas([m1])["f1_macro"]["desv"] == 0.0
    with pytest.raises(ValueError):
        d.agregar_semillas([])


# ---- fugas
def conjuntos_limpios():
    return {
        "train": [caso("t1", "P1", "A"), caso("t2", "P2", "B")],
        "val": [caso("v1", "P3", "A")],
        "eval": [caso("e1", "P4", "C")],
    }


def test_sin_fugas_reporta_cited_compartido_sin_bloquear():
    rep = d.verificar_fugas(conjuntos_limpios(), excluidos={"x"}, gold_v2={"g1"})
    assert rep["total_fugas"] == 0
    assert rep["cited_id_compartidos_no_bloqueante"]["train~val"] == 1


@pytest.mark.parametrize("mutar,clave", [
    (lambda c: c["eval"].append(caso("t1", "P9", "Z")), "context_id"),
    (lambda c: c["eval"].append(caso("e2", "P1", "Z")), "citing_id"),
    (lambda c: c["val"].append(caso("v2", "P1", "A")), "par_citante_citado"),
    (lambda c: c["eval"].append(caso("e2", "P9", "Z", ctx="  texto unico t1   TARGETCIT fin")),
     "sha_texto_targetcit"),
])
def test_fuga_bloquea(mutar, clave):
    c = conjuntos_limpios()
    mutar(c)
    with pytest.raises(ValueError, match=clave):
        d.verificar_fugas(c)


def test_fuga_con_excluidos_y_gold_v2():
    with pytest.raises(ValueError, match="excluidos"):
        d.verificar_fugas(conjuntos_limpios(), excluidos={"e1"})
    with pytest.raises(ValueError, match="gold_v2"):
        d.verificar_fugas(conjuntos_limpios(), gold_v2={"v1"})


def test_fugas_rechaza_duplicados_y_casos_incompletos():
    c = conjuntos_limpios()
    c["train"].append(caso("t1", "P8", "Q"))
    with pytest.raises(ValueError, match="duplicado"):
        d.verificar_fugas(c)
    c = conjuntos_limpios()
    c["val"][0]["citing_id"] = ""
    with pytest.raises(ValueError, match="incompleto"):
        d.verificar_fugas(c)
