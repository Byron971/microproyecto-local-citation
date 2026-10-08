"""Pruebas de inspeccion G1.1, sin corpus real, red ni escritura."""
import csv
import json

import pytest

from proyecto_de_grado.src.data.inspeccionar_alineacion import (
    extracto, inspeccionar_caso, inspeccionar_reporte,
)


def sample():
    cid = "CIT-REF-0"
    ctx = {cid: {"citing_id": "CIT", "refid": "REF", "masked_text": "Old TARGETCIT method"}}
    papers = {"REF": {"title": "An Effective Scientific Method for Citations"}}
    txt = "Prior studies propose (Smith, 2012), and more recent work contrasts them."
    start = txt.index("(Smith, 2012)")
    citation = {"ref_id": "BIBREF1", "text": "(Smith, 2012)",
                "start": start, "end": start + len("(Smith, 2012)")}
    doc = {"paper_id": "CIT", "pdf_parse": {
        "bib_entries": {"BIBREF1": {"title": "An Effective Scientific Method for Citations"}},
        "body_text": [{"text": txt, "section": "Background", "cite_spans": [citation]}],
    }}
    row = {"context_id": cid, "split": "train", "citing_id": "CIT",
           "cited_id": "REF", "score_texto": "1.0", "parrafo_texto": "0"}
    return row, ctx, papers, doc


def test_inspector_enlaza_span_y_solo_lo_declara_candidato():
    row, ctx, papers, doc = sample()
    r = inspeccionar_caso(row, ctx, papers, doc)
    assert r["estado"] == "cita_bibliografica_candidata_en_parrafo"
    assert r["refs_candidatas"] == ["BIBREF1"]
    assert len(r["spans_candidatos"]) == 1
    assert r["spans_candidatos"][0]["posicion_valida"]
    assert r["spans_candidatos"][0]["texto_en_posicion"] == "(Smith, 2012)"
    assert r["nota"] == "NO ES VALIDACION DE TARGETCIT"


def test_no_confunde_span_de_otra_referencia():
    row, ctx, papers, doc = sample()
    doc["pdf_parse"]["body_text"][0]["cite_spans"][0]["ref_id"] = "BIBREF9"
    r = inspeccionar_caso(row, ctx, papers, doc)
    assert r["estado"] == "bibliografia_candidata_sin_cita_en_parrafo"
    assert r["spans_candidatos"] == []


def test_id_ocl_equivocado_no_se_acepta():
    row, ctx, papers, doc = sample()
    doc["paper_id"] = "OTRO"
    assert inspeccionar_caso(row, ctx, papers, doc)["estado"] == "id_citante_incorrecto"


def test_parrafo_fuera_de_rango_y_no_descargado():
    row, ctx, papers, doc = sample()
    assert inspeccionar_caso(row, ctx, papers, None)["estado"] == "citante_no_descargado_o_invalido"
    row["parrafo_texto"] = "100"
    assert inspeccionar_caso(row, ctx, papers, doc)["estado"] == "parrafo_fuera_de_rango"


def test_contexto_diferente_rechazado():
    row, ctx, papers, doc = sample()
    row["cited_id"] = "REF_DISTINTO"
    with pytest.raises(ValueError, match="incoherente"):
        inspeccionar_caso(row, ctx, papers, doc)


def test_dos_contextos_del_mismo_par_no_se_fusionan(tmp_path):
    row, ctx, papers, doc = sample()
    row2 = {**row, "context_id": "CIT-REF-1"}
    ctx[row2["context_id"]] = {**ctx[row["context_id"]]}
    raw = tmp_path / "raw"
    raw.mkdir()
    cache = tmp_path / "cache"
    cache.mkdir()
    for fname, data in (("contexts.json", ctx), ("papers.json", papers)):
        (raw / fname).write_text(json.dumps(data), encoding="utf-8")
    (cache / "CIT.json").write_text(json.dumps(doc), encoding="utf-8")
    csv_path = tmp_path / "report.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=[*row, "estado"])
        writer.writeheader()
        writer.writerow({**row, "estado": "alineacion_candidata"})
        writer.writerow({**row2, "estado": "alineacion_candidata"})
    result = inspeccionar_reporte(raw, cache, csv_path)
    assert [r["context_id"] for r in result] == ["CIT-REF-0", "CIT-REF-1"]


def test_extracto_no_inventa_texto():
    assert extracto("", caracteres=20) == ""
    assert extracto("ABCDEFGHIJK", 3, caracteres=5) == "...BCDEF..."
