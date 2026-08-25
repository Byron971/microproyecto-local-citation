from src.evaluation.ranking_metrics import mean_reciprocal_rank, recall_at_k


def test_recall_at_k_returns_one_when_relevant_item_is_in_top_k():
    ranked_ids = ["paper-a", "paper-b", "paper-c"]
    relevant_ids = {"paper-b"}

    result = recall_at_k(
        ranked_ids=ranked_ids,
        relevant_ids=relevant_ids,
        k=2,
    )

    assert result == 1.0


def test_recall_at_k_returns_zero_when_relevant_item_is_outside_top_k():
    ranked_ids = ["paper-a", "paper-b", "paper-c"]
    relevant_ids = {"paper-c"}

    result = recall_at_k(
        ranked_ids=ranked_ids,
        relevant_ids=relevant_ids,
        k=2,
    )

    assert result == 0.0


def test_recall_at_k_supports_multiple_relevant_items():
    ranked_ids = ["paper-a", "paper-b", "paper-c", "paper-d"]
    relevant_ids = {"paper-b", "paper-d"}

    result = recall_at_k(
        ranked_ids=ranked_ids,
        relevant_ids=relevant_ids,
        k=2,
    )

    assert result == 0.5


def test_mean_reciprocal_rank_uses_rank_of_first_relevant_item():
    rankings = [
        (["paper-a", "paper-b", "paper-c"], {"paper-b"}),
        (["paper-d", "paper-e", "paper-f"], {"paper-d"}),
    ]

    result = mean_reciprocal_rank(rankings)

    assert result == 0.75


def test_mean_reciprocal_rank_uses_zero_when_no_relevant_item_is_found():
    rankings = [
        (["paper-a", "paper-b"], {"paper-x"}),
        (["paper-c", "paper-d"], {"paper-c"}),
    ]

    result = mean_reciprocal_rank(rankings)

    assert result == 0.5