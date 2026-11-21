"""Comparador M/S sobre predicciones sintéticas, sin datos privados."""
import json

import pytest

from scripts.evaluar_predicciones_ms_pareadas import cargar_predicciones, comparar, metricas


def test_macro_f1_9_y_matriz():
    r = metricas(["Background", "Evidence"], ["Background", "Background"])
    assert r["n"] == 2
    assert r["accuracy"] == 0.5
    assert r["por_clase"]["Background"]["soporte"] == 1
    assert r["matriz_confusion"][6][0] == 1
    assert r["macro_f1_9_clases"] == round((2/3)/9, 6)


def test_empareja_por_id_y_fuente():
    gold = {
        "a": {"etiqueta": "Background", "evaluable": "True", "fuente": "concordancia"},
        "b": {"etiqueta": "Evidence", "evaluable": "True", "fuente": "solo_opus"},
        "c": {"etiqueta": "No evaluable", "evaluable": "False", "fuente": "una_anotacion"},
        "d": {"etiqueta": "Gap", "evaluable": "True", "fuente": "una_anotacion"},
    }
    m = {"d": "Gap", "a": "Background", "b": "Background"}
    s = {"b": "Evidence", "a": "Background"}
    r = comparar(gold, m, s)
    assert r["ids_pareados_evaluables"] == 2
    assert r["solo_M_evaluables"] == 1
    assert r["resultados"]["concordancia"]["n"] == 1
    assert r["resultados"]["solo_opus"]["desacuerdos_predicciones_M_S"] == 1


def test_sin_solape_no_inventa_metricas():
    with pytest.raises(ValueError, match="No hay contextos"):
        comparar({"x": {"etiqueta": "Background", "evaluable": "True", "fuente": "concordancia"}},
                 {"a": "Background"}, {"b": "Evidence"})


def test_duplicado_y_clase_invalida(tmp_path):
    p = tmp_path / "pred.jsonl"
    fila = json.dumps({"context_id": "x", "pred_label": "Evidence"})
    p.write_text(fila + "\n" + fila + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="duplicado"):
        cargar_predicciones(p)
    p.write_text(json.dumps({"context_id": "x", "pred_label": "Desconocido"}), encoding="utf-8")
    with pytest.raises(ValueError, match="clase válida"):
        cargar_predicciones(p)


def test_notebook_10_pred_y_pred_ph(tmp_path):
    p = tmp_path / "pred_gold.jsonl"
    p.write_text(
        json.dumps({"context_id": "a", "pred": 0, "pred_ph": 6, "probs": [0.0] * 9}) + "\n"
        + json.dumps({"context_id": "b", "pred": 3, "pred_ph": 3, "probs": [0.0] * 9}) + "\n",
        encoding="utf-8"
    )
    assert cargar_predicciones(p, "pred") == {"a": "Background", "b": "Comparison"}
    assert cargar_predicciones(p, "pred_ph") == {"a": "Evidence", "b": "Comparison"}


def test_notebook_10_indices_invalidos(tmp_path):
    p = tmp_path / "pred_gold.jsonl"
    for valor in (-1, 9, "6", None):
        p.write_text(json.dumps({"context_id": "a", "pred_ph": valor}), encoding="utf-8")
        with pytest.raises(ValueError, match="índice válido"):
            cargar_predicciones(p, "pred_ph")
