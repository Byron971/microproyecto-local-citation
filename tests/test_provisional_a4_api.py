"""Contrato provisional A4: ningún modelo sin pesos entra por API."""
import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from src.app.classifier_runtime import A4Classifier
from src.app.main import app, state
from src.app.settings import ROOT, get_app_settings


@pytest.fixture
def classifier(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "packages/clasificacion-funcion/src"))
    from clasificacion_funcion import dominio

    class FakeTokenizer:
        pad_id = 0

    class FakeCT:
        @staticmethod
        def preparar_ejemplos(rows, entrada, tokenizador, max_len):
            assert entrada == "A" and max_len == 512
            sections = dominio.construir_segmentos(rows[0], entrada)
            assert [p["tipo"] for p in sections] == ["contexto", "titulo", "abstract"]
            return [{"context_id": rows[0]["context_id"], "input_ids": [1, 2, 3]}]

        @staticmethod
        def predecir_probabilidades(model, rows, pad_id, device, batch_size):
            assert batch_size == 1 and pad_id == 0
            return [[0.05, 0.02, 0.04, 0.56, 0.01, 0.1, 0.08, 0.06, 0.08]], [4.2]

    return A4Classifier(
        model=object(), tokenizer=FakeTokenizer(), ct=FakeCT, domain=dominio,
        device="cpu", evidence={"experiment_id": "scibert_A_42",
                                "hiperparametros": {"max_len": 512}},
    )


def valid_body():
    return {
        "contexto": "We compare neural networks TARGETCIT with prior work.",
        "cited_title": "Neural Methods for NLP",
        "cited_abstract": "We introduce scientific representations for citations.",
    }


def test_clasificador_desactivado_responde_503(monkeypatch):
    monkeypatch.setitem(state, "a4", None)
    response = TestClient(app).post("/api/clasificar-cita", json=valid_body())
    assert response.status_code == 503
    assert "checkpoint" in response.json()["detail"]


def test_inferencia_provisional_usa_receta_exacta_y_nueve_categorias(classifier, monkeypatch):
    monkeypatch.setitem(state, "a4", classifier)
    response = TestClient(app).post("/api/clasificar-cita", json=valid_body())
    assert response.status_code == 200
    result = response.json()
    assert result["clase"] == "Comparison"
    assert result["indice_clase"] == 3
    assert len(result["puntuaciones_softmax"]) == 9
    assert result["training_labels"] == "Haiku"
    assert result["validacion"] == "provisional_no_gold_humano"
    assert "no calibradas" in result["advertencia"]
    assert "Gold" in result["advertencia"]
    assert "probabilidad_acierto" not in result


def test_validador_rechaza_contexto_sin_marcador_y_abstract_vacio(classifier, monkeypatch):
    monkeypatch.setitem(state, "a4", classifier)
    body = valid_body()
    body["contexto"] = "Without citation marker"
    assert TestClient(app).post("/api/clasificar-cita", json=body).status_code == 422
    body = valid_body()
    body["cited_abstract"] = "   "
    assert TestClient(app).post("/api/clasificar-cita", json=body).status_code == 422


def test_config_a4_es_opt_in_y_exige_checkpoint():
    cfg = get_app_settings({})
    assert cfg.a4_enabled is False and cfg.a4_run is None
    with pytest.raises(ValueError, match="APP_A4_RUN"):
        get_app_settings({"APP_A4_ENABLED": "true"})
    with pytest.raises(ValueError, match="APP_A4_DEVICE"):
        get_app_settings({"APP_A4_DEVICE": "tpu"})
    cfg = get_app_settings({"APP_A4_ENABLED": "true", "APP_A4_RUN": "tmp/a4"})
    assert cfg.a4_enabled is True
    assert cfg.a4_run == ROOT / "tmp/a4"
    assert cfg.a4_evidence.name == "manifiesto.json"


def test_load_no_puede_fabricar_checkpoint_ni_aceptar_sha_erroneo(tmp_path):
    run = tmp_path / "scibert_A_42"
    run.mkdir()
    manifest = tmp_path / "evidence.json"
    base = tmp_path / "base.json"
    manifest.write_text(json.dumps({"checkpoint_sha256": "0" * 64}), encoding="utf-8")
    base.write_text("{}", encoding="utf-8")
    with pytest.raises(RuntimeError, match="Faltan checkpoint"):
        A4Classifier.load(run, manifest, base)
    (run / "model.safetensors").write_bytes(b"no-son-pesos-de-verdad")
    with pytest.raises(RuntimeError, match="SHA-256 histórico"):
        A4Classifier.load(run, manifest, base)


def test_taxonomia_debe_coincidir_con_nueve_funciones_del_curso():
    with pytest.raises(ValueError, match="taxonomía"):
        A4Classifier(
            model=None, tokenizer=None, ct=None,
            domain=SimpleNamespace(CATEGORIAS=("one", "two")),
            device="cpu", evidence={"experiment_id": "fake"},
        )
