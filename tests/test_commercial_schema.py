import pytest

from src.evaluation.commercial.schema import EvaluationCase, PromptTemplate, RunRecord


def test_evaluation_case_rejects_blank_id():
    with pytest.raises(ValueError, match="id"):
        EvaluationCase(id="   ", input="text", gold="label")


def test_prompt_template_requires_input_placeholder():
    with pytest.raises(ValueError, match=r"\{input\}"):
        PromptTemplate(name="zero", template="Classify this")


def test_run_record_to_dict_serializes_expected_fields():
    record = RunRecord(
        case_id="c1",
        provider="p",
        model="m",
        prompt_name="zero",
        prompt_text="Q: x",
        raw_response="A",
        parsed_output="A",
        latency_ms=12.5,
        input_tokens=10,
        output_tokens=2,
        estimated_cost_usd=0.001,
        retry_count=1,
        status="ok",
        error=None,
        started_at="2026-09-17T00:00:00+00:00",
        gold="A",
    )
    assert record.to_dict()["case_id"] == "c1"
    assert record.to_dict()["estimated_cost_usd"] == 0.001
