"""Auditoría de los CSV 2.700 ya existentes; NUNCA vuelve a anotar.

Distingue las pre-etiquetas Haiku (entrenamiento), las anotaciones revisadas
y el Test Gold *candidato* de 2015. La procedencia humana, independencia
y elegibilidad del Gold final requieren acta/evidencia externa al CSV.
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

from .gold_policy import REPO_ROOT, exclusion_ids
from .metrics import CATEGORIES

BASE = REPO_ROOT / "proyecto_de_grado" / "anotacion" / "test_gold"
ANNOTATED = BASE / "TEST_GOLD_2700_ANOTADO.csv"
MANIFEST = BASE / "TEST_GOLD_2700_MANIFIESTO.csv"
HAIKU = REPO_ROOT / "notebooks" / "qlora-training" / "ANOTACION_UNICA_2700_CITAS_REALES_ANOTADO.csv"
DATA_COLUMNS = (
    "context_id", "Contexto TARGETCIT", "¿Evaluable?", "Función principal",
    "Confianza", "Justificación / duda", "Estado",
)
VALID_STATES = {"COMPLETO", "REGISTRADO"}
VALID_EVALUABILITY = {"Evaluable", "Ambiguo", "No evaluable"}


def _read(path: Path, columns: tuple[str, ...]) -> dict[str, dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        present = set(reader.fieldnames or [])
        missing = set(columns) - present
        if missing:
            raise ValueError(f"{path.name}: faltan columnas {sorted(missing)}")
        rows: dict[str, dict[str, str]] = {}
        for n, row in enumerate(reader, start=2):
            cid = (row.get("context_id") or "").strip()
            if not cid:
                raise ValueError(f"{path.name}:{n}: context_id vacío")
            if cid in rows:
                raise ValueError(f"{path.name}: context_id duplicado (línea {n})")
            rows[cid] = {key: (value or "").strip() for key, value in row.items() if key}
    if not rows:
        raise ValueError(f"{path.name}: CSV vacío")
    return rows


def _parts(cid: str) -> tuple[str, str, str]:
    elements = cid.rsplit("_", 2)
    if len(elements) != 3 or not all(elements) or not elements[2].isdigit():
        raise ValueError("context_id sin estructura citante_citado_posición")
    return elements[0], elements[1], elements[2]


def _sha(path: Path) -> str:
    sha = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            sha.update(block)
    return sha.hexdigest()


def audit_existing(
    annotated: dict[str, dict[str, str]],
    haiku: dict[str, dict[str, str]],
    manifest: dict[str, dict[str, str]],
    *,
    excluded: set[str],
    expected_count: int = 2700,
    dataset_final_total: int | None = None,
    split_index: Any | None = None,
) -> dict[str, Any]:
    """Auditoría de integridad de archivos; no identifica personas reales."""
    if expected_count < 1:
        raise ValueError("expected_count debe ser positivo")
    if dataset_final_total is not None and dataset_final_total < 1:
        raise ValueError("dataset_final_total debe ser positivo")

    blockers: list[str] = []
    warnings: list[str] = []
    if len(annotated) != expected_count:
        blockers.append(f"Anotaciones: {len(annotated)} registros; esperados {expected_count}")
    if len(haiku) != expected_count:
        blockers.append(f"Haiku: {len(haiku)} registros; esperados {expected_count}")
    if set(annotated) != set(manifest):
        blockers.append(
            f"Manifiesto desalineado: {len(set(annotated) - set(manifest))} ausentes "
            f"y {len(set(manifest) - set(annotated))} adicionales"
        )

    year_counts: Counter[str] = Counter()
    year_completed: Counter[str] = Counter()
    year_ambiguous: Counter[str] = Counter()
    status_counts: Counter[str] = Counter()
    eval_counts: Counter[str] = Counter()
    class_counts: Counter[str] = Counter()
    missing_confidence = 0
    n_bad_markers = 0

    def verify_file(name: str, rows: dict[str, dict[str, str]], expected_years: set[str]) -> None:
        nonlocal missing_confidence, n_bad_markers
        for cid, row in rows.items():
            citing, cited, _ = _parts(cid)
            yy = citing[1:3] if len(citing) >= 3 else ""
            if not (len(citing) >= 3 and citing[0].isalpha() and yy in expected_years):
                blockers.append(f"{name}: año citante fuera del rango permitido (id oculto)")
            if (row.get("Contexto TARGETCIT") or "").count("TARGETCIT") != 1:
                n_bad_markers += 1
            status = row["Estado"]
            evaluable = row["¿Evaluable?"]
            label = row["Función principal"]
            if status not in VALID_STATES or evaluable not in VALID_EVALUABILITY:
                blockers.append(f"{name}: Estado/¿Evaluable? inválido")
                continue
            if evaluable == "Evaluable":
                if status != "COMPLETO" or label not in CATEGORIES:
                    blockers.append(f"{name}: Evaluable sin clase canónica y estado COMPLETO")
            else:
                if status != "REGISTRADO" or label or not row["Justificación / duda"]:
                    blockers.append(f"{name}: ambiguo/no evaluable sin justificación o con etiqueta")
            if not row["Confianza"]:
                missing_confidence += 1
    verify_file("Anotaciones", annotated, {"14", "15"})
    verify_file("Haiku", haiku, {"09", "10", "11", "12", "13"})
    if n_bad_markers:
        blockers.append(f"{n_bad_markers} contextos sin exactamente un TARGETCIT")
    if missing_confidence:
        warnings.append(f"{missing_confidence} registros sin nivel de confianza (revisión editorial)")

    for cid, row in annotated.items():
        yy = _parts(cid)[0][1:3]
        year_counts["20" + yy] += 1
        status_counts[row["Estado"]] += 1
        eval_counts[row["¿Evaluable?"]] += 1
        if row["Estado"] == "COMPLETO":
            year_completed["20" + yy] += 1
            class_counts[row["Función principal"]] += 1
        else:
            year_ambiguous["20" + yy] += 1
        m = manifest.get(cid)
        if m is not None and m.get("anio_citante") != "20" + yy:
            blockers.append("Manifiesto: año citante incongruente (id oculto)")

    # Las listas de exclusión se aplican al TEST CANDIDATO, no borran
    # filas históricas ya anotadas. Conservamos el CSV original inmutable.
    excluded_present = set(annotated) & excluded
    excluded_years: Counter[str] = Counter()
    excluded_completed_years: Counter[str] = Counter()
    for cid in excluded_present:
        year = "20" + _parts(cid)[0][1:3]
        excluded_years[year] += 1
        if annotated[cid]["Estado"] == "COMPLETO":
            excluded_completed_years[year] += 1
    if excluded_present:
        warnings.append(
            f"{len(excluded_present)} anotaciones previamente excluidas se conservan en "
            "el CSV histórico, pero NO son elegibles para Test Gold."
        )

    overlap_ids = set(annotated) & set(haiku)
    if overlap_ids:
        blockers.append(f"Anotaciones y Haiku comparten {len(overlap_ids)} IDs")
    review_citings = {_parts(cid)[0] for cid in annotated}
    train_citings = {_parts(cid)[0] for cid in haiku}
    if review_citings & train_citings:
        blockers.append(f"Documentos citantes compartidos: {len(review_citings & train_citings)}")
    review_pairs = {tuple(_parts(cid)[:2]) for cid in annotated}
    train_pairs = {tuple(_parts(cid)[:2]) for cid in haiku}
    if review_pairs & train_pairs:
        blockers.append(f"Pares citante–citado compartidos: {len(review_pairs & train_pairs)}")

    checked_split = False
    if split_index is not None:
        checked_split = True
        for cid in annotated:
            expected = "val" if _parts(cid)[0][1:3] == "14" else "test"
            actual = split_index.by_context.get(cid)
            if actual != expected:
                blockers.append(f"ACL-200: un registro de {expected} no coincide con partición oficial")
            ctx = split_index.contexts.get(cid, {})
            row = annotated[cid]
            if ctx and ctx.get("masked_text") != row["Contexto TARGETCIT"]:
                blockers.append("ACL-200: contexto de anotación diferente al original")
    else:
        warnings.append(
            "Sin --raw-dir: no se verificaron las particiones oficiales de ACL-200."
        )

    if dataset_final_total is None:
        fraction = None
        warnings.append(
            "Sin denominador auditado del dataset final: no se puede certificar el 15% humano."
        )
    else:
        fraction = round(len(annotated) / dataset_final_total, 6)
        if fraction < 0.15:
            blockers.append(
                f"Cobertura documental {len(annotated)}/{dataset_final_total} <15% "
                "(sin certificar autoría humana)"
            )
    warnings.extend([
        "El CSV no incluye identidad, fecha y evidencia independiente del anotador humano.",
        "Las pre-etiquetas Haiku son automáticas y NO cuentan como validación humana.",
        "El grupo 2014 es VALIDACIÓN, el de 2015 es TEST CANDIDATO; "
        "no sumar los 2700 como Test Gold final.",
        "No está integrado el registro de doble anotación de las tandas de 1533 casos "
        "ni adjudicaciones: reconciliar por IDs antes de certificar Gold.",
    ])
    return {
        "status": "BLOQUEADO" if blockers else "INTEGRIDAD_CSV_OK_CERTIFICACION_HUMANA_PENDIENTE",
        "scientific_gold_certified": False,
        "ready_for_final_benchmark": False,
        "input_records": {"anotacion": len(annotated), "haiku_prelabel": len(haiku),
                          "manifest": len(manifest)},
        "split_by_citing_year": dict(sorted(year_counts.items())),
        "classifiable_by_year": dict(sorted(year_completed.items())),
        "ambiguous_or_nonevaluable_by_year": dict(sorted(year_ambiguous.items())),
        "status_counts": dict(status_counts),
        "evaluability_counts": dict(eval_counts),
        "completed_class_counts": {key: class_counts.get(key, 0) for key in CATEGORIES},
        "shared_ids_with_haiku": len(overlap_ids),
        "shared_citing_documents_with_haiku": len(review_citings & train_citings),
        "shared_citing_cited_pairs_with_haiku": len(review_pairs & train_pairs),
        "acl_official_splits_verified": checked_split,
        "dataset_final_total": dataset_final_total,
        "annotation_file_fraction_if_all_human": fraction,
        "human_provenance_verified": False,
        "double_annotation_verified": False,
        "n_provisional_test_2015": year_counts.get("2015", 0),
        "n_provisional_test_classifiable_2015": year_completed.get("2015", 0),
        "n_excluded_from_final_gold": len(excluded_present),
        "excluded_from_final_gold_by_year": dict(sorted(excluded_years.items())),
        "n_test_candidates_2015_after_exclusions": (
            year_counts.get("2015", 0) - excluded_years.get("2015", 0)
        ),
        "n_classifiable_test_candidates_2015_after_exclusions": (
            year_completed.get("2015", 0) - excluded_completed_years.get("2015", 0)
        ),
        "blockers": list(dict.fromkeys(blockers)),
        "warnings": warnings,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audita 2700 anotaciones existentes (sin crear ninguna).")
    parser.add_argument("--annotated", type=Path, default=ANNOTATED)
    parser.add_argument("--haiku-train", type=Path, default=HAIKU)
    parser.add_argument("--manifest", type=Path, default=MANIFEST)
    parser.add_argument("--raw-dir", type=Path, default=None)
    parser.add_argument("--dataset-final-total", type=int, default=None)
    parser.add_argument("--expected-count", type=int, default=2700)
    parser.add_argument("--output-dir", type=Path, default=Path("artifacts/auditoria_gold_existente"))
    args = parser.parse_args(argv)
    try:
        index = None
        if args.raw_dir is not None:
            from proyecto_de_grado.src.data.validar_splits import load_split_index
            index = load_split_index(args.raw_dir)
        annotated = _read(args.annotated, DATA_COLUMNS)
        haiku = _read(args.haiku_train, DATA_COLUMNS)
        manifest = _read(args.manifest, ("context_id", "anio_citante", "prelabel_qlora"))
        report = audit_existing(
            annotated, haiku, manifest, excluded=exclusion_ids(),
            expected_count=args.expected_count,
            dataset_final_total=args.dataset_final_total,
            split_index=index,
        )
        report["audit_utc"] = datetime.now(timezone.utc).isoformat()
        report["sha256"] = {
            "annotated": _sha(args.annotated),
            "haiku_train": _sha(args.haiku_train),
            "manifest": _sha(args.manifest),
        }
        args.output_dir.mkdir(parents=True, exist_ok=True)
        (args.output_dir / "gold_existing_audit.json").write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"Auditoría no ejecutable: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    print(f"Integridad: {report['status']} | N={len(annotated)} | "
          f"2014={report['split_by_citing_year'].get('2014', 0)} "
          f"2015={report['split_by_citing_year'].get('2015', 0)}; "
          f"bloqueos={len(report['blockers'])}")
    return 2 if report["blockers"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
