"""Logica de manifiestos (sin red). Necesita huggingface-hub (grupo `modelo`)."""
import json

import pytest

pytest.importorskip("huggingface_hub")

from clasificacion_funcion import descarga_modelo as dm  # noqa: E402
from recuperacion_densa.descarga_modelo import hash_manifiesto, manifiesto_de  # noqa: E402


@pytest.fixture
def snapshot(tmp_path):
    carpeta = tmp_path / "snap"
    carpeta.mkdir()
    (carpeta / "config.json").write_text("{}", encoding="utf-8")
    (carpeta / "vocab.txt").write_text("a\nb\n", encoding="utf-8")
    return carpeta


def test_crea_y_luego_verifica(tmp_path, snapshot):
    m = manifiesto_de(snapshot, "org/m", "a" * 40)
    ruta = tmp_path / "ev" / dm.ruta_manifiesto("specter").name
    assert dm.verificar_o_escribir(ruta, m) == "creado"
    guardado = json.loads(ruta.read_text())
    assert guardado["sha256_manifiesto"] == hash_manifiesto(m)
    assert dm.verificar_o_escribir(ruta, m) == "verificado"


def test_detecta_snapshot_alterado_y_no_sobrescribe(tmp_path, snapshot):
    ruta = tmp_path / "m.json"
    dm.verificar_o_escribir(ruta, manifiesto_de(snapshot, "org/m", "a" * 40))
    antes = ruta.read_text()
    (snapshot / "vocab.txt").write_text("a\nc\n", encoding="utf-8")
    with pytest.raises(ValueError, match="no coincide"):
        dm.verificar_o_escribir(ruta, manifiesto_de(snapshot, "org/m", "a" * 40))
    assert ruta.read_text() == antes


def test_esperado_de_a1_bloquea_la_escritura(tmp_path, snapshot):
    m = manifiesto_de(snapshot, "org/m", "a" * 40)
    ruta = tmp_path / "m.json"
    with pytest.raises(ValueError, match="difiere"):
        dm.verificar_o_escribir(ruta, m, esperado="0" * 64)
    assert not ruta.exists()
    assert dm.verificar_o_escribir(ruta, m, esperado=hash_manifiesto(m)) == "creado"


def test_rutas_de_manifiesto_por_encoder():
    assert dm.ruta_manifiesto("scibert").name == "manifiesto_modelo_scibert.json"
    assert dm.ruta_manifiesto("specter").parent.name == "evidencias_clasificacion_a4"


def test_manifiestos_versionados_son_coherentes():
    for encoder in ("scibert", "specter"):
        guardado = json.loads(dm.ruta_manifiesto(encoder).read_text(encoding="utf-8"))
        sin_hash = {k: v for k, v in guardado.items() if k != "sha256_manifiesto"}
        assert guardado["sha256_manifiesto"] == hash_manifiesto(sin_hash)
    scibert = json.loads(dm.ruta_manifiesto("scibert").read_text(encoding="utf-8"))
    assert scibert["sha256_manifiesto"] == dm.sha_a1()  # igual al de A1
