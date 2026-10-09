"""Pruebas del corte vertical: Top-3 de fragmentos aportados, sin red ni LLM."""
import pytest
from fastapi.testclient import TestClient

from src.app.fragment_retrieval import recuperar_top3, tokens
from src.app.main import app


def parrafos():
    return [
        {"chunk_id": "p2", "texto": "We describe morphological segmentation."},
        {"chunk_id": "p1", "texto": "Graph neural networks improve node classification."},
        {"chunk_id": "p3", "texto": "Neural graph architectures learn distributed representations."},
        {"chunk_id": "p4", "texto": "Machine translation evaluation is difficult."},
    ]


def test_tokens_excluyen_markers_pero_no_contexto():
    assert "targetcit" not in tokens("TARGETCIT OTHERCIT graph network")
    assert tokens("TARGETCIT OTHERCIT graph network") == ["graph", "network"]


def test_ranking_lexico_devuelve_fragmentos_coincidentes():
    resultados = recuperar_top3("Neural graph methods TARGETCIT", parrafos())
    assert len(resultados) == 2
    assert {x["chunk_id"] for x in resultados} == {"p1", "p3"}
    assert [x["posicion"] for x in resultados] == [1, 2]
    assert all(x["puntaje_bm25"] > 0 for x in resultados)


def test_no_inventa_resultados_sin_coincidencia():
    assert recuperar_top3("quasar supernova", parrafos()) == []
    assert recuperar_top3("TARGETCIT OTHERCIT", parrafos()) == []


def test_top3_limita_a_tres_y_ordena_empates_por_id():
    docs = [
        {"chunk_id": f"c{x}", "texto": "evidence evidence"}
        for x in ("5", "1", "4", "2", "3")
    ]
    results = recuperar_top3("evidence", docs)
    assert [x["chunk_id"] for x in results] == ["c1", "c2", "c3"]


def test_endpoint_responde_sin_llm_ni_cargar_modelo_de_articulos():
    client = TestClient(app)
    r = client.post("/api/top3-fragmentos", json={
        "cited_id": "P14-1011",
        "contexto": "Neural graph methods TARGETCIT",
        "parrafos": parrafos(),
    })
    assert r.status_code == 200
    payload = r.json()
    assert payload["cited_id"] == "P14-1011"
    assert payload["metodo"] == "BM25_lexico_baseline"
    assert payload["total_resultados"] == 2
    assert payload["clasificacion"]["estado"] == "no_ejecutada"
    assert "articulo_citado" in payload["alcance"]


def test_endpoint_rechaza_ids_duplicados_y_texto_vacio():
    client = TestClient(app)
    r = client.post("/api/top3-fragmentos", json={
        "cited_id": "P14-1011",
        "contexto": "Graph",
        "parrafos": [{"chunk_id": "X", "texto": "Graph"},
                     {"chunk_id": "X", "texto": "Graph"}],
    })
    assert r.status_code == 422
    r = client.post("/api/top3-fragmentos", json={
        "cited_id": "P14-1011", "contexto": "Graph",
        "parrafos": [{"chunk_id": "X", "texto": "   "}],
    })
    assert r.status_code == 422


def test_endpoint_rechaza_carga_excesiva():
    client = TestClient(app)
    r = client.post("/api/top3-fragmentos", json={
        "cited_id": "P14-1011", "contexto": "graph",
        "parrafos": [{"chunk_id": str(x), "texto": "graph"} for x in range(101)],
    })
    assert r.status_code == 422


def test_api_original_conserva_sus_rutas():
    paths = {route.path for route in app.routes}
    assert "/api/recomendar" in paths
    assert "/api/estado" in paths
    assert "/api/insights" in paths
    assert "/api/top3-fragmentos" in paths


def test_bm25_puntajes_esperados_de_ejemplo_resuelto_a_mano():
    """Protege IDF, saturacion K1 y normalizacion B, no solo orden Top-3.

    N=3; longitudes 3, 1, 5; promedio=3; df(rare)=1, df(common)=3.
    IDF rare=ln(8/3); IDF common=ln(8/7).
    K1=1.5 y B=0.75; la salida redondea a seis decimales.
    D1: IDF_rare*(10/7) + IDF_common
    D2: IDF_common*(10/7)
    D3: IDF_common*(10/13)
    """
    docs = [
        {"chunk_id": "d1", "texto": "rare rare common"},
        {"chunk_id": "d2", "texto": "common"},
        {"chunk_id": "d3", "texto": "common extra extra extra extra"},
    ]
    ranking = recuperar_top3("rare common TARGETCIT", docs)
    assert [r["chunk_id"] for r in ranking] == ["d1", "d2", "d3"]
    assert ranking[0]["puntaje_bm25"] == pytest.approx(1.534716, abs=1e-6)
    assert ranking[1]["puntaje_bm25"] == pytest.approx(0.190759, abs=1e-6)
    assert ranking[2]["puntaje_bm25"] == pytest.approx(0.102716, abs=1e-6)


def test_idf_raro_mayor_que_termino_ubicuo_misma_frecuencia():
    """Con tf y longitud iguales, un termino en 1/3 supera uno en 3/3."""
    docs = [
        {"chunk_id": "raro", "texto": "rare extra"},
        {"chunk_id": "comun1", "texto": "common common"},
        {"chunk_id": "comun2", "texto": "common common"},
    ]
    # El documento 'raro' es el unico con rare y suma una señal menos frecuente.
    ranking = recuperar_top3("rare common", docs)
    assert ranking[0]["chunk_id"] == "raro"
    assert ranking[0]["puntaje_bm25"] > ranking[1]["puntaje_bm25"]


def test_tokenizador_crudo_no_tiene_stemming_ni_lematizacion():
    """Limitacion declarada: se comparara una segunda variante normalizada."""
    assert tokens("word embedding") != tokens("words embeddings")
    assert recuperar_top3(
        "word embedding",
        [{"chunk_id": "morfologia", "texto": "words embeddings"}],
    ) == []


def test_api_limita_el_total_de_texto_no_solo_cada_parrafo():
    client = TestClient(app)
    r = client.post("/api/top3-fragmentos", json={
        "cited_id": "P14-1011",
        "contexto": "graph",
        "parrafos": [
            {"chunk_id": f"c{i}", "texto": "a" * 5000}
            for i in range(13)
        ],
    })
    assert r.status_code == 422
    assert "60000" in r.text


def test_frontend_controla_respuestas_no_json_y_limites():
    from pathlib import Path
    script = (
        Path(__file__).resolve().parents[1] / "src/app/static/top3.js"
    ).read_text(encoding="utf-8")
    assert "async function leerRespuestaJSON" in script
    assert "MAX_CARACTERES_MANUAL = 60000" in script
    assert 'await leerRespuestaJSON(respuesta)' in script
    assert 'await leerRespuestaJSON(listado)' in script
    assert "innerHTML" not in script
