"""Smoke HTTP 2x2: pruebas de contrato (NO modelos reales ni Gold)."""
import copy

import pytest

from scripts.ci.smoke_tesis import validar_demo


def responses():
    nine = [{"categoria": f"synthetic-{i}", "score": 1 / 9} for i in range(9)]
    chunks = [{"chunk_id": f"p{i}", "texto": f"Graph {i}",
               "seccion": "Methods"} for i in range(1, 4)]
    a = {"modelo": "scibert_A_42", "encoder": "scibert", "entrada": "A",
         "training_labels": "Haiku", "validacion": "provisional_no_gold_humano",
         "puntuaciones_softmax": nine}
    b = {"modelo": "scibert_B_42", "encoder": "scibert", "entrada": "B",
         "training_labels": "Haiku", "validacion": "provisional_no_gold_humano",
         "puntuaciones_softmax": nine}
    return {
        "/api/estado": {"listo": True},
        "/api/recomendar": {"modelo": "tfidf_reranker_v1",
                           "recomendaciones": [{"paper_id": "paper-1"}]},
        "/api/top3-fragmentos": {"metodo": "BM25_lexico_baseline",
                                "fragmentos": [{"chunk_id": "p1"}]},
        "/api/capacidades": {"tareas": {
            "top3_scibert": {"disponible": True, "revision": "a" * 40},
            "clasificacion_nueve_funciones": {"disponible": True, "modelo": "scibert_A_42"},
            "clasificacion_nueve_funciones_b": {"disponible": True, "modelo": "scibert_B_42"},
            "clasificacion_specter_a": {"disponible": True, "modelo": "specter_A_42"},
            "clasificacion_specter_b": {"disponible": True, "modelo": "specter_B_42"},
        }},
        "/api/top3-scibert": {"metodo": "scibert_base_mean_pooling_cosine",
                             "fragmentos": chunks, "modelo": "SciBERT",
                             "revision": "a" * 40},
        "/api/clasificar-cita": a,
        "/api/clasificar-cita-b": {"recuperacion": {
            "metodo": "scibert_base_mean_pooling_cosine", "fragmentos": chunks},
            "clasificacion": b, "gold_certificado": False},
        "/api/clasificar-cita-specter-a": {
            **a, "modelo": "specter_A_42", "encoder": "specter"},
        "/api/clasificar-cita-specter-b": {"recuperacion": {
            "metodo": "scibert_base_mean_pooling_cosine", "fragmentos": chunks},
            "clasificacion": {**b, "modelo": "specter_B_42", "encoder": "specter"},
            "gold_certificado": False},
    }


def simulate(data):
    def request(base, path, payload, timeout):
        assert path in data, f"Ruta inesperada: {path}"
        return data[path]
    return request


def test_four_arm_full_contract_without_forged_gold():
    result = validar_demo("http://127.0.0.1:8000", scientific=True,
                          request=simulate(responses()), all_four=True)
    output = result["cientifico"]["cuatro_brazos_a4"]
    assert output["scibert_a"] == "scibert_A_42"
    assert output["scibert_b"] == "scibert_B_42"
    assert output["specter_a"] == "specter_A_42"
    assert output["specter_b"] == "specter_B_42"
    assert output["inferencia_http_ejecutada"] is True
    assert output["gold_certificado"] is False


def test_four_arm_mode_rejected_without_scientific():
    with pytest.raises(ValueError, match="--cientifico"):
        validar_demo("http://127.0.0.1:8000", all_four=True,
                     request=simulate(responses()))


def test_four_arm_rejects_missing_specter_weight():
    data = responses()
    data["/api/capacidades"]["tareas"]["clasificacion_specter_b"]["disponible"] = False
    with pytest.raises(RuntimeError, match="BLOQUEADO"):
        validar_demo("http://127.0.0.1:8000", scientific=True,
                     request=simulate(data), all_four=True)


def test_four_arm_rejects_specter_claiming_scibert_encoder():
    data = responses()
    data["/api/clasificar-cita-specter-a"]["encoder"] = "scibert"
    with pytest.raises(RuntimeError, match="SPECTER-A"):
        validar_demo("http://127.0.0.1:8000", scientific=True,
                     request=simulate(data), all_four=True)


def test_four_arm_rejects_bm25_specter_b_fallback():
    data = responses()
    data["/api/clasificar-cita-specter-b"]["recuperacion"]["metodo"] = "BM25"
    with pytest.raises(RuntimeError, match="SPECTER-B"):
        validar_demo("http://127.0.0.1:8000", scientific=True,
                     request=simulate(data), all_four=True)


def test_four_arm_rejects_specter_gold_claim_or_incorrect_class_count():
    data = responses()
    data["/api/clasificar-cita-specter-b"]["gold_certificado"] = True
    with pytest.raises(RuntimeError, match="SPECTER-B"):
        validar_demo("http://127.0.0.1:8000", scientific=True,
                     request=simulate(data), all_four=True)
    data = responses()
    data["/api/clasificar-cita-specter-a"]["puntuaciones_softmax"] = []
    with pytest.raises(RuntimeError, match="SPECTER-A"):
        validar_demo("http://127.0.0.1:8000", scientific=True,
                     request=simulate(data), all_four=True)
