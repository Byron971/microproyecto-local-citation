import hashlib
import json

import pytest

from clasificacion_funcion import adaptador_proyecto_grado as ad
from clasificacion_funcion import descarga_ocl as d


def falso(cache_estados):
    def descargar(acl_id, cache):
        estado = cache_estados[acl_id]
        if estado == "error":
            raise RuntimeError("sin red")
        if estado == "404":
            return None
        (cache / f"{acl_id}.json").write_text(json.dumps({"paper_id": acl_id}))
        return {"paper_id": acl_id}
    return descargar


def test_descargar_uno_estados(tmp_path):
    f = falso({"A": "ok", "B": "404", "C": "error"})
    a = d.descargar_uno("A", tmp_path, f)
    assert a["estado"] == "descargado" and a["sha256"] == hashlib.sha256(
        (tmp_path / "A.json").read_bytes()).hexdigest()
    assert d.descargar_uno("B", tmp_path, f) == {"id": "B", "estado": "404"}
    c = d.descargar_uno("C", tmp_path, f)
    assert c["estado"] == "error" and "RuntimeError: sin red" in c["detalle"]


def test_manifiesto_ordenado_y_con_hash():
    r = [{"id": "B", "estado": "404"}, {"id": "A", "estado": "descargado", "sha256": "x"},
         {"id": "C", "estado": "error", "detalle": "d"}]
    m = d.construir_manifiesto(r, "h")
    assert [x["id"] for x in m["descargas"]] == ["A", "B", "C"]
    assert m["estados"] == {"descargado": 1, "404": 1, "error": 1} and m["n_citados"] == 3
    assert m == d.construir_manifiesto(list(reversed(r)), "h")
    assert m["sha256_manifiesto"] != d.construir_manifiesto(r, "otro")["sha256_manifiesto"]


def test_leer_citados(tmp_path):
    (tmp_path / "c.txt").write_text("A\nB\n\n")
    assert d.leer_citados(tmp_path / "c.txt") == ["A", "B"]
    (tmp_path / "dup.txt").write_text("A\nA\n")
    with pytest.raises(ValueError):
        d.leer_citados(tmp_path / "dup.txt")
    with pytest.raises(FileNotFoundError):
        d.leer_citados(tmp_path / "no.txt")


def test_main_escribe_manifiesto_y_no_sobrescribe(tmp_path, monkeypatch, capsys):
    (tmp_path / "c.txt").write_text("A\nB\nC\n")
    monkeypatch.setattr(ad, "descargar_ocl", falso({"A": "ok", "B": "404", "C": "ok"}))
    argv = ["--citados", str(tmp_path / "c.txt"), "--cache", str(tmp_path / "cache"),
            "--manifiesto", str(tmp_path / "m.json")]
    assert d.main(argv) == 0
    m = json.loads((tmp_path / "m.json").read_text())
    assert m["estados"] == {"descargado": 2, "404": 1, "error": 0}
    assert m["citados_requeridos_sha256"] == hashlib.sha256(b"A\nB\nC\n").hexdigest()
    assert d.main(argv) == 2 and "No se sobrescribe" in capsys.readouterr().err


def test_main_errores_de_red_devuelven_1(tmp_path, monkeypatch):
    (tmp_path / "c.txt").write_text("A\nB\n")
    monkeypatch.setattr(ad, "descargar_ocl", falso({"A": "ok", "B": "error"}))
    assert d.main(["--citados", str(tmp_path / "c.txt"), "--cache", str(tmp_path / "cache"),
                   "--manifiesto", str(tmp_path / "m.json"), "--limite", "2"]) == 1


def test_main_limite(tmp_path, monkeypatch):
    (tmp_path / "c.txt").write_text("A\nB\nC\n")
    monkeypatch.setattr(ad, "descargar_ocl", falso({"A": "ok", "B": "ok", "C": "ok"}))
    d.main(["--citados", str(tmp_path / "c.txt"), "--cache", str(tmp_path / "cache"),
            "--manifiesto", str(tmp_path / "m.json"), "--limite", "2"])
    assert json.loads((tmp_path / "m.json").read_text())["n_citados"] == 2
