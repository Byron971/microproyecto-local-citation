"""A7 sin Gold: percentiles y validación de contrato HTTP."""
import pytest

from scripts.ci.benchmark_api import benchmark, resumir, validar_url


def test_percentiles_nearest_rank_sin_escoger_el_mejor_resultado():
    p = resumir([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
    assert p["n"] == 10
    assert p["p50_ms"] == 5
    assert p["p95_ms"] == 10
    assert p["media_ms"] == 5.5


@pytest.mark.parametrize("url", [
    "https://example.org", "http://192.168.1.1:8080",
    "http://localhost:8000/admin", "file:///etc/passwd",
    "http://bad:password@localhost:8000", "http://localhost:8000?key=secret",
])
def test_no_enviar_datos_a_red_sin_permiso_explicito(url):
    with pytest.raises(ValueError):
        validar_url(url)


def test_remoto_solo_si_https_y_con_aprobacion():
    assert validar_url("http://localhost:8000") == "http://localhost:8000"
    assert validar_url("https://example.org", True) == "https://example.org"
    with pytest.raises(ValueError):
        validar_url("http://example.org", True)


def test_benchmark_respuesta_tecnica_realista_y_warmup_excluido():
    calls = []

    def query(url, data, timeout):
        calls.append((url, data, timeout))
        return {"recomendaciones": [{"paper_id": "P14-1001"}]}

    doc = benchmark("http://127.0.0.1:8000", "recommend", 4, 2, request_fn=query)
    assert len(calls) == 6
    assert doc["resumen"]["n"] == 4
    assert doc["warmup_excluidos"] == 2
    assert doc["estado"] == "benchmark_tecnico_no_gold"
    assert len(doc["sha256_payload"]) == 64
    assert "contexto" not in doc  # no textos en el reporte de evidencia


def test_bm25_rechaza_respuesta_de_backend_distinto():
    with pytest.raises(RuntimeError, match="backend"):
        benchmark("http://127.0.0.1:8000", "top3-bm25", 1, 0,
                  request_fn=lambda *_: {"metodo": "scibert_base_mean_pooling_cosine",
                                        "fragmentos": []})


@pytest.mark.parametrize("n,warmup", [(0, 0), (101, 0), (1, -1), (1, 21)])
def test_limites_de_carga_para_no_saturar_servicios(n, warmup):
    with pytest.raises(ValueError, match="rango"):
        benchmark("http://127.0.0.1:8000", "recommend", n, warmup)


def test_rechaza_medicion_no_finita():
    with pytest.raises(ValueError, match="inválida"):
        resumir([0.1, float("nan")])
