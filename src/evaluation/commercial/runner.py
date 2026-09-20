from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from time import perf_counter, sleep
from typing import Any, Callable, Iterable, Mapping

from .providers import CommercialModelClient, ProviderCallError
from .schema import EvaluationCase, PromptTemplate, ProviderResponse, RunRecord


@dataclass(frozen=True)
class ModelPricing:
    input_usd_per_million: float
    output_usd_per_million: float


def _estimate_cost(response: ProviderResponse, price: ModelPricing | None) -> float | None:
    if price is None or response.input_tokens is None or response.output_tokens is None:
        return None
    return (
        response.input_tokens * price.input_usd_per_million
        + response.output_tokens * price.output_usd_per_million
    ) / 1_000_000


def run_evaluation(
    cases: Iterable[EvaluationCase],
    prompts: Iterable[PromptTemplate],
    clients: Iterable[CommercialModelClient],
    *,
    max_retries: int = 2,
    parser: Callable[[str], Any] | None = None,
    pricing: Mapping[tuple[str, str], ModelPricing] | None = None,
    request_delay_seconds: float = 0.0,
) -> list[RunRecord]:
    if max_retries < 0:
        raise ValueError("max_retries must be >= 0")
    if request_delay_seconds < 0:
        raise ValueError("request_delay_seconds must be >= 0")

    records: list[RunRecord] = []
    prices = pricing or {}

    for case in cases:
        for prompt in prompts:
            prompt_text = prompt.render(case.input)
            for client in clients:
                started_at = datetime.now(timezone.utc).isoformat()
                started = perf_counter()
                retry_count = 0
                response: ProviderResponse | None = None
                provider_error: str | None = None

                while True:
                    try:
                        response = client.generate(prompt_text)
                        break
                    except ProviderCallError as exc:
                        provider_error = str(exc)
                        if not exc.transient or retry_count >= max_retries:
                            break
                        retry_count += 1

                latency_ms = (perf_counter() - started) * 1000.0

                if response is None:
                    records.append(
                        RunRecord(
                            case_id=case.id,
                            provider=client.provider,
                            model=client.model,
                            prompt_name=prompt.name,
                            prompt_text=prompt_text,
                            raw_response=None,
                            parsed_output=None,
                            latency_ms=latency_ms,
                            input_tokens=None,
                            output_tokens=None,
                            estimated_cost_usd=None,
                            retry_count=retry_count,
                            status="provider_error",
                            error=provider_error,
                            started_at=started_at,
                            gold=case.gold,
                        )
                    )
                    if request_delay_seconds:
                        sleep(request_delay_seconds)
                    continue

                parsed_output: Any | None = response.text
                status = "ok"
                parse_error: str | None = None
                if parser is not None:
                    try:
                        parsed_output = parser(response.text)
                    except Exception as exc:
                        parsed_output = None
                        status = "parse_error"
                        parse_error = str(exc)

                records.append(
                    RunRecord(
                        case_id=case.id,
                        provider=client.provider,
                        model=client.model,
                        prompt_name=prompt.name,
                        prompt_text=prompt_text,
                        raw_response=response.text,
                        parsed_output=parsed_output,
                        latency_ms=latency_ms,
                        input_tokens=response.input_tokens,
                        output_tokens=response.output_tokens,
                        estimated_cost_usd=_estimate_cost(
                            response, prices.get((client.provider, client.model))
                        ),
                        retry_count=retry_count,
                        status=status,
                        error=parse_error,
                        started_at=started_at,
                        gold=case.gold,
                    )
                )
                if request_delay_seconds:
                    sleep(request_delay_seconds)

    return records
