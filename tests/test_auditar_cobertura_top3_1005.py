"""Pruebas de auditoría exhaustiva, sin acceso a datos privados."""
from scripts.auditar_cobertura_top3_1005 import auditar


def corpus():
    return {"version": 1, "tipo": "test", "casos": [
        {"context_id": "a", "chunks": [{"chunk_id": "c1"}, {"chunk_id": "c2"}]},
        {"context_id": "b", "chunks": [{"chunk_id": "d1"}]},
    ]}


def test_cobertura_total():
    resultado = auditar(corpus(), {"a": {"c1": 1, "c2": 0}, "b": {"d1": 0}},
                        {"BM25": {"a": ["c1", "c2"], "b": ["d1"]}})
    assert resultado["estado"] == "exhaustivo"
    assert resultado["pares_corpus"] == 3
    assert resultado["relevancia_exhaustiva_en_corpus"]
    assert resultado["rankings_validos"]
    assert resultado["consultas_sin_positivos"] == 1


def test_ausente_no_es_exhaustivo():
    resultado = auditar(corpus(), {"a": {"c1": 1}, "b": {"d1": 0}})
    assert not resultado["relevancia_exhaustiva_en_corpus"]
    assert resultado["pares_sin_etiqueta"] == 1


def test_ranking_ajeno_falla():
    resultado = auditar(corpus(), {"a": {"c1": 1, "c2": 0}, "b": {"d1": 0}},
                        {"SciBERT": {"a": ["ajeno"], "b": ["d1"]}})
    assert not resultado["rankings_validos"]
    assert resultado["rankings"]["SciBERT"]["top3_chunks_fuera_corpus"] == 1
