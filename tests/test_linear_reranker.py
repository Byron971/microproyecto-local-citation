import numpy as np
import pytest

from src.models.linear_reranker import LinearReranker, rerank_candidate_records


def test_linear_reranker_assigns_higher_score_to_learned_positive_pattern():
    features = np.asarray(
        [
            [0.9, 0.8, 10, 5, 100],
            [0.8, 0.9, 11, 6, 110],
            [0.1, 0.0, 10, 5, 100],
            [0.0, 0.1, 11, 6, 110],
        ]
    )
    labels = [1, 1, 0, 0]
    model = LinearReranker().fit(features, labels)

    scores = model.predict_scores(features)

    assert scores[:2].mean() > scores[2:].mean()


def test_linear_reranker_requires_both_classes():
    with pytest.raises(ValueError, match="ambas clases"):
        LinearReranker().fit(np.ones((2, 2)), [1, 1])


def test_predict_scores_requires_fit():
    with pytest.raises(RuntimeError):
        LinearReranker().predict_scores(np.ones((1, 2)))


def test_rerank_candidate_records_preserves_candidates_and_groups():
    records = [
        {"context_id": "c1", "candidate_ids": ["p1", "p2"]},
        {"context_id": "c2", "candidate_ids": ["p3", "p4"]},
    ]

    rankings = rerank_candidate_records(records, [0.1, 0.9, 0.8, 0.2])

    assert rankings == [["p2", "p1"], ["p3", "p4"]]
    assert all(len(ranking) == 2 for ranking in rankings)


def test_rerank_rejects_wrong_number_of_scores():
    records = [{"context_id": "c1", "candidate_ids": ["p1", "p2"]}]
    with pytest.raises(ValueError, match="Se esperaban 2"):
        rerank_candidate_records(records, [0.5])
