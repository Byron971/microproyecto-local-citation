import pytest

from src.evaluation.evaluate_reranker import evaluate_rankings
from src.training.experiment import labels_from_pairs


def test_evaluate_rankings_reports_recall_and_truncated_mrr():
    rankings = [["p1", "target"], ["target", "p2"]]
    relevant = [{"target"}, {"target"}]

    metrics = evaluate_rankings(rankings, relevant, ks=(1, 2))

    assert metrics["recall_at_1"] == pytest.approx(0.5)
    assert metrics["recall_at_2"] == pytest.approx(1.0)
    assert metrics["mrr_at_1"] == pytest.approx(0.5)
    assert metrics["mrr_at_2"] == pytest.approx(0.75)


def test_evaluate_rankings_keeps_missing_positive_as_zero():
    metrics = evaluate_rankings([["p1", "p2"]], [{"missing"}], ks=(2,))

    assert metrics == {"recall_at_2": 0.0, "mrr_at_2": 0.0}


def test_evaluate_rankings_rejects_misaligned_inputs():
    with pytest.raises(ValueError, match="misma longitud"):
        evaluate_rankings([["p1"]], [], ks=(1,))


def test_labels_from_pairs_preserves_order():
    pairs = [
        {"context_id": "c", "paper_id": "p1", "label": 1},
        {"context_id": "c", "paper_id": "p2", "label": 0},
    ]
    assert labels_from_pairs(pairs).tolist() == [1, 0]
