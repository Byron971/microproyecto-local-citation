"""Regresiones de CSV existentes: no crea etiquetas humanas nuevas."""
import csv
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.evaluation.commercial.gold_existing_csv_audit import (
    _read, _parts, audit_existing, DATA_COLUMNS, ANNOTATED, HAIKU,
    MANIFEST, main,
)
from src.evaluation.commercial.gold_policy import exclusion_ids


def sample(cid, label="Background", status="COMPLETO", evaluability="Evaluable"):
    return {
        "context_id": cid,
        "Contexto TARGETCIT": "We apply TARGETCIT in this study.",
        "¿Evaluable?": evaluability,
        "Función principal": label,
        "Confianza": "Alta",
        "Justificación / duda": "" if status == "COMPLETO" else "No es posible determinarlo.",
        "Estado": status,
    }


def payload():
    annotated = {
        "P14-1_P11-1_0": sample("P14-1_P11-1_0"),
        "P15-2_P12-2_0": sample(
            "P15-2_P12-2_0", "", "REGISTRADO", "Ambiguo"
        ),
    }
    train = {
        "P10-3_P08-3_0": sample("P10-3_P08-3_0"),
        "P11-4_P09-4_0": sample("P11-4_P09-4_0"),
    }
    manifest = {
        "P14-1_P11-1_0": {"context_id": "P14-1_P11-1_0", "anio_citante": "2014"},
        "P15-2_P12-2_0": {"context_id": "P15-2_P12-2_0", "anio_citante": "2015"},
    }
    return annotated, train, manifest


def audit_fake(*, excluded=None, total=None, split_index=None):
    a, h, m = payload()
    return audit_existing(a, h, m, excluded=excluded or set(),
                          expected_count=2, dataset_final_total=total,
                          split_index=split_index)


def test_audit_preserves_val_and_test_and_no_human_certification():
    report = audit_fake()
    assert report["blockers"] == []
    assert report["status"] == "INTEGRIDAD_CSV_OK_CERTIFICACION_HUMANA_PENDIENTE"
    assert report["split_by_citing_year"] == {"2014": 1, "2015": 1}
    assert report["n_provisional_test_2015"] == 1
    assert report["n_provisional_test_classifiable_2015"] == 0
    assert report["scientific_gold_certified"] is False
    assert report["ready_for_final_benchmark"] is False
    assert report["human_provenance_verified"] is False
    assert report["acl_official_splits_verified"] is False


def test_human_percentage_is_conditional_and_never_certified():
    high = audit_fake(total=10)
    low = audit_fake(total=20)
    assert high["annotation_file_fraction_if_all_human"] == pytest.approx(0.2)
    assert high["human_provenance_verified"] is False
    assert low["status"] == "BLOQUEADO"
    assert any("15%" in b for b in low["blockers"])


def test_prior_prelabels_not_automatically_counted_as_humans():
    report = audit_fake()
    assert report["input_records"]["haiku_prelabel"] == 2
    assert report["human_provenance_verified"] is False
    assert "Haiku" in " ".join(report["warnings"])


def test_excluded_id_is_not_a_test_candidate_without_reannotation():
    a, h, m = payload()
    result = audit_existing(a, h, m, expected_count=2, excluded={"P15-2_P12-2_0"})
    assert result["blockers"] == []
    assert result["input_records"]["anotacion"] == 2
    assert result["n_excluded_from_final_gold"] == 1
    assert result["n_test_candidates_2015_after_exclusions"] == 0
    assert any("NO son elegibles" in msg for msg in result["warnings"])


def test_manifests_must_match_exactly():
    a, h, m = payload()
    m.pop("P14-1_P11-1_0")
    report = audit_existing(a, h, m, excluded=set(), expected_count=2)
    assert any("desalineado" in x for x in report["blockers"])


def test_incorrect_manifest_year_is_blocker():
    a, h, m = payload()
    m["P15-2_P12-2_0"]["anio_citante"] = "2014"
    report = audit_existing(a, h, m, excluded=set(), expected_count=2)
    assert any("año citante" in x for x in report["blockers"])


def test_invalid_status_and_ambiguous_label_is_blocker():
    a, h, m = payload()
    a["P15-2_P12-2_0"]["Función principal"] = "Gap"
    report = audit_existing(a, h, m, excluded=set(), expected_count=2)
    assert any("ambiguo/no evaluable" in x for x in report["blockers"])


def test_invalid_target_marker_is_blocker():
    a, h, m = payload()
    a["P14-1_P11-1_0"]["Contexto TARGETCIT"] = "No citation marker."
    report = audit_existing(a, h, m, excluded=set(), expected_count=2)
    assert any("TARGETCIT" in x for x in report["blockers"])


def test_identical_ids_between_haiku_and_gold_block():
    a, h, m = payload()
    h["P14-1_P11-1_0"] = h.pop("P10-3_P08-3_0")
    report = audit_existing(a, h, m, excluded=set(), expected_count=2)
    assert any("comparten" in x for x in report["blockers"])


def test_partitions_verified_only_with_raw_split_index():
    a, h, m = payload()
    contexts = {
        cid: {"masked_text": row["Contexto TARGETCIT"]}
        for cid, row in a.items()
    }
    index = SimpleNamespace(
        by_context={"P14-1_P11-1_0": "val", "P15-2_P12-2_0": "test"},
        contexts=contexts,
    )
    report = audit_existing(a, h, m, excluded=set(), expected_count=2, split_index=index)
    assert report["acl_official_splits_verified"] is True
    assert report["blockers"] == []
    index.by_context["P15-2_P12-2_0"] = "train"
    report = audit_existing(a, h, m, excluded=set(), expected_count=2, split_index=index)
    assert any("ACL-200" in x for x in report["blockers"])


def test_read_csv_rejects_duplicate_ids(tmp_path):
    path = tmp_path / "rows.csv"
    header = list(DATA_COLUMNS)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=header)
        writer.writeheader()
        row = sample("P14-1_P11-1_0")
        writer.writerow(row)
        writer.writerow(row)
    with pytest.raises(ValueError, match="duplicado"):
        _read(path, DATA_COLUMNS)


def test_malformed_id_rejected():
    with pytest.raises(ValueError, match="estructura"):
        _parts("no-underscore-id")


def test_actual_repository_2700_files_without_modifying_them(tmp_path):
    """Audita los archivos reales de 2.700, sin importar datos a la salida."""
    assert ANNOTATED.is_file() and HAIKU.is_file() and MANIFEST.is_file()
    annotated = _read(ANNOTATED, DATA_COLUMNS)
    haiku = _read(HAIKU, DATA_COLUMNS)
    manifest = _read(MANIFEST, ("context_id", "anio_citante", "prelabel_qlora"))
    result = audit_existing(annotated, haiku, manifest, excluded=exclusion_ids())
    assert result["input_records"] == {
        "anotacion": 2700, "haiku_prelabel": 2700, "manifest": 2700
    }
    assert result["split_by_citing_year"] == {"2014": 1321, "2015": 1379}
    assert result["status_counts"] == {"COMPLETO": 2672, "REGISTRADO": 28}
    assert result["shared_ids_with_haiku"] == 0
    assert result["scientific_gold_certified"] is False
    assert result["n_excluded_from_final_gold"] == 5
    assert result["excluded_from_final_gold_by_year"] == {"2014": 1, "2015": 4}
    assert result["n_test_candidates_2015_after_exclusions"] == 1375
    assert result["blockers"] == []


def test_cli_produces_only_aggregate_json_and_hashes(tmp_path):
    status = main(["--output-dir", str(tmp_path)])
    assert status == 0
    output = (tmp_path / "gold_existing_audit.json").read_text(encoding="utf-8")
    assert '"status": "INTEGRIDAD_CSV_OK_CERTIFICACION_HUMANA_PENDIENTE"' in output
    assert '"scientific_gold_certified": false' in output
    assert '"sha256"' in output
    assert "We apply TARGETCIT" not in output
