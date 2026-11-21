"""Pruebas sin pesos originales ni dependencias de PyTorch."""
import hashlib
import json
from pathlib import Path

from scripts.verificar_artefactos_ms import verificar

REV = "24f92d32b1bfb0bcaf9ab193ff3ad01e87732fc1"


def crear_fixture(tmp_path: Path):
    items = []
    for pista in ("M", "S"):
        directory = tmp_path / "proyecto_de_grado" / "artifacts" / "experimentos_10" / pista
        directory.mkdir(parents=True)
        content = ("checkpoint_" + pista).encode("utf8")
        weight = directory / "model.safetensors"
        weight.write_bytes(content)
        digest = hashlib.sha256(content).hexdigest()
        (directory / "manifiesto_entrenamiento.json").write_text(
            json.dumps({"sha256_model_safetensors": digest, "scibert_snapshot": REV,
                        "config": {"entrada": "AB", "semilla": 42}}), encoding="utf8"
        )
        items.append({"pista": pista, "archivo": str(weight.relative_to(tmp_path)),
                      "bytes": len(content), "sha256": digest})
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps({"checkpoints": items, "revision_modelo_base": REV}), encoding="utf8")
    return manifest_path


def test_preflight_valido(tmp_path):
    manifest = crear_fixture(tmp_path)
    result = verificar(tmp_path, manifest)
    assert result["listo"]
    assert len(result["checkpoints"]) == 2
    assert all(x["sha256_correcto"] and x["manifiesto_entrenamiento_valido"]
               for x in result["checkpoints"])


def test_preflight_rechaza_peso_corrupto(tmp_path):
    manifest = crear_fixture(tmp_path)
    path = tmp_path / "proyecto_de_grado/artifacts/experimentos_10/M/model.safetensors"
    path.write_bytes(b"checkpoint_X")
    result = verificar(tmp_path, manifest)
    assert not result["listo"]
    assert any("M: SHA256" in x for x in result["errores"])


def test_preflight_rechaza_manifiesto_faltante(tmp_path):
    manifest = crear_fixture(tmp_path)
    (tmp_path / "proyecto_de_grado/artifacts/experimentos_10/S/manifiesto_entrenamiento.json").unlink()
    result = verificar(tmp_path, manifest)
    assert not result["listo"]
    assert any("S: manifiesto de entrenamiento" in x for x in result["errores"])


def test_preflight_rechaza_ruta_fuera_del_repositorio(tmp_path):
    manifest = crear_fixture(tmp_path)
    data = json.loads(manifest.read_text(encoding="utf8"))
    data["checkpoints"][0]["archivo"] = "../fuera/model.safetensors"
    manifest.write_text(json.dumps(data), encoding="utf8")
    result = verificar(tmp_path, manifest)
    assert not result["listo"]
    assert any("M: ruta insegura" in x for x in result["errores"])


def test_preflight_rechaza_mismo_checkpoint_dos_veces(tmp_path):
    manifest = crear_fixture(tmp_path)
    data = json.loads(manifest.read_text(encoding="utf8"))
    data["checkpoints"][1]["pista"] = "M"
    manifest.write_text(json.dumps(data), encoding="utf8")
    result = verificar(tmp_path, manifest)
    assert not result["listo"]
