from __future__ import annotations

import argparse
import csv
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

from sklearn.metrics import accuracy_score, confusion_matrix, precision_recall_fscore_support

from .stability import parse_score_array

CATEGORIES = (
    "Background",
    "Gap",
    "Basis",
    "Comparison",
    "Application",
    "Improvement / Modification",
    "Evidence",
    "Identification of the Originator",
    "Further Reading",
)

_ALIASES = {
    "background": 0,
    "gap": 1,
    "basis": 2,
    "comparison": 3,
    "application": 4,
    "improvement / modification": 5,
    "improvement/modification": 5,
    "improvement": 5,
    "modification": 5,
    "evidence": 6,
    "identification of the originator": 7,
    "identification of originator": 7,
    "originator": 7,
    "further reading": 8,
}


def _validate_scores(values: Any) -> list[float]:
    if not isinstance(values, (list, tuple)) or len(values) != 9:
        raise ValueError("score vector must contain exactly 9 values")
    scores: list[float] = []
    for value in values:
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise ValueError("score vector must contain only numbers")
        score = float(value)
        if not 0.0 <= score <= 1.0:
            raise ValueError("score values must be between 0.0 and 1.0")
        scores.append(score)
    return scores


def gold_to_index(gold: Any) -> int | None:
    """Normaliza una etiqueta gold de clase única al índice 0..8.

    Admite el nombre de la categoría, un índice entero o un vector de nueve
    puntajes con máximo único. None se conserva para conjuntos piloto que
    todavía no tienen validación humana.
    """
    if gold is None:
        return None
    if isinstance(gold, bool):
        raise ValueError("boolean is not a valid gold label")
    if isinstance(gold, int):
        if 0 <= gold < len(CATEGORIES):
            return gold
        raise ValueError(f"gold index out of range: {gold}")
    if isinstance(gold, str):
        normalized = " ".join(gold.strip().casefold().split())
        if normalized in _ALIASES:
            return _ALIASES[normalized]
        raise ValueError(f"unknown gold label: {gold!r}")
    if isinstance(gold, (list, tuple)):
        scores = _validate_scores(gold)
        best = max(scores)
        winners = [i for i, score in enumerate(scores) if score == best]
        if len(winners) != 1:
            raise ValueError("gold score vector must have a unique maximum")
        return winners[0]
    raise ValueError(f"unsupported gold label type: {type(gold).__name__}")


def _scores_from_record(record: dict[str, Any]) -> list[float]:
    parsed = record.get("parsed_output")
    if isinstance(parsed, (list, tuple)):
        return _validate_scores(parsed)
    return parse_score_array(record.get("raw_response") or "")


def _group_key(record: dict[str, Any]) -> tuple[str, str, str]:
    return (str(record["prompt_name"]), str(record["provider"]), str(record["model"]))


def _safe_slug(parts: Iterable[str]) -> str:
    raw = "__".join(parts)
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", raw).strip("-._")
    return slug or "group"


def evaluate_records(
    records: Iterable[dict[str, Any]],
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    dict[tuple[str, str, str], list[list[int]]],
]:
    """Calcula métricas comparables por prompt/proveedor/modelo.

    Si hay varias repeticiones del mismo caso, promedia los vectores válidos
    antes de tomar argmax. Las respuestas no parseables y errores de proveedor
    se reportan por separado y no se convierten artificialmente en una clase.
    """
    records = list(records)
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        grouped[_group_key(record)].append(record)

    summaries: list[dict[str, Any]] = []
    predictions: list[dict[str, Any]] = []
    matrices: dict[tuple[str, str, str], list[list[int]]] = {}

    for key in sorted(grouped):
        prompt_name, provider, model = key
        group = grouped[key]
        by_case: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for record in group:
            by_case[str(record["case_id"])].append(record)

        y_true: list[int] = []
        y_pred: list[int] = []
        provider_errors = sum(r.get("status") == "provider_error" for r in group)
        non_provider_runs = len(group) - provider_errors
        format_errors = 0
        latencies = [float(r.get("latency_ms") or 0.0) for r in group]
        retries = [int(r.get("retry_count") or 0) for r in group]
        total_input_tokens = sum(int(r.get("input_tokens") or 0) for r in group)
        total_output_tokens = sum(int(r.get("output_tokens") or 0) for r in group)
        costs = [
            r.get("estimated_cost_usd")
            for r in group
            if r.get("estimated_cost_usd") is not None
        ]

        n_labeled_cases = 0
        for case_id in sorted(by_case):
            case_records = by_case[case_id]
            gold_indices = {
                gold_to_index(r.get("gold"))
                for r in case_records
                if r.get("gold") is not None
            }
            if len(gold_indices) > 1:
                raise ValueError(
                    f"inconsistent gold labels for case {case_id}: {sorted(gold_indices)}"
                )
            gold_index = next(iter(gold_indices), None)
            if gold_index is not None:
                n_labeled_cases += 1

            valid_scores: list[list[float]] = []
            for record in case_records:
                if record.get("status") == "provider_error":
                    continue
                try:
                    valid_scores.append(_scores_from_record(record))
                except ValueError:
                    format_errors += 1

            pred_index: int | None = None
            mean_scores: list[float] | None = None
            if valid_scores:
                mean_scores = [
                    sum(values) / len(values) for values in zip(*valid_scores)
                ]
                pred_index = max(range(len(mean_scores)), key=mean_scores.__getitem__)
                if gold_index is not None:
                    y_true.append(gold_index)
                    y_pred.append(pred_index)

            row: dict[str, Any] = {
                "prompt_name": prompt_name,
                "provider": provider,
                "model": model,
                "case_id": case_id,
                "gold_index": gold_index,
                "gold_label": CATEGORIES[gold_index] if gold_index is not None else None,
                "pred_index": pred_index,
                "pred_label": CATEGORIES[pred_index] if pred_index is not None else None,
                "n_total_runs": len(case_records),
                "n_valid_runs": len(valid_scores),
            }
            for idx, category in enumerate(CATEGORIES):
                row[f"score_{idx}"] = (
                    mean_scores[idx] if mean_scores is not None else None
                )
                row[f"category_{idx}"] = category
            predictions.append(row)

        if y_true:
            labels_for_macro = sorted(set(y_true))
            p_macro, r_macro, f_macro, _ = precision_recall_fscore_support(
                y_true,
                y_pred,
                labels=labels_for_macro,
                average="macro",
                zero_division=0,
            )
            p_micro, r_micro, f_micro, _ = precision_recall_fscore_support(
                y_true, y_pred, average="micro", zero_division=0
            )
            acc = accuracy_score(y_true, y_pred)
            matrix = confusion_matrix(
                y_true, y_pred, labels=list(range(len(CATEGORIES)))
            ).tolist()
        else:
            p_macro = r_macro = f_macro = None
            p_micro = r_micro = f_micro = None
            acc = None
            matrix = [[0 for _ in CATEGORIES] for _ in CATEGORIES]

        matrices[key] = matrix
        summaries.append(
            {
                "prompt_name": prompt_name,
                "provider": provider,
                "model": model,
                "n_cases": len(by_case),
                "n_labeled_cases": n_labeled_cases,
                "n_scored_labeled_cases": len(y_true),
                "classification_coverage": (
                    len(y_true) / n_labeled_cases if n_labeled_cases else None
                ),
                "n_gold_classes": len(set(y_true)),
                "n_runs": len(group),
                "provider_error_runs": provider_errors,
                "format_error_runs": format_errors,
                "provider_error_rate": (
                    provider_errors / len(group) if group else None
                ),
                "format_error_rate": (
                    format_errors / non_provider_runs if non_provider_runs else None
                ),
                "precision_macro": p_macro,
                "recall_macro": r_macro,
                "f1_macro": f_macro,
                "precision_micro": p_micro,
                "recall_micro": r_micro,
                "f1_micro": f_micro,
                "accuracy": acc,
                "avg_latency_ms": (
                    sum(latencies) / len(latencies) if latencies else None
                ),
                "avg_retry_count": (
                    sum(retries) / len(retries) if retries else None
                ),
                "total_input_tokens": total_input_tokens,
                "total_output_tokens": total_output_tokens,
                "total_estimated_cost_usd": (
                    sum(float(c) for c in costs) if costs else None
                ),
            }
        )

    return summaries, predictions, matrices


def load_results(path: str | Path) -> list[dict[str, Any]]:
    path = Path(path)
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"invalid JSON on line {line_number}: {exc.msg}"
            ) from exc
        if not isinstance(payload, dict):
            raise ValueError(f"line {line_number} must contain a JSON object")
        records.append(payload)
    if not records:
        raise ValueError("results file is empty")
    return records


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        raise ValueError("cannot write empty CSV")
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_evaluation_artifacts(
    output_dir: str | Path,
    summaries: list[dict[str, Any]],
    predictions: list[dict[str, Any]],
    matrices: dict[tuple[str, str, str], list[list[int]]],
) -> None:
    output_dir = Path(output_dir)
    _write_csv(output_dir / "evaluation_summary.csv", summaries)
    _write_csv(output_dir / "predictions.csv", predictions)

    confusion_dir = output_dir / "confusion_matrices"
    confusion_dir.mkdir(parents=True, exist_ok=True)
    for key, matrix in matrices.items():
        path = confusion_dir / f"{_safe_slug(key)}.csv"
        with path.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.writer(fh)
            writer.writerow(["gold\\pred", *CATEGORIES])
            for label, row in zip(CATEGORIES, matrix):
                writer.writerow([label, *row])


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Calcula Precision/Recall/F1 y matrices de confusión"
    )
    parser.add_argument("--results", required=True, help="Ruta a results.jsonl")
    parser.add_argument(
        "--output-dir", required=True, help="Directorio de artefactos de evaluación"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        records = load_results(args.results)
        summaries, predictions, matrices = evaluate_records(records)
        write_evaluation_artifacts(
            args.output_dir, summaries, predictions, matrices
        )
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"Error de evaluación: {exc}")
        return 2

    print(
        f"Métricas escritas en {args.output_dir} "
        f"({len(summaries)} combinaciones modelo/prompt)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
