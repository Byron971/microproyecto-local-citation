from pathlib import Path

from src.data.load_data import load_json
from src.training.run_tfidf_baseline import export_top100


def export_split_top100(
    raw_dir: str | Path,
    output_dir: str | Path,
    split_name: str,
) -> Path:
    """Genera y guarda el Top-100 TF-IDF para un split."""
    raw_path = Path(raw_dir)
    output_path = Path(output_dir) / f"{split_name}_tfidf_top100.json"

    papers = load_json(raw_path / "papers.json")
    contexts = load_json(raw_path / "contexts.json")
    split = load_json(raw_path / f"{split_name}.json")

    export_top100(
        papers=papers,
        contexts=contexts,
        split=split,
        output_path=output_path,
    )

    return output_path


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

    