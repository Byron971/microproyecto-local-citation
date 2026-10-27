"""Pruebas sin red del reproductor G1.3 y su baseline, independientes de DVC."""
import json

import pytest

from proyecto_de_grado.scripts.reproducir_g1_3_equipo import (
    cargar_baseline, comparar_resultado, ejecutar,
)


def preparar(tmp_path):
    raw = tmp_path / "raw"
    cache = tmp_path / "cache"
    raw.mkdir()
    cache.mkdir()
    cid = "P12-1000_P09-1000_0"
    cuerpo = (
        "An earlier method established these procedures and important alternatives; "
        "our approach adopts rich features from the previous system "
        "(Feng and Hirst, 2012) . However scalability remains limited when "
        "processing large collections."
    )
    masked = (
        "An earlier method established these procedures and important alternatives; "
        "our approach adopts rich features from the previous system "
        "( TARGETCIT . However scalability remains limited when "
        "processing large collections."
    )
    comienzo = cuerpo.index("(Feng and Hirst, 2012)")
    (raw / "contexts.json").write_text(json.dumps({cid: {
        "citing_id": "P12-1000", "refid": "P09-1000", "masked_text": masked
    }}), encoding="utf-8")
    (raw / "papers.json").write_text(json.dumps({
        "P09-1000": {"title": "An Effective Scientific Method for Citations"}
    }), encoding="utf-8")
    for part in ("train", "val", "test"):
        rows = [{"context_id": cid, "positive_ids": ["P09-1000"]}] if part == "train" else []
        (raw / f"{part}.json").write_text(json.dumps(rows), encoding="utf-8")
    citing_doc = {"paper_id": "P12-1000", "pdf_parse": {
        "bib_entries": {"BIBREF4": {"title": "An Effective Scientific Method for Citations"}},
        "body_text": [{"text": cuerpo, "section": "Background",
                       "cite_spans": [{"ref_id": "BIBREF4", "text": "(Feng and Hirst, 2012)",
                                       "start": comienzo, "end": comienzo + len("(Feng and Hirst, 2012)")}]}],
    }}
    (cache / "P12-1000.json").write_text(json.dumps(citing_doc), encoding="utf-8")
    (cache / "P09-1000.json").write_text(
        json.dumps({"paper_id": "P09-1000", "pdf_parse": {"body_text": []}}),
        encoding="utf-8")
    baseline = tmp_path / "baseline.jsonl"
    baseline.write_text(json.dumps({
        "context_id": cid,
        "split": "train",
        "estado": "reconstruccion_candidata_revision_humana",
        "motivo": None,
        "citation_ref_id": "BIBREF4",
        "oracion_con_targetcit": (
            "An earlier method established these procedures and important alternatives; "
            "our approach adopts rich features from the previous system (TARGETCIT)."
        )
    }) + "\n", encoding="utf-8")
    return raw, cache, baseline, tmp_path / "out.jsonl"


def test_solo_reproduce_original_y_compara_baseline(tmp_path):
    raw, cache, baseline, out = preparar(tmp_path)
    total, diferentes = ejecutar(raw, cache, baseline, out)
    assert (total, diferentes) == (1, 0)
    registros = [json.loads(s) for s in out.read_text(encoding="utf-8").splitlines()]
    assert registros[0]["resultado"] == "coincide"
    assert registros[0]["parrafo_indice"] == 0
    assert registros[0]["oracion_con_targetcit"].endswith("(TARGETCIT).")


def test_no_descarga_documentos_ni_oculta_su_ausencia(tmp_path):
    raw, cache, baseline, out = preparar(tmp_path)
    (cache / "P09-1000.json").unlink()
    with pytest.raises(FileNotFoundError, match="--descargar-faltantes"):
        ejecutar(raw, cache, baseline, out)
    assert not out.exists()


def test_inconsistencia_de_splits_no_se_oculta(tmp_path):
    raw, cache, baseline, out = preparar(tmp_path)
    reg = json.loads(baseline.read_text(encoding="utf-8"))
    reg["split"] = "test"
    baseline.write_text(json.dumps(reg), encoding="utf-8")
    with pytest.raises(ValueError, match="Split original"):
        ejecutar(raw, cache, baseline, out)


def test_resultado_distinto_queda_reportado(tmp_path):
    raw, cache, baseline, out = preparar(tmp_path)
    reg = json.loads(baseline.read_text(encoding="utf-8"))
    reg["oracion_con_targetcit"] = "texto esperado falso"
    baseline.write_text(json.dumps(reg), encoding="utf-8")
    total, diferentes = ejecutar(raw, cache, baseline, out)
    assert (total, diferentes) == (1, 1)
    registrado = json.loads(out.read_text(encoding="utf-8"))
    assert registrado["diferencias_vs_baseline"] == ["oracion_con_targetcit"]


def test_id_baseline_duplicado_no_aceptado(tmp_path):
    _, _, baseline, _ = preparar(tmp_path)
    original = baseline.read_text(encoding="utf-8")
    baseline.write_text(original + original, encoding="utf-8")
    with pytest.raises(ValueError, match="repetidos"):
        cargar_baseline(baseline)


def test_comparador_no_confunde_motivo_y_estado():
    esperado = {"split": "train", "estado": "revision_manual",
                "motivo": "ambiguedad", "citation_ref_id": None,
                "oracion_con_targetcit": None}
    actual = {**esperado, "motivo": "otra_razon"}
    assert comparar_resultado(actual, esperado) == ["motivo"]
