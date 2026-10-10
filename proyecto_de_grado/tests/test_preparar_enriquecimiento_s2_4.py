"""Controles S2.4: etiquetas nulas, fuentes, splits, duplicados y DVC intacto."""
import json
from pathlib import Path

import pytest

from proyecto_de_grado.src.data.preparar_enriquecimiento_s2_4 import (
    _analizar_citado, auditar_y_seleccionar, ejecutar, huella_contexto,
)
from proyecto_de_grado.src.data.validar_splits import load_split_index


def _corpus(tmp_path):
    raw, cache = tmp_path / "raw", tmp_path / "cache"
    raw.mkdir()
    cache.mkdir()
    contextos, papers = {}, {}
    splits = {"train": [], "val": [], "test": []}
    casos = [
        ("train", "P12-1001", "P11-1000", "Background neural models TARGETCIT one."),
        ("train", "P12-1002", "P11-1000", "Methods graph networks TARGETCIT two."),
        ("train", "P12-1003", "P11-9999", "Uncached document TARGETCIT three."),
        ("train", "P12-1004", "P11-1000", "Repeated text TARGETCIT across split."),
        ("val", "P13-1001", "P11-1000", "Repeated text TARGETCIT across split."),
        ("test", "P14-1001", "P11-1000", "Independent TARGETCIT test example."),
    ]
    for split, citante, citado, texto in casos:
        cid = f"{citante}_{citado}_0"
        contextos[cid] = {"citing_id": citante, "refid": citado, "masked_text": texto}
        splits[split].append({"context_id": cid, "positive_ids": [citado]})
        papers[citado] = {"title": f"Paper {citado}", "abstract": "Scientific abstract."}
    doc = {
        "paper_id": "P11-1000", "title": "ACL OCL Paper",
        "pdf_parse": {"body_text": [
            {"text": "Graphs and citation functions are studied.", "section": "Methods"},
            {"text": "Background evidence helps identify sources.", "section": "Methods"},
            {"text": "Experiments compare methods.", "section": "Results"},
        ]},
    }
    (cache / "P11-1000.json").write_text(json.dumps(doc), encoding="utf-8")
    for name, payload in {"contexts.json": contextos, "papers.json": papers,
                          **{f"{s}.json": rows for s, rows in splits.items()}}.items():
        (raw / name).write_text(json.dumps(payload), encoding="utf-8")
    return raw, cache, splits


def test_incluye_varios_contextos_del_mismo_articulo_y_solo_train(tmp_path):
    raw, cache, splits = _corpus(tmp_path)
    result, summary = auditar_y_seleccionar(
        load_split_index(raw),
        json.loads((raw / "papers.json").read_text()), cache, set(),
        limite=10, semilla=42, max_por_citado=4,
    )
    assert len(result) == 2
    assert {r["id"] for r in result} == {
        splits["train"][0]["context_id"], splits["train"][1]["context_id"]
    }
    assert {r["cited_id"] for r in result} == {"P11-1000"}
    assert all(r["split"] == "train" for r in result)
    assert summary["por_split"]["val"]["contextos"] == 1
    assert summary["por_split"]["test"]["contextos"] == 1
    assert summary["por_split"]["train"]["train_excluido_texto_cruzado"] == 1
    assert summary["textos_exactos_cruzados_distintos"] == 1


def test_registros_preservan_fuentes_y_no_crean_etiquetas(tmp_path):
    raw, cache, _ = _corpus(tmp_path)
    selected, summary = auditar_y_seleccionar(
        load_split_index(raw),
        json.loads((raw / "papers.json").read_text()), cache, set(), 10,
    )
    assert len(summary["taxonomia_funcion_cita"]) == 9
    assert summary["clases_funcion_cita_con_etiquetas_verificadas"] == 0
    assert summary["fuentes_externas_fusionadas"] == []
    for r in selected:
        assert r["citation_context"].count("TARGETCIT") == 1
        assert r["funcion_cita"]["etiqueta_principal"] is None
        assert r["funcion_cita"]["estado"] == "no_etiquetado"
        assert r["evidencia_top3"]["fragmentos_relevantes_adjudicados"] is None
        assert r["fuentes"]["contexto"]["nombre"] == "ACL-200"
        assert r["fuentes"]["texto_citado"]["paper_id"] == r["cited_id"]
        assert len(r["fuentes"]["texto_citado"]["sha256"]) == 64
        assert r["fuentes"]["otras_fuentes_integradas"] == []
        assert all(c["palabras"] <= 300 and len(c["paragraph_indices"]) <= 2
                   for c in r["cited_chunks"])


def test_exclusiones_y_maximo_por_citado(tmp_path):
    raw, cache, splits = _corpus(tmp_path)
    index = load_split_index(raw)
    papers = json.loads((raw / "papers.json").read_text())
    selected, res = auditar_y_seleccionar(index, papers, cache, set(),
                                         limite=10, max_por_citado=1)
    assert len(selected) == 1
    assert res["omision_por_equilibrio"]["limite_por_articulo_citado"] == 1
    excluded = {splits["train"][0]["context_id"]}
    selected, res = auditar_y_seleccionar(index, papers, cache, excluded,
                                         limite=10, max_por_citado=4)
    assert [x["id"] for x in selected] == [splits["train"][1]["context_id"]]


def test_cache_faltante_y_404_no_son_datos_falsos(tmp_path):
    raw, cache, splits = _corpus(tmp_path)
    (cache / "P11-9999.404").write_text("", encoding="utf-8")
    index = load_split_index(raw)
    selected, res = auditar_y_seleccionar(
        index, json.loads((raw / "papers.json").read_text()), cache, set(),
    )
    assert len(selected) == 2
    assert res["por_split"]["train"]["estado_citado_no_disponible_404"] == 1


def test_id_ocl_incoherente_no_se_exporta(tmp_path):
    raw, cache, _ = _corpus(tmp_path)
    ruta = cache / "P11-1000.json"
    doc = json.loads(ruta.read_text())
    doc["paper_id"] = "P11-OTHER"
    ruta.write_text(json.dumps(doc), encoding="utf-8")
    candidates, summary = auditar_y_seleccionar(
        load_split_index(raw), json.loads((raw / "papers.json").read_text()),
        cache, set(),
    )
    assert candidates == []
    assert summary["documentos_citados_utilizables"] == 0
    assert summary["por_split"]["train"]["estado_citado_id_ocl_incorrecto"] == 3


def test_exportacion_reproducible_e_idempotente_no_toca_raw(tmp_path):
    raw, cache, _ = _corpus(tmp_path)
    salida = tmp_path / "out"
    original = {p.name: p.read_bytes() for p in raw.iterdir()}
    summary1 = ejecutar(raw, cache, salida, set(), 10, 42, 4)
    first = (salida / "candidatos_train_enriquecidos.jsonl").read_bytes()
    summary2 = ejecutar(raw, cache, salida, set(), 10, 42, 4)
    assert summary1 == summary2
    assert (salida / "candidatos_train_enriquecidos.jsonl").read_bytes() == first
    assert len(first.splitlines()) == 2
    assert {p.name: p.read_bytes() for p in raw.iterdir()} == original
    assert summary1["sha256_candidatos"]


def test_no_sobrescribe_evidencia_si_la_cache_cambia(tmp_path):
    raw, cache, _ = _corpus(tmp_path)
    salida = tmp_path / "out"
    ejecutar(raw, cache, salida, set(), 10)
    ruta = cache / "P11-1000.json"
    doc = json.loads(ruta.read_text())
    doc["pdf_parse"]["body_text"][0]["text"] = "New version of full text."
    ruta.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(ValueError, match="No se sobrescriben"):
        ejecutar(raw, cache, salida, set(), 10)


def test_no_selecciona_datos_val_test_si_train_no_tiene_cache(tmp_path):
    raw, cache, splits = _corpus(tmp_path)
    (cache / "P11-1000.json").unlink()
    selected, summary = auditar_y_seleccionar(
        load_split_index(raw), json.loads((raw / "papers.json").read_text()),
        cache, set(),
    )
    assert selected == []
    assert summary["seleccionados"] == 0
    assert summary["por_split"]["test"]["contextos"] == 1


def test_huella_exacta_no_sustituye_deduplicacion_semantica():
    assert huella_contexto("HELLO   TARGETCIT") == huella_contexto("hello TARGETCIT")
    assert huella_contexto("HELLO TARGETCIT") != huella_contexto("Hello, TARGETCIT")


def test_articulo_con_parrafos_largos_se_recupera_para_enriquecimiento_s2_4(tmp_path):
    raw, cache, splits = _corpus(tmp_path)
    ruta = cache / "P11-1000.json"
    doc = json.loads(ruta.read_text(encoding="utf-8"))
    texto_largo = " ".join(f"token{i}" for i in range(524))
    doc["pdf_parse"]["body_text"][0]["text"] = texto_largo
    ruta.write_text(json.dumps(doc), encoding="utf-8")
    metadata = json.loads((raw / "papers.json").read_text())
    audit = _analizar_citado("P11-1000", cache, metadata)
    assert audit["estado"] == "utilizable"
    chunks = [ch for ch in audit["chunks"] if ch["paragraph_indices"] == [0]]
    assert len(chunks) == 2
    assert "".join(ch["texto"] for ch in chunks) == texto_largo
    assert all(ch["seccion"] == "Methods" for ch in chunks)
    selected, summary = auditar_y_seleccionar(
        load_split_index(raw), metadata, cache, set(), limite=10
    )
    assert len(selected) == 2
    assert summary["documentos_citados_utilizables"] == 1
    assert all(any(ch["chunk_id"] == "p00000-s000" for ch in r["cited_chunks"]) for r in selected)
