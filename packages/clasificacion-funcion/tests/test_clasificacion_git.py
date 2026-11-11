import subprocess

import pytest

from clasificacion_funcion import adaptador_proyecto_grado as ad
from clasificacion_funcion import cli


def git(repo, *args):
    subprocess.run(["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t", *args],
                   check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path, monkeypatch):
    git(tmp_path, "init", "-q")
    (tmp_path / "codigo.py").write_text("x = 1\n")
    (tmp_path / "ev").mkdir()
    (tmp_path / "ev/previa.json").write_text("{}")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-q", "-m", "base")
    monkeypatch.setattr(ad, "REPO", tmp_path)
    monkeypatch.setattr(cli, "EVIDENCIAS", tmp_path / "ev")
    return tmp_path


def test_arbol_limpio(repo):
    g = cli._git()
    assert len(g["head"]) == 40 and g["dirty"] is False and g["evidencia_sin_commit"] is False


def test_evidencia_nueva_no_ensucia_el_codigo(repo):
    (repo / "ev/nueva.json").write_text("{}")
    (repo / "ev/previa.json").write_text('{"cambio": 1}')
    g = cli._git()
    assert g["dirty"] is False and g["evidencia_sin_commit"] is True


def test_codigo_modificado_o_nuevo_si_ensucia(repo):
    (repo / "codigo.py").write_text("x = 2\n")
    assert cli._git()["dirty"] is True
    git(repo, "checkout", "--", "codigo.py")
    (repo / "otro.py").write_text("y = 1\n")
    assert cli._git()["dirty"] is True and cli._git()["evidencia_sin_commit"] is False


def test_codigo_y_evidencia_a_la_vez(repo):
    (repo / "codigo.py").write_text("x = 3\n")
    (repo / "ev/nueva.json").write_text("{}")
    g = cli._git()
    assert g["dirty"] is True and g["evidencia_sin_commit"] is True


def test_fuera_de_un_repositorio_devuelve_none(tmp_path, monkeypatch):
    monkeypatch.setattr(ad, "REPO", tmp_path)
    monkeypatch.setattr(cli, "EVIDENCIAS", tmp_path / "ev")
    assert cli._git() == {"head": None, "dirty": None, "evidencia_sin_commit": None}
