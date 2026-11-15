"""Flujo experimental A/B: contratos reales de dominio, sin pesos ni Gold."""
import hashlib
import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from src.app.classifier_runtime import A4Classifier, validate_evidence
from src.app.main import app, state
from src.app.scibert_runtime import SciBERTRuntime
from src.app.settings import ROOT, get_app_settings


class EncoderFalsoSOLO_TEST:
    def __init__(self):
        self.calls = []
        self.model_id = "encoder_prueba_sin_torch"

    def encode(self, textos):
        self.calls.append(tuple(textos))
        return [(1., 0.) if "graph" in t.lower() else (0., 1.) for t in textos]


@pytest.fixture
def original_domains(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "packages/recuperacion-densa/src"))
    monkeypatch.syspath_prepend(str(ROOT / "packages/clasificacion-funcion/src"))
    monkeypatch.syspath_prepend(str(ROOT / "packages/auditoria-corpus/src"))
    from recuperacion_densa import dominio as dense_domain
    from clasificacion_funcion import dominio as class_domain
    from auditoria_corpus.dominio import perfil_seccion
    return dense_domain, class_domain, perfil_seccion


@pytest.fixture
def models(original_domains):
    dense_domain, class_domain, profiler = original_domains

    class FakeTokenizer:
        pad_id = 0
        cls_id = 101
        sep_id = 102

    class FakeCT:
        observations = []

        @classmethod
        def preparar_ejemplos(cls, entries, entry_type, tokenizer, max_len):
            segments = class_domain.construir_segmentos(entries[0], entry_type)
            cls.observations.append(segments)
            assert entry_type in ("A", "B")
            assert max_len == 512
            return [{"context_id": "synthetic_case", "input_ids": [101, 100, 102]}]

        @staticmethod
        def predecir_probabilidades(*args, **kwargs):
            return [[0.02, 0.02, 0.02, 0.80, 0.02, 0.02, 0.04, 0.04, 0.02]], [3.5]

    dense = SciBERTRuntime(EncoderFalsoSOLO_TEST(), revision="a" * 40,
                             domain=dense_domain, max_chunks=3, max_cached_papers=2)
    a4a = A4Classifier(object(), FakeTokenizer(), FakeCT, class_domain, "cpu",
                         {"experiment_id": "scibert_A_42", "entrada": "A",
                          "hiperparametros": {"max_len": 512}}, profiler)
    a4b = A4Classifier(object(), FakeTokenizer(), FakeCT, class_domain, "cpu",
                         {"experiment_id": "scibert_B_42", "entrada": "B",
                          "hiperparametros": {"max_len": 512}}, profiler)
    return dense, a4a, a4b, FakeCT


def case_payload():
    return {
        "contexto": "We extend graph methods TARGETCIT for this study.",
        "cited_id": "P14-1001",
        "parrafos": [
            {"chunk_id": "p1", "texto": "Graph methods model nodes.", "seccion": "Methods"},
            {"chunk_id": "p2", "texto": "Graph networks improve learning.", "seccion": "Introduction"},
            {"chunk_id": "p3", "texto": "Embedding experiments are reported.", "seccion": "Results"},
        ],
    }


def test_b_is_the_exact_three_chunk_A4_recipe(models, monkeypatch):
    dense, a4a, a4b, ct = models
    monkeypatch.setitem(state, "scibert", dense)
    monkeypatch.setitem(state, "a4_b", a4b)
    resp = TestClient(app).post("/api/clasificar-cita-b", json=case_payload())
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["recuperacion"]["metodo"] == "scibert_base_mean_pooling_cosine"
    assert len(data["recuperacion"]["fragmentos"]) == 3
    assert data["clasificacion"]["entrada"] == "B"
    assert len(data["clasificacion"]["puntuaciones_softmax"]) == 9
    assert data["clasificacion"]["training_labels"] == "Haiku"
    assert data["gold_certificado"] is False
    segments = ct.observations[-1]
    assert [x["tipo"] for x in segments] == ["contexto", "chunk", "chunk", "chunk"]
    assert all(" : " in x["texto"] for x in segments[1:])
    assert all(x["texto"].split(" : ")[0] != "None" for x in segments[1:])


def test_a_is_independent_of_b(models, monkeypatch):
    dense, a4a, a4b, _ = models
    monkeypatch.setitem(state, "a4", a4a)
    response = TestClient(app).post("/api/clasificar-cita", json={
        "contexto": "We compare TARGETCIT to graph baselines.",
        "cited_title": "Original cited paper", "cited_abstract": "Academic graph methods",
    })
    assert response.status_code == 200, response.text
    assert response.json()["entrada"] == "A"
    assert response.json()["clase"] == "Comparison"


def test_b_not_present_does_not_fall_back_to_a_or_bm25(models, monkeypatch):
    dense, a4a, _, _ = models
    monkeypatch.setitem(state, "scibert", dense)
    monkeypatch.setitem(state, "a4", a4a)
    monkeypatch.setitem(state, "a4_b", None)
    assert TestClient(app).post("/api/clasificar-cita-b", json=case_payload()).status_code == 503


def test_b_requires_three_and_unique_chunks(models, monkeypatch):
    dense, _, a4b, _ = models
    monkeypatch.setitem(state, "scibert", dense)
    monkeypatch.setitem(state, "a4_b", a4b)
    body = case_payload()
    body["parrafos"] = body["parrafos"][:2]
    assert TestClient(app).post("/api/clasificar-cita-b", json=body).status_code == 422
    body = case_payload()
    body["parrafos"][2]["chunk_id"] = "p1"
    assert TestClient(app).post("/api/clasificar-cita-b", json=body).status_code == 422


def test_b_corpus_requires_train_and_hash_and_reuses_cache(models, monkeypatch, tmp_path):
    dense, _, a4b, _ = models
    monkeypatch.setitem(state, "scibert", dense)
    monkeypatch.setitem(state, "a4_b", a4b)
    path = tmp_path / "train.json"
    payload = {
        "version": 1, "resumen": {"tipo": "muestra_desarrollo_train_no_gold"},
        "casos": [{
            "context_id": "ctx1", "citing_id": "P15", "cited_id": "P14",
            "cited_title": "Graph research", "split": "train",
            "sha256_ocl_citado": "a" * 64,
            "citation_context": "We use graph methods TARGETCIT for citation.",
            "chunks": [{
                "chunk_id": f"p0000{i}-p0000{i}", "texto": f"Graph research {i}",
                "seccion": "Methods", "paragraph_indices": [i], "palabras": 3
            } for i in range(3)],
        }],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setenv("TOP3_CORPUS_PATH", str(path))
    client = TestClient(app)
    a = client.get("/api/clasificar-cita-b/corpus/ctx1")
    b = client.get("/api/clasificar-cita-b/corpus/ctx1")
    assert a.status_code == b.status_code == 200
    assert a.json()["split"] == "train"
    assert dense.cache_stats()["hits"] == 1
    payload["casos"][0]["split"] = "test"
    path.write_text(json.dumps(payload), encoding="utf-8")
    assert client.get("/api/clasificar-cita-b/corpus/ctx1").status_code == 503


def test_cache_lru_fingerprint_no_manual_persistence(models):
    dense = models[0]
    payload = case_payload()
    chunks = payload["parrafos"]
    dense.top3(payload["contexto"], chunks)
    assert dense.cache_stats()["papers"] == 0
    dense.top3(payload["contexto"], chunks, document_key="P14:sha")
    before = len(dense.encoder.calls)
    dense.top3(payload["contexto"], chunks, document_key="P14:sha")
    assert len(dense.encoder.calls) == before + 1  # only query encoded on hit
    assert dense.cache_stats()["hits"] == 1
    modified = [*chunks[:2], {**chunks[2], "texto": "Different text."}]
    dense.top3(payload["contexto"], modified, document_key="P14:sha")
    assert dense.cache_stats()["misses"] == 3
    dense.top3(payload["contexto"], chunks, document_key="P15:sha")
    assert dense.cache_stats()["papers"] == 2
    assert dense.cache_stats()["bytes_estimated"] > 0


def test_resource_limits_before_model_call(models):
    dense = models[0]
    with pytest.raises(ValueError, match="Demasiados chunks"):
        dense.top3("Graph TARGETCIT", case_payload()["parrafos"] + [
            {"chunk_id": "p4", "texto": "Four"}
        ])
    assert dense.encoder.calls == []


def test_missing_or_modified_checkpoint_is_rejected_before_torch(tmp_path):
    run = tmp_path / "scibert_B_42"
    run.mkdir()
    weight = run / "model.safetensors"
    evidence = tmp_path / "manifiesto.json"
    evidence.write_text(json.dumps({"experiment_id": "scibert_B_42",
                                   "checkpoint_sha256": "0"*64,
                                   "encoder": "scibert", "entrada": "B",
                                   "data_use": "provisional_only",
                                   "training_labels": "Haiku", "semilla": 42,
                                   "hiperparametros": {"max_len": 512}}), encoding="utf-8")
    with pytest.raises(RuntimeError, match="Faltan"):
        validate_evidence(run, evidence, entrada="B")
    weight.write_bytes(b"this-is-not-the-original-weight")
    with pytest.raises(RuntimeError, match="SHA-256"):
        validate_evidence(run, evidence, entrada="B")


def test_opt_in_config_denies_b_without_scibert():
    with pytest.raises(ValueError, match="APP_SCIBERT_ENABLED"):
        get_app_settings({"APP_A4_B_ENABLED": "true", "APP_A4_B_RUN": "any"})
    cfg = get_app_settings({})
    assert not cfg.a4_enabled and not cfg.a4_b_enabled
    assert cfg.max_cached_papers == 8
    with pytest.raises(ValueError, match="APP_SCIENCE_MAX_CHUNKS"):
        get_app_settings({"APP_SCIENCE_MAX_CHUNKS": "0"})
