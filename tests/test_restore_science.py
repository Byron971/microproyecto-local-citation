"""Checkpoints recuperados solamente si son los bytes originales SHA-256."""
import hashlib
import json
from pathlib import Path

import pytest

from src.app.restore_a4 import recuperar
from src.app.science_preflight import preflight


def sample(tmp):
    source, dest = tmp / "source", tmp / "dest"
    folder = source / "scibert_A_42"
    folder.mkdir(parents=True)
    bytes_ = b"only-a-test-file-no-real-model"
    sha = hashlib.sha256(bytes_).hexdigest()
    (folder / "model.safetensors").write_bytes(bytes_)
    evidence = tmp / "evidencia/manifiesto.json"
    evidence.parent.mkdir()
    evidence.write_text(json.dumps({"checkpoint_sha256": sha, "encoder": "scibert",
                                   "entrada": "A", "semilla": 42,
                                   "training_labels": "Haiku"}), encoding="utf-8")
    registry = tmp / "registry.json"
    registry.write_text(json.dumps({"version": 1, "root": "source",
        "models": [{
            "id": "scibert_A_42", "encoder": "scibert", "entrada": "A", "semilla": 42,
            "training_labels": "Haiku", "validation": "provisional_not_gold",
            "checkpoint": "scibert_A_42/model.safetensors",
            "source_manifest": "evidencia/manifiesto.json", "expected_sha256": sha,
        }]}), encoding="utf-8")
    return source, dest, registry, sha


def test_restoration_dry_run_does_not_create_fake_weight(tmp_path):
    source, dest, registry, sha = sample(tmp_path)
    result = recuperar(source, dest, registry=registry, repo=tmp_path, apply=False)
    assert result["modo"] == "simulacion_sin_escritura"
    assert result["checkpoints"][0]["estado"] == "listo_para_copiar"
    assert not dest.exists()


def test_restoration_copies_original_and_does_not_overwrite(tmp_path):
    source, dest, registry, sha = sample(tmp_path)
    result = recuperar(source, dest, registry=registry, repo=tmp_path, apply=True)
    checkpoint = dest / "scibert_A_42/model.safetensors"
    assert checkpoint.is_file()
    assert hashlib.sha256(checkpoint.read_bytes()).hexdigest() == sha
    assert result["checkpoints"][0]["estado"] == "copiado"
    assert recuperar(source, dest, registry=registry, repo=tmp_path, apply=True)["checkpoints"][0]["estado"] == "ya_verificado"
    checkpoint.write_bytes(b"tampered")
    with pytest.raises(ValueError, match="sobrescribir"):
        recuperar(source, dest, registry=registry, repo=tmp_path, apply=True)
    assert checkpoint.read_bytes() == b"tampered"


def test_restoration_rejects_tampered_source(tmp_path):
    source, dest, registry, sha = sample(tmp_path)
    (source / "scibert_A_42/model.safetensors").write_bytes(b"fake")
    with pytest.raises(ValueError, match="no se localizaron|No se localizaron"):
        recuperar(source, dest, registry=registry, repo=tmp_path, apply=True)
    assert not dest.exists()


def test_restoration_rejects_symlink_source_and_destination(tmp_path):
    source, dest, registry, sha = sample(tmp_path)
    other = tmp_path / "other"
    other.mkdir()
    source_link = tmp_path / "shortcut"
    source_link.symlink_to(source, target_is_directory=True)
    with pytest.raises(ValueError, match="symlink"):
        recuperar(source_link, dest, registry=registry, repo=tmp_path, apply=True)
    dest.symlink_to(other, target_is_directory=True)
    with pytest.raises(ValueError, match="enlace simbólico"):
        recuperar(source, dest, registry=registry, repo=tmp_path, apply=True)


def test_science_preflight_is_honest_if_weights_missing(monkeypatch, tmp_path):
    import src.app.science_preflight as gate
    monkeypatch.setattr(gate, "verificar_registro", lambda base=None: {
        "models": [
            {"id": "scibert_A_42", "status": "missing"},
            {"id": "scibert_B_42", "status": "verified"},
        ], "ready": False})
    monkeypatch.setattr(gate, "snapshot_status",
                        lambda download=False: {"status": "verified"})
    result = preflight(tmp_path)
    assert result["ready_a_b"] is False
    assert result["tipo"] == "preflight_cientifico_no_gold"
    assert "inferencia real" in result["nota"]


def test_science_preflight_needs_both_a_and_b_and_snapshot(monkeypatch):
    import src.app.science_preflight as gate
    monkeypatch.setattr(gate, "verificar_registro", lambda base=None: {
        "models": [
            {"id": "scibert_A_42", "status": "verified"},
            {"id": "scibert_B_42", "status": "verified"},
        ]})
    monkeypatch.setattr(gate, "snapshot_status",
                        lambda download=False: {"status": "verified"})
    assert gate.preflight()["ready_a_b"] is True
    monkeypatch.setattr(gate, "snapshot_status",
                        lambda download=False: {"status": "sha_mismatch"})
    assert gate.preflight()["ready_a_b"] is False
