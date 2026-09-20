import csv
import json

import pytest

from src.evaluation.commercial.metrics import (
    CATEGORIES,
    evaluate_records,
    gold_to_index,
    write_evaluation_artifacts,
)


def _record(
    case_id,
    gold,
    scores=None,
    *,
    status="ok",
    prompt_name="zero",
    provider="fake",
    model="fake-model",
    latency_ms=100.0,
    retry_count=0,
):
    return {
        "case_id": case_id,
        "prompt_name": prompt_name,
        "provider": provider,
        "model": model,
        "gold": gold,
        "status": status,
        "parsed_output": scores if status == "ok" else None,
        "raw_response": json.dumps(scores) if scores is not None else "not-json",
        "latency_ms": latency_ms,
        "retry_count": retry_count,
        "input_tokens": 10,
        "output_tokens": 5,
        "estimated_cost_usd": 0.001,
    }


def _scores(index):
    values = [0.0] * 9
    values[index] = 0.9
    return values


def test_gold_to_index_accepts_names_indices_and_vectors():
    assert gold_to_index("Background") == 0
    assert gold_to_index("Improvement / Modification") == 5
    assert gold_to_index("originator") == 7
    assert gold_to_index(8) == 8
    assert gold_to_index(_scores(6)) == 6
    assert gold_to_index(None) is None


def test_gold_to_index_rejects_unknown_and_ambiguous_values():
    with pytest.raises(ValueError):
        gold_to_index("Unknown")
    with pytest.raises(ValueError):
        gold_to_index([0.5, 0.5, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])


def test_evaluate_records_perfect_predictions():
    records = [
        _record("c1", "Background", _scores(0)),
        _record("c2", "Gap", _scores(1)),
        _record("c3", "Evidence", _scores(6)),
    ]

    summaries, predictions, matrices = evaluate_records(records)

    summary = summaries[0]
    assert summary["precision_macro"] == pytest.approx(3 / 9)
    assert summary["recall_macro"] == pytest.approx(3 / 9)
    assert summary["f1_macro"] == pytest.approx(3 / 9)
    assert summary["precision_macro_observed"] == pytest.approx(1.0)
    assert summary["recall_macro_observed"] == pytest.approx(1.0)
    assert summary["f1_macro_observed"] == pytest.approx(1.0)
    assert summary["f1_micro"] == pytest.approx(1.0)
    assert summary["classification_coverage"] == pytest.approx(1.0)
    assert len(predictions) == 3
    assert matrices[("zero", "fake", "fake-model")][0][0] == 1
    assert matrices[("zero", "fake", "fake-model")][1][1] == 1
    assert matrices[("zero", "fake", "fake-model")][6][6] == 1


def test_nonparseable_response_is_counted_and_reduces_coverage():
    records = [
        _record("c1", "Background", _scores(0)),
        _record("c2", "Gap", None, status="parse_error"),
    ]

    summaries, predictions, _ = evaluate_records(records)

    summary = summaries[0]
    assert summary["format_error_runs"] == 1
    assert summary["format_error_rate"] == pytest.approx(0.5)
    assert summary["n_labeled_cases"] == 2
    assert summary["n_scored_labeled_cases"] == 1
    assert summary["classification_coverage"] == pytest.approx(0.5)
    by_case = {row["case_id"]: row for row in predictions}
    assert by_case["c2"]["pred_index"] is None


def test_provider_error_is_separate_from_format_error():
    records = [
        _record("c1", "Background", _scores(0)),
        _record("c2", "Gap", None, status="provider_error"),
    ]

    summaries, _, _ = evaluate_records(records)

    summary = summaries[0]
    assert summary["provider_error_runs"] == 1
    assert summary["provider_error_rate"] == pytest.approx(0.5)
    assert summary["format_error_runs"] == 0
    assert summary["format_error_rate"] == pytest.approx(0.0)


def test_repetitions_are_averaged_per_case_before_scoring():
    first = _scores(0)
    second = [0.8, 0.2, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    records = [
        _record("c1", "Background", first),
        _record("c1", "Background", second),
    ]

    summaries, predictions, _ = evaluate_records(records)

    assert summaries[0]["n_cases"] == 1
    assert summaries[0]["n_runs"] == 2
    assert predictions[0]["n_valid_runs"] == 2
    assert predictions[0]["pred_label"] == "Background"


def test_pilot_without_gold_produces_operational_metrics_only():
    records = [_record("c1", None, _scores(0))]

    summaries, _, matrices = evaluate_records(records)

    summary = summaries[0]
    assert summary["n_labeled_cases"] == 0
    assert summary["f1_macro"] is None
    assert summary["classification_coverage"] is None
    assert len(matrices[("zero", "fake", "fake-model")]) == len(CATEGORIES)


def test_write_evaluation_artifacts(tmp_path):
    records = [
        _record("c1", "Background", _scores(0)),
        _record("c2", "Gap", _scores(1)),
    ]
    summaries, predictions, matrices = evaluate_records(records)

    write_evaluation_artifacts(tmp_path, summaries, predictions, matrices)

    assert (tmp_path / "evaluation_summary.csv").exists()
    assert (tmp_path / "predictions.csv").exists()
    confusion_files = list((tmp_path / "confusion_matrices").glob("*.csv"))
    assert len(confusion_files) == 1

    with (tmp_path / "evaluation_summary.csv").open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert float(rows[0]["f1_macro"]) == pytest.approx(2 / 9)
    assert rows[0]["f1_macro_observed"] == "1.0"
