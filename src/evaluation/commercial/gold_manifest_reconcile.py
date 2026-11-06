"""Reconciliación de dos manifiestos Test Gold ya versionados.

PR #91: 1533 casos escogidos (tandas 519/441/573) y 20 calibraciones.
PR #92: CSV con 2700 anotaciones diligenciadas (2014 y 2015).
No crea anotaciones nuevas, no extrae texto ni declara acuerdo humano.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

from .gold_existing_csv_audit import (
    ANNOTATED, DATA_COLUMNS, HAIKU, MANIFEST, _read, _parts,
)
from .gold_policy import REPO_ROOT, exclusion_ids

PR91_MANIFEST = (
    REPO_ROOT / "proyecto_de_grado" / "anotacion" / "test_gold_v2"
    / "manifiesto_ids.csv"
)
ALLOWED_GROUPS = {"testgold", "calibracion3"}
ALLOWED_TANDAS = {"1", "2", "3"}


def read_pr91_manifest(path: Path) -> list[dict[str, str]]:
    """Valida duplicados, grupo, tanda y año, sin exponer IDs en el reporte."""
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not {"context_id", "grupo", "tanda"}.issubset(reader.fieldnames or []):
            raise ValueError("PR91: faltan columnas context_id/grupo/tanda")
        for row in reader:
            cid = (row.get("context_id") or "").strip()
            group = (row.get("grupo") or "").strip()
            tanda = (row.get("tanda") or "").strip()
            if not cid or cid in seen:
                raise ValueError("PR91: context_id ausente o duplicado")
            seen.add(cid)
            citing, _, _ = _parts(cid)
            if group not in ALLOWED_GROUPS:
                raise ValueError("PR91: grupo inválido")
            if group == "testgold" and (tanda not in ALLOWED_TANDAS or citing[1:3] != "15"):
                raise ValueError("PR91: tanda/año de testgold inválido")
            if group == "calibracion3" and (tanda or citing[1:3] != "14"):
                raise ValueError("PR91: calibración no corresponde a validación 2014")
            rows.append({"context_id": cid, "grupo": group, "tanda": tanda})
    if not rows:
        raise ValueError("PR91: manifiesto vacío")
    return rows


def reconcile(
    rows91: list[dict[str, str]],
    annotated92: dict[str, dict[str, str]],
    manifest92: dict[str, dict[str, str]],
    haiku_train: dict[str, dict[str, str]],
    excluded: set[str],
) -> dict[str, Any]:
    """Compara identidad de ejemplos; coincidencia de IDs != doble anotación."""
    if not rows91 or not annotated92 or not haiku_train:
        raise ValueError("Reconciliación requiere los archivos originales completos")
    ids91 = [row["context_id"] for row in rows91]
    if len(ids91) != len(set(ids91)):
        raise ValueError("PR91: IDs duplicados")
    if set(annotated92) != set(manifest92):
        raise ValueError("PR92: archivo anotado y manifiesto no coinciden por IDs")
    tests91 = {row["context_id"] for row in rows91 if row["grupo"] == "testgold"}
    calibration91 = {row["context_id"] for row in rows91 if row["grupo"] == "calibracion3"}
    years92 = Counter("20" + _parts(cid)[0][1:3] for cid in annotated92)
    tests92 = {cid for cid in annotated92 if _parts(cid)[0][1:3] == "15"}
    validation92 = set(annotated92) - tests92
    if years92.keys() - {"2014", "2015"}:
        raise ValueError("PR92: anotaciones fuera de 2014/2015")
    overlap = tests91 & tests92
    only91 = tests91 - tests92
    only92 = tests92 - tests91
    by_tanda: dict[str, dict[str, int]] = {}
    for tanda in ("1", "2", "3"):
        ids = {
            row["context_id"] for row in rows91
            if row["grupo"] == "testgold" and row["tanda"] == tanda
        }
        by_tanda[tanda] = {
            "planned": len(ids),
            "present_in_annotated_2700": len(ids & tests92),
            "absent_from_annotated_2700": len(ids - tests92),
            "historical_exclusions": len(ids & excluded),
        }

    def count_status(ids: set[str]) -> dict[str, int]:
        counter = Counter(annotated92[cid]["Estado"] for cid in ids)
        return dict(sorted(counter.items()))

    exc92 = set(annotated92) & excluded
    exc91 = tests91 & excluded
    tr = set(haiku_train)
    return {
        "status": "DECISION_MANIFIESTO_CANONICO_PENDIENTE",
        "source": "IDs de archivos reales; NO se comprobó doble anotación humana",
        "pr91": {
            "manifest_rows": len(rows91),
            "testgold_2015": len(tests91),
            "calibration_2014": len(calibration91),
            "tandas": by_tanda,
        },
        "pr92": {
            "annotation_rows": len(annotated92),
            "annotation_years": dict(sorted(years92.items())),
            "manifest_rows": len(manifest92),
            "haiku_prelabels_rows": len(tr),
            "test_2015_candidates": len(tests92),
            "validation_2014_candidates": len(validation92),
            "historical_exclusions_all": len(exc92),
            "historical_exclusions_2014": len(exc92 & validation92),
            "historical_exclusions_2015": len(exc92 & tests92),
            "test_2015_after_historical_exclusions": len(tests92 - excluded),
        },
        "cross_manifest": {
            "pr91_test_present_in_pr92": len(overlap),
            "pr91_test_not_in_pr92": len(only91),
            "pr92_test_not_in_pr91": len(only92),
            "pr91_test_present_status": count_status(overlap),
            "pr91_test_overlap_with_haiku": len(tests91 & tr),
            "pr92_all_overlap_with_haiku": len(set(annotated92) & tr),
            "pr91_calibration_present_in_pr92": len(calibration91 & validation92),
            "pr91_test_historical_exclusions": len(exc91),
        },
        "gold_human_certified": False,
        "double_annotation_verified": False,
        "acl_official_splits_verified": False,
        "final_benchmark_allowed": False,
        "next_decision": (
            "Equipo: elegir/firmar un solo manifiesto de test 2015, "
            "conciliar ID a ID las hojas humanas privadas con ambos conjuntos, "
            "validar ACL oficiales y no reutilizar Gold en ajuste."
        ),
    }


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Reconciliar PR91/PR92 por IDs sin reanotar")
    p.add_argument("--pr91", type=Path, default=PR91_MANIFEST)
    p.add_argument("--annotated", type=Path, default=ANNOTATED)
    p.add_argument("--pr92-manifest", type=Path, default=MANIFEST)
    p.add_argument("--haiku", type=Path, default=HAIKU)
    p.add_argument("--output-dir", type=Path, default=Path("artifacts/conciliacion_test_gold"))
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        inputs = {
            "pr91_manifest": args.pr91,
            "pr92_annotated": args.annotated,
            "pr92_manifest": args.pr92_manifest,
            "haiku_prelabels": args.haiku,
        }
        report = reconcile(
            read_pr91_manifest(args.pr91),
            _read(args.annotated, DATA_COLUMNS),
            _read(args.pr92_manifest, ("context_id", "anio_citante", "prelabel_qlora")),
            _read(args.haiku, DATA_COLUMNS),
            exclusion_ids(),
        )
        report["source_sha256"] = {
            key: _sha(path) for key, path in inputs.items()
        }
        report["checked_at_utc"] = datetime.now(timezone.utc).isoformat()
        args.output_dir.mkdir(parents=True, exist_ok=True)
        output = args.output_dir / "resumen_conciliacion_gold.json"
        output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"Conciliación bloqueada: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    cross = report["cross_manifest"]
    print(
        f"Conciliación completada; PR91↔PR92={cross['pr91_test_present_in_pr92']}, "
        f"solo PR91={cross['pr91_test_not_in_pr92']}, "
        f"solo PR92 test={cross['pr92_test_not_in_pr91']}; "
        "NO certificado como Gold humano."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
