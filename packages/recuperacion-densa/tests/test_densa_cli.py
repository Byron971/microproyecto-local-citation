import json
import os
import subprocess
import sys

import pytest

pytest.importorskip("recuperacion_densa")
ad = pytest.importorskip("recuperacion_densa.adaptador_proyecto_grado")

from recuperacion_densa import cli  # noqa: E402
from recuperacion_densa.revision import validar_revision  # noqa: E402
from test_densa_servicio import Falso, Indice, doc  # noqa: E402


@pytest.fixture
def mundo(tmp_path, monkeypatch):
    cache = tmp_path / "ocl"
    cache.mkdir()
    (cache / "A1.json").write_text(json.dumps(doc("A1", [
        ("neural parsing models", "Intro"), ("graph methods for syntax", "Methods"),
        ("evaluation on treebank data", "Results"), ("related work on parsing", "Related Work")])))
    ctx = {f"c{i}": {"refid": "A1", "citing_id": f"C{i}", "masked_text": t} for i, t in
           enumerate(["parsing TARGETCIT models", "TARGETCIT treebank", "syntax TARGETCIT"])}
    by = {k: "train" for k in ctx}
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "papers.json").write_text(json.dumps({"A1": {"title": "T", "abstract": ""}}))
    monkeypatch.setattr(ad, "cargar_indice", lambda _r: Indice(by, ctx))
    monkeypatch.setattr(ad, "cargar_exclusiones", lambda *a: set())
    monkeypatch.setattr(cli, "SALIDA", tmp_path / "artifacts")
    return ["--raw", str(raw), "--cache-ocl", str(cache), "--sin-cache"], tmp_path


def test_cli_no_importa_torch():
    """En un subproceso: borrar torch de sys.modules en este proceso rompe su re-import."""
    codigo = "import sys, recuperacion_densa.cli; sys.exit(int('torch' in sys.modules))"
    env = {**os.environ, "PYTHONPATH": os.pathsep.join(p for p in sys.path if p)}
    assert subprocess.run([sys.executable, "-c", codigo], env=env).returncode == 0


def test_solo_validar(mundo, capsys):
    base, _ = mundo
    assert cli.main([*base, "--solo-validar"]) == 0
    assert "3 contextos / 1 articulos" in capsys.readouterr().out


def test_e2e_codificador_falso_y_determinismo(mundo):
    base, tmp = mundo
    for n in ("1", "2"):
        assert cli.main([*base, "--salida", str(tmp / n)], fabrica_codificador=lambda a: Falso()) == 0
    for f in ("resumen.json", "top3.csv", "comparacion.csv"):
        assert (tmp / "1" / f).read_bytes() == (tmp / "2" / f).read_bytes()
    man = json.loads((tmp / "1" / "manifiesto.json").read_text())
    assert "resumen.json" in man["salidas"] and man["encoder"]["dispositivo"] == "falso"
    assert "recall" not in (tmp / "1" / "resumen.json").read_text().lower().replace(
        "recall@3 no calculado", "")


def test_se_niega_a_sobrescribir(mundo):
    base, tmp = mundo
    (tmp / "out").mkdir()
    (tmp / "out" / "x").write_text("a")
    with pytest.raises(SystemExit) as e:
        cli.main([*base, "--salida", str(tmp / "out")], fabrica_codificador=lambda a: Falso())
    assert e.value.code == 2
    assert (tmp / "out" / "x").read_text() == "a"


def test_integridad_violada_no_escribe(mundo):
    base, tmp = mundo

    class Malo(Falso):
        def encode(self, textos):
            return [(0.0,) * 16 for _ in textos]  # embedding nulo -> ValueError

    with pytest.raises(SystemExit):
        cli.main([*base, "--salida", str(tmp / "o")], fabrica_codificador=lambda a: Malo())
    assert not (tmp / "o").exists()


def test_revision_invalida_rechazada():
    for mala in (None, "main", "abc", "G" * 40):
        with pytest.raises(ValueError):
            validar_revision(mala)
    assert validar_revision("a" * 40) == "a" * 40


def test_sin_codificador_inyectado_falla(mundo):
    base, tmp = mundo
    with pytest.raises(SystemExit) as e:
        cli.main([*base, "--salida", str(tmp / "o")])
    assert e.value.code == 2 and not (tmp / "o").exists()
