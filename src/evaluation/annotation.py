from __future__ import annotations

import argparse
import csv
import json
import random
from pathlib import Path
from typing import Any

from sklearn.metrics import cohen_kappa_score

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

ALIASES = {category.casefold(): category for category in CATEGORIES}
ALIASES.update(
    {
        "improvement/modification": "Improvement / Modification",
        "improvement": "Improvement / Modification",
        "modification": "Improvement / Modification",
        "originator": "Identification of the Originator",
        "identification of originator": "Identification of the Originator",
    }
)


def normalize_label(value: str) -> str:
    normalized = " ".join(value.strip().casefold().split())
    if not normalized:
        raise ValueError("empty label")
    if normalized not in ALIASES:
        raise ValueError(f"unknown label: {value!r}")
    return ALIASES[normalized]


def load_source_jsonl(path: str | Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for line_number, line in enumerate(
        Path(path).read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not line.strip():
            continue
        payload = json.loads(line)
        if not isinstance(payload, dict) or "id" not in payload or "input" not in payload:
            raise ValueError(f"invalid source row {line_number}")
        case_id = str(payload["id"])
        if case_id in seen:
            raise ValueError(f"duplicate id: {case_id}")
        seen.add(case_id)
        rows.append(payload)
    if not rows:
        raise ValueError("source is empty")
    return rows


def write_annotation_sheet(
    path: str | Path,
    rows: list[dict[str, Any]],
    seed: int,
) -> None:
    ordered = list(rows)
    random.Random(seed).shuffle(ordered)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["id", "input", "label"])
        writer.writeheader()
        for row in ordered:
            writer.writerow({"id": row["id"], "input": row["input"], "label": ""})


def prepare_sheets(
    source: str | Path,
    output_dir: str | Path,
    seed: int = 42,
) -> tuple[Path, Path]:
    rows = load_source_jsonl(source)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    annotator_a = output_dir / "annotator_a.csv"
    annotator_b = output_dir / "annotator_b.csv"
    write_annotation_sheet(annotator_a, rows, seed)
    write_annotation_sheet(annotator_b, rows, seed + 1)
    return annotator_a, annotator_b


def load_annotations(path: str | Path) -> dict[str, str]:
    labels: dict[str, str] = {}
    with Path(path).open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            case_id = (row.get("id") or "").strip()
            raw_label = (row.get("label") or "").strip()
            if not case_id:
                raise ValueError("annotation row without id")
            if not raw_label:
                continue
            if case_id in labels:
                raise ValueError(f"duplicate annotation id: {case_id}")
            labels[case_id] = normalize_label(raw_label)
    return labels


def compute_agreement(
    source: str | Path,
    annotator_a: str | Path,
    annotator_b: str | Path,
) -> tuple[dict[str, Any], dict[str, str], dict[str, str], list[str], list[str]]:
    source_rows = load_source_jsonl(source)
    ids = [str(row["id"]) for row in source_rows]
    labels_a = load_annotations(annotator_a)
    labels_b = load_annotations(annotator_b)

    common = [case_id for case_id in ids if case_id in labels_a and case_id in labels_b]
    agreed = [case_id for case_id in common if labels_a[case_id] == labels_b[case_id]]
    disagreements = [
        case_id for case_id in common if labels_a[case_id] != labels_b[case_id]
    ]

    kappa = (
        float(
            cohen_kappa_score(
                [labels_a[case_id] for case_id in common],
                [labels_b[case_id] for case_id in common],
                labels=list(CATEGORIES),
            )
        )
        if common
        else None
    )

    summary = {
        "n_source": len(ids),
        "n_annotator_a": len(labels_a),
        "n_annotator_b": len(labels_b),
        "n_common": len(common),
        "n_agreements": len(agreed),
        "n_disagreements": len(disagreements),
        "agreement_rate": len(agreed) / len(common) if common else None,
        "cohen_kappa": kappa,
    }
    return summary, labels_a, labels_b, agreed, disagreements


def write_agreement_artifacts(
    source: str | Path,
    annotator_a: str | Path,
    annotator_b: str | Path,
    output_dir: str | Path,
) -> dict[str, Any]:
    summary, labels_a, labels_b, _, disagreements = compute_agreement(
        source, annotator_a, annotator_b
    )
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    (output_dir / "agreement_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    with (output_dir / "disagreements.csv").open(
        "w", encoding="utf-8", newline=""
    ) as fh:
        writer = csv.DictWriter(
            fh, fieldnames=["id", "annotator_a", "annotator_b"]
        )
        writer.writeheader()
        for case_id in disagreements:
            writer.writerow(
                {
                    "id": case_id,
                    "annotator_a": labels_a[case_id],
                    "annotator_b": labels_b[case_id],
                }
            )

    ids = [str(row["id"]) for row in load_source_jsonl(source)]
    with (output_dir / "reconciliation.csv").open(
        "w", encoding="utf-8", newline=""
    ) as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=["id", "annotator_a", "annotator_b", "final_label"],
        )
        writer.writeheader()
        for case_id in ids:
            label_a = labels_a.get(case_id, "")
            label_b = labels_b.get(case_id, "")
            final_label = label_a if label_a and label_a == label_b else ""
            writer.writerow(
                {
                    "id": case_id,
                    "annotator_a": label_a,
                    "annotator_b": label_b,
                    "final_label": final_label,
                }
            )

    return summary


def finalize_gold(
    source: str | Path,
    reconciliation: str | Path,
    output: str | Path,
) -> int:
    final_labels: dict[str, str] = {}
    with Path(reconciliation).open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            case_id = (row.get("id") or "").strip()
            raw_label = (row.get("final_label") or "").strip()
            if raw_label:
                final_labels[case_id] = normalize_label(raw_label)

    source_rows = load_source_jsonl(source)
    missing = [
        str(row["id"])
        for row in source_rows
        if str(row["id"]) not in final_labels
    ]
    if missing:
        raise ValueError(f"missing final labels for {len(missing)} cases")

    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as fh:
        for row in source_rows:
            payload = dict(row)
            payload["gold"] = final_labels[str(row["id"])]
            fh.write(
                json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n"
            )
    return len(source_rows)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Prepara, compara y consolida anotaciones humanas"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare = subparsers.add_parser("prepare")
    prepare.add_argument("--source", required=True)
    prepare.add_argument("--output-dir", required=True)
    prepare.add_argument("--seed", type=int, default=42)

    agreement = subparsers.add_parser("agreement")
    agreement.add_argument("--source", required=True)
    agreement.add_argument("--annotator-a", required=True)
    agreement.add_argument("--annotator-b", required=True)
    agreement.add_argument("--output-dir", required=True)

    finalize = subparsers.add_parser("finalize")
    finalize.add_argument("--source", required=True)
    finalize.add_argument("--reconciliation", required=True)
    finalize.add_argument("--output", required=True)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "prepare":
            annotator_a, annotator_b = prepare_sheets(
                args.source, args.output_dir, args.seed
            )
            print(f"Hojas creadas: {annotator_a} y {annotator_b}")
        elif args.command == "agreement":
            summary = write_agreement_artifacts(
                args.source,
                args.annotator_a,
                args.annotator_b,
                args.output_dir,
            )
            print(json.dumps(summary, indent=2, ensure_ascii=False))
        else:
            count = finalize_gold(
                args.source, args.reconciliation, args.output
            )
            print(f"Test Gold escrito en {args.output}: {count} casos")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Error de anotación: {exc}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
