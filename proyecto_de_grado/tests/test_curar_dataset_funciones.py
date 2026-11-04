"""Pruebas del dataset de funciones y de fugas hacia el Test Gold (issues #95 y #96)."""
import csv
from pathlib import Path

import pytest

from proyecto_de_grado.src.data.curar_dataset_funciones import a_ciegas, anio_citante, asignar_uso, curar, fugas
from proyecto_de_grado.src.data.validar_splits import check_gold_membership, load_split_index

RAIZ = Path(__file__).resolve().parents[2]
RAW = RAIZ / "data" / "raw"
MANIFIESTO = RAIZ / "proyecto_de_grado" / "anotacion" / "test_gold_v2" / "manifiesto_ids.csv"
DATASET = RAIZ / "data" / "dataset_funciones" / "v1" / "dataset_funciones_v1.csv"


def test_anio_citante():
    assert anio_citante("P15-1122_W11-0908_0") == 2015
    assert anio_citante("W99-0101_J93-2004_1") == 1999
    assert anio_citante("A00-1012_P98-2140_0") == 2000


@pytest.mark.parametrize("voto, particion, anio, grupo, tanda, esperado", [
    ("Basis", "test", 2015, "testgold", "1", "test_gold_t1"),
    ("SIN_CONSENSO", "val", 2014, "calibracion3", "", "calibracion"),
    ("SIN_CONSENSO", "train", 2012, "", "", "excluida_sin_consenso"),
    ("Ambiguo", "train", 2012, "", "", "excluida_ambigua"),
    ("Basis", "test", 2015, "", "", "reserva_test"),
    ("Basis", "val", 2014, "", "", "validacion"),
    ("Basis", "sin_particion", 2014, "", "", "validacion"),
    ("Basis", "train", 2011, "", "", "entrenamiento"),
    ("Basis", "sin_particion", 2005, "", "", "entrenamiento"),
])
def test_asignar_uso(voto, particion, anio, grupo, tanda, esperado):
    assert asignar_uso(voto, particion, anio, grupo, tanda) == esperado


def test_ninguna_cita_de_test_llega_a_entrenamiento():
    """Una cita de 2015 que no está en el Test Gold queda en reserva, aunque no figure en la partición oficial."""
    for particion in ("test", "sin_particion"):
        assert asignar_uso("Background", particion, 2015) == "reserva_test"


def test_fugas_detecta_citante_compartido():
    contextos = {"P12-1_X_0": {"citing_id": "P12-1", "refid": "X"}, "P12-1_Y_0": {"citing_id": "P12-1", "refid": "Y"}}
    jurado = [{"context_id": c, "voto": "Basis", "jueces_de_acuerdo": "3"} for c in contextos]
    manifiesto = {"P12-1_Y_0": {"grupo": "testgold", "tanda": "1"}}
    filas = curar(jurado, {}, contextos, manifiesto, set())
    assert fugas(filas) == {"citantes": 1, "pares": 0, "contextos": 0}


def test_copia_publicable_oculta_el_voto_de_lo_que_anotan_personas():
    filas = [{"uso": u, "etiqueta_jurado": "Basis", "jueces_de_acuerdo": "3"}
             for u in ("test_gold_t1", "calibracion", "entrenamiento", "reserva_test")]
    assert [f["etiqueta_jurado"] for f in a_ciegas(filas)] == ["", "", "Basis", "Basis"]
    assert filas[0]["etiqueta_jurado"] == "Basis"          # no modifica la lista original


@pytest.mark.skipif(not (RAW / "test.json").exists() or not MANIFIESTO.exists(),
                    reason="requiere data/raw (dvc pull) y el manifiesto del Test Gold")
def test_test_gold_real_esta_completo_en_test():
    indice = load_split_index(RAW)
    with open(MANIFIESTO, encoding="utf-8") as f:
        filas = list(csv.DictReader(f))
    gold = [type("Caso", (), {"id": r["context_id"], "metadata": {}}) for r in filas if r["grupo"] == "testgold"]
    assert len(gold) == len({c.id for c in gold})        # sin repetidas
    assert check_gold_membership(gold, indice) == []


@pytest.mark.skipif(not DATASET.exists(), reason="requiere data/dataset_funciones (dvc pull)")
def test_dataset_real_sin_fugas():
    with open(DATASET, encoding="utf-8") as f:
        filas = list(csv.DictReader(f))
    assert fugas(filas) == {"citantes": 0, "pares": 0, "contextos": 0}
    assert not [f for f in filas if f["uso"] in ("entrenamiento", "validacion") and f["anio_citante"] == "2015"]
    assert not [f for f in filas if f["uso"].startswith("test_gold") and f["etiqueta_jurado"]]   # publicado a ciegas
