"""Contratos S3/C2 sin inferencia real ni acceso a Gold."""
from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace

import pytest

from proyecto_de_grado.src.data.clasificar_scibert_s3 import (
    crear_prompt_c2, ejecutar, huella_ejecucion, validar_reporte,
)


def casos():
    return [
        {
            "id": f"CTX-{i}", "split": "train", "cited_id": f"P10-100{i}",
            "citation_context": "We use TARGETCIT to model a novel approach.",
            "cited_title": "Method for Citation", "cited_abstract": "Method description.",
            "cited_chunks": [
                {"chunk_id": f"p0000{j}-p0000{j}",
                 "texto": f"Scientific abstract and different approach {j}.",
                 "seccion": "Methods"} for j in range(1, 5)
            ],
        } for i in range(2)
    ]


def informe(c):
    return {
        "tipo": "comparacion_tecnica_train_s2_8_no_gold",
        "sha256_entrada": "sha-corpus",
        "parametros": {"query_sin_marcadores": True},
        "resumen": {"metricas_gold_calculadas": False},
        "modelo_commit_resuelto": "commit-scibert",
        "resultados": [{
            "context_id": fila["id"], "split": "train", "cited_id": fila["cited_id"],
            "scibert_top3": [
                {"chunk_id": ch["chunk_id"], "similitud_coseno": 0.9 - j / 10}
                for j, ch in enumerate(fila["cited_chunks"][:3])
            ],
        } for fila in c],
    }


def test_acepta_reporte_valido():
    c = casos()
    assert len(validar_reporte(c, "sha-corpus", informe(c))) == 2


def test_rechaza_huella_incompatible():
    c = casos()
    with pytest.raises(ValueError, match="Huella"):
        validar_reporte(c, "otra-huella", informe(c))


def test_rechaza_test():
    c = casos()
    info = informe(c)
    info["resultados"][0]["split"] = "test"
    with pytest.raises(ValueError, match="split"):
        validar_reporte(c, "sha-corpus", info)


def test_rechaza_articulo_cruzado():
    c = casos()
    info = informe(c)
    info["resultados"][0]["cited_id"] = "OTRO-ARTICULO"
    with pytest.raises(ValueError, match="citado distinto"):
        validar_reporte(c, "sha-corpus", info)


def test_rechaza_ids_incompletos():
    c = casos()
    info = informe(c)
    info["resultados"] = info["resultados"][:1]
    with pytest.raises(ValueError, match="IDs"):
        validar_reporte(c, "sha-corpus", info)


def test_rechaza_ids_repetidos():
    c = casos()
    info = informe(c)
    info["resultados"][1]["context_id"] = info["resultados"][0]["context_id"]
    with pytest.raises(ValueError, match="repetidos"):
        validar_reporte(c, "sha-corpus", info)


def test_rechaza_chunk_ajeno():
    c = casos()
    info = informe(c)
    info["resultados"][0]["scibert_top3"][0]["chunk_id"] = "CHUNK-AJENO"
    with pytest.raises(ValueError, match="ajeno"):
        validar_reporte(c, "sha-corpus", info)


def test_rechaza_ranking_repetido():
    c = casos()
    info = informe(c)
    info["resultados"][0]["scibert_top3"][1]["chunk_id"] = info["resultados"][0]["scibert_top3"][0]["chunk_id"]
    with pytest.raises(ValueError, match="repetidos"):
        validar_reporte(c, "sha-corpus", info)


def test_rechaza_similitud_invalida():
    c = casos()
    info = informe(c)
    info["resultados"][0]["scibert_top3"][0]["similitud_coseno"] = float("nan")
    with pytest.raises(ValueError, match="Similitud"):
        validar_reporte(c, "sha-corpus", info)


def test_prompt_no_filtra_seccion_de_c3():
    c = casos()
    info = informe(c)
    prompt = crear_prompt_c2(c[0], info["resultados"][0])
    assert "TARGETCIT" in prompt
    assert "Cited paper title: Method for Citation" in prompt
    assert "retrieved by SciBERT" in prompt
    assert "section=Methods" not in prompt
    assert "[p00001-p00001 | cited_id=P10-1000]" in prompt
    assert prompt.count("cited_id=P10-1000") == 3


def test_huella_aisla_experimentos_y_modelo():
    h = huella_ejecucion("qwen3:4b-instruct", "abc", "reporteA", "rev")
    assert h != huella_ejecucion("qwen3:4b-instruct", "abc", "reporteB", "rev")
    assert h != huella_ejecucion("otro", "abc", "reporteA", "rev")


def test_reanudacion_y_traza_sin_gold(tmp_path):
    class Cliente:
        model = "mock-qwen"
        def __init__(self):
            self.prompts = []
        def generate(self, prompt):
            self.prompts.append(prompt)
            return SimpleNamespace(text="Basis", input_tokens=100, output_tokens=1)

    c = casos()
    index = validar_reporte(c, "sha-corpus", informe(c))
    cliente = Cliente()
    salida = tmp_path / "predicciones.jsonl"
    x = ejecutar(c, index, cliente=cliente, salida=salida, run_id="id-run", limite=2)
    assert x["estados"] == {"ok": 2}
    assert x["nuevas_inferencias"] == 2
    assert len(cliente.prompts) == 2
    from json import loads
    registros = [loads(z) for z in salida.read_text(encoding="utf-8").splitlines()]
    assert all(r["is_human_label"] is False for r in registros)
    assert all(r["scores"] is None and r["suggested_label"] == "Basis" for r in registros)
    assert all(len(r["retrieved_chunks"]) == 3 for r in registros)
    assert all("text_sha256" in t for r in registros for t in r["retrieved_chunks"])
    y = ejecutar(c, index, cliente=cliente, salida=salida, run_id="id-run", limite=2)
    assert y["omitidos_por_reanudacion"] == 2 and y["nuevas_inferencias"] == 0


def test_respuesta_invalida_no_inventa_etiqueta(tmp_path):
    class Cliente:
        model = "mock-qwen"
        def generate(self, prompt):
            return SimpleNamespace(text="Basis or Evidence", input_tokens=None, output_tokens=None)
    c = casos()
    index = validar_reporte(c, "sha-corpus", informe(c))
    salida = tmp_path / "bad.jsonl"
    r = ejecutar(c, index, cliente=Cliente(), salida=salida, run_id="id", limite=1)
    assert r["estados"] == {"parse_error": 1}
    import json
    item = json.loads(salida.read_text(encoding="utf-8"))
    assert item["suggested_label"] is None and item["raw_response"] == "Basis or Evidence"
