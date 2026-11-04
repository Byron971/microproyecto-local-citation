"""Pruebas sintéticas: no usar estos registros como resultados de tesis."""
import json

import pytest

from src.evaluation.commercial.paired_benchmark import (
    compare, index_gold, index_predictions, main, model_metrics, read_jsonl,
)


def gold(cid, label, citing=None):
    return {
        "id": cid, "input": "We apply TARGETCIT here.",
        "gold": label, "citing_id": citing or f"paper-{cid}", "cited_id": "paper-cited",
    }


def prediction(cid, label, status="ok"):
    return {"case_id": cid, "status": status, "pred_label": label}


def test_both_variants_identical_ids_and_perfect():
    g = [gold("a", "Background"), gold("b", "Gap")]
    a = [prediction("b", "Gap"), prediction("a", "Background")]
    b = [prediction("a", "Background"), prediction("b", "Gap")]
    result = compare(g, a, b, factor="input", name_a="entrada_A", name_b="entrada_B")
    assert result["status"] == "PROVISIONAL_NO_CERTIFICADO"
    assert result["n_same_gold"] == 2
    assert result["variants"]["entrada_A"]["f1_macro"] == pytest.approx(2 / 9)
    assert result["variants"]["entrada_A"]["f1_micro"] == pytest.approx(1)
    assert result["paired_cases"]["both_correct"] == 2
    assert result["paired_cases"]["same_prediction"] == 2
    assert result["delta_f1_macro_b_minus_a"] == pytest.approx(0)
    assert len(result["variants"]["entrada_A"]["per_class"]) == 9
    assert len(result["variants"]["entrada_A"]["confusion_matrix"]) == 9


def test_comparison_uses_same_gold_and_detects_pairwise_wins():
    g = [gold("a", "Background"), gold("b", "Gap"), gold("c", "Basis")]
    a = [prediction("a", "Background"), prediction("b", "Gap"), prediction("c", "Gap")]
    b = [prediction("a", "Gap"), prediction("b", "Gap"), prediction("c", "Basis")]
    result = compare(g, a, b, factor="training_labels", name_a="haiku", name_b="jurado")
    assert result["paired_cases"] == {
        "same_prediction": 1, "a_only_correct": 1,
        "b_only_correct": 1, "both_correct": 1, "both_wrong": 0,
    }
    assert result["n_same_gold"] == 3


@pytest.mark.parametrize("bad", [
    [prediction("a", "Background")],
    [prediction("a", "Background"), prediction("b", "Gap"), prediction("x", "Gap")],
])
def test_missing_or_extra_ids_fail_closed(bad):
    g = [gold("a", "Background"), gold("b", "Gap")]
    a = [prediction("a", "Background"), prediction("b", "Gap")]
    with pytest.raises(ValueError, match="IDs no comparables"):
        compare(g, a, bad, factor="input", name_a="a", name_b="b")


def test_duplicate_predictions_fail_closed():
    with pytest.raises(ValueError, match="duplicado"):
        index_predictions([prediction("a", "Background"), prediction("a", "Background")], {"a"}, "A")


def test_gold_duplicate_and_bad_target_and_absent_label_fail():
    with pytest.raises(ValueError, match="duplicado"):
        index_gold([gold("a", "Background"), gold("a", "Gap")])
    with pytest.raises(ValueError, match="TARGETCIT"):
        index_gold([{**gold("a", "Background"), "input": "No target."}])
    with pytest.raises(ValueError, match="etiqueta ausente"):
        index_gold([gold("a", None)])


def test_invalid_label_or_abstention_fail_closed():
    with pytest.raises(ValueError):
        index_predictions([prediction("a", "Ambiguo")], {"a"}, "A")
    with pytest.raises(ValueError, match="incompleta"):
        index_predictions([prediction("a", None, "provider_error")], {"a"}, "A")


def test_inconsistent_label_and_index_fail():
    bad = {"case_id": "a", "status": "ok", "pred_label": "Background", "pred_index": 1}
    with pytest.raises(ValueError, match="discrepan"):
        index_predictions([bad], {"a"}, "A")


def test_macro_fixed_9_even_when_test_has_only_one_class():
    metrics = model_metrics([0, 0], [0, 0])
    assert metrics["f1_macro"] == pytest.approx(1 / 9)
    assert metrics["f1_weighted"] == pytest.approx(1)
    assert sum(row["support"] for row in metrics["per_class"]) == 2


def test_jsonl_parser_rejects_empty_and_nonobjects(tmp_path):
    p = tmp_path / "test.jsonl"
    p.write_text("  \n", encoding="utf-8")
    with pytest.raises(ValueError, match="vacío"):
        read_jsonl(p)
    p.write_text("[]\n", encoding="utf-8")
    with pytest.raises(ValueError, match="objeto"):
        read_jsonl(p)


def test_cli_refuses_final_claim_without_provisional(tmp_path):
    gold_file = tmp_path / "gold.jsonl"
    p_a = tmp_path / "a.jsonl"
    p_b = tmp_path / "b.jsonl"
    for p in (gold_file, p_a, p_b):
        p.write_text("{}\n", encoding="utf-8")
    rc = main([
        "--gold", str(gold_file), "--predictions-a", str(p_a),
        "--predictions-b", str(p_b), "--name-a", "A", "--name-b", "B",
        "--factor", "input", "--raw-dir", str(tmp_path),
        "--output-dir", str(tmp_path / "results"),
    ])
    assert rc == 2
    assert not (tmp_path / "results").exists()


def test_cli_provisional_refuses_gold_outside_verified_split(tmp_path):
    gold_file = tmp_path / "gold.jsonl"
    p_a = tmp_path / "a.jsonl"
    p_b = tmp_path / "b.jsonl"
    gold_file.write_text(json.dumps(gold("x", "Background"))+"\n", encoding="utf-8")
    for p in (p_a, p_b):
        p.write_text(json.dumps(prediction("x", "Background"))+"\n", encoding="utf-8")
    rc = main([
        "--gold", str(gold_file), "--predictions-a", str(p_a),
        "--predictions-b", str(p_b), "--name-a", "A", "--name-b", "B",
        "--factor", "input", "--raw-dir", str(tmp_path / "missing_raw"),
        "--output-dir", str(tmp_path / "results"), "--provisional",
    ])
    assert rc == 2
    assert not (tmp_path / "results").exists()
