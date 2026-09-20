import json
from pathlib import Path

import pytest

from src.data.build_citation_function_pilot import build_pilot_cases, write_pilot_jsonl
from src.evaluation.commercial.io import load_gold_jsonl


def _write_fake_dataset(data_dir: Path) -> None:
    contexts = {
        "ctx-1": {"masked_text": "This builds on TARGETCIT for encoding.", "context_id": "ctx-1"},
        "ctx-2": {"masked_text": "We compare against OTHERCIT and TARGETCIT.", "context_id": "ctx-2"},
        "ctx-3": {"masked_text": "TARGETCIT introduced the original idea.", "context_id": "ctx-3"},
        "ctx-4": {"masked_text": "We used the Chu-Liu-Edmonds algorithm for trees ( ; McOTHERCIT). The loss function was computed.", "context_id": "ctx-4"},
    }
    papers = {
        "paper-1": {"title": "Paper One", "abstract": "Abstract one."},
        "paper-2": {"title": "Paper Two", "abstract": "Abstract two."},
        "paper-3": {"title": "Paper Three", "abstract": "Abstract three."},
        "paper-4": {"title": "Paper Four", "abstract": "Abstract four."},
    }
    test_entries = [
        {"context_id": "ctx-1", "positive_ids": ["paper-1"]},
        {"context_id": "ctx-2", "positive_ids": ["paper-2"]},
        {"context_id": "ctx-3", "positive_ids": ["paper-3"]},
        {"context_id": "ctx-4", "positive_ids": ["paper-4"]},
    ]
    (data_dir / "contexts.json").write_text(json.dumps(contexts), encoding="utf-8")
    (data_dir / "papers.json").write_text(json.dumps(papers), encoding="utf-8")
    (data_dir / "test.json").write_text(json.dumps(test_entries), encoding="utf-8")


def test_build_pilot_cases_returns_requested_count(tmp_path):
    _write_fake_dataset(tmp_path)
    cases = build_pilot_cases(tmp_path, n_cases=2, seed=42)
    assert len(cases) == 2


def test_build_pilot_cases_is_deterministic(tmp_path):
    _write_fake_dataset(tmp_path)
    first = build_pilot_cases(tmp_path, n_cases=2, seed=42)
    second = build_pilot_cases(tmp_path, n_cases=2, seed=42)
    assert [c["id"] for c in first] == [c["id"] for c in second]


def test_build_pilot_cases_has_expected_shape(tmp_path):
    _write_fake_dataset(tmp_path)
    cases = build_pilot_cases(tmp_path, n_cases=1, seed=42)
    case = cases[0]
    assert set(case.keys()) == {"id", "input", "gold"}
    assert case["gold"] is None
    assert "Citation context:" in case["input"]
    assert "Cited paper title:" in case["input"]
    assert "TARGETCIT" not in case["input"]
    assert "OTHERCIT" not in case["input"]


def test_build_pilot_cases_removes_fused_citation_markers(tmp_path):
    """Test that fused markers (e.g., McOTHERCIT) are also removed."""
    _write_fake_dataset(tmp_path)
    # Get case with index 3 (ctx-4 with McOTHERCIT), need to sample more to ensure it's included
    cases = build_pilot_cases(tmp_path, n_cases=4, seed=42)
    # Find the case with ctx-4 (should have McOTHERCIT originally)
    ctx4_case = [c for c in cases if c["id"] == "ctx-4"]
    assert len(ctx4_case) == 1, "ctx-4 should be in the sample"
    case = ctx4_case[0]
    # Verify no citation markers appear anywhere, including fused ones
    assert "TARGETCIT" not in case["input"], "TARGETCIT should not appear as substring"
    assert "OTHERCIT" not in case["input"], "OTHERCIT should not appear as substring"
    # The original text had "McOTHERCIT" which should be cleaned to "Mc" and
    # the leftover double space collapsed, not left visible in the prompt.
    assert "McOTHERCIT" not in case["input"], "Fused marker McOTHERCIT should be removed"
    assert "  " not in case["input"], "no debe quedar doble espacio tras quitar el marcador"


def test_write_pilot_jsonl_is_loadable_by_commercial_io(tmp_path):
    _write_fake_dataset(tmp_path)
    cases = build_pilot_cases(tmp_path, n_cases=3, seed=42)
    output_path = tmp_path / "pilot.jsonl"
    write_pilot_jsonl(cases, output_path)

    loaded = load_gold_jsonl(output_path)
    assert len(loaded) == 3
    assert all(case.gold is None for case in loaded)
