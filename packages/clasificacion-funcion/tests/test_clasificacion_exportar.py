"""Compatibilidad con `paired_benchmark.index_gold` / `index_predictions` (rama de John)."""
import json

import pytest

from clasificacion_funcion import dominio, exportar

paired = pytest.importorskip("src.evaluation.commercial.paired_benchmark")
_validate_scores = pytest.importorskip("src.evaluation.commercial.metrics")._validate_scores


def entrada(i, indice, ctx="se usa TARGETCIT aqui"):
    return {"context_id": f"c{i}", "citing_id": f"P{i}", "cited_id": f"Q{i}",
            "citation_context": ctx, "indice": indice}


def test_gold_pasa_index_gold_con_las_9_clases():
    entradas = [entrada(i, i) for i in range(9)]
    filas = exportar.filas_gold(list(reversed(entradas)))
    assert [f["id"] for f in filas] == [f"c{i}" for i in range(9)]  # ordenado
    indexado = paired.index_gold([json.loads(l) for l in exportar.jsonl_texto(filas).splitlines()])
    assert {k: v["gold"] for k, v in indexado.items()} == {f"c{i}": i for i in range(9)}
    assert indexado["c3"]["citing_id"] == "P3" and indexado["c3"]["cited_id"] == "Q3"


def test_gold_exige_etiqueta_y_targetcit():
    with pytest.raises(ValueError, match="sin etiqueta"):
        exportar.fila_gold({**entrada(1, 0), "indice": None})
    with pytest.raises(ValueError, match="TARGETCIT"):
        paired.index_gold([exportar.fila_gold(entrada(1, 0, ctx="sin marca"))])


def scores(ganador, resto=0.01):
    s = [resto] * 9
    s[ganador] = 1 - resto * 8
    return s


def pred(i, ganador, **kw):
    datos = {"model_id": "allenai/scibert", "model_version": "a" * 40, "experiment_id": "exp",
             "latency_ms": 1.5, "gold_manifest_sha256": "g" * 64, **kw}
    return exportar.fila_prediccion(f"c{i}", scores(ganador), **datos)


def test_predicciones_pasan_index_predictions():
    filas = [pred(i, i) for i in range(9)]
    indexado = paired.index_predictions(filas, {f"c{i}" for i in range(9)}, "A")
    assert indexado == {f"c{i}": i for i in range(9)}
    assert filas[0]["pred_label"] == dominio.CATEGORIAS[0] and filas[0]["status"] == "ok"


def test_predicciones_no_llevan_la_etiqueta_verdadera():
    f = pred(1, 4)
    assert set(f) == set(exportar.ESQUEMA_PREDICCION)
    assert not {"gold", "label", "truth", "etiqueta", "indice"} & set(f)


def test_las_metricas_aceptan_los_scores_9():
    # `metrics._validate_scores` exige 9 numeros entre 0 y 1
    assert len(_validate_scores(pred(1, 2)["scores_9"])) == 9


def test_empate_elige_el_menor_indice_y_roundtrip_json():
    f = exportar.fila_prediccion("c1", [0.5, 0.5] + [0.0] * 7, model_id="m", model_version="v",
                                 experiment_id="e", latency_ms=0, gold_manifest_sha256=None)
    assert f["pred_index"] == 0
    assert json.loads(exportar.jsonl_texto([f]).strip()) == f


@pytest.mark.parametrize("malos", [[0.1] * 8, [0.1] * 10, [1.5] + [0] * 8, [-0.1] + [0] * 8,
                                   [float("nan")] + [0] * 8, [True] + [0] * 8, "no es lista"])
def test_scores_invalidos(malos):
    with pytest.raises(ValueError):
        exportar.fila_prediccion("c1", malos, model_id="m", model_version="v", experiment_id="e",
                                 latency_ms=0, gold_manifest_sha256=None)


def test_case_id_vacio():
    with pytest.raises(ValueError):
        exportar.fila_prediccion(" ", scores(0), model_id="m", model_version="v",
                                 experiment_id="e", latency_ms=0, gold_manifest_sha256=None)
