"""Pruebas de seguridad A4 sin Torch, GPU, red ni Gold humano."""
import hashlib
import json

import pytest

from src.app.classifier_runtime import verify_historical_identity
from src.app.science_preflight import _models_verified


def fixture_registry(tmp_path):
    repo = tmp_path
    archive = repo / "archive/manifests/scibert_A_42.json"
    archive.parent.mkdir(parents=True)
    runs = repo / "private/runs/scibert_A_42"
    runs.mkdir(parents=True)
    bytes_ = b"synthetic-test-weights-not-a-real-checkpoint"
    weight = runs / "model.safetensors"
    weight.write_bytes(bytes_)
    sha = hashlib.sha256(bytes_).hexdigest()
    evidence = {
        "experiment_id": "scibert_A_42", "encoder": "scibert",
        "entrada": "A", "semilla": 42, "checkpoint_sha256": sha,
        "hiperparametros": {"max_len": 512},
        "training_labels": "Haiku", "data_use": "provisional_only",
    }
    archive.write_text(json.dumps(evidence), encoding="utf-8")
    registry = repo / "config/checkpoint_registry.json"
    registry.parent.mkdir()
    row = {
        "id": "scibert_A_42", "encoder": "scibert",
        "entrada": "A", "semilla": 42,
        "checkpoint": "scibert_A_42/model.safetensors",
        "source_manifest": "archive/manifests/scibert_A_42.json",
        "expected_sha256": sha, "training_labels": "Haiku",
        "validation": "provisional_not_gold",
    }
    registry.write_text(json.dumps({"version": 1, "models": [row]}), encoding="utf-8")
    return repo, runs, archive, registry, sha


def test_archived_checkpoint_identity_accepts_only_original_registered_manifest(tmp_path):
    repo, run, archived, registry, sha = fixture_registry(tmp_path)
    result = verify_historical_identity(run, archived, registry=registry, repo=repo)
    assert result["checkpoint_sha256"] == sha
    assert result["data_use"] == "provisional_only"


def test_archived_checkpoint_rejects_attacker_pair_weight_and_manifest(tmp_path):
    repo, run, archived, registry, _ = fixture_registry(tmp_path)
    malicious = b"synthetic-tampered-weights"
    (run / "model.safetensors").write_bytes(malicious)
    doc = json.loads(archived.read_text())
    doc["checkpoint_sha256"] = hashlib.sha256(malicious).hexdigest()
    archived.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(RuntimeError, match="registro histórico"):
        verify_historical_identity(run, archived, registry=registry, repo=repo)


def test_archived_checkpoint_rejects_custom_manifest_even_when_bytes_match(tmp_path):
    repo, run, archived, registry, _ = fixture_registry(tmp_path)
    forged = tmp_path / "copy.json"
    forged.write_bytes(archived.read_bytes())
    with pytest.raises(RuntimeError, match="manifiesto A4 histórico"):
        verify_historical_identity(run, forged, registry=registry, repo=repo)


def test_archived_checkpoint_rejects_wrong_registry_arm(tmp_path):
    repo, run, archived, registry, _ = fixture_registry(tmp_path)
    doc = json.loads(registry.read_text())
    doc["models"][0]["encoder"] = "specter"
    registry.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(RuntimeError, match="Identidad/SHA"):
        verify_historical_identity(run, archived, registry=registry, repo=repo)


def test_preflight_ids_must_exist_and_not_duplicate():
    expected = frozenset(("scibert_A_42", "scibert_B_42"))
    assert not _models_verified([], expected)
    assert not _models_verified([{"id": "scibert_A_42", "status": "verified"}], expected)
    assert not _models_verified([
        {"id": "scibert_A_42", "status": "verified"},
        {"id": "scibert_A_42", "status": "verified"}], expected)
    assert not _models_verified([
        {"id": "scibert_A_42", "status": "verified"},
        {"id": "scibert_B_42", "status": "missing"}], expected)
    assert _models_verified([
        {"id": "scibert_A_42", "status": "verified"},
        {"id": "scibert_B_42", "status": "verified"}], expected)


def test_four_arm_preflight_not_ready_with_scibert_only(monkeypatch):
    import src.app.science_preflight as gate

    inventory = [{"id": x, "status": "verified"} for x in
                 ("scibert_A_42", "scibert_B_42")]
    monkeypatch.setattr(gate, "verificar_registro", lambda base=None: {"models": inventory})
    monkeypatch.setattr(gate, "snapshot_status", lambda download=False: {"status": "verified"})
    monkeypatch.setattr(gate, "specter_snapshot_status",
                        lambda download=False: {"status": "verified"})
    result = gate.preflight(include_specter=True)
    assert result["ready_a_b"] is True
    assert result["ready_four_a4"] is False
    assert result["gold_humano_certificado"] is False


def test_four_arm_preflight_requires_specter_snapshot_not_just_weights(monkeypatch):
    import src.app.science_preflight as gate

    inventory = [{"id": x, "status": "verified"} for x in
                 ("scibert_A_42", "scibert_B_42", "specter_A_42", "specter_B_42")]
    monkeypatch.setattr(gate, "verificar_registro", lambda base=None: {"models": inventory})
    monkeypatch.setattr(gate, "snapshot_status", lambda download=False: {"status": "verified"})
    monkeypatch.setattr(gate, "specter_snapshot_status",
                        lambda download=False: {"status": "verified"})
    assert gate.preflight(include_specter=False)["ready_four_a4"] is False
    assert gate.preflight(include_specter=True)["ready_four_a4"] is True
    monkeypatch.setattr(gate, "specter_snapshot_status",
                        lambda download=False: {"status": "sha_mismatch"})
    assert gate.preflight(include_specter=True)["ready_four_a4"] is False


@pytest.mark.parametrize("bad_scores", [
    [float("nan")] + [0.0] * 8,
    [float("inf")] + [0.0] * 8,
    [0.9] + [0.0] * 8,  # sin normalizar
    [-0.1] + [0.1375] * 8,
])
def test_a4_api_rechaza_softmax_corrupto_sin_torch(bad_scores):
    from src.app.classifier_runtime import A4Classifier
    from types import SimpleNamespace

    class FakeCT:
        @staticmethod
        def preparar_ejemplos(*args):
            return [{"context_id": "synthetic"}]

        @staticmethod
        def predecir_probabilidades(*args, **kwargs):
            return [bad_scores], [0.5]

    fake_domain = SimpleNamespace(CATEGORIAS=tuple(f"Label_{i}" for i in range(9)))
    model = A4Classifier(object(), object(), FakeCT(), fake_domain, "cpu", {
        "experiment_id": "scibert_A_42", "entrada": "A",
        "hiperparametros": {"max_len": 512},
    })
    with pytest.raises(RuntimeError, match="Softmax A4 inválido"):
        model.classify("Graph TARGETCIT work", "Graph title", "Graph abstract.")
