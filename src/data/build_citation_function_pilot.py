"""Construye un conjunto piloto de contextos de cita para probar prompts.

No incluye etiquetas de funcion de cita reales: el campo `gold` se deja
explicitamente en `None`. Sirve unicamente para medir formato y
estabilidad de respuestas, ver docs/prompts_estabilidad.md.
"""
from __future__ import annotations

import json
import random
import re
from pathlib import Path

from src.data.load_data import load_json
from src.models.tfidf_baseline import clean_context_text

DEFAULT_OUTPUT_PATH = Path("tests/fixtures/citation_function_pilot.jsonl")


def _remove_citation_markers_no_word_boundary(text: str) -> str:
    """Remove TARGETCIT and OTHERCIT markers regardless of word boundaries.

    This is a supplementary cleanup step applied after clean_context_text()
    to catch fused markers like "McOTHERCIT" that the word-boundary regex
    in clean_context_text() does not catch.
    """
    text = re.sub(r"TARGETCIT", " ", text)
    text = re.sub(r"OTHERCIT", " ", text)
    return text.strip()


def build_pilot_cases(
    data_dir: str | Path,
    n_cases: int = 20,
    seed: int = 42,
) -> list[dict]:
    data_dir = Path(data_dir)
    contexts = load_json(data_dir / "contexts.json")
    papers = load_json(data_dir / "papers.json")
    test_entries = load_json(data_dir / "test.json")

    rng = random.Random(seed)
    sampled = rng.sample(test_entries, k=min(n_cases, len(test_entries)))

    cases: list[dict] = []
    for entry in sampled:
        context_id = entry["context_id"]
        positive_id = entry["positive_ids"][0]
        context = contexts[context_id]
        paper = papers.get(positive_id, {"title": "", "abstract": ""})
        cleaned = clean_context_text(context.get("masked_text", ""))
        # Apply supplementary cleanup to catch markers without word boundaries (e.g., "McOTHERCIT")
        cleaned = _remove_citation_markers_no_word_boundary(cleaned)
        input_text = (
            f"Citation context: {cleaned}\n\n"
            f"Cited paper title: {paper.get('title', '')}\n"
            f"Cited paper abstract: {paper.get('abstract', '')}"
        )
        cases.append({"id": context_id, "input": input_text, "gold": None})
    return cases


def write_pilot_jsonl(cases: list[dict], output_path: str | Path) -> None:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as fh:
        for case in cases:
            fh.write(json.dumps(case, ensure_ascii=False) + "\n")


def main() -> None:
    cases = build_pilot_cases("data/raw", n_cases=20, seed=42)
    write_pilot_jsonl(cases, DEFAULT_OUTPUT_PATH)
    print(f"Generados {len(cases)} casos piloto en {DEFAULT_OUTPUT_PATH}")


if __name__ == "__main__":
    main()
