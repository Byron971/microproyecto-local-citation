"""Auditoría previa a congelación del Test Gold, sin certificación automática.

Compara anotaciones humanas independientes, adjudicaciones, cobertura real y
aislamiento de particiones. Nunca publica texto Gold ni declara que hubo
revisión humana genuina: esa certificación la hace el equipo con evidencia.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any, Iterable

from .gold_policy import REPO_ROOT, inspect_gold
from .metrics import CATEGORIES, gold_to_index
from .paired_benchmark import index_gold, read_jsonl
from .schema import EvaluationCase


def _required(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Campo obligatorio ausente: {field}")
    return value.strip()


def _label(value: Any, where: str) -> int:
    # El Gold final debe tener UNA clase explícita, no probabilidades de un juez.
    if not isinstance(value, (str, int)) or isinstance(value, bool):
        raise ValueError(f"{where}: se requiere una de nueve etiquetas/índices")
    idx = gold_to_index(value)
    if idx is None:
        raise ValueError(f"{where}: etiqueta ausente")
    return idx


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_dataset_ids(path: Path) -> set[str]:
    result: set[str] = set()
    for n, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        cid = _required(line, f"{path.name}:{n}")
        if cid in result:
            raise ValueError(f"Dataset: ID duplicado {cid}")
        result.add(cid)
    if not result:
        raise ValueError("Dataset: manifiesto de IDs vacío")
    return result


def _normal_text(value: str) -> str:
    return " ".join(re.findall(r"\w+", value.casefold()))


def _load_training(rows: list[dict[str, Any]], name: str, expected_split: str,
                   split_index: Any, blockers: list[str]) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    for row in rows:
        cid = _required(row.get("id"), f"{name}.id")
        citing = _required(row.get("citing_id"), f"{name}[{cid}].citing_id")
        cited = _required(row.get("cited_id"), f"{name}[{cid}].cited_id")
        body = _required(row.get("input"), f"{name}[{cid}].input")
        if cid in result:
            blockers.append(f"{name}: ID repetido {cid}")
            continue
        result[cid] = {"citing_id": citing, "cited_id": cited, "input": body}
        if split_index.by_context.get(cid) != expected_split:
            blockers.append(f"{name}: {cid} no está en la partición ACL-200 {expected_split}")
        original = split_index.contexts.get(cid, {})
        if original.get("citing_id") != citing or original.get("refid") != cited:
            blockers.append(f"{name}: {cid} tiene par documental incoherente con ACL-200")
        if original.get("masked_text") != body:
            blockers.append(f"{name}: {cid} tiene contexto distinto del corpus ACL-200")
    return result


def _annotation_checks(
    gold: dict[str, dict[str, Any]],
    reviews: list[dict[str, Any]],
    adjudications: list[dict[str, Any]],
    dataset_ids: set[str],
    blockers: list[str],
) -> dict[str, Any]:
    # IDs humanos revisados (no identificadores preetiquetados por IA).
    by_case: dict[str, dict[str, int]] = defaultdict(dict)
    for row in reviews:
        cid = _required(row.get("case_id"), "reviews.case_id")
        reviewer = _required(row.get("annotator_id"), f"reviews[{cid}].annotator_id")
        label = _label(row.get("label"), f"reviews[{cid}].label")
        if cid not in dataset_ids:
            blockers.append(f"Revisión {cid}: ID fuera del dataset final")
        if reviewer in by_case[cid]:
            blockers.append(f"Revisión {cid}: anotador duplicado {reviewer}")
        else:
            by_case[cid][reviewer] = label

    by_adjudication: dict[str, dict[str, str | int]] = {}
    for row in adjudications:
        cid = _required(row.get("case_id"), "adjudications.case_id")
        adjudicator = _required(row.get("adjudicator_id"), f"adjudications[{cid}].adjudicator_id")
        label = _label(row.get("label"), f"adjudications[{cid}].label")
        reason = _required(row.get("reason"), f"adjudications[{cid}].reason")
        if cid in by_adjudication:
            blockers.append(f"Adjudicación {cid}: registro duplicado")
        by_adjudication[cid] = {
            "adjudicator_id": adjudicator, "label": label, "reason": reason
        }
        if cid not in gold:
            blockers.append(f"Adjudicación {cid}: ID no pertenece al Gold presentado")

    n_agreements = n_disagreements = 0
    for cid, row in gold.items():
        labels = by_case.get(cid, {})
        if len(labels) < 2:
            blockers.append(f"Gold {cid}: faltan dos anotaciones humanas independientes")
            continue
        if len(labels) != 2:
            blockers.append(f"Gold {cid}: se requieren exactamente dos anotadores primarios, no {len(labels)}")
            continue
        independent = list(labels.values())
        if independent[0] == independent[1]:
            n_agreements += 1
            if row["gold"] != independent[0]:
                blockers.append(f"Gold {cid}: etiqueta final contradice consenso humano")
            if cid in by_adjudication and by_adjudication[cid]["label"] != row["gold"]:
                blockers.append(f"Gold {cid}: adjudicación no coincide con etiqueta final")
        else:
            n_disagreements += 1
            adj = by_adjudication.get(cid)
            if adj is None:
                blockers.append(f"Gold {cid}: desacuerdo sin adjudicación registrada")
            elif adj["adjudicator_id"] in labels:
                blockers.append(f"Gold {cid}: adjudicador coincide con anotador primario")
            elif adj["label"] != row["gold"]:
                blockers.append(f"Gold {cid}: etiqueta final contradice adjudicación")
    return {
        "n_gold_double_reviewed": sum(len(by_case.get(cid, {})) == 2 for cid in gold),
        "n_gold_agreements": n_agreements,
        "n_gold_disagreements": n_disagreements,
        "n_unique_human_reviewed": len(by_case),
        "n_adjudications": len(by_adjudication),
    }


def audit_candidate(
    gold_rows: list[dict[str, Any]],
    independent_reviews: list[dict[str, Any]],
    adjudications: list[dict[str, Any]],
    dataset_ids: set[str],
    train_rows: list[dict[str, Any]],
    val_rows: list[dict[str, Any]],
    *,
    gold_path: Path,
    raw_dir: Path,
    root: Path = REPO_ROOT,
    min_reviewed_fraction: float = 0.15,
) -> dict[str, Any]:
    if not 0 < min_reviewed_fraction <= 1:
        raise ValueError("min_reviewed_fraction fuera de (0,1]")
    gold = index_gold(gold_rows)
    blockers: list[str] = []
    warnings: list[str] = []
    outside_dataset = set(gold) - dataset_ids
    if outside_dataset:
        blockers.append(f"{len(outside_dataset)} IDs Gold fuera del dataset final")
    # La política existente incluye exclusiones de práctica y partición ACL-200.
    cases = [
        EvaluationCase(
            id=_required(row.get("id"), "gold.id"),
            input=_required(row.get("input"), "gold.input"),
            gold=row.get("gold"),
            metadata={
                "citing_id": row.get("citing_id"), "cited_id": row.get("cited_id"),
            },
        )
        for row in gold_rows
    ]
    try:
        policy = inspect_gold(gold_path, cases, root=root, raw_dir=raw_dir)
    except (OSError, ValueError, TypeError) as exc:
        blockers.append(f"Política Gold: {type(exc).__name__}: {exc}")
    else:
        blockers += ["Política Gold: " + s for s in policy.reasons]

    try:
        from proyecto_de_grado.src.data.validar_splits import load_split_index
        split_index = load_split_index(raw_dir)
    except (OSError, ValueError, TypeError) as exc:
        blockers.append(f"Particiones ACL-200 no verificables: {type(exc).__name__}: {exc}")
        split_index = None
    train: dict[str, dict[str, str]] = {}
    val: dict[str, dict[str, str]] = {}
    if split_index is not None:
        train = _load_training(train_rows, "train", "train", split_index, blockers)
        val = _load_training(val_rows, "validation", "val", split_index, blockers)
    if not train_rows:
        blockers.append("Falta manifiesto de ejemplos train (no se puede verificar leakage)")
    if not val_rows:
        blockers.append("Falta manifiesto de ejemplos validation (no se puede verificar leakage)")

    def ids_and_contexts(rows: dict[str, dict[str, Any]]) -> tuple[set[str], set[tuple[str, str]], set[str]]:
        return (
            {r["citing_id"] for r in rows.values()},
            {(r["citing_id"], r["cited_id"]) for r in rows.values()},
            {_normal_text(r["input"]) for r in rows.values()},
        )

    contexts = {str(row["id"]): row for row in gold_rows}
    gold_citing, gold_pairs, gold_text = ids_and_contexts(contexts)
    for name, selected in (("train", train), ("validation", val)):
        if not selected:
            continue
        citing, pairs, contexts_train = ids_and_contexts(selected)
        shared_ids = set(gold) & set(selected)
        shared_citing = gold_citing & citing
        shared_pairs = gold_pairs & pairs
        shared_text = gold_text & contexts_train
        if shared_ids:
            blockers.append(f"Leakage {name}: {len(shared_ids)} IDs Gold compartidos")
        if shared_citing:
            blockers.append(f"Leakage {name}: {len(shared_citing)} citantes Gold compartidos")
        if shared_pairs:
            blockers.append(f"Leakage {name}: {len(shared_pairs)} pares citante-citado compartidos")
        if shared_text:
            blockers.append(f"Leakage {name}: {len(shared_text)} contextos textuales repetidos (revisar cita agrupada)")

    shared_tv = set(train) & set(val)
    if shared_tv:
        blockers.append(f"Leakage train/validation: {len(shared_tv)} IDs duplicados")

    human = _annotation_checks(gold, independent_reviews, adjudications, dataset_ids, blockers)
    reviewed = human["n_unique_human_reviewed"]
    fraction = reviewed / len(dataset_ids)
    if fraction + 1e-12 < min_reviewed_fraction:
        blockers.append(
            f"Validación humana {reviewed}/{len(dataset_ids)} ({fraction:.2%}) "
            f"inferior al mínimo {min_reviewed_fraction:.0%}"
        )
    if reviewed != len({row["case_id"] for row in independent_reviews if isinstance(row, dict) and "case_id" in row}):
        warnings.append("Revisar registros de anotación independientes anómalos")
    if gold and human["n_gold_double_reviewed"] != len(gold):
        blockers.append("Hay casos Gold sin doble anotación comprobable")
    warnings.append(
        "No se comprueba la identidad real, cegamiento o independencia humana: "
        "se requieren bitácoras y aprobación cruzada fuera del código."
    )
    warnings.append(
        "La fracción humana se calcula sobre las IDs de revisiones entregadas, "
        "no sobre preetiquetas IA ni sobre una muestra extrapolada."
    )
    return {
        "status": "BLOQUEADO" if blockers else "CANDIDATO_PARA_REVISION_HUMANA_NO_CERTIFICADO",
        "n_dataset_ids": len(dataset_ids),
        "n_gold": len(gold),
        "human_review_fraction": round(fraction, 6),
        "human_review_target": min_reviewed_fraction,
        "human_stats": human,
        "n_gold_classes": len({row["gold"] for row in gold.values()}),
        "support_by_class": {
            category: sum(row["gold"] == idx for row in gold.values())
            for idx, category in enumerate(CATEGORIES)
        },
        "blockers": blockers,
        "warnings": warnings,
        "gold_human_certified": False,
        "ready_for_final_benchmark": False,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Audita candidato Gold, sin certificarlo")
    for flag in (
        "gold", "reviews", "adjudications", "dataset-ids", "train", "validation", "raw-dir",
        "output-dir",
    ):
        parser.add_argument(f"--{flag}", type=Path, required=True)
    parser.add_argument("--min-reviewed-fraction", type=float, default=0.15)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        inputs = {
            "gold": args.gold, "reviews": args.reviews,
            "adjudications": args.adjudications, "dataset_ids": args.dataset_ids,
            "train": args.train, "validation": args.validation,
        }
        report = audit_candidate(
            read_jsonl(args.gold), read_jsonl(args.reviews),
            read_jsonl(args.adjudications), load_dataset_ids(args.dataset_ids),
            read_jsonl(args.train), read_jsonl(args.validation),
            gold_path=args.gold, raw_dir=args.raw_dir,
            min_reviewed_fraction=args.min_reviewed_fraction,
        )
        report["audit_timestamp_utc"] = datetime.now(timezone.utc).isoformat()
        report["input_sha256"] = {key: _digest(value) for key, value in inputs.items()}
        args.output_dir.mkdir(parents=True, exist_ok=True)
        (args.output_dir / "gold_audit.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(f"Gold audit no ejecutable: {exc}", file=sys.stderr)
        return 2
    print(f"Gold candidate: {report['status']}; bloqueos={len(report['blockers'])}; "
          f"n_gold={report['n_gold']} n_human={report['human_stats']['n_unique_human_reviewed']}")
    # Código de salida NO implica certificación. Incluso cero bloqueos es
    # CANDIDATO_PARA_REVISION_HUMANA_NO_CERTIFICADO.
    return 2 if report["blockers"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
