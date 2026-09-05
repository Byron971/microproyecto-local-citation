import pytest

from src.data.build_hard_pairs import build_candidate_pairs, build_hard_pairs


RECORDS = [
    {
        "context_id": "c1",
        "positive_ids": ["p2"],
        "candidate_ids": ["citing", "p1", "p2", "p3", "p4"],
    }
]
CONTEXTS = {"c1": {"citing_id": "citing"}}


def test_build_hard_pairs_keeps_positive_and_top_ranked_negatives():
    pairs = build_hard_pairs(RECORDS, negatives_per_positive=2, contexts=CONTEXTS)

    assert pairs == [
        {"context_id": "c1", "paper_id": "p2", "label": 1},
        {"context_id": "c1", "paper_id": "p1", "label": 0},
        {"context_id": "c1", "paper_id": "p3", "label": 0},
    ]


def test_build_hard_pairs_is_deterministic():
    first = build_hard_pairs(RECORDS, contexts=CONTEXTS)
    second = build_hard_pairs(RECORDS, contexts=CONTEXTS)
    assert first == second


def test_build_hard_pairs_rejects_insufficient_candidates():
    with pytest.raises(ValueError, match="suficientes negativos"):
        build_hard_pairs(RECORDS, negatives_per_positive=10, contexts=CONTEXTS)


def test_build_candidate_pairs_labels_all_candidates():
    pairs = build_candidate_pairs(RECORDS)

    assert len(pairs) == len(RECORDS[0]["candidate_ids"])
    assert [pair["label"] for pair in pairs] == [0, 0, 1, 0, 0]


def test_build_candidate_pairs_does_not_insert_missing_positive():
    records = [
        {"context_id": "c1", "positive_ids": ["missing"], "candidate_ids": ["p1"]}
    ]
    assert build_candidate_pairs(records) == [
        {"context_id": "c1", "paper_id": "p1", "label": 0}
    ]
