"""Pruebas sin red ni dataset real para la auditoría de la caché ACL OCL."""

import csv
import json
from pathlib import Path

from proyecto_de_grado.src.data.auditar_corpus import (
    apariciones_cita,
    auditar,
    referencias_candidatas,
)


def test_bibref_candidata_y_cite_spans():
    doc = {"pdf_parse": {"bib_entries": {"BIBREF8": {
        "title": "Improving mention detection robustness to noisy input"
    }}, "body_text": [{"cite_spans": [{"ref_id": "BIBREF8"}]}]}}
    refs = referencias_candidatas(doc, "Improving mention detection robustness to noisy input")
    assert refs == {"BIBREF8"}
    assert apariciones_cita(doc, refs) == [0]


def test_sin_coincidencia_no_inventa_referencias():
    doc = {"pdf_parse": {"bib_entries": {"X": {"title": "Entirely different work title"}},
                         "body_text": [{"cite_spans": []}]}}
    assert not referencias_candidatas(doc, "Improving mention detection robustness to noisy input")
    assert not apariciones_cita(doc, set())


def test_auditoria_con_documento_citante_no_descargado(tmp_path):
    raw = tmp_path / "raw"
    cache = tmp_path / "cache"
    salida = tmp_path / "salida"
    raw.mkdir()
    cache.mkdir()
    contexto_id = "P15-2138_N04-1019_0"
    data = {
        "contexts.json": {contexto_id: {
            "citing_id": "P15-2138", "refid": "N04-1019",
            "masked_text": "In the study TARGETCIT we found strong evidence for this statement."
        }},
        "papers.json": {"N04-1019": {"title": "Some Example Article", "abstract": "Abstract"}},
        "train.json": [{"context_id": contexto_id}],
        "val.json": [],
        "test.json": [],
    }
    for nombre, contenido in data.items():
        (raw / nombre).write_text(json.dumps(contenido), encoding="utf-8")
    doc = {
        "paper_id": "N04-1019", "title": "Some Example Article",
        "pdf_parse": {"bib_entries": {}, "body_text": [
            {"text": ("scientific word " * 110), "section": "Introduction"},
            {"text": ("scientific word " * 110), "section": "Methods"},
            {"text": ("scientific word " * 110), "section": "Results"},
        ]},
    }
    (cache / "N04-1019.json").write_text(json.dumps(doc), encoding="utf-8")
    filas = auditar(raw, cache, salida)
    assert len(filas) == 1
    assert filas[0]["estado"] == "citante_no_descargado"
    assert filas[0]["citado_usable"] == 1
    assert (salida / "resumen_auditoria.md").exists()
    with (salida / "auditoria_contextos.csv").open(encoding="utf-8-sig", newline="") as fh:
        registros = list(csv.DictReader(fh))
    assert registros[0]["context_id"] == contexto_id


def test_limite_negativo_prohibido(tmp_path):
    import pytest
    with pytest.raises(ValueError, match="limite"):
        auditar(tmp_path, tmp_path, tmp_path, -1)
