import pytest

from clasificacion_funcion import servicio

from fuentes_falsas import FuentesFalsas


def ids(r, n):
    return [c["context_id"] for c in r["conjuntos"][n]]


def test_conjuntos_y_reglas_de_seleccion():
    r = servicio.cargar_conjuntos(FuentesFalsas())
    assert ids(r, "train") == ["t1", "t2", "t4"]  # t3 Ambiguo: abstencion
    assert ids(r, "val") == []                   # v1 No evaluable
    assert ids(r, "eval_2015") == ["e1", "e3"]   # e2 abstencion, e4 excluido, d1 es de 2014
    assert ids(r, "gold_v2") == ["e1", "e3", "e5"]
    assert r["estado"] == "provisional_etiquetas_haiku_no_gold_humano"
    assert "etiqueta" not in r["conjuntos"]["gold_v2"][0]  # ciego


def test_abstenciones_y_excluidos_se_declaran():
    r = servicio.cargar_conjuntos(FuentesFalsas())
    assert sorted((a["conjunto"], a["context_id"], a["motivo"]) for a in r["abstenciones"]) == [
        ("eval_2015", "e2", "Ambiguo"), ("train", "t3", "Ambiguo"), ("val", "v1", "No evaluable")]
    assert r["excluidos"] == [{"conjunto": "eval_2015", "context_id": "e4",
                               "motivo": "excluido_test_gold"}]


def test_casos_traen_indice_de_clase_y_texto_del_indice():
    r = servicio.cargar_conjuntos(FuentesFalsas())
    t1 = r["conjuntos"]["train"][0]
    assert (t1["indice"], t1["etiqueta"], t1["citing_id"], t1["cited_id"]) == (0, "Background", "P1", "A")
    assert t1["citation_context"] == "texto de t1 TARGETCIT fin" and t1["titulo"] == "titulo t1"


def test_gold_v2_solapa_con_eval_sin_ser_fuga_y_citados_requeridos():
    r = servicio.cargar_conjuntos(FuentesFalsas())
    assert r["fugas"]["total_fugas"] == 0
    assert r["citados_requeridos"] == sorted({"A", "B", "E", "G"})


def test_limite_recorta_cada_conjunto():
    r = servicio.cargar_conjuntos(FuentesFalsas(), limite=1)
    assert {n: len(c) for n, c in r["conjuntos"].items()} == {
        "train": 1, "val": 0, "eval_2015": 1, "gold_v2": 1}
    with pytest.raises(ValueError):
        servicio.cargar_conjuntos(FuentesFalsas(), limite=0)


def test_fuente_jurado_no_disponible_y_fuente_desconocida():
    with pytest.raises(NotImplementedError):
        servicio.cargar_conjuntos(FuentesFalsas(), "jurado")
    with pytest.raises(ValueError):
        servicio.cargar_conjuntos(FuentesFalsas(), "otra")


@pytest.mark.parametrize("mutar,mensaje", [
    (lambda f: f.split.update(t1="test"), "no pertenece al split train"),
    (lambda f: f.split.update(e1="val"), "no pertenece al split test"),
    (lambda f: f.split.update(e5="train"), "Gold v2"),
])
def test_pertenencia_a_splits_se_verifica(mutar, mensaje):
    f = FuentesFalsas()
    mutar(f)
    with pytest.raises(ValueError, match=mensaje):
        servicio.cargar_conjuntos(f)


def test_filas_haiku_deben_coincidir_con_el_split():
    f = FuentesFalsas()
    f.split_entrenamiento = lambda: {"train": ["t1", "t2", "t3"], "val": ["v1"]}
    with pytest.raises(ValueError, match="no coinciden"):
        servicio.cargar_conjuntos(f)
    f.split_entrenamiento = lambda: {"train": ["t1", "t2", "t3", "t4"], "val": ["t1"]}
    with pytest.raises(ValueError):
        servicio.cargar_conjuntos(f)


def test_fuga_entre_train_y_eval_bloquea():
    f = FuentesFalsas()
    f.ctx["e1"]["citing_id"] = "P1"  # el citante de t1 aparece tambien en eval
    with pytest.raises(ValueError, match="citing_id"):
        servicio.cargar_conjuntos(f)


def test_fuga_entre_train_y_gold_v2_bloquea():
    f = FuentesFalsas()
    f.ctx["e5"]["citing_id"] = "P1"  # citante de t1 (train) en el Gold v2
    with pytest.raises(ValueError, match="citing_id"):
        servicio.cargar_conjuntos(f)


def test_etiqueta_desconocida_bloquea():
    f = FuentesFalsas()
    original = f.filas_haiku
    f.filas_haiku = lambda: [{**original()[0], "etiqueta": "Inventada"}, *original()[1:]]
    with pytest.raises(ValueError, match="desconocida"):
        servicio.cargar_conjuntos(f)
