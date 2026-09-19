from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Iterable

from .schema import EvaluationCase, PromptTemplate, RunRecord


def load_gold_jsonl(path: str | Path) -> list[EvaluationCase]:
    cases: list[EvaluationCase] = []
    path = Path(path)
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not raw_line.strip():
            continue
        try:
            payload = json.loads(raw_line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSON on line {line_number}: {exc.msg}") from exc
        if not isinstance(payload, dict):
            raise ValueError(f"line {line_number} must contain a JSON object")
        missing = [key for key in ("id", "input", "gold") if key not in payload]
        if missing:
            raise ValueError(f"line {line_number} missing required fields: {', '.join(missing)}")
        metadata = {k: v for k, v in payload.items() if k not in {"id", "input", "gold"}}
        try:
            cases.append(
                EvaluationCase(
                    id=str(payload["id"]),
                    input=str(payload["input"]),
                    gold=payload["gold"],
                    metadata=metadata,
                )
            )
        except ValueError as exc:
            raise ValueError(f"invalid case on line {line_number}: {exc}") from exc
    if not cases:
        raise ValueError("Test Gold is empty")
    return cases


def load_prompts_json(path: str | Path) -> list[PromptTemplate]:
    path = Path(path)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid prompts JSON: {exc.msg}") from exc
    if not isinstance(payload, dict) or not payload:
        raise ValueError("prompts JSON must be a non-empty object")
    prompts: list[PromptTemplate] = []
    for name, template in payload.items():
        if not isinstance(template, str):
            raise ValueError(f"prompt {name!r} must be a string")
        prompts.append(PromptTemplate(name=str(name), template=template))
    return prompts


def write_results_jsonl(path: str | Path, records: Iterable[RunRecord]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for record in records:
            fh.write(json.dumps(record.to_dict(), ensure_ascii=False, sort_keys=True) + "\n")


def write_summary_csv(path: str | Path, records: Iterable[RunRecord]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [record.to_dict() for record in records]
    fieldnames = list(RunRecord.__dataclass_fields__.keys())
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
