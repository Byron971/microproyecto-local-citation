"""Pruebas de cobertura y viabilidad de los datos (issue #125)."""
import csv
import json
from pathlib import Path

import pytest

from proyecto_de_grado.src.data.cobertura_datos import (concentracion, duplicados, gamma_q, medir_pares,
                                                        medir_particiones, proyectar, prueba_muestra, wilson)

RAIZ = Path(__file__).resolve().parents[2]
RAW = RAIZ / "data" / "raw"
DATASET = RAIZ / "data" / "dataset_funciones" / "v1" / "dataset_funciones_v1.csv"


def ctx(citante, citado, texto="x TARGETCIT y"):
    return {"citing_id": citante, "refid": citado, "masked_text": texto}


def test_par_completo_exige_marca_citante_y_titulo_y_resumen_del_citado():
    papers = {"P12-1": {"title": "a", "abstract": "b"}, "N10-1": {"title": "c", "abstract": "d"},
              "N10-2": {"title": "c", "abstract": "  "}}
    contextos = {"1": ctx("P12-1", "N10-1"), "2": ctx("P12-1", "N10-2"),
                 "3": ctx("P12-1", "N10-1", "sin marca"), "4": ctx("P12-9", "N10-1")}
    m = medir_pares(contextos, papers)
    assert m["par_completo"] == 1
    assert m["citado_con_titulo_y_resumen"] == 3
    assert m["con_targetcit"] == 3
    assert m["citante_en_papers"] == 3


def test_particiones_detectan_anio_fuera_de_rango_y_cruces():
    contextos = {"a": ctx("P12-1", "X"), "b": ctx("P14-1", "X"), "c": ctx("P15-1", "X"),
                 "d": ctx("P15-2", "Y"), "e": ctx("P05-1", "Y"), "f": ctx("P13-3", "Z")}
    por_contexto = {"a": "train", "b": "val", "c": "test", "d": "train", "f": "val"}   # d y f, fuera de su rango
    m = medir_particiones(contextos, por_contexto)
    assert m["por_split"]["train"]["anio_fuera_de_rango"] == 1
    assert m["por_split"]["val"]["anio_fuera_de_rango"] == 1   # 2013 en val: por debajo del rango
    assert m["por_split"]["test"].get("anio_fuera_de_rango", 0) == 0
    assert m["por_split"]["sin_particion"]["2000-2008"] == 1
    assert m["cruces"]["train-test"] == {"citantes": 0, "citados": 1, "pares": 0}


def test_duplicados_separan_fuga_real_de_riesgo_futuro():
    contextos = {"g1": ctx("P15-1", "A", "mismo texto"), "t1": ctx("P13-1", "A", "mismo texto"),
                 "g2": ctx("P15-2", "B", "otro texto"), "v2": ctx("P14-2", "B", "otro texto"),
                 "s1": ctx("P12-3", "C", "cita doble"), "s2": ctx("P12-3", "D", "cita doble")}
    por_contexto = {"g1": "test", "t1": "train", "g2": "test", "v2": "val", "s1": "train", "s2": "train"}
    usos = {"g1": "test_gold_t1", "t1": "entrenamiento", "g2": "test_gold_t3"}   # v2 no está en el dataset
    d = duplicados(contextos, por_contexto, usos)
    assert d["grupos"] == 3 and d["mismo_citante"] == 1 and d["grupos_entre_particiones"] == 2
    assert d["gold_en_modelo"] == ["g1"]
    assert d["gold_fuera_de_test"] == ["g2"]
    assert duplicados(contextos, por_contexto, usos | {"v2": "validacion"})["gold_en_modelo"] == ["g1", "g2"]
    contextos |= {"g3": ctx("P15-3", "E", "tercer texto"), "t3": ctx("P11-3", "E", "tercer texto")}
    d = duplicados(contextos, por_contexto | {"g3": "test", "t3": "train"}, usos | {"g3": "test_gold_t2"})
    assert d["gold_fuera_de_test"] == ["g2", "g3"]          # gemelo en train que todavía no está en el dataset


def test_concentracion():
    c = concentracion(["A"] * 6 + ["B"] * 2 + ["C"] + ["D"])
    assert c["articulos"] == 4 and c["maximo"] == 6 and c["mediana"] == 1.5
    assert c["parte_top10"] == pytest.approx(0.6)        # el 10 % de 4 artículos redondea a 1
    c = concentracion(["A"] * 5 + ["B"] * 3 + [f"x{i}" for i in range(13)])
    assert c["parte_top10"] == pytest.approx(8 / 21)     # el 10 % de 15 artículos redondea hacia arriba, a 2


def test_valor_p_de_ji_cuadrado():
    assert gamma_q(1.5, 7.815 / 2) == pytest.approx(0.05, abs=1e-3)   # valor crítico con 3 grados de libertad
    assert gamma_q(1.5, 0.0) == 1.0
    assert gamma_q(1.0, 2.0 / 2) == pytest.approx(0.3679, abs=1e-4)  # 2 grados de libertad: p = exp(-χ²/2)


def test_prueba_muestra_distingue_muestra_al_azar_de_sesgada():
    poblacion = {f"t{i}": "train" for i in range(600)} | {f"v{i}": "val" for i in range(400)}
    proporcional = {f"t{i}" for i in range(60)} | {f"v{i}" for i in range(40)}
    sesgada = {f"t{i}" for i in range(100)}
    assert prueba_muestra(proporcional, poblacion)["p"] > 0.9
    assert prueba_muestra(sesgada, poblacion)["p"] < 0.001
    assert prueba_muestra(proporcional | {"fuera"}, poblacion)["fuera_de_poblacion"] == 1
    r = prueba_muestra({f"t{i}" for i in range(70)} | {f"v{i}" for i in range(30)}, poblacion)
    assert r["gl"] == 1 and r["chi2"] == pytest.approx(100 / 60 + 100 / 40)   # 70/30 frente a 60/40 esperados
    assert r["p"] == pytest.approx(0.0412, abs=1e-4)


def test_wilson():
    lo, hi = wilson(411, 500)
    assert lo == pytest.approx(0.786, abs=1e-3) and hi == pytest.approx(0.853, abs=1e-3)
    assert wilson(0, 0) == (0.0, 0.0)


def test_proyeccion_marca_lo_que_no_alcanza():
    filas = {f["clase"]: f for f in proyectar({"Background": 900, "Basis": 10, "Gap": 830}, 1000, 2400)}
    assert filas["Background"]["alcanza"] == "sí"          # 2.160 esperadas, todo el intervalo sobre 2.000
    assert filas["Basis"]["alcanza"] == "no"
    assert filas["Gap"]["alcanza"] == "incierto"           # 1.992 esperadas: el intervalo cruza 2.000
    assert filas["Gap"]["proyeccion"] == pytest.approx(1992)


@pytest.mark.skipif(not (RAW / "contexts.json").exists() or not DATASET.exists(),
                    reason="requiere data/raw y data/dataset_funciones (dvc pull)")
def test_corpus_real_sin_fugas_de_texto_hacia_el_test_gold():
    from proyecto_de_grado.src.data.validar_splits import load_split_index
    contextos = json.loads((RAW / "contexts.json").read_text(encoding="utf-8-sig"))
    por_contexto = load_split_index(RAW).by_context
    with open(DATASET, encoding="utf-8") as f:
        usos = {r["context_id"]: r["uso"] for r in csv.DictReader(f)}
    assert duplicados(contextos, por_contexto, usos)["gold_en_modelo"] == []
    cruces = medir_particiones(contextos, por_contexto)["cruces"]
    assert all(v["citantes"] == 0 and v["pares"] == 0 for v in cruces.values())
