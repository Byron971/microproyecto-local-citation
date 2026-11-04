"""S2.2: API consume corpus real de desarrollo sin tocar DVC ni red."""
import json

import pytest
from fastapi.testclient import TestClient

from src.app.corpus_adapter import CorpusError, leer_corpus
from src.app.main import app


def _corpus(tmp_path, *, split="train", cited_id="P14-1001"):
    ruta = tmp_path / "casos_train.json"
    datos = {
        "version": 1,
        "resumen": {"tipo": "muestra_desarrollo_train_no_gold"},
        "casos": [{
            "context_id": "P15-1001_P14-1001_0",
            "split": split,
            "citing_id": "P15-1001",
            "cited_id": cited_id,
            "cited_title": "Neural Graph Model",
            "sha256_ocl_citado": "a" * 64,
            "citation_context": "We used neural graph representations TARGETCIT.",
            "chunks": [
                {"chunk_id": "p00000-p00000",
                 "texto": "Neural graph methods learn representations from neighbors.",
                 "seccion": "Methods", "paragraph_indices": [0], "palabras": 8},
                {"chunk_id": "p00001-p00001",
                 "texto": "The evaluation uses neural networks for graphs.",
                 "seccion": "Results", "paragraph_indices": [1], "palabras": 8},
                {"chunk_id": "p00002-p00002",
                 "texto": "This paper introduces a new error taxonomy.",
                 "seccion": "Related Work", "paragraph_indices": [2], "palabras": 8}
            ],
        }]
    }
    ruta.write_text(json.dumps(datos), encoding="utf-8")
    return ruta


def test_api_real_devuelve_procedencia_y_ranking(tmp_path, monkeypatch):
    ruta = _corpus(tmp_path)
    monkeypatch.setenv("TOP3_CORPUS_PATH", str(ruta))
    client = TestClient(app)
    r = client.get("/api/top3-corpus/ejemplos")
    assert r.status_code == 200
    assert r.json()["ejemplos"][0]["cited_id"] == "P14-1001"
    respuesta = client.get("/api/top3-corpus/P15-1001_P14-1001_0")
    assert respuesta.status_code == 200
    result = respuesta.json()
    assert result["context_id"] == "P15-1001_P14-1001_0"
    assert result["split"] == "train"
    assert result["fuente"] == "ACL-200 + ACL OCL local"
    assert result["sha256_ocl_citado"] == "a" * 64
    assert result["clasificacion"]["estado"] == "no_ejecutada"
    assert result["fragmentos"][0]["paragraph_indices"] == [0]
    assert all(x["puntaje_bm25"] > 0 for x in result["fragmentos"])


def test_api_ausencia_de_artefacto_es_503_no_fallback_falso(tmp_path, monkeypatch):
    monkeypatch.setenv("TOP3_CORPUS_PATH", str(tmp_path / "no_existe.json"))
    client = TestClient(app)
    assert client.get("/api/top3-corpus/ejemplos").status_code == 503
    assert client.get("/api/top3-corpus/ABC").status_code == 503


def test_api_id_desconocido_no_inventa_ejemplos(tmp_path, monkeypatch):
    monkeypatch.setenv("TOP3_CORPUS_PATH", str(_corpus(tmp_path)))
    assert TestClient(app).get("/api/top3-corpus/NO_EXISTE").status_code == 404


def test_artefacto_de_test_no_se_publica_por_error(tmp_path):
    with pytest.raises(CorpusError, match="inconsistente"):
        leer_corpus(_corpus(tmp_path, split="test"))


def test_artefacto_duplicado_no_se_publica(tmp_path):
    ruta = _corpus(tmp_path)
    j = json.loads(ruta.read_text(encoding="utf-8"))
    j["casos"].append(j["casos"][0])
    ruta.write_text(json.dumps(j), encoding="utf-8")
    with pytest.raises(CorpusError, match="inconsistente"):
        leer_corpus(ruta)


def test_parrafo_demasiado_largo_no_se_publica(tmp_path):
    ruta = _corpus(tmp_path)
    j = json.loads(ruta.read_text(encoding="utf-8"))
    j["casos"][0]["chunks"][0]["texto"] = "word " * 301
    ruta.write_text(json.dumps(j), encoding="utf-8")
    with pytest.raises(CorpusError, match="Chunk incompatible"):
        leer_corpus(ruta)


def test_artefacto_no_se_sustituye_por_datos_sinteticos(tmp_path):
    ruta = _corpus(tmp_path)
    j = json.loads(ruta.read_text(encoding="utf-8"))
    j["version"] = 2
    ruta.write_text(json.dumps(j), encoding="utf-8")
    with pytest.raises(CorpusError, match="Version"):
        leer_corpus(ruta)
