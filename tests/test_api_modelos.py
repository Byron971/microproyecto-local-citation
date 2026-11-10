from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from src.app.main import app, state, MODELO_PREDETERMINADO


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setitem(state, "recomendador", SimpleNamespace(
        is_ready=True, recommend=lambda text, top_k: [{"paper_id": "P01", "posicion": 1}]))
    return TestClient(app)


def test_lista_solo_modelo_integrado(client):
    data = client.get("/api/modelos").json()
    assert data["predeterminado"] == MODELO_PREDETERMINADO
    assert len(data["modelos"]) == 1
    assert data["modelos"][0]["disponible"] is True


def test_contrato_anterior_y_selector_usan_mismo_modelo(client):
    for extra in ({}, {"modelo": MODELO_PREDETERMINADO}):
        response = client.post("/api/recomendar", json={"contexto": "graph networks", **extra})
        assert response.status_code == 200
        assert response.json()["modelo"] == MODELO_PREDETERMINADO
        assert response.json()["recomendaciones"][0]["paper_id"] == "P01"


def test_no_se_ignora_modelo_desconocido(client):
    response = client.post("/api/recomendar", json={"contexto": "graph", "modelo": "scibert"})
    assert response.status_code == 404


def test_modelo_no_disponible_y_compatibilidad_503(client, monkeypatch):
    monkeypatch.setitem(state, "recomendador", None)
    assert client.get("/api/modelos").json()["modelos"][0]["disponible"] is False
    assert client.post("/api/recomendar", json={"contexto": "graph", "modelo": MODELO_PREDETERMINADO}).status_code == 409
    assert client.post("/api/recomendar", json={"contexto": "graph"}).status_code == 503


def test_ejemplos_conservan_textos_ids_y_citas_del_dataset(client, monkeypatch):
    from src.app.insights import load_insights
    datos = load_insights()
    monkeypatch.setitem(state, "insights", datos)
    response = client.get("/api/ejemplos")
    assert response.status_code == 200
    payload = response.json()
    assert payload["particion"] == "val"
    assert payload["total"] == len(datos["ejemplos"]) == 50
    assert payload["ejemplos"] == datos["ejemplos"]
    assert len({e["context_id"] for e in payload["ejemplos"]}) == 50
    assert client.get("/api/ejemplo").json() in payload["ejemplos"]


def test_ejemplos_sin_datos_responde_503(client, monkeypatch):
    monkeypatch.setitem(state, "insights", None)
    assert client.get("/api/ejemplos").status_code == 503
