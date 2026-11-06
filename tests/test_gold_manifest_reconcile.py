"""Comparación PR91/PR92: pruebas sintéticas y caso real inmutable."""
import csv
import json
from pathlib import Path

import pytest

from src.evaluation.commercial.gold_existing_csv_audit import (
    ANNOTATED, DATA_COLUMNS, HAIKU, MANIFEST, _read,
)
from src.evaluation.commercial.gold_policy import exclusion_ids
from src.evaluation.commercial.gold_manifest_reconcile import (
    PR91_MANIFEST, main, read_pr91_manifest, reconcile,
)


def _annotation(cid, status="COMPLETO"):
    return {
        "context_id": cid, "Estado": status, "Función principal": "Background",
    }


def _inputs():
    test1 = "P15-0001_P13-0001_0"
    test2 = "P15-0002_P13-0002_0"
    test3 = "P15-0003_P13-0003_0"
    cal = "P14-0001_P13-0001_0"
    rows91 = [
        {"context_id": test1, "grupo": "testgold", "tanda": "1"},
        {"context_id": test2, "grupo": "testgold", "tanda": "2"},
        {"context_id": cal, "grupo": "calibracion3", "tanda": ""},
    ]
    annotated = {
        test1: _annotation(test1),
        test3: _annotation(test3),
        cal: _annotation(cal),
    }
    manifest = {cid: {"context_id": cid} for cid in annotated}
    haiku_id = "P12-0001_P08-0002_0"
    haiku = {haiku_id: _annotation(haiku_id)}
    return rows91, annotated, manifest, haiku, test1, test2, test3, cal


def test_reconciliation_does_not_claim_double_annotation():
    rows91, a, m, h, t1, t2, t3, cal = _inputs()
    report = reconcile(rows91, a, m, h, excluded=set())
    x = report["cross_manifest"]
    assert x["pr91_test_present_in_pr92"] == 1
    assert x["pr91_test_not_in_pr92"] == 1
    assert x["pr92_test_not_in_pr91"] == 1
    assert x["pr91_calibration_present_in_pr92"] == 1
    assert x["pr91_test_present_status"] == {"COMPLETO": 1}
    assert report["pr91"]["tandas"]["1"]["present_in_annotated_2700"] == 1
    assert report["pr91"]["tandas"]["2"]["absent_from_annotated_2700"] == 1
    assert report["status"] == "DECISION_MANIFIESTO_CANONICO_PENDIENTE"
    assert report["gold_human_certified"] is False
    assert report["double_annotation_verified"] is False
    assert report["final_benchmark_allowed"] is False


def test_exclusion_filters_not_destroy_annotations():
    rows91, a, m, h, t1, _, t3, _ = _inputs()
    report = reconcile(rows91, a, m, h, excluded={t1, t3})
    assert report["pr92"]["annotation_rows"] == 3
    assert report["pr92"]["test_2015_after_historical_exclusions"] == 0
    assert report["pr91"]["tandas"]["1"]["historical_exclusions"] == 1
    assert report["cross_manifest"]["pr91_test_historical_exclusions"] == 1


def test_overlap_with_haiku_is_counted_not_hidden():
    rows91, a, m, h, t1, _, _, _ = _inputs()
    h[t1] = _annotation(t1)
    report = reconcile(rows91, a, m, h, excluded=set())
    assert report["cross_manifest"]["pr91_test_overlap_with_haiku"] == 1
    assert report["cross_manifest"]["pr92_all_overlap_with_haiku"] == 1
    assert not report["final_benchmark_allowed"]


def test_manifest_mismatch_fails_closed():
    rows91, a, m, h, t1, _, _, _ = _inputs()
    m.pop(t1)
    with pytest.raises(ValueError, match="no coinciden"):
        reconcile(rows91, a, m, h, excluded=set())


def test_duplicate_pr91_ids_not_accepted():
    rows91, a, m, h, _, _, _, _ = _inputs()
    with pytest.raises(ValueError, match="duplicados"):
        reconcile(rows91 + [rows91[0]], a, m, h, excluded=set())


def test_pr91_reader_rejects_wrong_tanda_or_year(tmp_path):
    p = tmp_path / "manifest.csv"
    p.write_text("context_id,grupo,tanda\nP14-0001_P13-0001_0,testgold,1\n", encoding="utf-8")
    with pytest.raises(ValueError, match="tanda/año"):
        read_pr91_manifest(p)
    p.write_text("context_id,grupo,tanda\nP15-0001_P13-0001_0,calibracion3,\n", encoding="utf-8")
    with pytest.raises(ValueError, match="calibración"):
        read_pr91_manifest(p)


def test_real_pr91_vs_pr92_existing_files():
    # Nunca incluir los IDs ni textos de casos individuales en artefactos CI.
    rows91 = read_pr91_manifest(PR91_MANIFEST)
    a = _read(ANNOTATED, DATA_COLUMNS)
    m = _read(MANIFEST, ("context_id", "anio_citante", "prelabel_qlora"))
    h = _read(HAIKU, DATA_COLUMNS)
    report = reconcile(rows91, a, m, h, excluded=exclusion_ids())
    assert report["pr91"]["manifest_rows"] == 1553
    assert report["pr91"]["testgold_2015"] == 1533
    assert report["pr91"]["calibration_2014"] == 20
    assert report["pr91"]["tandas"]["1"]["planned"] == 519
    assert report["pr91"]["tandas"]["2"]["planned"] == 441
    assert report["pr91"]["tandas"]["3"]["planned"] == 573
    assert report["pr92"]["annotation_rows"] == 2700
    assert report["pr92"]["annotation_years"] == {"2014": 1321, "2015": 1379}
    assert report["pr92"]["test_2015_after_historical_exclusions"] == 1375
    assert report["cross_manifest"]["pr91_test_present_in_pr92"] == 832
    assert report["cross_manifest"]["pr91_test_not_in_pr92"] == 701
    assert report["cross_manifest"]["pr92_test_not_in_pr91"] == 547
    assert report["cross_manifest"]["pr91_test_overlap_with_haiku"] == 0
    assert report["cross_manifest"]["pr92_all_overlap_with_haiku"] == 0
    assert report["cross_manifest"]["pr91_calibration_present_in_pr92"] == 13
    assert report["cross_manifest"]["pr91_test_historical_exclusions"] == 0
    assert report["gold_human_certified"] is False


def test_cli_writes_only_aggregate_summary(tmp_path):
    assert main(["--output-dir", str(tmp_path)]) == 0
    data = json.loads(
        (tmp_path / "resumen_conciliacion_gold.json").read_text(encoding="utf-8")
    )
    assert data["status"] == "DECISION_MANIFIESTO_CANONICO_PENDIENTE"
    assert set(data["source_sha256"]) == {
        "pr91_manifest", "pr92_annotated", "pr92_manifest", "haiku_prelabels"
    }
    assert all(len(s) == 64 for s in data["source_sha256"].values())
    assert "TARGETCIT" not in json.dumps(data)
    assert "P15-0001" not in json.dumps(data)
    assert data["final_benchmark_allowed"] is False
