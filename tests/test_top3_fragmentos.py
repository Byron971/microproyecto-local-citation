"""Pruebas del corte vertical: Top-3 de fragmentos aportados, sin red ni LLM."""
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


def test_ranking_lexico_devuelve_tres_fragmentos_del_mismo_corpus():
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
