"""Controles S2.2: procedencia, chunks, separacion train y artefacto local."""
import json

import pytest

from proyecto_de_grado.src.data.exportar_corpus_top3 import (
    exportar, fragmentar, preparar
)


def _parrafo(numero, texto, seccion="Methods"):
    return {"numero": numero, "texto": texto, "seccion": seccion}


def _datos(tmp_path):
    raw = tmp_path / "raw"
    cache = tmp_path / "cache"
    raw.mkdir()
    cache.mkdir()
    ids = {
        "train": ("P15-1001", "P14-1001"),
        "val": ("P15-1002", "P14-1002"),
        "test": ("P15-1003", "P14-1003"),
    }
    ctx, splits, papers = {}, {}, {}
    for split, (citante, citado) in ids.items():
        cid = f"{citante}_{citado}_0"
        ctx[cid] = {
            "citing_id": citante, "refid": citado,
            "masked_text": "Background and neural methods (TARGETCIT) are used."
        }
        splits[split] = [{"context_id": cid, "positive_ids": [citado]}]
        papers[citado] = {"title": f"Paper {citado}", "abstract": "Abstract"}
        doc = {
            "paper_id": citado, "title": "Original",
            "pdf_parse": {"body_text": [
                {"text": "Neural representation methods are useful.", "section": "Methods"},
                {"text": "Embeddings capture evidence from context.", "section": "Methods"},
                {"text": "Results differ across the experiments.", "section": "Results"},
            ]}
        }
        (cache / f"{citado}.json").write_text(json.dumps(doc), encoding="utf-8")
    (raw / "contexts.json").write_text(json.dumps(ctx), encoding="utf-8")
    (raw / "papers.json").write_text(json.dumps(papers), encoding="utf-8")
    for split, rows in splits.items():
        (raw / f"{split}.json").write_text(json.dumps(rows), encoding="utf-8")
    return raw, cache, ctx, papers, splits


def test_chunks_respetan_limites_y_secciones():
    chunks = fragmentar([
        _parrafo(0, "Neural graph structures."),
        _parrafo(1, "Scientific evidence supports results."),
        _parrafo(2, "A separate section.", "Results"),
    ])
    assert len(chunks) == 2
    assert chunks[0]["paragraph_indices"] == [0, 1]
    assert chunks[0]["seccion"] == "Methods"
    assert chunks[1]["paragraph_indices"] == [2]
    assert all(c["palabras"] <= 300 for c in chunks)


def test_nunca_trunca_parrafos_largos_en_silencio():
    with pytest.raises(ValueError, match="demasiado largo"):
        fragmentar([_parrafo(0, "x " * 301)])


def test_indices_incorrectos_se_rechazan():
    with pytest.raises(ValueError, match="duplicado"):
        fragmentar([_parrafo(0, "a"), _parrafo(0, "b")])


def test_exporta_solo_train_con_identidad_ocl_verificada(tmp_path):
    raw, cache, ctx, papers, splits = _datos(tmp_path)
    salida = tmp_path / "artifacts" / "casos_train.json"
    info = exportar(raw, cache, salida, excluidos=set(), limite=5)
    assert salida.exists()
    assert info["resumen"]["total"] == 1
    caso = info["casos"][0]
    assert caso["context_id"] == splits["train"][0]["context_id"]
    assert caso["split"] == "train"
    assert caso["cited_id"] == "P14-1001"
    assert caso["citation_context"].count("TARGETCIT") == 1
    assert len(caso["sha256_ocl_citado"]) == 64
    assert [c["chunk_id"] for c in caso["chunks"]] == ["p00000-p00001", "p00002-p00002"]
    assert not any(caso["context_id"] == cid for cid in (
        splits["val"][0]["context_id"], splits["test"][0]["context_id"]
    ))


def test_exclusiones_no_se_filtran_al_artefacto(tmp_path):
    raw, cache, ctx, papers, splits = _datos(tmp_path)
    out = tmp_path / "out.json"
    with pytest.raises(ValueError, match="No hay casos"):
        exportar(raw, cache, out, {splits["train"][0]["context_id"]}, 5)
    assert not out.exists()


def test_citado_con_paper_id_incoherente_es_omitido(tmp_path):
    raw, cache, ctx, papers, splits = _datos(tmp_path)
    archivo = cache / "P14-1001.json"
    j = json.loads(archivo.read_text(encoding="utf-8"))
    j["paper_id"] = "P14-9999"
    archivo.write_text(json.dumps(j), encoding="utf-8")
    salida = tmp_path / "output.json"
    with pytest.raises(ValueError, match="No hay casos"):
        exportar(raw, cache, salida, set(), 5)
    assert not salida.exists()


def test_artefacto_se_reproduce_byte_por_byte(tmp_path):
    raw, cache, *_ = _datos(tmp_path)
    out1, out2 = tmp_path/"one.json", tmp_path/"two.json"
    exportar(raw, cache, out1, set(), 5)
    exportar(raw, cache, out2, set(), 5)
    assert out1.read_bytes() == out2.read_bytes()


def test_secciones_multiples_no_se_cruzan_con_chunk():
    chunks = fragmentar([
        _parrafo(0,"first", "Intro"),
        _parrafo(1,"second", "Method"),
        _parrafo(2,"third", "Method"),
    ])
    assert [c["paragraph_indices"] for c in chunks] == [[0], [1,2]]
