"""Contratos de despliegue sin llamar a APIs comerciales ni usar Test Gold.

La suite cubre infraestructura real a nivel ASGI con un recomendador simulado;
la prueba en Docker de CI comprueba por separado el wheel empaquetado REAL.
"""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.app import main
from src.app.corpus_adapter import CorpusError


def test_liveness_is_independent_of_model():
    with TestClient(main.app, raise_server_exceptions=False) as client:
        # La app real puede iniciar con el wheel cuando se usa lifespan;
        # la ruta viva se prueba sin forzar siquiera esa carga.
        assert client.get("/api/salud/viva").json() == {"estado": "vivo"}


def test_readiness_is_503_before_model_and_insights(monkeypatch):
    monkeypatch.setitem(main.state, "recomendador", None)
    monkeypatch.setitem(main.state, "insights", None)
    r = TestClient(main.app).get("/api/salud/lista")
    assert r.status_code == 503
    assert r.json()["detail"] == "La aplicación aún no está lista para atender solicitudes."


def test_readiness_is_200_only_when_both_dependencies_ready(monkeypatch):
    class Stub:
        is_ready = True

    monkeypatch.setitem(main.state, "recomendador", Stub())
    monkeypatch.setitem(main.state, "insights", {"ejemplos": []})
    assert TestClient(main.app).get("/api/salud/lista").json() == {"estado": "listo"}


def test_capabilities_are_truthful_without_corpus(monkeypatch, tmp_path):
    monkeypatch.setitem(main.state, "recomendador", None)
    monkeypatch.setenv("TOP3_CORPUS_PATH", str(tmp_path / "ausente.json"))
    r = TestClient(main.app).get("/api/capacidades")
    assert r.status_code == 200
    c = r.json()
    assert c["recomendacion_articulos"]["disponible"] is False
    assert c["top3_manual"]["disponible"] is True
    assert c["top3_manual"]["metodo"] == "BM25_lexico_baseline"
    assert c["top3_corpus_train"]["disponible"] is False
    assert c["top3_scibert"]["disponible"] is False
    assert c["clasificacion_funcion_cita"]["disponible"] is False
    assert c["clasificacion_funcion_cita"]["clases_objetivo"] == 9


def test_capabilities_are_truthful_with_valid_train_corpus(monkeypatch):
    class Stub:
        is_ready = True

    monkeypatch.setitem(main.state, "recomendador", Stub())
    monkeypatch.setattr(main, "leer_corpus", lambda: {"version": 1, "casos": [{"split": "train"}]})
    c = TestClient(main.app).get("/api/capacidades").json()
    assert c["recomendacion_articulos"]["disponible"] is True
    assert c["top3_corpus_train"]["disponible"] is True
    assert c["clasificacion_funcion_cita"]["disponible"] is False


def test_corrupted_train_corpus_not_reported_as_available(monkeypatch):
    monkeypatch.setattr(main, "leer_corpus", lambda: (_ for _ in ()).throw(CorpusError("invalid")))
    c = TestClient(main.app).get("/api/capacidades").json()
    assert c["top3_corpus_train"]["disponible"] is False


def test_capabilities_do_not_include_internal_paths_or_credentials(monkeypatch, tmp_path):
    secret = "SECRET-DEPLOYMENT-CANARY"
    monkeypatch.setenv("OPENAI_API_KEY", secret)
    monkeypatch.setenv("TOP3_CORPUS_PATH", str(tmp_path / "private.json"))
    body = TestClient(main.app).get("/api/capacidades").text
    assert secret not in body
    assert str(tmp_path) not in body
    assert "OPENAI_API_KEY" not in body


def test_top3_uses_existing_bm25_and_explicitly_omits_classifier():
    response = TestClient(main.app).post(
        "/api/top3-fragmentos",
        json={
            "contexto": "Neural graph methods TARGETCIT",
            "cited_id": "P14-1011",
            "parrafos": [
                {"chunk_id": "p1", "texto": "Neural graph methods improve classification.", "seccion": "Methods"},
                {"chunk_id": "p2", "texto": "A model for image segmentation.", "seccion": "Results"},
            ],
        },
    )
    assert response.status_code == 200
    result = response.json()
    assert result["metodo"] == "BM25_lexico_baseline"
    assert result["clasificacion"]["estado"] == "no_ejecutada"
    assert result["fragmentos"][0]["chunk_id"] == "p1"


def test_top3_rejects_duplicates_and_large_input():
    client = TestClient(main.app)
    malformed = {
        "contexto": "Graph TARGETCIT", "cited_id": "P12-1",
        "parrafos": [{"chunk_id": "a", "texto": "graph"}, {"chunk_id": "a", "texto": "graph"}],
    }
    assert client.post("/api/top3-fragmentos", json=malformed).status_code == 422
    large = {
        "contexto": "Graph TARGETCIT", "cited_id": "P12-1",
        "parrafos": [{"chunk_id": str(i), "texto": "x" * 1000} for i in range(70)],
    }
    assert client.post("/api/top3-fragmentos", json=large).status_code == 422


def test_static_ui_displays_not_integrated_baselines():
    html = (Path(main.STATIC_DIR) / "top3.html").read_text(encoding="utf-8")
    script = (Path(main.STATIC_DIR) / "top3.js").read_text(encoding="utf-8")
    assert 'id="capacidades-servicio"' in html
    assert "/api/capacidades" in script
    assert "no integrada" in script
