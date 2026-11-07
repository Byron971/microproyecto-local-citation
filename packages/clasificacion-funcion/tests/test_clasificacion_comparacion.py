import json

import pytest

from clasificacion_funcion import comparacion as c
from clasificacion_funcion import dominio, exportar


def gold_filas(n=10, extra=()):
    return [{"id": f"g{i}", "gold": dominio.CATEGORIAS[i % 3]} for i in range(n)] + list(extra)


def pred_filas(ids, indices, **kw):
    return [{"case_id": i, "status": "ok", "pred_index": p, "pred_label": dominio.CATEGORIAS[p], **kw}
            for i, p in zip(ids, indices)]


def test_leer_jsonl():
    assert c.leer_jsonl('{"a": 1}\n\n{"a": 2}\n') == [{"a": 1}, {"a": 2}]
    for malo in ("", "no json", "[1]"):
        with pytest.raises(ValueError):
            c.leer_jsonl(malo)


def test_gold_con_abstenciones_y_errores():
    gold, abst = c.indexar_gold(gold_filas(3, [{"id": "x", "gold": "Ambiguo"},
                                                {"context_id": "y", "gold": "No evaluable"}]))
    assert gold == {"g0": 0, "g1": 1, "g2": 2} and abst == {"Ambiguo": 1, "No evaluable": 1}
    for malo in ([{"id": "a", "gold": "Gap"}, {"id": "a", "gold": "Gap"}], [{"gold": "Gap"}],
                 [{"id": "a", "gold": "Inventada"}]):
        with pytest.raises(ValueError):
            c.indexar_gold(malo)


def test_predicciones_validan_estado_duplicados_y_discrepancias():
    assert c.indexar_predicciones(pred_filas(["a", "b"], [0, 8])) == {"a": 0, "b": 8}
    with pytest.raises(ValueError, match="incompleta"):
        c.indexar_predicciones([{**pred_filas(["a"], [0])[0], "status": "error"}])
    with pytest.raises(ValueError, match="duplicada"):
        c.indexar_predicciones(pred_filas(["a", "a"], [0, 0]))
    with pytest.raises(ValueError, match="discrepan"):
        c.indexar_predicciones([{**pred_filas(["a"], [0])[0], "pred_label": "Gap"}])


def test_puntuar_exacto_y_no_exacto():
    gold, _ = c.indexar_gold(gold_filas(6))
    pred = {f"g{i}": i % 3 for i in range(6)}
    m = c.puntuar(gold, pred)
    assert m["accuracy"] == 1.0 and m["n"] == 6 and m["f1_macro"] == pytest.approx(3 / 9)
    with pytest.raises(ValueError, match="no comparables"):
        c.puntuar(gold, {k: v for k, v in pred.items() if k != "g0"})
    parcial = {**{k: v for k, v in pred.items() if k != "g0"}, "extra": 1}
    m2 = c.puntuar(gold, parcial, exacto=False)
    assert m2["n"] == 5 and m2["ids_predichos"] == 6 and m2["ids_sin_gold_evaluable"] == 1
    with pytest.raises(ValueError):
        c.puntuar(gold, {"zzz": 1}, exacto=False)


def metricas_con(aciertos, n=6):
    gold = {f"g{i}": i % 3 for i in range(n)}
    pred = {k: (v if i < aciertos else (v + 1) % 3) for i, (k, v) in enumerate(gold.items())}
    return c.puntuar(gold, pred)


def test_delta_por_semilla_y_agregado():
    a = {1: metricas_con(6), 2: metricas_con(6)}
    b = {1: metricas_con(3), 2: metricas_con(0), 3: metricas_con(6)}
    d = c.delta(a, b, factor="x", nombre="n")
    assert d["semillas"] == [1, 2]  # solo las comunes
    assert d["por_semilla"]["1"]["accuracy"] == pytest.approx(-0.5)
    assert d["agregado"]["accuracy"]["media"] == pytest.approx(-0.75)
    assert d["agregado"]["accuracy"]["desv"] == pytest.approx(0.25 * 2 ** 0.5)
    assert c.delta({1: a[1]}, {2: a[1]}) is None


def matriz():
    m = {}
    for e, base in (("scibert", 6), ("specter", 3)):
        for i, extra in (("A", 0), ("B", 1), ("B_sin_seccion", 0), ("B_barajada", 0)):
            if e == "specter" and i in ("B_sin_seccion", "B_barajada"):
                continue
            for s in (1, 2, 3):
                m[(e, i, s)] = metricas_con(min(6, base + extra * (s % 2)))
    return m


def test_comparar_estructura_y_deltas():
    comp = c.comparar(matriz(), {("scibert", s): metricas_con(2) for s in (1, 2, 3)})
    assert set(comp["celdas"]) == {"scibert|A", "scibert|B", "scibert|B_sin_seccion",
                                   "scibert|B_barajada", "specter|A", "specter|B"}
    assert comp["celdas"]["scibert|A"]["agregado"]["semillas"] == 3
    factores = [(d["factor"], d["nombre"]) for d in comp["deltas"]]
    assert ("entrada", "scibert|A->B") in factores and ("entrada", "specter|A->B") in factores
    assert ("encoder", "SciBERT->SPECTER|A") in factores and ("encoder", "SciBERT->SPECTER|B") in factores
    assert ("ablacion", "B->B_sin_seccion") in factores and ("ablacion", "B->B_barajada") in factores
    assert ("sondeo_secciones_barajadas", "scibert|B->B_con_eval_barajado") in factores
    por_nombre = {d["nombre"]: d for d in comp["deltas"]}
    assert por_nombre["SciBERT->SPECTER|A"]["agregado"]["accuracy"]["media"] < 0  # SPECTER peor
    assert comp["estado"] == "provisional_etiquetas_haiku_no_gold_humano" and comp["advertencias"]
    json.dumps(comp)


def test_comparar_omite_ablaciones_y_sondeo_ausentes():
    m = {k: v for k, v in matriz().items() if k[1] in ("A", "B")}
    comp = c.comparar(m)
    assert {d["factor"] for d in comp["deltas"]} == {"entrada", "encoder"}


def test_csv_tiene_una_fila_por_celda_y_delta():
    comp = c.comparar(matriz())
    filas = c.filas_csv(comp)
    assert len(filas) == len(comp["celdas"]) + len(comp["deltas"])
    assert all(set(f) == set(c.COLUMNAS_CSV) for f in filas)
    assert {f["tipo"] for f in filas} >= {"celda", "delta_entrada", "delta_encoder", "delta_ablacion"}


# ---- config a4_factorial_v1
def manifiesto(encoder, entrada, semilla, **kw):
    base = {"encoder": encoder, "entrada": entrada, "semilla": semilla, "training_labels": "Haiku",
            "data_use": "provisional_only", "checkpoint_sha256": ("c" + encoder[0] + entrada) * 21 + "c",
            "input_spec_sha256": ("5" + entrada) * 32,
            "entradas": {"train_ids_sha256": "a" * 64, "train_labels_sha256": "b" * 64}}
    return {**base, **kw}


def cuatro(semilla=42, **kw):
    return {(e, i): manifiesto(e, i, semilla, **kw) for e in ("scibert", "specter") for i in ("A", "B")}


def test_config_a4_forma_y_rutas_relativas():
    cfg = exportar.config_a4(cuatro(), 42)
    assert cfg["schema_version"] == "a4_factorial_v1" and cfg["data_use"] == "provisional_only"
    nombres = [v["name"] for v in cfg["variants"]]
    assert sorted(nombres) == ["SPECTER_A_s42", "SPECTER_B_s42", "SciBERT_A_s42", "SciBERT_B_s42"]
    v = next(v for v in cfg["variants"] if v["name"] == "SciBERT_B_s42")
    assert v["predictions"] == "scibert_B_42/predicciones_eval.jsonl" and not v["predictions"].startswith("/")
    assert v["encoder"] == "SciBERT" and v["input"] == "B" and v["training_labels"] == "Haiku"
    assert len(v["train_ids_sha256"]) == 64 and v["train_ids_sha256"] == "a" * 64


def test_config_a4_rechaza_matriz_incompleta_y_material_no_provisional():
    incompleta = cuatro()
    incompleta.pop(("specter", "B"))
    with pytest.raises(ValueError, match="incompleta"):
        exportar.config_a4(incompleta, 42)
    with pytest.raises(ValueError, match="provisional"):
        exportar.config_a4(cuatro(training_labels="Jurado"), 42)
    with pytest.raises(ValueError, match="inconsistente"):
        exportar.config_a4(cuatro(42), 7)


def test_config_pasa_load_config_de_la_rama_de_john(tmp_path):
    a4 = pytest.importorskip("src.evaluation.commercial.a4_factorial_benchmark")
    ruta = tmp_path / "cfg.json"
    ruta.write_text(json.dumps(exportar.config_a4(cuatro(), 42)), encoding="utf-8")
    arms = a4.load_config(ruta)
    assert len(arms) == 4 and {a["training_labels"] for a in arms} == {"Haiku"}
