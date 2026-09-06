from src.data.build_pairs import build_pairs


def test_build_pairs_preserves_positive_example():
    split = [
        {
            "context_id": "context-1",
            "positive_ids": ["paper-a"],
        }
    ]

    paper_ids = ["paper-a", "paper-b", "paper-c"]

    pairs = build_pairs(
        split=split,
        paper_ids=paper_ids,
        negatives_per_positive=1,
        random_state=42,
    )

    positive_pairs = [
        pair
        for pair in pairs
        if pair["label"] == 1
    ]

    assert positive_pairs == [
        {
            "context_id": "context-1",
            "paper_id": "paper-a",
            "label": 1,
        }
    ]


def test_build_pairs_does_not_use_positive_paper_as_negative():
    split = [
        {
            "context_id": "context-1",
            "positive_ids": ["paper-a"],
        }
    ]

    paper_ids = ["paper-a", "paper-b", "paper-c", "paper-d"]

    pairs = build_pairs(
        split=split,
        paper_ids=paper_ids,
        negatives_per_positive=2,
        random_state=42,
    )

    negative_pairs = [
        pair
        for pair in pairs
        if pair["label"] == 0
    ]

    negative_ids = {
        pair["paper_id"]
        for pair in negative_pairs
    }

    assert "paper-a" not in negative_ids
    assert len(negative_ids) == 2


def test_build_pairs_is_reproducible_with_same_random_state():
    split = [
        {
            "context_id": "context-1",
            "positive_ids": ["paper-a"],
        }
    ]

    paper_ids = [
        "paper-a",
        "paper-b",
        "paper-c",
        "paper-d",
        "paper-e",
    ]

    first_result = build_pairs(
        split=split,
        paper_ids=paper_ids,
        negatives_per_positive=2,
        random_state=42,
    )

    second_result = build_pairs(
        split=split,
        paper_ids=paper_ids,
        negatives_per_positive=2,
        random_state=42,
    )

    assert first_result == second_result


def test_build_pairs_excludes_additional_papers_for_context():
    split = [{"context_id": "context-1", "positive_ids": ["paper-a"]}]

    pairs = build_pairs(
        split=split,
        paper_ids=["paper-a", "citing-paper", "paper-b"],
        negatives_per_positive=1,
        random_state=42,
        excluded_paper_ids={"context-1": {"citing-paper"}},
    )

    assert pairs[-1] == {
        "context_id": "context-1",
        "paper_id": "paper-b",
        "label": 0,
    }
