import json
import shutil

import pytest

from clasificacion_funcion import adaptador_proyecto_grado as ad
from clasificacion_funcion import cli

from chunks_falsos import (CodificadorFalso, crear_integrar, fragmentar_falso, parrafos,
                           preparar_cache)
from fuentes_falsas import FuentesFalsas

CITADOS = ["A", "B", "C", "D", "E", "F", "G", "H"]


@pytest.fixture
def entorno(tmp_path, monkeypatch):
    f = FuentesFalsas(tmp_path)
    monkeypatch.setattr(cli, "crear_fuentes", lambda: f)
    monkeypatch.setattr(cli, "_git", lambda: {"head": "abc", "dirty": False})
    monkeypatch.setattr(ad, "cargar_papers", lambda raw: {c: {} for c in CITADOS})
    monkeypatch.setattr(ad, "integrar", crear_integrar({c: parrafos(c) for c in CITADOS}))
    monkeypatch.setattr(ad, "fragmentar", fragmentar_falso)
    preparar_cache(tmp_path / "ocl", CITADOS, ausentes=("G",))
    return tmp_path


def correr(tmp, *extra, fabrica=CodificadorFalso):
    argv = ["recuperar", "--salida", str(tmp / "ev"), "--cache-ocl", str(tmp / "ocl"),
            "--cache", str(tmp / "emb"), "--raw", str(tmp / "raw"), "--regresion-a1", str(tmp / "a1.csv"),
            "--manifiesto-modelo", str(tmp / "mm.json"), "--manifiesto-ocl", str(tmp / "mo.json"), *extra]
    return cli.main(argv, fabrica_codificador=(lambda args: fabrica()) if fabrica else None)


def test_solo_validar_reporta_cobertura_sin_modelo(entorno, capsys):
    assert correr(entorno, "--solo-validar", fabrica=None) == 0
    out = capsys.readouterr().out
    assert '"gold_v2"' in out and '"cobertura_pct"' in out and not (entorno / "ev").exists()


def test_recuperar_escribe_top3_excluidos_y_manifiesto(entorno):
    assert correr(entorno) == 0
    ev = entorno / "ev"
    assert sorted(p.name for p in ev.iterdir()) == [
        "excluidos_recuperacion.csv", "manifiesto_recuperacion.json", "top3_eval_2015.csv",
        "top3_gold_v2.csv", "top3_train.csv", "top3_val.csv"]
    filas = (ev / "top3_train.csv").read_text().splitlines()
    assert filas[0] == "context_id,posicion,cited_id,chunk_id,seccion,perfil_seccion,paragraph_indices,puntaje"
    assert len(filas) == 1 + 3 * 3
    excl = (ev / "excluidos_recuperacion.csv").read_text()
    assert "gold_v2,e5,sin_descargar" in excl  # G sin descargar
    m = json.loads((ev / "manifiesto_recuperacion.json").read_text())
    assert m["git"] == {"head": "abc", "dirty": False}
    assert m["cobertura"]["gold_v2"]["con_chunks"] == 2 and set(m["huellas"]) == {
        "train", "val", "eval_2015", "gold_v2"}
    assert m["encoder"]["model_id"] == "falso/encoder" and "top3_train.csv" in m["salidas"]
    assert m["regresion_a1"] is None


def test_perfil_de_seccion_en_el_csv(entorno):
    correr(entorno)
    cuerpo = (entorno / "ev/top3_train.csv").read_text()
    assert ",introduction," in cuerpo or ",method," in cuerpo or ",results," in cuerpo


def test_no_sobrescribe(entorno, capsys):
    assert correr(entorno) == 0
    assert correr(entorno) == 2
    assert "No se sobrescribe" in capsys.readouterr().err


def test_regresion_a1_discrepante_aborta_sin_escribir(entorno, capsys):
    (entorno / "a1.csv").write_text(
        "context_id,metodo,posicion,cited_id,chunk_id,seccion,perfil_seccion,paragraph_indices,puntaje\n"
        "t1,scibert,1,A,p99999,x,otra,0,0.9\n", encoding="utf-8")
    assert correr(entorno) == 2
    assert "Regresion contra A1" in capsys.readouterr().err and not (entorno / "ev").exists()


def test_regresion_a1_coincidente_se_registra(entorno):
    assert correr(entorno) == 0
    filas = (entorno / "ev/top3_train.csv").read_text().splitlines()[1:]
    cab = "context_id,metodo,posicion,cited_id,chunk_id,seccion,perfil_seccion,paragraph_indices,puntaje\n"
    (entorno / "a1.csv").write_text(cab + "".join(
        f"{c[0]},scibert,{c[1]},{c[2]},{c[3]},{c[4]},{c[5]},{c[6]},{c[7]}\n"
        for c in (l.split(",") for l in filas)), encoding="utf-8")
    shutil.rmtree(entorno / "ev")
    assert correr(entorno) == 0
    m = json.loads((entorno / "ev/manifiesto_recuperacion.json").read_text())
    assert m["regresion_a1"]["contextos_comparados"] == 3 and m["regresion_a1"]["discrepancias"] == []


def test_sin_codificador_falla_claro(entorno, capsys):
    assert correr(entorno, fabrica=None) == 2
    assert "codificador" in capsys.readouterr().err
