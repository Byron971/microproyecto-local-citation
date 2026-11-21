"""Pruebas aisladas del recálculo Top-3 sobre etiquetas y rankings."""
import csv
import json

import pytest

from scripts.recalcular_top3_etiquetas_finales import (
    cargar_etiquetas, cargar_rankings, evaluar,
)


def test_evaluacion_pareada(tmp_path):
    p = tmp_path / "gold.csv"
    with p.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["context_id", "chunk_id", "relevante_0_1"])
        w.writerows([
            ("a", "c1", 1), ("a", "c2", 0), ("a", "c3", 1),
            ("b", "d1", 0), ("b", "d2", 0),
        ])
    gold = cargar_etiquetas(p)
    r = evaluar(gold, {"a": ["c1", "c2", "c3"], "b": ["d1"]},
                {"a": ["c2", "c1", "c3"], "b": ["d2"]})
    assert r["consultas_elegibles"] == 1
    assert r["consultas_sin_positivos"] == 1
    assert r["juicios"] == 5
    assert r["relevantes"] == 2
    assert r["resultados"]["BM25"]["hit_at_3"] == 1
    assert r["resultados"]["BM25"]["recall_at_3"] == 1
    assert r["resultados"]["BM25"]["mrr_at_3"] == 1
    assert r["resultados"]["SciBERT"]["mrr_at_3"] == 0.5


def test_ranking_lista_y_mapa(tmp_path):
    p = tmp_path / "ranking.json"
    p.write_text(json.dumps({"casos": [{"context_id": "a", "top3": [
        {"chunk_id": "c1"}, {"chunk_id": "c2"}]}]}))
    assert cargar_rankings(p) == {"a": ["c1", "c2"]}
    p.write_text(json.dumps({"a": ["c1", "c2"]}))
    assert cargar_rankings(p) == {"a": ["c1", "c2"]}


def test_falla_si_ranking_no_cubre_consultas():
    with pytest.raises(ValueError, match="IDs no coinciden"):
        evaluar({"a": {"c1": 1}}, {"a": ["c1"]}, {})
