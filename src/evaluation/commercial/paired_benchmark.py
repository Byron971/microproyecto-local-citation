"""Benchmark pareado para NUEVO Gold: modo provisional hasta certificarlo.

No ejecuta inferencia ni accede a proveedores. Compara predicciones de dos
configuraciones sobre IDENTICOS ejemplos. Rechaza abstenciones o faltantes
para no inflar F1 filtrando casos difíciles. Nunca certifica anotación humana.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

from sklearn.metrics import (
    accuracy_score, confusion_matrix, precision_recall_fscore_support,
)

from .gold_policy import inspect_gold
from .metrics import CATEGORIES, gold_to_index
from .schema import EvaluationCase


def read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    path = Path(path)
    rows: list[dict[str, Any]] = []
    for n, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path.name}, línea {n}: JSON inválido") from exc
        if not isinstance(row, dict):
            raise ValueError(f"{path.name}, línea {n}: se esperaba objeto")
        rows.append(row)
    if not rows:
        raise ValueError(f"{path.name}: archivo vacío")
    return rows


def _nonblank(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Campo obligatorio inválido: {field}")
    return value.strip()


def index_gold(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Exige etiqueta única y procedencia documental para comparaciones."""
    indexed: dict[str, dict[str, Any]] = {}
    for row in rows:
        cid = _nonblank(row.get("id"), "id")
        if cid in indexed:
            raise ValueError(f"Gold: ID duplicado {cid}")
        source = _nonblank(row.get("citing_id"), f"{cid}.citing_id")
        cited = _nonblank(row.get("cited_id"), f"{cid}.cited_id")
        context = _nonblank(row.get("input"), f"{cid}.input")
        if context.count("TARGETCIT") != 1:
            raise ValueError(f"Gold: TARGETCIT debe aparecer exactamente una vez: {cid}")
        label = gold_to_index(row.get("gold"))
        if label is None:
            raise ValueError(f"Gold: etiqueta ausente: {cid}")
        indexed[cid] = {"gold": label, "citing_id": source, "cited_id": cited}
    return indexed


def index_predictions(
    rows: list[dict[str, Any]], expected: set[str], variant: str,
) -> dict[str, int]:
    indexed: dict[str, int] = {}
    for row in rows:
        cid = _nonblank(row.get("case_id"), f"{variant}.case_id")
        if cid in indexed:
            raise ValueError(f"{variant}: ID duplicado {cid}")
        if row.get("status") != "ok":
            raise ValueError(f"{variant}: predicción incompleta en {cid}: {row.get('status')}")
        raw = row.get("pred_label", row.get("pred_index"))
        pred = gold_to_index(raw)
        if pred is None:
            raise ValueError(f"{variant}: predicción vacía en {cid}")
        if "pred_label" in row and "pred_index" in row:
            second = gold_to_index(row["pred_index"])
            if second != pred:
                raise ValueError(f"{variant}: índice y etiqueta discrepan en {cid}")
        indexed[cid] = pred
    missing = expected - set(indexed)
    extra = set(indexed) - expected
    if missing or extra:
        raise ValueError(
            f"{variant}: IDs no comparables (faltantes={len(missing)}, extras={len(extra)})"
        )
    return indexed


def model_metrics(truth: list[int], predictions: list[int]) -> dict[str, Any]:
    labels = list(range(len(CATEGORIES)))
    p, r, f1, support = precision_recall_fscore_support(
        truth, predictions, labels=labels, average=None, zero_division=0
    )
    p_macro, r_macro, f_macro, _ = precision_recall_fscore_support(
        truth, predictions, labels=labels, average="macro", zero_division=0
    )
    p_micro, r_micro, f_micro, _ = precision_recall_fscore_support(
        truth, predictions, labels=labels, average="micro", zero_division=0
    )
    p_weighted, r_weighted, f_weighted, _ = precision_recall_fscore_support(
        truth, predictions, labels=labels, average="weighted", zero_division=0
    )
    matrix = confusion_matrix(truth, predictions, labels=labels).tolist()
    return {
        "n": len(truth),
        "accuracy": float(accuracy_score(truth, predictions)),
        "precision_macro": float(p_macro),
        "recall_macro": float(r_macro),
        "f1_macro": float(f_macro),
        "precision_micro": float(p_micro),
        "recall_micro": float(r_micro),
        "f1_micro": float(f_micro),
        "precision_weighted": float(p_weighted),
        "recall_weighted": float(r_weighted),
        "f1_weighted": float(f_weighted),
        "per_class": [
            {
                "label": CATEGORIES[i], "support": int(support[i]),
                "precision": float(p[i]), "recall": float(r[i]), "f1": float(f1[i]),
            }
            for i in labels
        ],
        "confusion_matrix": matrix,
    }


def compare(
    gold_rows: list[dict[str, Any]],
    rows_a: list[dict[str, Any]],
    rows_b: list[dict[str, Any]],
    *,
    factor: str,
    name_a: str,
    name_b: str,
) -> dict[str, Any]:
    if factor not in {"input", "training_labels"}:
        raise ValueError("Factor debe ser input o training_labels")
    name_a = _nonblank(name_a, "name_a")
    name_b = _nonblank(name_b, "name_b")
    if name_a == name_b:
        raise ValueError("Nombres de variantes deben ser diferentes")
    gold = index_gold(gold_rows)
    ids = sorted(gold)
    a = index_predictions(rows_a, set(gold), name_a)
    b = index_predictions(rows_b, set(gold), name_b)
    y = [gold[c]["gold"] for c in ids]
    pa, pb = [a[c] for c in ids], [b[c] for c in ids]
    ma, mb = model_metrics(y, pa), model_metrics(y, pb)
    a_only = sum(a[c] == gold[c]["gold"] and b[c] != gold[c]["gold"] for c in ids)
    b_only = sum(b[c] == gold[c]["gold"] and a[c] != gold[c]["gold"] for c in ids)
    return {
        "status": "PROVISIONAL_NO_CERTIFICADO",
        "factor": factor,
        "variants": {name_a: ma, name_b: mb},
        "n_same_gold": len(ids),
        "coverage_a": 1.0,
        "coverage_b": 1.0,
        "delta_f1_macro_b_minus_a": mb["f1_macro"] - ma["f1_macro"],
        "paired_cases": {
            "same_prediction": sum(a[c] == b[c] for c in ids),
            "a_only_correct": a_only,
            "b_only_correct": b_only,
            "both_correct": sum(a[c] == b[c] == gold[c]["gold"] for c in ids),
            "both_wrong": sum(a[c] != gold[c]["gold"] and b[c] != gold[c]["gold"] for c in ids),
        },
        "errors": [
            {
                "id": c, "citing_id": gold[c]["citing_id"],
                "gold_label": CATEGORIES[gold[c]["gold"]],
                name_a: CATEGORIES[a[c]], name_b: CATEGORIES[b[c]],
            }
            for c in ids if a[c] != gold[c]["gold"] or b[c] != gold[c]["gold"]
        ],
    }


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Comparador pareado de función de cita (solo provisional)")
    p.add_argument("--gold", type=Path, required=True)
    p.add_argument("--predictions-a", type=Path, required=True)
    p.add_argument("--predictions-b", type=Path, required=True)
    p.add_argument("--name-a", required=True)
    p.add_argument("--name-b", required=True)
    p.add_argument("--factor", required=True, choices=["input", "training_labels"])
    p.add_argument("--raw-dir", type=Path, required=True, help="ACL-200 en DVC para control split test")
    p.add_argument("--output-dir", type=Path, required=True)
    p.add_argument("--provisional", action="store_true", help="Reconoce explícitamente que Gold no está certificado")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if not args.provisional:
            raise ValueError(
                "Evaluación final bloqueada: aún no existe certificación del Gold. "
                "Use --provisional solo para desarrollo."
            )
        gold_rows = read_jsonl(args.gold)
        cases = [
            EvaluationCase(
                id=_nonblank(row.get("id"), "id"),
                input=_nonblank(row.get("input"), "input"),
                gold=row.get("gold"),
                metadata={k: row[k] for k in ("citing_id", "cited_id") if k in row},
            ) for row in gold_rows
        ]
        audit = inspect_gold(args.gold, cases, raw_dir=args.raw_dir)
        # El modo provisional NO salta la integridad: ni los splits ni las
        # exclusiones pueden estar dañados. La anotación sigue sin certificar.
        if audit.reasons:
            raise ValueError("Auditoría Gold bloqueada: " + "; ".join(audit.reasons))
        result = compare(
            gold_rows, read_jsonl(args.predictions_a), read_jsonl(args.predictions_b),
            factor=args.factor, name_a=args.name_a, name_b=args.name_b,
        )
        result["manifest"] = {
            "gold_sha256": sha256_file(args.gold),
            "predictions_a_sha256": sha256_file(args.predictions_a),
            "predictions_b_sha256": sha256_file(args.predictions_b),
            "raw_dir": str(args.raw_dir),
            "human_gold_certified": False,
            "note": "La auditoría de esquema/split NO prueba doble anotación ni adjudicación humana.",
        }
        args.output_dir.mkdir(parents=True, exist_ok=True)
        (args.output_dir / "paired_summary_provisional.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        for variant, metrics in result["variants"].items():
            name = "a" if variant == args.name_a else "b"
            with (args.output_dir / f"per_class_{name}.csv").open("w", encoding="utf-8", newline="") as f:
                w = csv.DictWriter(f, fieldnames=["label", "support", "precision", "recall", "f1"])
                w.writeheader()
                w.writerows(metrics["per_class"])
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"Benchmark bloqueado: {exc}", file=sys.stderr)
        return 2
    print(f"Benchmark PROVISIONAL (N={result['n_same_gold']}) → {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
