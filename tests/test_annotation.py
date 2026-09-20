import csv
import json

import pytest

from src.evaluation.annotation import (
    compute_agreement,
    finalize_gold,
    normalize_label,
    prepare_sheets,
    write_agreement_artifacts,
)


def _write_source(path):
    rows = [
        {"id": "c1", "input": "context one", "gold": None},
        {"id": "c2", "input": "context two", "gold": None},
        {"id": "c3", "input": "context three", "gold": None},
    ]
    path.write_text(
        "\n".join(json.dumps(row) for row in rows) + "\n",
        encoding="utf-8",
    )


def _fill_sheet(path, labels):
    rows = list(csv.DictReader(path.open(encoding="utf-8")))
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["id", "input", "label"])
        writer.writeheader()
        for row in rows:
            row["label"] = labels[row["id"]]
            writer.writerow(row)


def test_normalize_label_accepts_aliases():
    assert normalize_label("Background") == "Background"
    assert normalize_label("originator") == "Identification of the Originator"
    assert normalize_label("improvement/modification") == "Improvement / Modification"


def test_prepare_sheets_randomizes_but_preserves_cases(tmp_path):
    source = tmp_path / "source.jsonl"
    _write_source(source)

    annotator_a, annotator_b = prepare_sheets(source, tmp_path / "annotations")

    rows_a = list(csv.DictReader(annotator_a.open(encoding="utf-8")))
    rows_b = list(csv.DictReader(annotator_b.open(encoding="utf-8")))
    assert {row["id"] for row in rows_a} == {"c1", "c2", "c3"}
    assert {row["id"] for row in rows_b} == {"c1", "c2", "c3"}
    assert all(row["label"] == "" for row in rows_a + rows_b)


def test_compute_agreement_and_reconciliation(tmp_path):
    source = tmp_path / "source.jsonl"
    _write_source(source)
    annotator_a, annotator_b = prepare_sheets(source, tmp_path / "annotations")

    _fill_sheet(
        annotator_a,
        {"c1": "Background", "c2": "Gap", "c3": "Evidence"},
    )
    _fill_sheet(
        annotator_b,
        {"c1": "Background", "c2": "Basis", "c3": "Evidence"},
    )

    summary, _, _, agreed, disagreements = compute_agreement(
        source, annotator_a, annotator_b
    )
    assert summary["n_common"] == 3
    assert summary["n_agreements"] == 2
    assert summary["n_disagreements"] == 1
    assert set(agreed) == {"c1", "c3"}
    assert disagreements == ["c2"]

    written = write_agreement_artifacts(
        source, annotator_a, annotator_b, tmp_path / "agreement"
    )
    assert written["n_common"] == 3
    assert (tmp_path / "agreement" / "agreement_summary.json").exists()
    assert (tmp_path / "agreement" / "disagreements.csv").exists()
    assert (tmp_path / "agreement" / "reconciliation.csv").exists()


def test_finalize_gold_requires_all_cases(tmp_path):
    source = tmp_path / "source.jsonl"
    _write_source(source)
    reconciliation = tmp_path / "reconciliation.csv"
    reconciliation.write_text(
        "id,annotator_a,annotator_b,final_label\n"
        "c1,Background,Background,Background\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError):
        finalize_gold(source, reconciliation, tmp_path / "gold.jsonl")


def test_finalize_gold_writes_valid_jsonl(tmp_path):
    source = tmp_path / "source.jsonl"
    _write_source(source)
    reconciliation = tmp_path / "reconciliation.csv"
    reconciliation.write_text(
        "id,annotator_a,annotator_b,final_label\n"
        "c1,Background,Background,Background\n"
        "c2,Gap,Basis,Gap\n"
        "c3,Evidence,Evidence,Evidence\n",
        encoding="utf-8",
    )

    count = finalize_gold(source, reconciliation, tmp_path / "gold.jsonl")
    assert count == 3
    rows = [
        json.loads(line)
        for line in (tmp_path / "gold.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert [row["gold"] for row in rows] == ["Background", "Gap", "Evidence"]
