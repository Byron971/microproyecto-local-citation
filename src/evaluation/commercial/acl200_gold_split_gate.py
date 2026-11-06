"""Control ACL-200 oficial: candidatos Gold PR91/PR92 vs Haiku (sin certificación humana).

Requiere data/raw materializado con DVC. No modifica anotaciones, no exporta IDs.
El documento citado puede repetirse entre splits; citante y par no.
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

from proyecto_de_grado.src.data.validar_splits import SplitIndex, load_split_index
from .gold_existing_csv_audit import ANNOTATED, DATA_COLUMNS, HAIKU, _parts, _read
from .gold_policy import REPO_ROOT, exclusion_ids

PR91 = REPO_ROOT / "proyecto_de_grado/anotacion/test_gold_v2/manifiesto_ids.csv"


def _manifest_pr91(path: Path) -> dict[str, dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if not {"context_id", "grupo", "tanda"}.issubset(reader.fieldnames or []):
            raise ValueError("PR91: falta context_id/grupo/tanda")
        rows: dict[str, dict[str, str]] = {}
        for row in reader:
            cid = (row.get("context_id") or "").strip()
            if not cid or cid in rows:
                raise ValueError("PR91: ID vacío o duplicado")
            group = (row.get("grupo") or "").strip()
            if group not in {"testgold", "calibracion3"}:
                raise ValueError("PR91: grupo inválido")
            rows[cid] = {"grupo": group, "tanda": (row.get("tanda") or "").strip()}
    if not rows:
        raise ValueError("PR91: manifiesto vacío")
    return rows


def _fingerprint(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def audit_acl_membership(
    index: SplitIndex,
    pr91: dict[str, dict[str, str]],
    annotated: dict[str, dict[str, str]],
    haiku: dict[str, dict[str, str]],
    excluded: set[str],
) -> dict:
    """Resumen agregado con bloqueo de inconsistencias, sin divulgar IDs."""
    sources = {
        "pr91": pr91,
        "pr92_annotated": annotated,
        "haiku_train": haiku,
    }
    expected = {"testgold": "test", "calibracion3": "val"}
    source_counts: dict[str, dict] = {}
    blockers: list[str] = []
    identities: dict[str, dict[str, set]] = {}
    for name, records in sources.items():
        if not records:
            raise ValueError(f"{name}: fuente vacía")
        bad = Counter()
        citings: set[str] = set()
        pairs: set[tuple[str, str]] = set()
        shared_cited: set[str] = set()
        candidate_ids: set[str] = set()
        for cid, row in records.items():
            requested = (
                expected.get(row["grupo"])
                if name == "pr91"
                else "train" if name == "haiku_train"
                else "val" if _parts(cid)[0][1:3] == "14" else "test"
            )
            if requested is None:
                bad["grupo_invalido"] += 1
                continue
            actual = index.by_context.get(cid)
            if actual is None:
                bad["fuera_de_splits"] += 1
                continue
            if actual != requested:
                bad["split_incorrecto"] += 1
            ctx = index.contexts.get(cid)
            if not isinstance(ctx, dict):
                bad["sin_contexto_original"] += 1
                continue
            citing, cited, _ = _parts(cid)
            if ctx.get("citing_id") != citing or ctx.get("refid") != cited:
                bad["identidad_documental_incoherente"] += 1
            original = ctx.get("masked_text")
            if not isinstance(original, str) or original.count("TARGETCIT") != 1:
                bad["marcador_original_invalido"] += 1
            if name != "pr91" and row.get("Contexto TARGETCIT") != original:
                bad["texto_distinto_del_original"] += 1
            if cid in excluded:
                bad["historicamente_excluido"] += 1
            if name == "pr91" and row["grupo"] == "testgold" and row["tanda"] not in {"1", "2", "3"}:
                bad["tanda_invalida"] += 1
            if name == "pr91" and row["grupo"] == "calibracion3" and row["tanda"]:
                bad["calibracion_con_tanda"] += 1
            citings.add(citing)
            pairs.add((citing, cited))
            shared_cited.add(cited)
            if cid not in excluded:
                candidate_ids.add(cid)
        identities[name] = {
            "ids": candidate_ids, "citings": citings, "pairs": pairs,
            "cited": shared_cited,
        }
        source_counts[name] = {
            "total": len(records),
            "errores_o_exclusiones": dict(sorted(bad.items())),
            "documentos_citantes": len(citings),
            "pares_citante_citado": len(pairs),
            "ids_candidatos_sin_exclusion": len(candidate_ids),
        }
        for key, count in bad.items():
            if key == "historicamente_excluido" and name == "pr92_annotated":
                continue  # CSV histórico intacto; se excluye del candidato Gold
            if count:
                blockers.append(f"{name}: {count} {key}")
    cross = {}
    for gold_name in ("pr91", "pr92_annotated"):
        train = identities["haiku_train"]
        gold = identities[gold_name]
        overlaps = {
            "ids": len(gold["ids"] & train["ids"]),
            "documentos_citantes": len(gold["citings"] & train["citings"]),
            "pares_citante_citado": len(gold["pairs"] & train["pairs"]),
            "documentos_citados_compartidos_no_fuga_automatica":
                len(gold["cited"] & train["cited"]),
        }
        cross[gold_name + "_vs_haiku"] = overlaps
        for dimension in ("ids", "documentos_citantes", "pares_citante_citado"):
            if overlaps[dimension]:
                blockers.append(f"{gold_name} vs Haiku: solapamiento de {dimension} ({overlaps[dimension]})")
    return {
        "status": "BLOQUEADO" if blockers else "SPLITS_Y_FUENTES_INSPECCIONADOS_CERTIFICACION_HUMANA_PENDIENTE",
        "source_counts": source_counts,
        "cross_checks": cross,
        "blockers": blockers,
        "acl_official_splits_loaded": True,
        "gold_human_certified": False,
        "final_benchmark_allowed": False,
        "notes": [
            "Citado compartido solo no constituye fuga; citante y par sí.",
            "No verifica otros corpus de jurado/SciBERT/SPECTER: requieren manifiestos de entrenamiento.",
            "No certifica doble anotación, adjudicación, revisión humana ni 15 %.",
            "PR91 y PR92 son candidatos distintos, no deben unirse sin decisión del equipo.",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Auditar ACL-200 real; sin raw no hay resultado")
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument("--pr91", type=Path, default=PR91)
    parser.add_argument("--pr92", type=Path, default=ANNOTATED)
    parser.add_argument("--haiku", type=Path, default=HAIKU)
    parser.add_argument("--output-dir", type=Path, default=Path("artifacts/auditoria_splits_acl200"))
    args = parser.parse_args(argv)
    try:
        files = {"pr91": args.pr91, "pr92": args.pr92, "haiku": args.haiku}
        index = load_split_index(args.raw_dir)
        report = audit_acl_membership(
            index, _manifest_pr91(args.pr91),
            _read(args.pr92, DATA_COLUMNS), _read(args.haiku, DATA_COLUMNS),
            exclusion_ids(),
        )
        report["input_sha256"] = {name: _fingerprint(p) for name, p in files.items()}
        report["acl_raw_sha256"] = {
            filename: _fingerprint(args.raw_dir / filename)
            for filename in ("contexts.json", "train.json", "val.json", "test.json")
        }
        report["audit_utc"] = datetime.now(timezone.utc).isoformat()
        args.output_dir.mkdir(parents=True, exist_ok=True)
        (args.output_dir / "resumen_acl200.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"ACL-200 NO verificado: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    print(f"ACL-200: {report['status']}; bloqueos={len(report['blockers'])}; Gold NO certificado")
    return 2 if report["blockers"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
