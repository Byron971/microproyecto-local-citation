import json
from pathlib import Path

from src.evaluation.commercial.io import load_prompts_json

PROMPTS_PATH = Path("config/prompts/citation_function_prompts.json")

CATEGORIES = [
    "Background",
    "Gap",
    "Basis",
    "Comparison",
    "Application",
    "Improvement",
    "Evidence",
    "Originator",
    "Further Reading",
]


def test_prompts_file_has_three_strategies():
    payload = json.loads(PROMPTS_PATH.read_text(encoding="utf-8"))
    assert set(payload.keys()) == {"zero_shot_generic", "zero_shot_detailed", "few_shot"}


def test_prompts_load_with_commercial_schema():
    prompts = load_prompts_json(PROMPTS_PATH)
    names = {p.name for p in prompts}
    assert names == {"zero_shot_generic", "zero_shot_detailed", "few_shot"}


def test_all_prompts_contain_input_placeholder():
    payload = json.loads(PROMPTS_PATH.read_text(encoding="utf-8"))
    for template in payload.values():
        assert "{input}" in template


def test_detailed_and_few_shot_mention_all_categories():
    payload = json.loads(PROMPTS_PATH.read_text(encoding="utf-8"))
    for name in ("zero_shot_detailed", "few_shot"):
        template = payload[name]
        for category in CATEGORIES:
            assert category in template, f"{category} falta en {name}"


def test_few_shot_has_worked_examples():
    payload = json.loads(PROMPTS_PATH.read_text(encoding="utf-8"))
    template = payload["few_shot"]
    assert template.count("Example") >= 2
