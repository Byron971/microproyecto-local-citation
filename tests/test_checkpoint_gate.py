"""Pruebas sin torch/red: checksums no son precisión ni certificación Gold."""
import hashlib
import json
from pathlib import Path

import pytest

from src.app.checkpoint_gate import verificar_registro, main


def escenario(tmp_path):
    base = tmp_path / "pesos"
    folder = base / "scibert_A_42"
    folder.mkdir(parents=True)
    payload = b"checkpoint-controlado-para-pruebas"
    sha = hashlib.sha256(payload).hexdigest()
    original = tmp_path / "proyecto_de_grado/docs/experimento/manifiesto.json"
    original.parent.mkdir(parents=True)
    original.write_text(json.dumps({
        "checkpoint_sha256": sha,
        "encoder": "scibert", "entrada": "A",
        "semilla": 42, "training_labels": "Haiku",
    }), encoding="utf-8")
    registry = tmp_path / "registro.json"
    doc = {
        "version": 1, "root": "pesos", "models": [{
            "id": "scibert_A_42", "encoder": "scibert", "entrada": "A",
            "semilla": 42, "training_labels": "Haiku",
            "validation": "provisional_not_gold",
            "checkpoint": "scibert_A_42/model.safetensors",
            "source_manifest": "proyecto_de_grado/docs/experimento/manifiesto.json",
            "expected_sha256": sha,
        }],
    }
    registry.write_text(json.dumps(doc), encoding="utf-8")
    return base, folder / "model.safetensors", registry, doc, payload


def test_inventario_reporta_peso_ausente_sin_inventarlo(tmp_path):
    base, file, registry, _, _ = escenario(tmp_path)
    audit = verificar_registro(registry, base, tmp_path)
    assert audit["missing"] == 1
    assert audit["verified"] == 0
    assert not audit["ready"]
    assert audit["models"][0]["certified_gold"] is False
    assert "texto" not in audit


def test_checkpoint_real_se_valida_por_bytes_y_no_por_nombre(tmp_path):
    base, file, registry, _, payload = escenario(tmp_path)
    file.write_bytes(payload)
    assert verificar_registro(registry, base, tmp_path)["ready"]
    file.write_bytes(payload + b"alterado")
    audit = verificar_registro(registry, base, tmp_path)
    assert audit["sha_mismatch"] == 1
    assert not audit["ready"]


def test_manifiesto_original_prevalece_sobre_registro_modificado(tmp_path):
    base, _, registry, doc, _ = escenario(tmp_path)
    doc["models"][0]["expected_sha256"] = "0" * 64
    registry.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(ValueError, match="SHA histórico"):
        verificar_registro(registry, base, tmp_path)


@pytest.mark.parametrize("part", ["../../outside/model.safetensors", "/tmp/model.safetensors",
                                  "c:\\tmp\\model.safetensors"])
def test_no_admite_rutas_inseguras(tmp_path, part):
    base, _, registry, doc, _ = escenario(tmp_path)
    doc["models"][0]["checkpoint"] = part
    registry.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(ValueError, match="[Rr]uta|relativas"):
        verificar_registro(registry, base, tmp_path)


def test_proveniencia_falsa_y_modelo_duplicado_son_rechazados(tmp_path):
    base, _, registry, doc, _ = escenario(tmp_path)
    doc["models"][0]["validation"] = "gold_certified"
    registry.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(ValueError, match="procedencia provisional"):
        verificar_registro(registry, base, tmp_path)
    doc["models"][0]["validation"] = "provisional_not_gold"
    doc["models"].append(doc["models"][0])
    registry.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(ValueError, match="duplicado"):
        verificar_registro(registry, base, tmp_path)


def test_enlace_simbolico_no_se_acepta(tmp_path):
    base, file, registry, _, payload = escenario(tmp_path)
    real = tmp_path / "otro.safetensors"
    real.write_bytes(payload)
    file.symlink_to(real)
    assert verificar_registro(registry, base, tmp_path)["unsafe_symlink"] == 1


def test_registro_archivado_tiene_cuatro_referencias_reales_sin_pesos():
    audit = verificar_registro()
    assert audit["total"] == 4
    assert audit["scope"] == "technical_provisional_checkpoints_no_human_gold"
    assert all(row["training_labels"] == "Haiku" for row in audit["models"])
    assert all(row["certified_gold"] is False for row in audit["models"])


def test_modo_inventario_no_falla_con_archivos_ausentes(tmp_path, capsys):
    base = tmp_path / "sin-pesos"
    assert main(["--base", str(base), "--permitir-faltantes"]) == 0
    audit = json.loads(capsys.readouterr().out)
    assert audit["missing"] == 4 and not audit["ready"]
    assert main(["--base", str(base)]) == 1
