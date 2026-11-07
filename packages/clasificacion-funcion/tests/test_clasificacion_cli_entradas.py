import hashlib
import json

import pytest

from clasificacion_funcion import adaptador_proyecto_grado as ad
from clasificacion_funcion import cli, dominio

from chunks_falsos import (CodificadorFalso, crear_integrar, fragmentar_falso, parrafos,
                           preparar_cache)
from fuentes_falsas import FuentesFalsas

CITADOS = ["A", "B", "C", "D", "E", "F", "G", "H"]


@pytest.fixture
def entorno(tmp_path, monkeypatch):
    f = FuentesFalsas(tmp_path)
    monkeypatch.setattr(cli, "crear_fuentes", lambda: f)
    monkeypatch.setattr(cli, "_git", lambda: {"head": "abc", "dirty": False})
    monkeypatch.setattr(ad, "cargar_papers", lambda raw: {
        c: {"title": f"Titulo {c}", "abstract": f"Resumen {c}"} for c in CITADOS})
    monkeypatch.setattr(ad, "integrar", crear_integrar({c: parrafos(c) for c in CITADOS}))
    monkeypatch.setattr(ad, "fragmentar", fragmentar_falso)
    preparar_cache(tmp_path / "ocl", CITADOS, ausentes=("G",))
    rec = ["recuperar", "--salida", str(tmp_path / "top3"), "--cache-ocl", str(tmp_path / "ocl"),
           "--cache", str(tmp_path / "emb"), "--raw", str(tmp_path / "raw"),
           "--regresion-a1", str(tmp_path / "no.csv"), "--manifiesto-modelo", str(tmp_path / "mm.json"),
           "--manifiesto-ocl", str(tmp_path / "mo.json")]
    assert cli.main(rec, fabrica_codificador=lambda args: CodificadorFalso()) == 0
    return tmp_path


def correr(tmp, *extra):
    return cli.main(["entradas", "--top3", str(tmp / "top3"), "--salida", str(tmp / "ev"),
                     "--artefactos", str(tmp / "art"), "--cache-ocl", str(tmp / "ocl"),
                     "--raw", str(tmp / "raw"), "--manifiesto-ocl", str(tmp / "mo.json"), *extra])


def test_escribe_evidencias_y_entradas(entorno):
    assert correr(entorno, "--umbral-cobertura", "50") == 0
    ev, art = entorno / "ev", entorno / "art"
    assert sorted(p.name for p in ev.iterdir()) == [
        "excluidos.csv", "gold_eval_2015_haiku.jsonl", "ids_interseccion_eval_2015.txt",
        "ids_interseccion_gold_v2.txt", "ids_interseccion_train.txt", "ids_interseccion_val.txt",
        "manifiesto_entradas.json"]
    assert sorted(p.name for p in art.iterdir()) == [
        f"entradas_{n}.jsonl" for n in ("eval_2015", "gold_v2", "train", "val")]
    assert (ev / "ids_interseccion_train.txt").read_text() == "t1\nt2\nt4\n"
    assert (ev / "ids_interseccion_gold_v2.txt").read_text() == "e1\ne3\n"
    assert (ev / "excluidos.csv").read_text().splitlines()[0] == "conjunto,context_id,motivo,etiqueta"
    entrada = json.loads((art / "entradas_train.jsonl").read_text().splitlines()[0])
    assert entrada["top3"][0]["texto"] and entrada["titulo"] == "Titulo A" and "chunks" not in entrada


def test_manifiesto_hashes_y_cobertura(entorno):
    correr(entorno, "--umbral-cobertura", "50")
    m = json.loads((entorno / "ev/manifiesto_entradas.json").read_text())
    assert m["train_ids_sha256"] == dominio.sha_ids(["t1", "t2", "t4"])
    assert m["train_labels_sha256"] == dominio.sha_etiquetas({"t1": 0, "t2": 1, "t4": 6})
    assert m["input_spec_sha256"]["A"] == dominio.sha_especificacion(dominio.especificacion_entrada("A", 512))
    assert set(m["input_spec_sha256"]) == {"A", "B", "B_sin_seccion"}
    assert set(m["texto_sha256"]) == {"A", "B", "B_sin_seccion"}
    assert m["cobertura"]["eval_2015"]["interseccion"] == 2 and m["git"]["head"] == "abc"
    assert m["bloqueos_cobertura"] == [] and m["estado"] == "provisional_etiquetas_haiku_no_gold_humano"
    gold = (entorno / "ev/gold_eval_2015_haiku.jsonl").read_bytes()
    assert m["gold_eval_2015_haiku_sha256"] == hashlib.sha256(gold).hexdigest()


def test_gold_exportado_pasa_index_gold(entorno):
    paired = pytest.importorskip("src.evaluation.commercial.paired_benchmark")
    correr(entorno, "--umbral-cobertura", "50")
    filas = [json.loads(l) for l in (entorno / "ev/gold_eval_2015_haiku.jsonl").read_text().splitlines()]
    assert {k: v["gold"] for k, v in paired.index_gold(filas).items()} == {"e1": 2, "e3": 3}


def test_cobertura_bajo_umbral_se_registra_como_bloqueo(entorno, capsys):
    assert correr(entorno, "--umbral-cobertura", "99") == 0
    assert "BLOQUEO" in capsys.readouterr().out
    m = json.loads((entorno / "ev/manifiesto_entradas.json").read_text())
    assert {b["conjunto"] for b in m["bloqueos_cobertura"]} == {"gold_v2"}  # 2/3; train y eval cubren 100%
    assert "no modificar la regla de A1" in m["bloqueos_cobertura"][0]["accion"]


def test_exigir_cobertura_devuelve_3_pero_escribe(entorno):
    assert correr(entorno, "--umbral-cobertura", "99", "--exigir-cobertura") == 3
    assert (entorno / "ev/manifiesto_entradas.json").exists()


def test_solo_validar_no_escribe(entorno):
    assert correr(entorno, "--solo-validar") == 0
    assert not (entorno / "ev").exists() and not (entorno / "art").exists()


def test_no_sobrescribe_y_falta_top3(entorno, capsys):
    assert correr(entorno, "--umbral-cobertura", "50") == 0
    assert correr(entorno, "--umbral-cobertura", "50") == 2
    assert "No se sobrescribe" in capsys.readouterr().err
    (entorno / "top3/top3_val.csv").unlink()
    assert correr(entorno, "--solo-validar") == 2
    assert "recuperar" in capsys.readouterr().err
