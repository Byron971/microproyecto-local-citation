"""S2.8: pruebas puras, sin GPU, red ni descargas de modelos."""
import json
import pytest

from proyecto_de_grado.src.retrieval.scibert_top3_s2_8 import (
    _normalizar_contexto, ordenar_top3, validar_casos, ejecutar, main
)


class EncoderFalso:
    model_id = "simulado-test"
    revision = "fixture"
    max_length = 512
    batch_size = 4

    def __init__(self):
        self.llamadas = []

    def encode(self, textos):
        self.llamadas.append(tuple(textos))
        return [(1.0, 0.0) if "alpha" in t.lower() else (0.0, 1.0) for t in textos]


def _caso(cid="id-1", pid="P05-1033", consulta="alpha TARGETCIT"):
    return {
        "id": cid, "split": "train", "cited_id": pid,
        "citation_context": consulta,
        "cited_chunks": [
            {"chunk_id": "a", "texto": "alpha evidence", "seccion": "A"},
            {"chunk_id": "b", "texto": "beta evidence", "seccion": "B"},
            {"chunk_id": "c", "texto": "alpha contribution", "seccion": "C"},
            {"chunk_id": "d", "texto": "beta related work", "seccion": "D"},
        ],
        "evidencia_top3": {"fragmentos_relevantes_adjudicados": None},
    }


def bm25_simulado(contexto, chunks):
    return [{"posicion": 1, "chunk_id": chunks[1]["chunk_id"], "puntaje_bm25": 1.2}]


def test_no_permite_val_test_gold():
    c = _caso()
    c["split"] = "test"
    with pytest.raises(ValueError, match="train"):
        validar_casos([c])
    c["split"] = "train"
    c["evidencia_top3"]["fragmentos_relevantes_adjudicados"] = ["a"]
    with pytest.raises(ValueError, match="relevancias humanas"):
        validar_casos([c])


def test_no_acepta_contexto_sin_cita_unica():
    c = _caso(consulta="alpha TARGETCIT TARGETCIT")
    with pytest.raises(ValueError, match="TARGETCIT"):
        validar_casos([c])


def test_no_acepta_chunks_duplicados():
    c = _caso()
    c["cited_chunks"][1]["chunk_id"] = "a"
    with pytest.raises(ValueError, match="duplicado"):
        validar_casos([c])


def test_no_acepta_contextos_repetidos_ni_corpus_inconsistente():
    with pytest.raises(ValueError, match="duplicado"):
        validar_casos([_caso(), _caso()])
    b = _caso(cid="id-2")
    b["cited_chunks"][0]["texto"] = "manipulado"
    with pytest.raises(ValueError, match="inconsistentes"):
        validar_casos([_caso(), b])


def test_top3_orden_estable_por_id_en_empates():
    chunks = [{"chunk_id": i} for i in ("z", "a", "y", "b")]
    res = ordenar_top3((2, 0), chunks, [(4, 0)] * 4)
    assert [x["chunk_id"] for x in res] == ["a", "b", "y"]
    assert [x["posicion"] for x in res] == [1, 2, 3]


def test_top3_valida_dimensiones():
    with pytest.raises(ValueError, match="Dimensiones"):
        ordenar_top3((1, 0), [{"chunk_id": "a"}], [(1, 0, 0)])


def test_reutiliza_embedding_por_articulo_y_no_genera_gold():
    falso = EncoderFalso()
    a = _caso()
    b = _caso(cid="id-2", consulta="beta TARGETCIT")
    informe = ejecutar([a, b], falso, bm25_simulado)
    assert informe["resumen"]["documentos_vectorizados_una_vez"] == 1
    assert len(falso.llamadas) == 3  # un corpus y dos consultas
    assert len(falso.llamadas[0]) == 4
    assert all(c["split"] == "train" for c in informe["resultados"])
    assert informe["resumen"]["metricas_gold_calculadas"] is False
    assert "recall" not in json.dumps(informe).lower()
    assert [r["chunk_id"] for r in informe["resultados"][0]["scibert_top3"]] == ["a", "c", "b"]
    assert not any("texto" in x for x in informe["resultados"][0]["scibert_top3"])


def test_mismo_paper_no_mezcla_chunks_de_otro_articulo():
    falso = EncoderFalso()
    a = _caso()
    b = _caso(cid="id-2", pid="P08-1122", consulta="beta TARGETCIT")
    for c in b["cited_chunks"]:
        c["chunk_id"] += "-otro"
    out = ejecutar([a, b], falso, bm25_simulado)
    assert out["resumen"]["articulos"] == 2
    assert all(x["chunk_id"].endswith("-otro") for x in out["resultados"][1]["scibert_top3"])


def test_validacion_offline_no_carga_modelo(tmp_path, capsys):
    archivo = tmp_path / "casos.jsonl"
    archivo.write_text(json.dumps(_caso()) + "\n", encoding="utf-8")
    assert main(["--input", str(archivo), "--solo-validar"]) == 0
    assert "CORPUS VÁLIDO" in capsys.readouterr().out


def test_normalizar_contexto_quita_marcadores():
    assert _normalizar_contexto("A OTHERCIT alpha TARGETCIT B") == "A alpha B"
