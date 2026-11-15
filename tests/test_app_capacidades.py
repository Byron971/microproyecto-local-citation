"""La salud del microproyecto NO implica que la tesis ya tenga modelos integrados."""
import json
from types import SimpleNamespace

from fastapi.testclient import TestClient

from src.app.main import app, state


def _corpus_train(tmp_path):
    path = tmp_path / "train_top3.json"
    path.write_text(json.dumps({
        "version": 1,
        "resumen": {"tipo": "muestra_desarrollo_train_no_gold"},
        "casos": [{
            "context_id": "P15-1001_P14-1001_0",
            "split": "train",
            "citing_id": "P15-1001",
            "cited_id": "P14-1001",
            "cited_title": "Un artículo de desarrollo",
            "sha256_ocl_citado": "a" * 64,
            "citation_context": "Methods TARGETCIT compare graphs.",
            "chunks": [{
                "chunk_id": "p00000-p00000",
                "texto": "Graph methods compare models.",
                "seccion": "Methods",
                "paragraph_indices": [0],
                "palabras": 4,
            }],
        }],
    }), encoding="utf-8")
    return path


def test_no_inventa_corpus_ni_clasificador_cuando_falta_artefacto(tmp_path, monkeypatch):
    monkeypatch.setenv("TOP3_CORPUS_PATH", str(tmp_path / "no_existe.json"))
    monkeypatch.setitem(state, "recomendador", None)
    response = TestClient(app).get("/api/capacidades")
    assert response.status_code == 200
    cap = response.json()
    assert cap["servicio"]["listo"] is False
    assert cap["tareas"]["top3_manual_bm25"]["disponible"] is True
    assert cap["tareas"]["top3_corpus_train_bm25"]["disponible"] is False
    assert cap["tareas"]["top3_corpus_train_bm25"]["n_casos_train"] == 0
    assert cap["tareas"]["top3_scibert"]["disponible"] is False
    assert cap["tareas"]["clasificacion_nueve_funciones"]["disponible"] is False
    assert cap["gold_humano_certificado"] is False


def test_distingue_corpus_train_de_modelos_cientificos(tmp_path, monkeypatch):
    monkeypatch.setenv("TOP3_CORPUS_PATH", str(_corpus_train(tmp_path)))
    monkeypatch.setitem(state, "recomendador", SimpleNamespace(is_ready=True))
    response = TestClient(app).get("/api/capacidades")
    assert response.status_code == 200
    cap = response.json()
    assert cap["servicio"]["listo"] is True
    assert cap["tareas"]["top3_corpus_train_bm25"] == {
        "disponible": True, "n_casos_train": 1, "motivo": None,
        "estado": "desarrollo_no_gold",
    }
    assert cap["tareas"]["top3_scibert"]["disponible"] is False
    assert cap["tareas"]["clasificacion_nueve_funciones"]["disponible"] is False


def test_corpus_ilegal_no_se_declara_disponible(tmp_path, monkeypatch):
    path = _corpus_train(tmp_path)
    doc = json.loads(path.read_text(encoding="utf-8"))
    doc["casos"][0]["split"] = "test"  # no publicar contenido de evaluación
    path.write_text(json.dumps(doc), encoding="utf-8")
    monkeypatch.setenv("TOP3_CORPUS_PATH", str(path))
    response = TestClient(app).get("/api/capacidades")
    assert response.status_code == 200
    cap = response.json()
    assert cap["tareas"]["top3_corpus_train_bm25"]["disponible"] is False
    assert cap["tareas"]["top3_corpus_train_bm25"]["motivo"]


def test_capacidades_reflejan_modelos_realmente_cargados_sin_certificar_gold(tmp_path, monkeypatch):
    monkeypatch.setenv("TOP3_CORPUS_PATH", str(tmp_path / "ausente.json"))
    monkeypatch.setitem(state, "scibert", SimpleNamespace(
        model="SciBERT_base_mean_pooling", revision="a" * 40
    ))
    monkeypatch.setitem(state, "a4", SimpleNamespace(model_id="scibert_A_42"))
    result = TestClient(app).get("/api/capacidades").json()
    assert result["tareas"]["top3_scibert"]["disponible"] is True
    assert result["tareas"]["top3_scibert"]["revision"] == "a" * 40
    a4 = result["tareas"]["clasificacion_nueve_funciones"]
    assert a4["disponible"] is True
    assert a4["modelo"] == "scibert_A_42"
    assert a4["validacion"] == "provisional_no_gold_humano"
    assert result["gold_humano_certificado"] is False
