# Prompts y estabilidad (issue #43) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Versionar tres estrategias de prompting para clasificación de función de cita (9 categorías) y un pipeline reproducible que mida, sin llamadas de red, qué tan estable y bien formateada es la respuesta de un modelo para cada estrategia.

**Architecture:** Se ramifica desde `feature/20sep-commercial-eval-john` (paquete `src/evaluation/commercial/` del issue #40) y se agrega: los prompts versionados, un generador reproducible de un conjunto piloto sin etiquetas reales, un cliente de proveedor placeholder que documenta la decisión pendiente, y un módulo de análisis de estabilidad que consume `results.jsonl` ya producido por el runner existente.

**Tech Stack:** Python estándar (`json`, `csv`, `re`, `argparse`, `random`, `pathlib`), `pytest`, la infraestructura ya implementada en `src/evaluation/commercial/` (rama de #40).

**Spec:** `docs/superpowers/specs/2026-09-19-prompt-design-stability-design.md`

## Global Constraints

- Ninguna prueba puede hacer llamadas de red.
- No se fija ni se inventa el modelo/proveedor de prueba en este PR; la decisión (Ollama local vs. API comercial) queda documentada como pendiente.
- El conjunto piloto no contiene etiquetas de función de cita inventadas: el campo `gold` va explícitamente en `null`.
- No se versionan API keys ni credenciales.
- El PR de esta rama apunta como base a `feature/20sep-commercial-eval-john`, no a `main`.
- Todas las plantillas de prompt deben contener `{input}` (contrato ya validado por `PromptTemplate` en `src/evaluation/commercial/schema.py`).

---

### Task 1: Preparar la rama de trabajo

**Files:** ninguno (solo control de versiones).

- [ ] **Step 1: Traer y ramificar desde la rama de #40**

```bash
git fetch origin feature/20sep-commercial-eval-john
git checkout -b feature/43-prompts-estabilidad origin/feature/20sep-commercial-eval-john
```

- [ ] **Step 2: Verificar que la infraestructura de #40 ya pasa sus pruebas en esta rama**

Run: `uv run pytest tests/test_commercial_schema.py tests/test_commercial_io.py tests/test_commercial_runner.py tests/test_commercial_cli.py -v`
Expected: 14 pruebas en PASS (ya implementadas por el issue #40; si alguna falla, detenerse e investigar antes de continuar, no es parte de este issue arreglarlas).

No hay commit en esta tarea: no se modifica ningún archivo todavía.

---

### Task 2: Prompts de clasificación de función de cita

**Files:**
- Create: `config/prompts/citation_function_prompts.json`
- Test: `tests/test_prompts_format.py`

**Interfaces:**
- Consumes: `src.evaluation.commercial.io.load_prompts_json(path) -> list[PromptTemplate]` (ya existente en la rama de #40).
- Produces: el archivo `config/prompts/citation_function_prompts.json`, consumido por todas las tareas siguientes y por `run_evaluation`.

- [ ] **Step 1: Escribir la prueba que falla**

```python
# tests/test_prompts_format.py
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
```

- [ ] **Step 2: Ejecutar y confirmar que falla**

Run: `uv run pytest tests/test_prompts_format.py -v`
Expected: FAIL (`FileNotFoundError`, el archivo de prompts todavía no existe).

- [ ] **Step 3: Crear el archivo de prompts**

```json
{
  "zero_shot_generic": "Classify the following academic citation context into one or more of these 9 citation function categories: Background, Gap, Basis, Comparison, Application, Improvement / Modification, Evidence, Identification of the Originator, Further Reading.\n\n{input}\n\nRespond ONLY with a JSON array of 9 floats between 0.0 and 1.0, one score per category, in the exact order listed above. Do not include any explanation, only the array. Example format: [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]",
  "zero_shot_detailed": "You are classifying the function of an academic citation. Read the definitions of the 9 citation function categories below, then classify the citation context that follows.\n\n1. Background: citations used to provide context, summarize the general background of a research topic, or trace the history of a field or idea.\n2. Gap: citations that help identify research gaps or unexplored areas, justifying the author's choice of research topic.\n3. Basis: citations that provide a foundation for the current research, at a macro (broad influence) or micro (specific key contribution) level.\n4. Comparison: citations used to compare the current work with cited studies or to draw comparisons between cited studies.\n5. Application: citations that directly employ a method, technique, or tool from the cited work without modification.\n6. Improvement / Modification: citations in which methods or tools from the cited work are adapted, expanded, or modified for the current research.\n7. Evidence: citations used to support claims, hypotheses, or findings in the current research.\n8. Identification of the Originator: citations used to acknowledge the original source of an idea, concept, method, or theory.\n9. Further Reading: citations that direct readers to additional or supplementary literature for more detailed information or context.\n\n{input}\n\nRespond ONLY with a JSON array of 9 floats between 0.0 and 1.0, one score per category, in the exact order listed above (Background, Gap, Basis, Comparison, Application, Improvement / Modification, Evidence, Identification of the Originator, Further Reading). Do not include any explanation, only the array.",
  "few_shot": "You are classifying the function of an academic citation. Read the definitions of the 9 citation function categories below, then classify the citation context that follows. Two worked examples are provided before the case you must classify.\n\n1. Background: citations used to provide context, summarize the general background of a research topic, or trace the history of a field or idea.\n2. Gap: citations that help identify research gaps or unexplored areas, justifying the author's choice of research topic.\n3. Basis: citations that provide a foundation for the current research, at a macro (broad influence) or micro (specific key contribution) level.\n4. Comparison: citations used to compare the current work with cited studies or to draw comparisons between cited studies.\n5. Application: citations that directly employ a method, technique, or tool from the cited work without modification.\n6. Improvement / Modification: citations in which methods or tools from the cited work are adapted, expanded, or modified for the current research.\n7. Evidence: citations used to support claims, hypotheses, or findings in the current research.\n8. Identification of the Originator: citations used to acknowledge the original source of an idea, concept, method, or theory.\n9. Further Reading: citations that direct readers to additional or supplementary literature for more detailed information or context.\n\nExample 1:\nCitation context: Recent transformer architectures have achieved state-of-the-art results on machine translation benchmarks, motivating their use as the backbone of our encoder.\nCited paper title: Attention Is All You Need\nCited paper abstract: The dominant sequence transduction models are based on complex recurrent or convolutional neural networks that include an encoder and a decoder.\nAnswer: [0.0, 0.0, 0.2, 0.0, 0.0, 0.0, 0.8, 0.0, 0.0]\n\nExample 2:\nCitation context: Unlike prior work, which evaluated their ranking model on a single small dataset, we test on three benchmarks of varying size to assess generalization.\nCited paper title: A Ranking Approach to Local Citation Recommendation\nCited paper abstract: We propose a supervised ranking model for local citation recommendation and evaluate it on a single benchmark dataset.\nAnswer: [0.0, 0.1, 0.0, 0.9, 0.0, 0.0, 0.0, 0.0, 0.0]\n\nNow classify the following case:\n\n{input}\n\nRespond ONLY with a JSON array of 9 floats between 0.0 and 1.0, one score per category, in the exact order listed above. Do not include any explanation, only the array."
}
```

Guardar este contenido exacto en `config/prompts/citation_function_prompts.json`.

- [ ] **Step 4: Ejecutar y confirmar que pasa**

Run: `uv run pytest tests/test_prompts_format.py -v`
Expected: 5 pruebas en PASS.

- [ ] **Step 5: Commit**

```bash
git add config/prompts/citation_function_prompts.json tests/test_prompts_format.py
git commit -m "Agrega los tres prompts de clasificacion de funcion de cita"
```

---

### Task 3: Conjunto piloto reproducible (sin etiquetas reales)

**Files:**
- Create: `src/data/build_citation_function_pilot.py`
- Test: `tests/test_build_citation_function_pilot.py`
- Create (generado por el script, se commitea): `tests/fixtures/citation_function_pilot.jsonl`

**Interfaces:**
- Consumes: `src.data.load_data.load_json(path) -> Any` (ya existente), `src.models.tfidf_baseline.clean_context_text(text) -> str` (ya existente), `src.evaluation.commercial.io.load_gold_jsonl(path) -> list[EvaluationCase]` (rama de #40, para la prueba de integración).
- Produces: `build_pilot_cases(data_dir, n_cases=20, seed=42) -> list[dict]`, `write_pilot_jsonl(cases, output_path) -> None`.

- [ ] **Step 1: Escribir la prueba que falla**

```python
# tests/test_build_citation_function_pilot.py
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
    }
    papers = {
        "paper-1": {"title": "Paper One", "abstract": "Abstract one."},
        "paper-2": {"title": "Paper Two", "abstract": "Abstract two."},
        "paper-3": {"title": "Paper Three", "abstract": "Abstract three."},
    }
    test_entries = [
        {"context_id": "ctx-1", "positive_ids": ["paper-1"]},
        {"context_id": "ctx-2", "positive_ids": ["paper-2"]},
        {"context_id": "ctx-3", "positive_ids": ["paper-3"]},
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


def test_write_pilot_jsonl_is_loadable_by_commercial_io(tmp_path):
    _write_fake_dataset(tmp_path)
    cases = build_pilot_cases(tmp_path, n_cases=3, seed=42)
    output_path = tmp_path / "pilot.jsonl"
    write_pilot_jsonl(cases, output_path)

    loaded = load_gold_jsonl(output_path)
    assert len(loaded) == 3
    assert all(case.gold is None for case in loaded)
```

- [ ] **Step 2: Ejecutar y confirmar que falla**

Run: `uv run pytest tests/test_build_citation_function_pilot.py -v`
Expected: FAIL (`ModuleNotFoundError: src.data.build_citation_function_pilot`).

- [ ] **Step 3: Implementar el módulo**

```python
# src/data/build_citation_function_pilot.py
"""Construye un conjunto piloto de contextos de cita para probar prompts.

No incluye etiquetas de funcion de cita reales: el campo `gold` se deja
explicitamente en `None`. Sirve unicamente para medir formato y
estabilidad de respuestas, ver seccion 6.1 de
docs/superpowers/specs/2026-09-19-prompt-design-stability-design.md.
"""
from __future__ import annotations

import json
import random
from pathlib import Path

from src.data.load_data import load_json
from src.models.tfidf_baseline import clean_context_text

DEFAULT_OUTPUT_PATH = Path("tests/fixtures/citation_function_pilot.jsonl")


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
```

- [ ] **Step 4: Ejecutar y confirmar que pasa**

Run: `uv run pytest tests/test_build_citation_function_pilot.py -v`
Expected: 4 pruebas en PASS.

- [ ] **Step 5: Generar el conjunto piloto real**

```bash
uv run python -m src.data.build_citation_function_pilot
```

Expected: crea `tests/fixtures/citation_function_pilot.jsonl` con 20 líneas.

- [ ] **Step 6: Commit**

```bash
git add src/data/build_citation_function_pilot.py tests/test_build_citation_function_pilot.py tests/fixtures/citation_function_pilot.jsonl
git commit -m "Agrega generador reproducible del conjunto piloto de estabilidad"
```

---

### Task 4: Cliente de proveedor placeholder

**Files:**
- Create: `src/evaluation/commercial/providers_local.py`
- Test: `tests/test_providers_local.py`

**Interfaces:**
- Consumes: `src.evaluation.commercial.schema.ProviderResponse` (rama de #40, solo para el type hint).
- Produces: `LocalPilotClient` (atributos `provider: str`, `model: str`, método `generate(prompt: str) -> ProviderResponse`), `LocalProviderNotConfiguredError(RuntimeError)`, `build_client() -> LocalPilotClient`.

- [ ] **Step 1: Escribir la prueba que falla**

```python
# tests/test_providers_local.py
import pytest

from src.evaluation.commercial.providers_local import (
    LocalPilotClient,
    LocalProviderNotConfiguredError,
    build_client,
)


def test_build_client_returns_local_pilot_client():
    client = build_client()
    assert isinstance(client, LocalPilotClient)


def test_client_exposes_provider_and_model_strings():
    client = build_client()
    assert isinstance(client.provider, str) and client.provider
    assert isinstance(client.model, str) and client.model


def test_generate_raises_not_configured_error_without_network():
    client = build_client()
    with pytest.raises(LocalProviderNotConfiguredError) as exc_info:
        client.generate("cualquier prompt")
    assert "proveedor" in str(exc_info.value).lower()
```

- [ ] **Step 2: Ejecutar y confirmar que falla**

Run: `uv run pytest tests/test_providers_local.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Implementar el cliente**

```python
# src/evaluation/commercial/providers_local.py
"""Cliente de proveedor placeholder para las pruebas de estabilidad del issue #43.

El equipo aun no ha decidido que modelo de prueba usar (Ollama local vs.
API comercial): ver seccion 4 de
docs/superpowers/specs/2026-09-19-prompt-design-stability-design.md.
Cuando se decida, solo este archivo cambia; el resto del pipeline
(prompts, datos piloto, analisis de estabilidad) no se modifica.
"""
from __future__ import annotations

from .schema import ProviderResponse


class LocalProviderNotConfiguredError(RuntimeError):
    """Se lanza mientras el equipo no configure un proveedor real."""


class LocalPilotClient:
    provider = "pending"
    model = "pending"

    def generate(self, prompt: str) -> ProviderResponse:
        raise LocalProviderNotConfiguredError(
            "Configura el proveedor de prueba (Ollama local o API comercial) "
            "antes de ejecutar corridas reales. Ver la seccion 4 de "
            "docs/superpowers/specs/2026-09-19-prompt-design-stability-design.md."
        )


def build_client() -> LocalPilotClient:
    return LocalPilotClient()
```

- [ ] **Step 4: Ejecutar y confirmar que pasa**

Run: `uv run pytest tests/test_providers_local.py -v`
Expected: 3 pruebas en PASS.

- [ ] **Step 5: Commit**

```bash
git add src/evaluation/commercial/providers_local.py tests/test_providers_local.py
git commit -m "Agrega cliente placeholder documentando la decision de modelo pendiente"
```

---

### Task 5: Análisis de estabilidad

**Files:**
- Create: `src/evaluation/commercial/stability.py`
- Test: `tests/test_stability.py`

**Interfaces:**
- Consumes: registros con forma de `RunRecord.to_dict()` (rama de #40): al menos `case_id: str`, `prompt_name: str`, `raw_response: str | None`, `latency_ms: float`, `retry_count: int`.
- Produces: `parse_score_array(text: str) -> list[float]`, `load_results(path) -> list[dict]`, `group_records(records) -> dict[tuple[str, str], list[dict]]`, `compute_group_metrics(group: list[dict]) -> dict`, `aggregate_by_prompt(records) -> dict[str, dict]`, `write_stability_summary_csv(path, aggregated) -> None`, `main(argv=None) -> int`.

- [ ] **Step 1: Escribir las pruebas que fallan**

```python
# tests/test_stability.py
import csv

import pytest

from src.evaluation.commercial.stability import (
    aggregate_by_prompt,
    compute_group_metrics,
    parse_score_array,
    write_stability_summary_csv,
)

VALID_ARRAY = "[0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.9, 0.0, 0.0]"  # argmax = indice 6
OTHER_ARRAY = "[0.0, 0.9, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]"  # argmax = indice 1


def _record(case_id, prompt_name, raw_response, latency_ms=100.0, retry_count=0):
    return {
        "case_id": case_id,
        "prompt_name": prompt_name,
        "raw_response": raw_response,
        "latency_ms": latency_ms,
        "retry_count": retry_count,
    }


def test_parse_score_array_valid():
    scores = parse_score_array(VALID_ARRAY)
    assert len(scores) == 9
    assert scores[6] == 0.9


def test_parse_score_array_rejects_wrong_length():
    with pytest.raises(ValueError):
        parse_score_array("[0.1, 0.2, 0.3]")


def test_parse_score_array_rejects_non_json():
    with pytest.raises(ValueError):
        parse_score_array("the answer is Background")


def test_compute_group_metrics_all_broken_format():
    group = [_record("c1", "p1", "not an array") for _ in range(5)]
    metrics = compute_group_metrics(group)
    assert metrics["format_error_rate"] == 1.0
    assert metrics["label_stability"] is None


def test_compute_group_metrics_fully_stable():
    group = [_record("c1", "p1", VALID_ARRAY) for _ in range(5)]
    metrics = compute_group_metrics(group)
    assert metrics["format_error_rate"] == 0.0
    assert metrics["label_stability"] == 1.0


def test_compute_group_metrics_partially_unstable():
    responses = [VALID_ARRAY, OTHER_ARRAY, VALID_ARRAY, OTHER_ARRAY, VALID_ARRAY]
    group = [_record("c1", "p1", r) for r in responses]
    metrics = compute_group_metrics(group)
    assert metrics["label_stability"] == pytest.approx(3 / 5)


def test_compute_group_metrics_maximally_unstable():
    arrays = [
        "[0.9,0,0,0,0,0,0,0,0]",
        "[0,0.9,0,0,0,0,0,0,0]",
        "[0,0,0.9,0,0,0,0,0,0]",
        "[0,0,0,0.9,0,0,0,0,0]",
        "[0,0,0,0,0.9,0,0,0,0]",
    ]
    group = [_record("c1", "p1", a) for a in arrays]
    metrics = compute_group_metrics(group)
    assert metrics["label_stability"] == pytest.approx(0.2)


def test_aggregate_by_prompt_averages_across_cases():
    records = [
        *[_record("c1", "p1", VALID_ARRAY) for _ in range(5)],
        *[_record("c2", "p1", "broken") for _ in range(5)],
    ]
    aggregated = aggregate_by_prompt(records)
    assert aggregated["p1"]["n_cases"] == 2
    assert aggregated["p1"]["avg_format_error_rate"] == pytest.approx(0.5)
    assert aggregated["p1"]["avg_label_stability"] == pytest.approx(1.0)


def test_write_stability_summary_csv(tmp_path):
    aggregated = {
        "p1": {
            "n_cases": 2,
            "avg_format_error_rate": 0.5,
            "avg_label_stability": 1.0,
            "avg_latency_ms": 120.0,
            "avg_retry_count": 0.0,
        },
    }
    output_path = tmp_path / "stability_summary.csv"
    write_stability_summary_csv(output_path, aggregated)

    with output_path.open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert rows[0]["prompt_name"] == "p1"
    assert rows[0]["n_cases"] == "2"
```

- [ ] **Step 2: Ejecutar y confirmar que falla**

Run: `uv run pytest tests/test_stability.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Implementar el módulo**

```python
# src/evaluation/commercial/stability.py
"""Analiza estabilidad y errores de formato a partir de results.jsonl.

No calcula Precision/Recall/F1 (eso corresponde al issue #42): solo mide
si la respuesta parsea como arreglo valido de 9 puntajes y si el
argmax se mantiene estable entre repeticiones de un mismo caso+prompt.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path
from typing import Iterable

_ARRAY_PATTERN = re.compile(r"\[[^\[\]]*\]")

FIELDNAMES = [
    "prompt_name",
    "n_cases",
    "avg_format_error_rate",
    "avg_label_stability",
    "avg_latency_ms",
    "avg_retry_count",
]


def parse_score_array(text: str) -> list[float]:
    if not text:
        raise ValueError("empty response")
    match = _ARRAY_PATTERN.search(text)
    if match is None:
        raise ValueError("no JSON array found in response")
    try:
        values = json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON array: {exc.msg}") from exc
    if not isinstance(values, list) or len(values) != 9:
        raise ValueError("array must contain exactly 9 values")
    scores: list[float] = []
    for value in values:
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise ValueError("array must contain only numbers")
        score = float(value)
        if not 0.0 <= score <= 1.0:
            raise ValueError("scores must be between 0.0 and 1.0")
        scores.append(score)
    return scores


def load_results(path: str | Path) -> list[dict]:
    path = Path(path)
    records: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            records.append(json.loads(line))
    return records


def group_records(records: Iterable[dict]) -> dict[tuple[str, str], list[dict]]:
    groups: dict[tuple[str, str], list[dict]] = {}
    for record in records:
        key = (record["case_id"], record["prompt_name"])
        groups.setdefault(key, []).append(record)
    return groups


def compute_group_metrics(group: list[dict]) -> dict[str, float | int | None]:
    if not group:
        raise ValueError("group must not be empty")

    labels: list[int] = []
    n_valid = 0
    for record in group:
        try:
            scores = parse_score_array(record.get("raw_response") or "")
        except ValueError:
            continue
        n_valid += 1
        labels.append(max(range(len(scores)), key=lambda i: scores[i]))

    n_total = len(group)
    format_error_rate = (n_total - n_valid) / n_total

    if labels:
        mode_label = max(set(labels), key=labels.count)
        label_stability: float | None = labels.count(mode_label) / len(labels)
    else:
        label_stability = None

    avg_latency_ms = sum(r["latency_ms"] for r in group) / n_total
    avg_retry_count = sum(r["retry_count"] for r in group) / n_total

    return {
        "n": n_total,
        "format_error_rate": format_error_rate,
        "label_stability": label_stability,
        "avg_latency_ms": avg_latency_ms,
        "avg_retry_count": avg_retry_count,
    }


def aggregate_by_prompt(records: Iterable[dict]) -> dict[str, dict[str, float | int | None]]:
    groups = group_records(records)
    per_prompt: dict[str, list[dict]] = {}
    for (case_id, prompt_name), group in groups.items():
        metrics = compute_group_metrics(group)
        per_prompt.setdefault(prompt_name, []).append(metrics)

    aggregated: dict[str, dict[str, float | int | None]] = {}
    for prompt_name, metric_list in per_prompt.items():
        n_cases = len(metric_list)
        stabilities = [m["label_stability"] for m in metric_list if m["label_stability"] is not None]
        aggregated[prompt_name] = {
            "n_cases": n_cases,
            "avg_format_error_rate": sum(m["format_error_rate"] for m in metric_list) / n_cases,
            "avg_label_stability": (sum(stabilities) / len(stabilities)) if stabilities else None,
            "avg_latency_ms": sum(m["avg_latency_ms"] for m in metric_list) / n_cases,
            "avg_retry_count": sum(m["avg_retry_count"] for m in metric_list) / n_cases,
        }
    return aggregated


def write_stability_summary_csv(path: str | Path, aggregated: dict[str, dict]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDNAMES)
        writer.writeheader()
        for prompt_name, metrics in aggregated.items():
            writer.writerow({"prompt_name": prompt_name, **metrics})


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Calcula metricas de estabilidad de prompts")
    parser.add_argument("--results", required=True, help="Ruta a results.jsonl")
    parser.add_argument("--output", required=True, help="Ruta de salida stability_summary.csv")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    records = load_results(args.results)
    aggregated = aggregate_by_prompt(records)
    write_stability_summary_csv(args.output, aggregated)
    print(f"Resumen de estabilidad escrito en {args.output} ({len(aggregated)} prompts)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Ejecutar y confirmar que pasa**

Run: `uv run pytest tests/test_stability.py -v`
Expected: 9 pruebas en PASS.

- [ ] **Step 5: Commit**

```bash
git add src/evaluation/commercial/stability.py tests/test_stability.py
git commit -m "Agrega analisis de estabilidad y errores de formato de prompts"
```

---

### Task 6: Prueba de integración end-to-end (sin red) y ejemplo ilustrativo

**Files:**
- Create: `tests/test_pipeline_dry_run.py`
- Create: `scripts/generate_example_stability_artifacts.py`

**Interfaces:**
- Consumes: `load_gold_jsonl`, `load_prompts_json`, `write_results_jsonl` (`src.evaluation.commercial.io`), `run_evaluation` (`src.evaluation.commercial.runner`), `ProviderResponse` (`src.evaluation.commercial.schema`), `aggregate_by_prompt`, `write_stability_summary_csv` (`src.evaluation.commercial.stability`, Task 5).
- Produces: evidencia de que las Tareas 2-5 encajan correctamente de punta a punta; `artifacts/commercial_eval_example/stability_summary.csv` ilustrativo (no versionado, `artifacts/` está en `.gitignore`).

Esta tarea no agrega código de producción nuevo más allá del script de
ejemplo: valida que las piezas de las tareas anteriores se integran
correctamente. Si el test falla, el problema está en una tarea previa,
no en esta.

- [ ] **Step 1: Escribir la prueba de integración**

```python
# tests/test_pipeline_dry_run.py
from src.evaluation.commercial.io import load_gold_jsonl, load_prompts_json
from src.evaluation.commercial.runner import run_evaluation
from src.evaluation.commercial.schema import ProviderResponse
from src.evaluation.commercial.stability import aggregate_by_prompt, write_stability_summary_csv


class _FakeStableClient:
    provider = "fake"
    model = "fake-stable-v1"

    def generate(self, prompt: str) -> ProviderResponse:
        return ProviderResponse(text="[0.0,0.0,0.0,0.0,0.0,0.0,0.9,0.0,0.0]")


def test_full_pipeline_runs_without_network(tmp_path):
    cases = load_gold_jsonl("tests/fixtures/citation_function_pilot.jsonl")
    prompts = load_prompts_json("config/prompts/citation_function_prompts.json")

    repeated_cases = [case for case in cases for _ in range(5)]
    records = run_evaluation(repeated_cases, prompts, [_FakeStableClient()], max_retries=0)

    record_dicts = [r.to_dict() for r in records]
    aggregated = aggregate_by_prompt(record_dicts)

    summary_path = tmp_path / "stability_summary.csv"
    write_stability_summary_csv(summary_path, aggregated)

    assert summary_path.exists()
    assert set(aggregated.keys()) == {"zero_shot_generic", "zero_shot_detailed", "few_shot"}
    for metrics in aggregated.values():
        assert metrics["avg_format_error_rate"] == 0.0
        assert metrics["avg_label_stability"] == 1.0
```

- [ ] **Step 2: Ejecutar y confirmar que pasa**

Run: `uv run pytest tests/test_pipeline_dry_run.py -v`
Expected: PASS. Si falla, revisar la Tarea correspondiente (2, 3, 4 o 5) antes de seguir.

- [ ] **Step 3: Escribir el script de ejemplo ilustrativo**

```python
# scripts/generate_example_stability_artifacts.py
"""Genera un ejemplo ilustrativo de resultados de estabilidad.

Usa un cliente de ejemplo (NO un modelo real) unicamente para mostrar el
formato de salida esperado por docs/evaluacion_comercial.md. Los numeros
no representan ningun modelo real; la corrida real depende de la decision
pendiente descrita en la seccion 4 de
docs/superpowers/specs/2026-09-19-prompt-design-stability-design.md.
"""
from __future__ import annotations

from pathlib import Path

from src.evaluation.commercial.io import load_gold_jsonl, load_prompts_json, write_results_jsonl
from src.evaluation.commercial.runner import run_evaluation
from src.evaluation.commercial.schema import ProviderResponse
from src.evaluation.commercial.stability import aggregate_by_prompt, write_stability_summary_csv

OUTPUT_DIR = Path("artifacts/commercial_eval_example")


class ExampleClient:
    provider = "example"
    model = "example-not-a-real-model"

    def generate(self, prompt: str) -> ProviderResponse:
        return ProviderResponse(text="[0.0,0.0,0.0,0.0,0.0,0.0,0.9,0.0,0.0]")


def main() -> None:
    cases = load_gold_jsonl("tests/fixtures/citation_function_pilot.jsonl")
    prompts = load_prompts_json("config/prompts/citation_function_prompts.json")
    repeated_cases = [case for case in cases for _ in range(5)]

    records = run_evaluation(repeated_cases, prompts, [ExampleClient()], max_retries=0)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    write_results_jsonl(OUTPUT_DIR / "results.jsonl", records)

    aggregated = aggregate_by_prompt([r.to_dict() for r in records])
    write_stability_summary_csv(OUTPUT_DIR / "stability_summary.csv", aggregated)

    print(f"Ejemplo ilustrativo escrito en {OUTPUT_DIR} (NO son resultados de un modelo real)")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Ejecutar el script y revisar la salida**

```bash
uv run python scripts/generate_example_stability_artifacts.py
cat artifacts/commercial_eval_example/stability_summary.csv
```

Expected: un archivo CSV con 3 filas (una por prompt), útil para la Tarea 7. `artifacts/` está en `.gitignore`, así que este archivo no se commitea; el contenido se transcribe manualmente a la documentación en la Tarea 7.

- [ ] **Step 5: Commit**

```bash
git add tests/test_pipeline_dry_run.py scripts/generate_example_stability_artifacts.py
git commit -m "Agrega prueba de integracion end-to-end y script de ejemplo ilustrativo"
```

---

### Task 7: Documentación

**Files:**
- Modify: `docs/evaluacion_comercial.md` (agregar sección nueva al final).

- [ ] **Step 1: Agregar la sección al final de `docs/evaluacion_comercial.md`**

Anexar (después del contenido existente del documento, que ya cubre el
frente del issue #40):

```markdown
## Prompts y estabilidad — issue #43

Los tres prompts para clasificación de función de cita (9 categorías)
están versionados en `config/prompts/citation_function_prompts.json`:
`zero_shot_generic`, `zero_shot_detallado` y `few_shot`. El diseño
completo, incluidas las definiciones de las 9 categorías y el criterio de
estabilidad, está en
`docs/superpowers/specs/2026-09-19-prompt-design-stability-design.md`.

### Metodología de estabilidad

Cada combinación caso+prompt se ejecuta 5 veces contra el mismo modelo.
`src/evaluation/commercial/stability.py` agrupa las repeticiones y
calcula, por prompt:

- `avg_format_error_rate`: fracción de respuestas que no parsean como
  arreglo válido de 9 números entre 0.0 y 1.0.
- `avg_label_stability`: fracción de repeticiones cuyo argmax coincide
  con la moda del caso, promediada sobre todos los casos piloto.
- `avg_latency_ms`, `avg_retry_count`: agregados directos de la
  telemetría que ya registra el runner del issue #40.

### Ejemplo ilustrativo (no son resultados de un modelo real)

`scripts/generate_example_stability_artifacts.py` corre el pipeline
completo con un cliente de ejemplo que siempre responde con el mismo
arreglo válido, únicamente para mostrar el formato de salida esperado:

| prompt_name | n_cases | avg_format_error_rate | avg_label_stability | avg_latency_ms | avg_retry_count |
|---|---:|---:|---:|---:|---:|
| zero_shot_generic | 20 | 0.0 | 1.0 | (ver salida local) | 0.0 |
| zero_shot_detailed | 20 | 0.0 | 1.0 | (ver salida local) | 0.0 |
| few_shot | 20 | 0.0 | 1.0 | (ver salida local) | 0.0 |

### Decisión pendiente

No hay todavía un modelo de prueba configurado (ni Ollama local ni una
API comercial). Hasta que el equipo decida, `providers_local.py` lanza
`LocalProviderNotConfiguredError` en vez de intentar una llamada real.
Ver la sección 4 del spec para las opciones y sus trade-offs.

### Recomendación de prompt(s) finalista(s)

Pendiente: se completa una vez se resuelva la decisión anterior y se
corran las 5 repeticiones por caso contra un modelo real. El criterio de
selección es: menor `avg_format_error_rate`, y entre empates, mayor
`avg_label_stability`.
```

- [ ] **Step 2: Commit**

```bash
git add docs/evaluacion_comercial.md
git commit -m "Documenta prompts y metodologia de estabilidad del issue 43"
```

---

### Task 8: Verificación final y Pull Request

**Files:** ninguno nuevo; verificación de todo lo anterior.

- [ ] **Step 1: Ejecutar toda la suite del proyecto**

Run: `uv run pytest -q`
Expected: todas las pruebas en PASS, incluidas las 14 de #40 y las nuevas de #43.

- [ ] **Step 2: Revisar que no haya secretos ni artefactos accidentales**

```bash
git status
git diff --stat feature/20sep-commercial-eval-john...HEAD
```

Expected: el diff contiene únicamente los archivos de las Tareas 2-7 (prompts, script del piloto, fixture, cliente placeholder, estabilidad, prueba de integración, script de ejemplo, documentación). Ningún archivo bajo `artifacts/`, ninguna credencial.

- [ ] **Step 3: Push y Pull Request contra la rama de #40 (no contra `main`)**

```bash
git push -u origin feature/43-prompts-estabilidad
gh pr create \
  --repo Byron971/microproyecto-local-citation \
  --base feature/20sep-commercial-eval-john \
  --title "feat: prompts y estabilidad para clasificacion de funcion de cita (issue 43)" \
  --body "Avanza #43. Agrega los tres prompts versionados, el conjunto piloto reproducible sin etiquetas reales, el analisis de estabilidad y la decision de modelo pendiente documentada. Depende de #40 (PR #44)."
```

- [ ] **Step 4: Reflejar la contribución en el reporte de trabajo en equipo**

En `reportes/reporte03/main.tex`, ubicar la fila de "José Zambrana" en la
tabla de aportes (alrededor de la línea 758) y añadir al final del texto
de esa celda:

```latex
Diseño y versionado de los tres prompts de clasificación de función de
cita (zero-shot genérico, zero-shot detallado, few-shot); generador
reproducible del conjunto piloto; análisis de estabilidad y errores de
formato (issue \#43).
```

```bash
git add reportes/reporte03/main.tex
git commit -m "Actualiza el reporte de trabajo en equipo con el aporte del issue 43"
```

- [ ] **Step 5: Actualizar el issue #43 y avisar al equipo**

Comentar en el issue #43 (y opcionalmente en #40) que los prompts están
listos, con el enlace al PR, y que la decisión de modelo de prueba
(sección 4 del spec) sigue pendiente y bloquea las corridas reales de
#40/#41/#42.
