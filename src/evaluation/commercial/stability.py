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
    "provider",
    "model",
    "n_cases",
    "n_cases_with_format_data",
    "n_cases_with_valid_responses",
    "avg_format_error_rate",
    "avg_label_stability",
    "provider_error_rate",
    "avg_latency_ms",
    "avg_retry_count",
]


def _validate_score_array(raw: str) -> list[float]:
    try:
        values = json.loads(raw)
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


def parse_score_array(text: str) -> list[float]:
    """Extrae el arreglo de 9 puntajes de una respuesta de modelo.

    Un prompt (zero_shot_generic) termina con un ejemplo de formato como
    `[0.0, 0.0, ..., 0.0]`. Si el modelo repite ese texto de instruccion
    antes de su respuesta real, la PRIMERA coincidencia de `[...]` seria
    ese arreglo de ejemplo (valido pero irrelevante). Por eso se revisan
    todas las coincidencias y se conserva la ULTIMA que valide como
    arreglo de 9 numeros en rango, asumiendo que la respuesta real del
    modelo aparece despues de cualquier texto de instruccion repetido.
    """
    if not text:
        raise ValueError("empty response")
    matches = list(_ARRAY_PATTERN.finditer(text))
    if not matches:
        raise ValueError("no JSON array found in response")

    result: list[float] | None = None
    last_error: ValueError = ValueError("no valid array found in response")
    for match in matches:
        try:
            result = _validate_score_array(match.group(0))
        except ValueError as exc:
            last_error = exc
    if result is None:
        raise last_error
    return result


def load_results(path: str | Path) -> list[dict]:
    path = Path(path)
    records: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            records.append(json.loads(line))
    return records


def group_records(records: Iterable[dict]) -> dict[tuple[str, str, str, str], list[dict]]:
    """Agrupa repeticiones por caso+prompt+proveedor+modelo.

    `runner.py` permite pasar varios `clients` en una sola corrida, asi
    que un mismo `results.jsonl` puede legitimamente mezclar filas de mas
    de un modelo. Agrupar sin incluir provider/model mezclaria
    repeticiones de modelos distintos en un mismo grupo de estabilidad.
    """
    groups: dict[tuple[str, str, str, str], list[dict]] = {}
    for record in records:
        key = (record["case_id"], record["prompt_name"], record["provider"], record["model"])
        groups.setdefault(key, []).append(record)
    return groups


def compute_group_metrics(group: list[dict]) -> dict[str, float | int | None]:
    if not group:
        raise ValueError("group must not be empty")

    n_total = len(group)
    n_provider_error = 0
    n_considered = 0
    n_valid = 0
    labels: list[int] = []
    for record in group:
        if record.get("status") == "provider_error":
            n_provider_error += 1
            continue
        n_considered += 1
        try:
            scores = parse_score_array(record.get("raw_response") or "")
        except ValueError:
            continue
        n_valid += 1
        labels.append(max(range(len(scores)), key=lambda i: scores[i]))

    # Los errores de proveedor (p.ej. timeout tras agotar reintentos) son
    # fallas de infraestructura, no de formato del prompt: se excluyen del
    # numerador y del denominador de format_error_rate para no corromper
    # la comparacion de prompts. Si un grupo es enteramente errores de
    # proveedor no hay nada que evaluar en formato: format_error_rate queda
    # en None (no 0.0) para que aggregate_by_prompt lo excluya del promedio,
    # igual que ya hace con label_stability. Promediar un 0.0 falso ahi
    # sesgaria avg_format_error_rate a favor de un prompt que simplemente
    # tuvo mala suerte de infraestructura, no buen formato.
    format_error_rate: float | None
    format_error_rate = (n_considered - n_valid) / n_considered if n_considered else None

    if labels:
        mode_label = max(set(labels), key=labels.count)
        label_stability: float | None = labels.count(mode_label) / len(labels)
    else:
        label_stability = None

    provider_error_rate = n_provider_error / n_total
    avg_latency_ms = sum(r["latency_ms"] for r in group) / n_total
    avg_retry_count = sum(r["retry_count"] for r in group) / n_total

    return {
        "n": n_total,
        "format_error_rate": format_error_rate,
        "label_stability": label_stability,
        "provider_error_rate": provider_error_rate,
        "avg_latency_ms": avg_latency_ms,
        "avg_retry_count": avg_retry_count,
    }


def aggregate_by_prompt(
    records: Iterable[dict],
) -> dict[tuple[str, str, str], dict[str, float | int | None]]:
    groups = group_records(records)
    per_prompt: dict[tuple[str, str, str], list[dict]] = {}
    for (case_id, prompt_name, provider, model), group in groups.items():
        metrics = compute_group_metrics(group)
        per_prompt.setdefault((prompt_name, provider, model), []).append(metrics)

    aggregated: dict[tuple[str, str, str], dict[str, float | int | None]] = {}
    for key, metric_list in per_prompt.items():
        n_cases = len(metric_list)
        # avg_format_error_rate y avg_label_stability excluyen los casos sin
        # datos relevantes en vez de rellenarlos con 0.0: un caso enteramente
        # de errores de proveedor no dice nada sobre el formato del prompt, y
        # un caso sin ninguna respuesta parseable no dice nada sobre
        # estabilidad de etiqueta. Promediarlos como 0.0/None inflaria el
        # resultado a favor de un prompt con mala suerte de infraestructura.
        format_error_rates = [m["format_error_rate"] for m in metric_list if m["format_error_rate"] is not None]
        stabilities = [m["label_stability"] for m in metric_list if m["label_stability"] is not None]
        n_cases_with_valid_responses = len(stabilities)
        aggregated[key] = {
            "n_cases": n_cases,
            "n_cases_with_format_data": len(format_error_rates),
            "n_cases_with_valid_responses": n_cases_with_valid_responses,
            "avg_format_error_rate": (
                sum(format_error_rates) / len(format_error_rates) if format_error_rates else None
            ),
            "avg_label_stability": (sum(stabilities) / len(stabilities)) if stabilities else None,
            "provider_error_rate": sum(m["provider_error_rate"] for m in metric_list) / n_cases,
            "avg_latency_ms": sum(m["avg_latency_ms"] for m in metric_list) / n_cases,
            "avg_retry_count": sum(m["avg_retry_count"] for m in metric_list) / n_cases,
        }
    return aggregated


def write_stability_summary_csv(
    path: str | Path, aggregated: dict[tuple[str, str, str], dict]
) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        # extrasaction="ignore": endurecimiento defensivo barato, por si
        # algun dia se pasa directo el dict crudo de compute_group_metrics
        # (que trae la clave interna "n", ausente de FIELDNAMES).
        writer = csv.DictWriter(fh, fieldnames=FIELDNAMES, extrasaction="ignore")
        writer.writeheader()
        for (prompt_name, provider, model), metrics in aggregated.items():
            writer.writerow(
                {"prompt_name": prompt_name, "provider": provider, "model": model, **metrics}
            )


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
