import json

from src.evaluation.commercial.providers import ProviderCallError
from src.evaluation.commercial.runner import ModelPricing, run_evaluation
from src.evaluation.commercial.schema import EvaluationCase, PromptTemplate, ProviderResponse


class SuccessClient:
    provider = "vendor"
    model = "model-a"

    def __init__(self):
        self.calls = 0

    def generate(self, prompt):
        self.calls += 1
        return ProviderResponse(text='{"label":"A"}', input_tokens=100, output_tokens=20)


class RetryClient(SuccessClient):
    def generate(self, prompt):
        self.calls += 1
        if self.calls < 3:
            raise ProviderCallError("rate limit", transient=True)
        return ProviderResponse(text="A", input_tokens=10, output_tokens=2)


class PermanentFailureClient(SuccessClient):
    def generate(self, prompt):
        self.calls += 1
        raise ProviderCallError("bad request", transient=False)


def test_runner_creates_cartesian_product_and_parses_response():
    cases = [EvaluationCase(id="c1", input="text", gold="A")]
    prompts = [PromptTemplate(name="zero", template="Classify {input}")]
    client = SuccessClient()
    records = run_evaluation(cases, prompts, [client], parser=lambda text: json.loads(text)["label"])
    assert len(records) == 1
    assert records[0].parsed_output == "A"
    assert records[0].status == "ok"
    assert records[0].retry_count == 0
    assert client.calls == 1


def test_runner_retries_only_transient_errors_and_counts_retries():
    client = RetryClient()
    records = run_evaluation(
        [EvaluationCase(id="c1", input="x", gold="A")],
        [PromptTemplate(name="zero", template="{input}")],
        [client],
        max_retries=2,
    )
    assert records[0].status == "ok"
    assert records[0].retry_count == 2
    assert client.calls == 3


def test_runner_records_permanent_provider_error_without_retry():
    client = PermanentFailureClient()
    records = run_evaluation(
        [EvaluationCase(id="c1", input="x", gold="A")],
        [PromptTemplate(name="zero", template="{input}")],
        [client],
        max_retries=2,
    )
    assert records[0].status == "provider_error"
    assert records[0].retry_count == 0
    assert records[0].raw_response is None
    assert "bad request" in records[0].error
    assert client.calls == 1


def test_runner_preserves_raw_response_when_parser_fails():
    client = SuccessClient()
    records = run_evaluation(
        [EvaluationCase(id="c1", input="x", gold="A")],
        [PromptTemplate(name="zero", template="{input}")],
        [client],
        parser=lambda _: (_ for _ in ()).throw(ValueError("bad format")),
    )
    assert records[0].status == "parse_error"
    assert records[0].raw_response == '{"label":"A"}'
    assert records[0].parsed_output is None
    assert "bad format" in records[0].error


def test_runner_cost_is_only_computed_with_explicit_pricing():
    case = EvaluationCase(id="c1", input="x", gold="A")
    prompt = PromptTemplate(name="zero", template="{input}")
    without_price = run_evaluation([case], [prompt], [SuccessClient()])[0]
    with_price = run_evaluation(
        [case],
        [prompt],
        [SuccessClient()],
        pricing={
            ("vendor", "model-a"): ModelPricing(
                input_usd_per_million=2.0,
                output_usd_per_million=10.0,
            )
        },
    )[0]
    assert without_price.estimated_cost_usd is None
    assert with_price.estimated_cost_usd == 0.0004
