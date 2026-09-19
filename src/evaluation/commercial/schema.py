from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

RunStatus = Literal["ok", "provider_error", "parse_error"]


@dataclass(frozen=True)
class EvaluationCase:
    id: str
    input: str
    gold: Any
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise ValueError("case id must not be blank")
        if not self.input.strip():
            raise ValueError("case input must not be blank")


@dataclass(frozen=True)
class PromptTemplate:
    name: str
    template: str

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("prompt name must not be blank")
        if "{input}" not in self.template:
            raise ValueError("prompt template must contain {input}")

    def render(self, input_text: str) -> str:
        return self.template.replace("{input}", input_text)


@dataclass(frozen=True)
class ProviderResponse:
    text: str
    input_tokens: int | None = None
    output_tokens: int | None = None


@dataclass(frozen=True)
class RunRecord:
    case_id: str
    provider: str
    model: str
    prompt_name: str
    prompt_text: str
    raw_response: str | None
    parsed_output: Any | None
    latency_ms: float
    input_tokens: int | None
    output_tokens: int | None
    estimated_cost_usd: float | None
    retry_count: int
    status: RunStatus
    error: str | None
    started_at: str
    gold: Any

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
