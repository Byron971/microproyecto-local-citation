import json

from src.data.load_data import load_dataset, load_json


def test_load_json_reads_json_file(tmp_path):
    expected = {
        "paper-1": {
            "title": "Example paper",
            "abstract": "Example abstract",
        }
    }

    file_path = tmp_path / "sample.json"
    file_path.write_text(
        json.dumps(expected),
        encoding="utf-8",
    )

    result = load_json(file_path)

    assert result == expected


def test_load_dataset_reads_all_required_files(tmp_path):
    files = {
        "contexts.json": {"context-1": {"masked_text": "Example context"}},
        "papers.json": {"paper-1": {"title": "Title", "abstract": "Abstract"}},
        "train.json": [{"context_id": "context-1", "positive_ids": ["paper-1"]}],
        "val.json": [{"context_id": "context-2", "positive_ids": ["paper-2"]}],
        "test.json": [{"context_id": "context-3", "positive_ids": ["paper-3"]}],
    }

    for filename, content in files.items():
        (tmp_path / filename).write_text(
            json.dumps(content),
            encoding="utf-8",
        )

    result = load_dataset(tmp_path)

    assert result["contexts"] == files["contexts.json"]
    assert result["papers"] == files["papers.json"]
    assert result["train"] == files["train.json"]
    assert result["val"] == files["val.json"]
    assert result["test"] == files["test.json"]