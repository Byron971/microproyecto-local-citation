from src.training import run_tfidf_baseline


def test_build_candidate_records_preserves_context_and_ranking():
    build_candidate_records = getattr(
        run_tfidf_baseline,
        "build_candidate_records",
        None,
    )

    assert build_candidate_records is not None

    split = [
        {
            "context_id": "context-1",
            "positive_ids": ["paper-positive"],
        }
    ]

    rankings = [
        [
            "paper-a",
            "paper-positive",
            "paper-b",
        ]
    ]

    records = build_candidate_records(split, rankings)

    assert records == [
        {
            "context_id": "context-1",
            "positive_ids": ["paper-positive"],
            "candidate_ids": [
                "paper-a",
                "paper-positive",
                "paper-b",
            ],
        }
    ]


def test_build_candidate_records_keeps_one_record_per_context():
    split = [
        {
            "context_id": "context-1",
            "positive_ids": ["paper-1"],
        },
        {
            "context_id": "context-2",
            "positive_ids": ["paper-2"],
        },
    ]

    rankings = [
        ["paper-a", "paper-b", "paper-1"],
        ["paper-c", "paper-2", "paper-d"],
    ]

    records = run_tfidf_baseline.build_candidate_records(split, rankings)

    assert len(records) == 2
    assert records[0]["context_id"] == "context-1"
    assert records[1]["context_id"] == "context-2"


def test_save_candidate_records_creates_json_file(tmp_path):
    records = [
        {
            "context_id": "context-1",
            "positive_ids": ["paper-1"],
            "candidate_ids": ["paper-a", "paper-b", "paper-1"],
        }
    ]

    output_path = tmp_path / "tfidf_top100.json"

    run_tfidf_baseline.save_candidate_records(records, output_path)

    assert output_path.exists()

def test_top100():
    papers = {
        f"paper-{i}": {
            "title": f"Topic {i}",
            "abstract": f"Study about topic {i} and methods",
        }
        for i in range(120)
    }

    contexts = {
        "context-1": {
            "masked_text": "Study about topic 5 TARGETCIT"
        }
    }

    split = [
        {
            "context_id": "context-1",
            "positive_ids": ["paper-5"],
        }
    ]

    records = run_tfidf_baseline.get_top_candidates(
        papers=papers,
        contexts=contexts,
        split=split,
        top_n=100,
    )

    assert len(records) == 1
    assert len(records[0]["candidate_ids"]) == 100
    assert records[0]["context_id"] == "context-1"

def test_export_top100(tmp_path):
    papers = {
        f"paper-{i}": {
            "title": f"Topic {i}",
            "abstract": f"Study about topic {i}",
        }
        for i in range(120)
    }

    contexts = {
        "context-1": {
            "masked_text": "Study about topic 5 TARGETCIT"
        }
    }

    split = [
        {
            "context_id": "context-1",
            "positive_ids": ["paper-5"],
        }
    ]

    output_path = tmp_path / "train_tfidf_top100.json"

    run_tfidf_baseline.export_top100(
        papers=papers,
        contexts=contexts,
        split=split,
        output_path=output_path,
    )

    assert output_path.exists()

def test_export_split_top100(tmp_path):
    import json

    from src.training import export_top100

    raw_dir = tmp_path / "raw"
    output_dir = tmp_path / "processed"
    raw_dir.mkdir()

    papers = {
        f"paper-{i}": {
            "title": f"Topic {i}",
            "abstract": f"Study about topic {i}",
        }
        for i in range(120)
    }

    contexts = {
        "context-1": {
            "masked_text": "Study about topic 5 TARGETCIT"
        }
    }

    train = [
        {
            "context_id": "context-1",
            "positive_ids": ["paper-5"],
        }
    ]

    for name, data in {
        "papers.json": papers,
        "contexts.json": contexts,
        "train.json": train,
    }.items():
        with (raw_dir / name).open("w", encoding="utf-8") as file:
            json.dump(data, file)

    output_path = export_top100.export_split_top100(
        raw_dir=raw_dir,
        output_dir=output_dir,
        split_name="train",
    )

    assert output_path.exists()

    with output_path.open("r", encoding="utf-8") as file:
        records = json.load(file)

    assert len(records) == 1
    assert len(records[0]["candidate_ids"]) == 100