import csv

import pytest

from src.evaluation.commercial.stability import (
    aggregate_by_prompt,
    compute_group_metrics,
    group_records,
    parse_score_array,
    write_stability_summary_csv,
)

VALID_ARRAY = "[0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.9, 0.0, 0.0]"  # argmax = indice 6
OTHER_ARRAY = "[0.0, 0.9, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]"  # argmax = indice 1
EXAMPLE_FORMAT_ARRAY = "[0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]"  # texto de ejemplo del prompt


def _record(
    case_id,
    prompt_name,
    raw_response,
    latency_ms=100.0,
    retry_count=0,
    provider="fake",
    model="fake-model",
    status="ok",
):
    return {
        "case_id": case_id,
        "prompt_name": prompt_name,
        "provider": provider,
        "model": model,
        "raw_response": raw_response,
        "latency_ms": latency_ms,
        "retry_count": retry_count,
        "status": status,
    }


def test_parse_score_array_valid():
    scores = parse_score_array(VALID_ARRAY)
    assert len(scores) == 9
    assert scores[6] == 0.9


def test_parse_score_array_rejects_wrong_length():
    with pytest.raises(ValueError):
        parse_score_array("[0.1, 0.2, 0.3]")


def test_parse_score_array_rejects_non_json():
    with pytest.raises(ValueError):
        parse_score_array("the answer is Background")


def test_parse_score_array_uses_last_valid_match_not_first():
    # El prompt zero_shot_generic termina con el texto literal
    # "Example format: [0.0, 0.0, ..., 0.0]". Si el modelo lo repite antes
    # de su respuesta real, la respuesta real (mas adelante en el texto)
    # debe ganar, no el arreglo de ejemplo que aparece primero.
    text = (
        f"Example format: {EXAMPLE_FORMAT_ARRAY}\n"
        f"Mi respuesta final es: {VALID_ARRAY}"
    )
    scores = parse_score_array(text)
    assert scores[6] == 0.9
    assert scores != [0.0] * 9


def test_compute_group_metrics_all_broken_format():
    group = [_record("c1", "p1", "not an array") for _ in range(5)]
    metrics = compute_group_metrics(group)
    assert metrics["format_error_rate"] == 1.0
    assert metrics["label_stability"] is None


def test_compute_group_metrics_fully_stable():
    group = [_record("c1", "p1", VALID_ARRAY) for _ in range(5)]
    metrics = compute_group_metrics(group)
    assert metrics["format_error_rate"] == 0.0
    assert metrics["label_stability"] == 1.0


def test_compute_group_metrics_partially_unstable():
    responses = [VALID_ARRAY, OTHER_ARRAY, VALID_ARRAY, OTHER_ARRAY, VALID_ARRAY]
    group = [_record("c1", "p1", r) for r in responses]
    metrics = compute_group_metrics(group)
    assert metrics["label_stability"] == pytest.approx(3 / 5)


def test_compute_group_metrics_maximally_unstable():
    arrays = [
        "[0.9,0,0,0,0,0,0,0,0]",
        "[0,0.9,0,0,0,0,0,0,0]",
        "[0,0,0.9,0,0,0,0,0,0]",
        "[0,0,0,0.9,0,0,0,0,0]",
        "[0,0,0,0,0.9,0,0,0,0]",
    ]
    group = [_record("c1", "p1", a) for a in arrays]
    metrics = compute_group_metrics(group)
    assert metrics["label_stability"] == pytest.approx(0.2)


def test_compute_group_metrics_excludes_provider_errors_from_format_error_rate():
    group = [
        _record("c1", "p1", VALID_ARRAY, status="ok"),
        _record("c1", "p1", VALID_ARRAY, status="ok"),
        _record("c1", "p1", None, status="provider_error"),
        _record("c1", "p1", None, status="provider_error"),
    ]
    metrics = compute_group_metrics(group)
    # Las 2 respuestas ok parsean bien: format_error_rate se calcula solo
    # sobre esas 2 (denominador excluye los provider_error), no sobre las 4.
    assert metrics["format_error_rate"] == pytest.approx(0.0)
    assert metrics["label_stability"] == pytest.approx(1.0)
    assert metrics["provider_error_rate"] == pytest.approx(0.5)


def test_compute_group_metrics_provider_error_mixed_with_format_error():
    group = [
        _record("c1", "p1", VALID_ARRAY, status="ok"),
        _record("c1", "p1", "not an array", status="ok"),
        _record("c1", "p1", None, status="provider_error"),
    ]
    metrics = compute_group_metrics(group)
    # denominador = 2 (registros no-provider_error), 1 de ellos invalido
    assert metrics["format_error_rate"] == pytest.approx(0.5)
    assert metrics["provider_error_rate"] == pytest.approx(1 / 3)


def test_group_records_keeps_different_providers_separate():
    records = [
        _record("c1", "p1", VALID_ARRAY, provider="fake", model="fake-model"),
        _record("c1", "p1", VALID_ARRAY, provider="other", model="other-model"),
    ]
    groups = group_records(records)
    assert len(groups) == 2
    assert ("c1", "p1", "fake", "fake-model") in groups
    assert ("c1", "p1", "other", "other-model") in groups


def test_aggregate_by_prompt_keeps_different_models_in_separate_groups():
    records = [
        *[_record("c1", "p1", VALID_ARRAY, provider="fake", model="fake-model") for _ in range(5)],
        *[_record("c1", "p1", OTHER_ARRAY, provider="other", model="other-model") for _ in range(5)],
    ]
    aggregated = aggregate_by_prompt(records)
    # Si se mezclaran, seria un solo grupo de 10 con label_stability 0.5;
    # si se mantienen separados, cada uno es un caso perfectamente estable.
    assert set(aggregated.keys()) == {
        ("p1", "fake", "fake-model"),
        ("p1", "other", "other-model"),
    }
    assert aggregated[("p1", "fake", "fake-model")]["avg_label_stability"] == pytest.approx(1.0)
    assert aggregated[("p1", "other", "other-model")]["avg_label_stability"] == pytest.approx(1.0)


def test_aggregate_by_prompt_averages_across_cases():
    records = [
        *[_record("c1", "p1", VALID_ARRAY) for _ in range(5)],
        *[_record("c2", "p1", "broken") for _ in range(5)],
    ]
    aggregated = aggregate_by_prompt(records)
    key = ("p1", "fake", "fake-model")
    assert aggregated[key]["n_cases"] == 2
    assert aggregated[key]["n_cases_with_valid_responses"] == 1
    assert aggregated[key]["avg_format_error_rate"] == pytest.approx(0.5)
    assert aggregated[key]["avg_label_stability"] == pytest.approx(1.0)


def test_write_stability_summary_csv(tmp_path):
    aggregated = {
        ("p1", "fake", "fake-model"): {
            "n_cases": 2,
            "n_cases_with_valid_responses": 1,
            "avg_format_error_rate": 0.5,
            "avg_label_stability": 1.0,
            "provider_error_rate": 0.0,
            "avg_latency_ms": 120.0,
            "avg_retry_count": 0.0,
        },
    }
    output_path = tmp_path / "stability_summary.csv"
    write_stability_summary_csv(output_path, aggregated)

    with output_path.open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert rows[0]["prompt_name"] == "p1"
    assert rows[0]["provider"] == "fake"
    assert rows[0]["model"] == "fake-model"
    assert rows[0]["n_cases"] == "2"
    assert rows[0]["n_cases_with_valid_responses"] == "1"


def test_write_stability_summary_csv_ignores_extra_keys(tmp_path):
    # compute_group_metrics devuelve una clave interna "n" que no esta en
    # FIELDNAMES; si alguien pasara ese dict crudo, DictWriter no debe
    # reventar (extrasaction="ignore").
    aggregated = {
        ("p1", "fake", "fake-model"): {
            "n": 5,
            "n_cases": 2,
            "n_cases_with_valid_responses": 1,
            "avg_format_error_rate": 0.5,
            "avg_label_stability": 1.0,
            "provider_error_rate": 0.0,
            "avg_latency_ms": 120.0,
            "avg_retry_count": 0.0,
        },
    }
    output_path = tmp_path / "stability_summary.csv"
    write_stability_summary_csv(output_path, aggregated)

    with output_path.open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert rows[0]["prompt_name"] == "p1"
    assert "n" not in rows[0]
