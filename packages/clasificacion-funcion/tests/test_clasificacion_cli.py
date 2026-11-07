import json

import pytest

from clasificacion_funcion import cli, dominio

from fuentes_falsas import FuentesFalsas


@pytest.fixture
def cli_falso(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "crear_fuentes", lambda: FuentesFalsas(tmp_path))
    monkeypatch.setattr(cli, "_git", lambda: {"head": "abc123", "dirty": True})
    return tmp_path


def correr(tmp_path, *extra):
    return cli.main(["preparar", "--salida", str(tmp_path / "ev"),
                     "--artefactos", str(tmp_path / "art"), *extra])


def test_solo_validar_no_escribe(cli_falso, capsys):
    assert correr(cli_falso, "--solo-validar") == 0
    assert not (cli_falso / "ev").exists() and not (cli_falso / "art").exists()
    assert '"total_fugas": 0' in capsys.readouterr().out


def test_preparar_escribe_evidencias_y_artefactos(cli_falso):
    assert correr(cli_falso) == 0
    ev, art = cli_falso / "ev", cli_falso / "art"
    assert sorted(p.name for p in ev.iterdir()) == [
        "abstenciones.csv", "citados_requeridos.txt", "excluidos_preparacion.csv",
        "fugas.json", "ids_eval_2015.txt", "ids_gold_v2.txt", "ids_train.txt", "ids_val.txt",
        "manifiesto_preparacion.json"]
    assert sorted(p.name for p in art.iterdir()) == [
        "etiquetas_eval_2015.csv", "etiquetas_train.csv", "etiquetas_val.csv"]
    assert (ev / "ids_train.txt").read_text() == "t1\nt2\nt4\n"
    assert (ev / "citados_requeridos.txt").read_text() == "A\nB\nE\nG\n"
    assert json.loads((ev / "fugas.json").read_text())["total_fugas"] == 0
    assert (art / "etiquetas_train.csv").read_text().splitlines()[1] == "t1,0,Background"
    assert not list(ev.glob("*.tmp")) and not list(art.glob("*.tmp"))


def test_manifiesto_registra_git_hashes_y_estado(cli_falso):
    correr(cli_falso)
    m = json.loads((cli_falso / "ev/manifiesto_preparacion.json").read_text())
    assert m["git"] == {"head": "abc123", "dirty": True}
    assert m["estado"] == "provisional_etiquetas_haiku_no_gold_humano"
    assert m["hashes"]["train"]["ids_sha256"] == dominio.sha_ids(["t1", "t2", "t4"])
    assert m["hashes"]["train"]["labels_sha256"] == dominio.sha_etiquetas({"t1": 0, "t2": 1, "t4": 6})
    assert "labels_sha256" not in m["hashes"]["gold_v2"]
    assert m["entradas"]["entrada"] and len(m["entradas"]["entrada"]) == 64


def test_no_sobrescribe(cli_falso, capsys):
    assert correr(cli_falso) == 0
    antes = (cli_falso / "ev/ids_train.txt").read_text()
    assert correr(cli_falso) == 2
    assert "No se sobrescribe" in capsys.readouterr().err
    assert (cli_falso / "ev/ids_train.txt").read_text() == antes


def test_no_sobrescribe_nada_si_un_solo_archivo_existe(cli_falso):
    (cli_falso / "art").mkdir()
    (cli_falso / "art/etiquetas_val.csv").write_text("previo")
    assert correr(cli_falso) == 2
    assert not (cli_falso / "ev").exists()
    assert (cli_falso / "art/etiquetas_val.csv").read_text() == "previo"


def test_error_de_fuga_devuelve_2_y_no_escribe(tmp_path, monkeypatch, capsys):
    f = FuentesFalsas(tmp_path)
    f.ctx["e1"]["citing_id"] = "P1"
    monkeypatch.setattr(cli, "crear_fuentes", lambda: f)
    assert correr(tmp_path) == 2
    assert "Fuga" in capsys.readouterr().err and not (tmp_path / "ev").exists()


def test_jurado_devuelve_error_claro(cli_falso, capsys):
    assert correr(cli_falso, "--fuente-etiquetas", "jurado") == 2
    assert "Jurado" in capsys.readouterr().err


def test_limite_se_registra(cli_falso):
    assert correr(cli_falso, "--limite", "1") == 0
    m = json.loads((cli_falso / "ev/manifiesto_preparacion.json").read_text())
    assert m["limite"] == 1 and m["casos"]["train"] == 1
