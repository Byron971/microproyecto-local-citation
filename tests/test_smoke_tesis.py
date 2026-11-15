"""Smoke de tesis: demostrar fallos cerrados, sin Gold ni modelos falsos."""
import pytest

from scripts.ci.smoke_tesis import validar_demo, validar_url


def baseline(path, payload, timeout):
    assert timeout > 0
    if path == "/api/estado":
        return {"listo": True, "modelo": {"nombre": "TF-IDF"}}
    if path == "/api/recomendar":
        return {"modelo": "tfidf_reranker_v1", "recomendaciones": [
            {"paper_id": "P14-1001", "posicion": 1},
        ]}
    if path == "/api/top3-fragmentos":
        return {"metodo": "BM25_lexico_baseline", "fragmentos": [
            {"chunk_id": "p1", "posicion": 1},
        ]}
    raise AssertionError(f"No debería llamarse {path}.")


def test_baseline_verifica_api_sin_levantar_modelos_cientificos():
    result = validar_demo("http://127.0.0.1:8000", request=lambda _, p, b, t: baseline(p, b, t))
    assert result["nivel"] == "baseline"
    assert result["baseline"]["fragmentos_bm25"] == 1
    assert result["gold_certificado"] is False
    assert "cientifico" not in result


def test_scientific_mode_rechaza_capacidad_ausente_incluso_si_baseline_funciona():
    def request(base, path, body, timeout):
        if path == "/api/capacidades":
            return {"tareas": {"top3_scibert": {"disponible": False},
                                "clasificacion_nueve_funciones": {"disponible": True}}}
        return baseline(path, body, timeout)
    with pytest.raises(RuntimeError, match="SciBERT real cargado"):
        validar_demo("http://127.0.0.1:8000", scientific=True, request=request)


def test_scientific_mode_rechaza_clasificador_ausente():
    def request(base, path, body, timeout):
        if path == "/api/capacidades":
            return {"tareas": {"top3_scibert": {"disponible": True},
                                "clasificacion_nueve_funciones": {"disponible": False}}}
        return baseline(path, body, timeout)
    with pytest.raises(RuntimeError, match="clasificador A4 real cargado"):
        validar_demo("http://127.0.0.1:8000", scientific=True, request=request)


def test_scientific_mode_requiere_version_coherente_y_a4_provisional():
    def request(base, path, body, timeout):
        if path == "/api/capacidades":
            return {"tareas": {
                "top3_scibert": {"disponible": True, "revision": "a" * 40},
                "clasificacion_nueve_funciones": {"disponible": True, "modelo": "scibert_A_42"},
            }}
        if path == "/api/top3-scibert":
            return {"metodo": "scibert_base_mean_pooling_cosine",
                    "fragmentos": [{"chunk_id": "p1"}], "revision": "a" * 40,
                    "modelo": "SciBERT_base_mean_pooling"}
        if path == "/api/clasificar-cita":
            return {"modelo": "scibert_A_42", "entrada": "A",
                    "validacion": "provisional_no_gold_humano", "training_labels": "Haiku",
                    "puntuaciones_softmax": [{"categoria": f"clase{i}", "score": 1 / 9} for i in range(9)]}
        return baseline(path, body, timeout)
    result = validar_demo("http://127.0.0.1:8000", scientific=True, request=request)
    assert result["nivel"] == "cientifico"
    assert result["cientifico"]["num_funciones"] == 9
    assert result["gold_certificado"] is False


def test_scientific_mode_no_pasa_con_respuesta_bm25_que_finge_ser_scibert():
    def request(base, path, body, timeout):
        if path == "/api/capacidades":
            return {"tareas": {
                "top3_scibert": {"disponible": True, "revision": "a" * 40},
                "clasificacion_nueve_funciones": {"disponible": True, "modelo": "scibert_A_42"}}}
        if path == "/api/top3-scibert":
            return {"metodo": "BM25_lexico_baseline", "revision": "a" * 40,
                    "fragmentos": [{"chunk_id": "p1"}]}
        return baseline(path, body, timeout)
    with pytest.raises(RuntimeError, match="ranking real trazable"):
        validar_demo("http://127.0.0.1:8000", scientific=True, request=request)


def test_api_sin_recomendaciones_falla_smoke():
    def request(base, path, body, timeout):
        if path == "/api/recomendar":
            return {"modelo": "tfidf_reranker_v1", "recomendaciones": []}
        return baseline(path, body, timeout)
    with pytest.raises(RuntimeError, match="no devolvió resultados"):
        validar_demo("http://127.0.0.1:8000", request=request)


@pytest.mark.parametrize("url", ["https://public.example", "http://192.168.0.1",
                                 "http://localhost:8000/hidden", "file:///secret"])
def test_no_mandar_solicitudes_a_remoto_por_defecto(url):
    with pytest.raises(ValueError):
        validar_url(url)


def test_url_remota_solo_con_https_y_aprobacion():
    assert validar_url("https://example.org", True) == "https://example.org"
    assert validar_url("http://localhost:8000") == "http://localhost:8000"
