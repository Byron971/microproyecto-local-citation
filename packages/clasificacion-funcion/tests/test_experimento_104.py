"""Evaluacion, bootstrap y perdida de `experimento_104` (sin entrenar encoders reales)."""
import pytest

pytest.importorskip("torch")
pytest.importorskip("mlflow")
pytest.importorskip("pandas")
pytest.importorskip("sklearn")

from clasificacion_funcion import dominio, experimento_104 as ex, seleccion_datos as sd  # noqa: E402


def _fila(cid, etiqueta, sonnet=None, haiku=None, p=0.9):
    dist = [0.0] * 11
    dist[dominio.normalizar_etiqueta(etiqueta)] = p
    dist[(dominio.normalizar_etiqueta(etiqueta) + 1) % 9] = 1 - p
    return {"context_id": cid, "citing_id": cid, "etiqueta": etiqueta, "etiqueta_entrenamiento": etiqueta,
            "fuente": "qlora", "qlora": {"label": etiqueta, "p": p, "dist": dist},
            "sonnet": {"label": sonnet, "confianza": "Alta"} if sonnet else None, "haiku": haiku, "gpt": None}


def _fuentes():
    return sd.Fuentes(qlora={}, jurado={}, haiku={}, haiku_train=set(), haiku_val={"a"}, gpt={"b": "Gap"},
                      contextos={}, ids_gold=set())


def test_conjuntos_eval_agrega_val_mixta_y_val_sonnet():
    c = dominio.CATEGORIAS
    v = [_fila("a", c[0], sonnet=c[1], haiku=c[0]), _fila("b", c[2], sonnet=c[2]), _fila("c", c[3])]
    sets = ex.conjuntos_eval(v, _fuentes())
    assert [x["etiqueta_entrenamiento"] for x in sets["val_mixta"]] == [c[0], c[2], c[3]]
    assert [x["etiqueta_entrenamiento"] for x in sets["val_sonnet"]] == [c[1], c[2]]  # sin Sonnet: fuera
    assert {x["context_id"] for x in sets["dev_haiku"]} == {"a"}


def test_con_modo_perdida_kd_y_ponderado_agregan_campos():
    c = dominio.CATEGORIAS
    caso = {"context_id": "a", "indice": 0, "_fila": _fila("a", c[0], p=0.8)}
    assert abs(sum(ex.con_modo_perdida([caso], "kd")[0]["objetivo"]) - 1) < 1e-9
    assert ex.con_modo_perdida([caso], "ponderado")[0]["peso"] == 0.8
    assert "objetivo" not in ex.con_modo_perdida([caso], "duro")[0]


def test_bootstrap_pareado_detecta_diferencia_y_es_reproducible():
    verdad = [i % 3 for i in range(90)]
    buena = list(verdad)
    mala = [(v + 1) % 3 if i % 2 else v for i, v in enumerate(verdad)]
    r = ex.bootstrap_diferencia(buena, mala, verdad, n=200, semilla=1)
    assert r["diferencia"] > 0 and r["ic95"][0] > 0 and r["prob_a_mayor"] == 1.0
    assert r == ex.bootstrap_diferencia(buena, mala, verdad, n=200, semilla=1)
    igual = ex.bootstrap_diferencia(buena, buena, verdad, n=50, semilla=1)
    assert igual["diferencia"] == 0 and igual["ic95"] == (0.0, 0.0)
    with pytest.raises(ValueError):
        ex.bootstrap_diferencia([0], [0, 1], [0, 1])
