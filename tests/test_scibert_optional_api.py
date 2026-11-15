"""Contratos SciBERT en API: encoder fake SOLO para tests, nunca para demo."""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.app.main import app, state
from src.app.scibert_runtime import SciBERTRuntime
from src.app.settings import ROOT, get_app_settings


class EncoderControlado:
    def encode(self, texts):
        vectors = []
        for text in texts:
            word = text.casefold()
            vectors.append((1.0, 0.0) if ("graph" in word or "node" in word) else (0.0, 1.0))
        return vectors


@pytest.fixture
def runtime(monkeypatch):
    # Se reutiliza la función de ranking A1, sin cargar pesos ni afirmar calidad.
    monkeypatch.syspath_prepend(str(ROOT / "packages/recuperacion-densa/src"))
    from recuperacion_densa import dominio
    return SciBERTRuntime(EncoderControlado(), revision="a" * 40, domain=dominio)


def test_top3_consistente_con_ordenador_cientifico_y_procedencia(runtime):
    chunks = [
        {"chunk_id": "p3", "texto": "Statistics are important.", "seccion": "Results"},
        {"chunk_id": "p1", "texto": "Graph networks model nodes.", "seccion": "Methods",
         "paragraph_indices": [1]},
        {"chunk_id": "p2", "texto": "Graph structure.", "seccion": "Introduction"},
    ]
    ranking = runtime.top3("Graph TARGETCIT", chunks)
    assert [r["chunk_id"] for r in ranking] == ["p1", "p2", "p3"]
    assert ranking[0]["similitud_coseno"] == 1.0
    assert ranking[0]["paragraph_indices"] == [1]
    assert "puntaje_bm25" not in ranking[0]
    assert ranking[2]["similitud_coseno"] == 0.0


def test_ruta_densa_falla_cerrado_si_desactivada(monkeypatch):
    monkeypatch.setitem(state, "scibert", None)
    response = TestClient(app).post("/api/top3-scibert", json={
        "cited_id": "P14-1001", "contexto": "Graph TARGETCIT",
        "parrafos": [{"chunk_id": "p1", "texto": "Graph methods."}],
    })
    assert response.status_code == 503
    assert "BM25" in response.json()["detail"]


def test_ruta_densa_inferida_con_adaptador_real_de_ranking(runtime, monkeypatch):
    monkeypatch.setitem(state, "scibert", runtime)
    response = TestClient(app).post("/api/top3-scibert", json={
        "cited_id": "P14-1001", "contexto": "Graph TARGETCIT",
        "parrafos": [
            {"chunk_id": "p2", "texto": "Statistical learning."},
            {"chunk_id": "p1", "texto": "Graph methods.", "seccion": "Methods"},
        ],
    })
    assert response.status_code == 200
    data = response.json()
    assert data["metodo"] == "scibert_base_mean_pooling_cosine"
    assert data["fragmentos"][0]["chunk_id"] == "p1"
    assert data["clasificacion"]["estado"] == "no_ejecutada"
    assert "Gold" in data["aviso"]


def test_ruta_rechaza_chunks_duplicados_antes_de_inferencia(runtime, monkeypatch):
    monkeypatch.setitem(state, "scibert", runtime)
    response = TestClient(app).post("/api/top3-scibert", json={
        "cited_id": "P14-1001", "contexto": "Graph TARGETCIT",
        "parrafos": [
            {"chunk_id": "p1", "texto": "Graph methods."},
            {"chunk_id": "p1", "texto": "Different text."},
        ],
    })
    assert response.status_code == 422


def test_config_densa_desactivada_de_forma_predeterminada():
    cfg = get_app_settings({})
    assert cfg.scibert_enabled is False
    assert cfg.scibert_manifest is None
    assert cfg.scibert_device == "cpu"


def test_config_densa_no_se_activa_sin_manifiesto():
    with pytest.raises(ValueError, match="APP_SCIBERT_MANIFEST"):
        get_app_settings({"APP_SCIBERT_ENABLED": "true"})
    with pytest.raises(ValueError, match="APP_SCIBERT_DEVICE"):
        get_app_settings({"APP_SCIBERT_DEVICE": "opencl"})
    with pytest.raises(ValueError, match="APP_SCIBERT_ENABLED"):
        get_app_settings({"APP_SCIBERT_ENABLED": "si"})


def test_load_rechaza_snapshot_sin_manifiesto_antes_de_torch(tmp_path):
    with pytest.raises(RuntimeError, match="manifiesto_modelo"):
        SciBERTRuntime.load(tmp_path / "no-existe.json")


def test_ruta_corpus_no_revela_test_gold(runtime, monkeypatch, tmp_path):
    import json
    path = tmp_path / "casos_train.json"
    path.write_text(json.dumps({
        "version": 1,
        "resumen": {"tipo": "muestra_desarrollo_train_no_gold"},
        "casos": [{
            "context_id": "ctx1", "citing_id": "P15", "cited_id": "P14",
            "cited_title": "Graph methods", "split": "train",
            "citation_context": "Graph TARGETCIT",
            "sha256_ocl_citado": "a" * 64,
            "chunks": [{"chunk_id": "p1", "texto": "Graph methods.", "seccion": "Methods",
                        "paragraph_indices": [0], "palabras": 2}],
        }],
    }), encoding="utf-8")
    monkeypatch.setenv("TOP3_CORPUS_PATH", str(path))
    monkeypatch.setitem(state, "scibert", runtime)
    response = TestClient(app).get("/api/top3-scibert/corpus/ctx1")
    assert response.status_code == 200
    assert response.json()["split"] == "train"
    assert response.json()["fragmentos"][0]["seccion"] == "Methods"

    doc = json.loads(path.read_text(encoding="utf-8"))
    doc["casos"][0]["gold"] = "Evidence"
    path.write_text(json.dumps(doc), encoding="utf-8")
    response = TestClient(app).get("/api/top3-scibert/corpus/ctx1")
    assert response.status_code == 503
