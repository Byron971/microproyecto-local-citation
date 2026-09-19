import csv
import json

import pytest

from src.evaluation.commercial.io import (
    load_gold_jsonl,
    load_prompts_json,
    write_results_jsonl,
    write_summary_csv,
)
from src.evaluation.commercial.schema import RunRecord


def test_load_gold_jsonl_preserves_extra_fields_as_metadata(tmp_path):
    path = tmp_path / "gold.jsonl"
    path.write_text(
        json.dumps({"id": "c1", "input": "x", "gold": "A", "source": "human"}) + "\n",
        encoding="utf-8",
    )
    cases = load_gold_jsonl(path)
    assert cases[0].metadata == {"source": "human"}


def test_load_gold_jsonl_reports_line_number_for_invalid_json(tmp_path):
    path = tmp_path / "gold.jsonl"
    path.write_text(
        '{"id":"c1","input":"x","gold":"A"}\nnot-json\n',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="line 2"):
        load_gold_jsonl(path)


def test_load_prompts_json_builds_named_templates(tmp_path):
    path = tmp_path / "prompts.json"
    path.write_text(json.dumps({"zero": "Classify: {input}"}), encoding="utf-8")
    prompts = load_prompts_json(path)
    assert prompts[0].name == "zero"
    assert prompts[0].render("abc") == "Classify: abc"


def test_writers_persist_jsonl_and_csv(tmp_path):
    record = RunRecord(
        case_id="c1",
        provider="p",
        model="m",
        prompt_name="zero",
        prompt_text="Q",
        raw_response="A",
        parsed_output="A",
        latency_ms=10.0,
        input_tokens=4,
        output_tokens=1,
        estimated_cost_usd=None,
        retry_count=0,
        status="ok",
        error=None,
        started_at="2026-09-17T00:00:00+00:00",
        gold="A",
    )
    jsonl = tmp_path / "results.jsonl"
    csv_path = tmp_path / "summary.csv"
    write_results_jsonl(jsonl, [record])
    write_summary_csv(csv_path, [record])
    assert json.loads(jsonl.read_text(encoding="utf-8"))["case_id"] == "c1"
    with csv_path.open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    assert rows[0]["status"] == "ok"
    assert rows[0]["gold"] == "A"
