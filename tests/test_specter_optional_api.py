"""SPECTER A/B opt-in: tests de contrato, NO inferencia Torch de pesos."""
import hashlib
import json

import pytest
from fastapi.testclient import TestClient

from src.app.classifier_runtime import validate_evidence
from src.app.main import app, state
from src.app.settings import get_app_settings


class SpecterStubOnlyTests:
    def __init__(self, variant):
        self.variant = variant
        self.model_id = "specter_" + variant + "_42"
        self.inputs = []

    def classify(self, context, title=None, abstract=None, top3=None):
        self.inputs.append((context, title, abstract, top3))
        return {
            "modelo": self.model_id, "encoder": "specter",
            "entrada": self.variant, "clase": "Comparison",
            "puntuaciones_softmax": [
                {"categoria": str(i), "score": 1/9} for i in range(9)],
            "training_labels": "Haiku",
            "validacion": "provisional_no_gold_humano",
        }


class DenseStubOnlyTests:
    method = "scibert_base_mean_pooling_cosine"
    model = "SciBERT_base_mean_pooling"
    revision = "a" * 40

    def top3(self, context, chunks, *, document_key=None):
        return [
            {"chunk_id": p["chunk_id"], "texto": p["texto"],
             "seccion": p.get("seccion"), "similitud_coseno": 0.5,
             "posicion": i + 1}
            for i, p in enumerate(chunks[:3])
        ]


def payload_b():
    return {
        "contexto": "A graph method TARGETCIT was used.",
        "cited_id": "P14-1001",
        "parrafos": [
            {"chunk_id": f"p{i}", "texto": f"Graph science {i}.", "seccion": "Methods"}
            for i in range(1, 4)
        ],
    }


def test_specter_disabled_is_http_503_and_not_gold(monkeypatch):
    monkeypatch.setitem(state, "specter_a", None)
    monkeypatch.setitem(state, "specter_b", None)
    monkeypatch.setitem(state, "scibert", None)
    client = TestClient(app)
    a = client.post("/api/clasificar-cita-specter-a", json={
        "contexto": "Graph TARGETCIT is useful.",
        "cited_title": "Authentic Title", "cited_abstract": "Authentic abstract.",
    })
    b = client.post("/api/clasificar-cita-specter-b", json=payload_b())
    assert a.status_code == 503
    assert b.status_code == 503
    status = client.get("/api/capacidades").json()
    assert status["tareas"]["clasificacion_specter_a"]["disponible"] is False
    assert status["tareas"]["clasificacion_specter_b"]["disponible"] is False
    assert status["gold_humano_certificado"] is False


def test_specter_a_uses_title_abstract_and_not_scibert_substitute(monkeypatch):
    model = SpecterStubOnlyTests("A")
    monkeypatch.setitem(state, "specter_a", model)
    client = TestClient(app)
    response = client.post("/api/clasificar-cita-specter-a", json={
        "contexto": "Graph TARGETCIT is useful.",
        "cited_title": "True Title", "cited_abstract": "True abstract.",
    })
    assert response.status_code == 200, response.text
    assert response.json()["modelo"] == "specter_A_42"
    assert response.json()["validacion"] == "provisional_no_gold_humano"
    assert model.inputs[-1][1:3] == ("True Title", "True abstract.")


def test_specter_b_uses_exact_scibert_top3_and_no_gold(monkeypatch):
    model = SpecterStubOnlyTests("B")
    monkeypatch.setitem(state, "specter_b", model)
    monkeypatch.setitem(state, "scibert", DenseStubOnlyTests())
    response = TestClient(app).post("/api/clasificar-cita-specter-b", json=payload_b())
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["clasificacion"]["modelo"] == "specter_B_42"
    assert result["recuperacion"]["metodo"] == "scibert_base_mean_pooling_cosine"
    assert len(result["recuperacion"]["fragmentos"]) == 3
    assert len(model.inputs[-1][3]) == 3
    assert result["gold_certificado"] is False


def test_specter_b_does_not_fall_back_when_retriever_missing(monkeypatch):
    monkeypatch.setitem(state, "specter_b", SpecterStubOnlyTests("B"))
    monkeypatch.setitem(state, "scibert", None)
    response = TestClient(app).post("/api/clasificar-cita-specter-b", json=payload_b())
    assert response.status_code == 503


def test_specter_config_needs_real_weight_paths_and_scibert_for_b():
    config = get_app_settings({})
    assert config.specter_a_enabled is False
    assert config.specter_b_enabled is False
    with pytest.raises(ValueError, match="APP_SPECTER_A_RUN"):
        get_app_settings({"APP_SPECTER_A_ENABLED": "true"})
    with pytest.raises(ValueError, match="APP_SCIBERT_ENABLED"):
        get_app_settings({"APP_SPECTER_B_ENABLED": "true", "APP_SPECTER_B_RUN": "/tmp/b"})
    with pytest.raises(ValueError, match="APP_SPECTER_DEVICE"):
        get_app_settings({"APP_SPECTER_DEVICE": "unknown"})


def test_specter_sha_is_checked_before_runtime(tmp_path):
    run = tmp_path / "specter_A_42"
    run.mkdir()
    weights = run / "model.safetensors"
    weights.write_bytes(b"SYNTHETIC_TEST_ONLY_NO_REAL_MODEL")
    sha = hashlib.sha256(weights.read_bytes()).hexdigest()
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({
        "experiment_id": "specter_A_42",
        "encoder": "specter", "entrada": "A",
        "checkpoint_sha256": sha, "data_use": "provisional_only",
        "training_labels": "Haiku", "semilla": 42,
        "hiperparametros": {"max_len": 512},
    }), encoding="utf-8")
    assert validate_evidence(run, manifest, entrada="A")["encoder"] == "specter"
    weights.write_bytes(b"MODIFIED")
    with pytest.raises(RuntimeError, match="SHA-256"):
        validate_evidence(run, manifest, entrada="A")
