"""Pruebas puras de agregados; no usa archivos Gold reales."""
from scripts.auditar_metricas_provisionales import auditar


def datos():
    gold = [
        {"context_id": "a", "evaluable": "True", "fuente": "concordancia"},
        {"context_id": "b", "evaluable": "True", "fuente": "una_anotacion"},
        {"context_id": "c", "evaluable": "False", "fuente": "solo_opus"},
        {"context_id": "d", "evaluable": "True", "fuente": "solo_opus"},
    ]
    rows = []
    for p in ("M", "S"):
        for sub, n in (("todo_cob", 3), ("humano_cob", 2), ("concordancia_cob", 1)):
            rows.append({"pista": p, "subconjunto": sub, "n": str(n), "f1_macro": "0.5",
                         "f1_micro": "0.5", "f1_weighted": "0.5", "accuracy": "0.5"})
    top3 = {"estado": "comparacion_tecnica_train_sin_gold",
            "validacion": {"contextos": 3, "articulos": 1},
            "comparacion": {"micro": {"solape_3": 0.4}},
            "metricas_relevancia": "no calculadas: sin gold validado"}
    return rows, gold, top3


def test_agregados_validos_no_certifica_gold():
    r = auditar(*datos())
    assert r["integridad_agregados"]
    assert r["resultados_historicos"]["M:todo_cob"]["casos_no_cubiertos"] == 0
    assert r["recuperacion_train_sin_gold"]["solape_top3_scibert_bm25"] == 0.4
    assert len(r["limitaciones"]) >= 4


def test_cobertura_ausente_no_es_error():
    rows, gold, top3 = datos()
    rows[0]["n"] = "2"
    rows[3]["n"] = "2"
    r = auditar(rows, gold, top3)
    assert r["integridad_agregados"]
    assert r["resultados_historicos"]["M:todo_cob"]["casos_no_cubiertos"] == 1
    assert not r["errores"]


def test_rechaza_n_mayor_a_gold():
    rows, gold, top3 = datos()
    rows[0]["n"] = "999"
    r = auditar(rows, gold, top3)
    assert not r["integridad_agregados"]
    assert any("excede" in x for x in r["errores"])


def test_rechaza_f1_invalido():
    rows, gold, top3 = datos()
    rows[0]["f1_macro"] = "3"
    r = auditar(rows, gold, top3)
    assert not r["integridad_agregados"]
