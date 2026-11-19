"""Pruebas de integración ligera de las rutas M/S.

No cargan checkpoints ni requieren GPU.
"""
from fastapi.testclient import TestClient

from src.app.main import app


client = TestClient(app)


def test_ms_estado_disponible():
    response = client.get("/api/analisis-cita-ms/estado")

    assert response.status_code == 200

    data = response.json()
    assert isinstance(data["habilitado"], bool)
    assert "manifest_scibert_existe" in data
    assert "checkpoint_m_existe" in data
    assert "checkpoint_s_existe" in data


def test_ms_rechaza_entrada_vacia():
    response = client.post(
        "/api/analisis-cita-ms",
        json={},
    )

    assert response.status_code == 422


def test_ms_rutas_en_openapi():
    response = client.get("/openapi.json")

    assert response.status_code == 200

    paths = response.json()["paths"]
    assert "/api/analisis-cita-ms" in paths
    assert "/api/analisis-cita-ms/estado" in paths
