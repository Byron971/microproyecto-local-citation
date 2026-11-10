"""La referencia usa metadatos oficiales y nunca inventa autores desde el modelo."""
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from urllib.error import URLError

import pytest
from fastapi.testclient import TestClient
from src.app.main import app, state
from src.app import references

BIBTEX = (Path(__file__).resolve().parents[1] / "frontend/src/test/fixtures/acl-P14-1062.bib").read_bytes()


@pytest.fixture
def client(monkeypatch):
    references.fetch_bibtex.cache_clear()
    monkeypatch.setitem(state, "recomendador", SimpleNamespace(model=SimpleNamespace(papers={"P14-1062": {"title": "A Convolutional Neural Network for Modelling Sentences"}})))
    yield TestClient(app)
    references.fetch_bibtex.cache_clear()


def test_descarga_solo_bibtex_oficial_y_cachea_exitos(client, monkeypatch):
    calls = []
    def fetch(request, timeout):
        calls.append((request.full_url, timeout))
        return BytesIO(BIBTEX)
    monkeypatch.setattr(references, "urlopen", fetch)
    for _ in range(2):
        response = client.get("/api/referencias/P14-1062")
        assert response.status_code == 200
        assert response.json()["bibtex"] == BIBTEX.decode().strip()
        assert response.json()["source_url"] == "https://aclanthology.org/P14-1062/"
    assert calls == [("https://aclanthology.org/P14-1062.bib", 8)]


def test_id_ajeno_al_corpus_no_dispara_descarga(client, monkeypatch):
    def unexpected(*args, **kwargs):
        pytest.fail("No debe consultar internet para IDs ajenos al corpus")
    monkeypatch.setattr(references, "urlopen", unexpected)
    assert client.get("/api/referencias/P99-9999").status_code == 404
    assert client.get("/api/referencias/https:evil").status_code == 404


def test_fallo_externo_no_inventa_referencia_ni_cachea_error(client, monkeypatch):
    def offline(*args, **kwargs):
        raise URLError("offline")
    monkeypatch.setattr(references, "urlopen", offline)
    response = client.get("/api/referencias/P14-1062")
    assert response.status_code == 503
    assert "bibtex" not in response.json()
    monkeypatch.setattr(references, "urlopen", lambda *args, **kwargs: BytesIO(BIBTEX))
    assert client.get("/api/referencias/P14-1062").status_code == 200


@pytest.mark.parametrize("body", [b"<html>error</html>", b"@" + b"x" * 262144])
def test_no_acepta_html_o_respuestas_excesivas(client, monkeypatch, body):
    monkeypatch.setattr(references, "urlopen", lambda *args, **kwargs: BytesIO(body))
    assert client.get("/api/referencias/P14-1062").status_code == 503
