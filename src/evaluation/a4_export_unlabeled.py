"""Exportación ciega A4 2x2 de casos elegidos del split test ACL-200.

No toma muestras implícitas ni observa predicciones, etiquetas humanas o Gold.
La lista seleccionada debe aprobarse ANTES de inferir, y cada ID debe estar
en test oficial y NO pertenecer al piloto histórico conocido. Si un artículo
no es compatible con el fragmentador V1 original, falla sin escribir nada.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

from proyecto_de_grado.src.data.integrar_acl import integrar_contexto
from proyecto_de_grado.src.data.validar_splits import load_split_index
from proyecto_de_grado.src.data.exportar_corpus_top3 import fragmentar
from src.evaluation.commercial.gold_policy import exclusion_ids
from src.evaluation.a4_infer_unlabeled import (
    ALLOWED_CASE, ALLOWED_CHUNK, InputError, hash_file,
    read_unlabeled_inputs, verify_ocl_sources, verify_source_papers,
)

SAFE_ID = re.compile(r"^[A-Za-z0-9_-]+$")


def selected_ids(file: Path) -> list[str]:
    if not file.is_file() or file.is_symlink():
        raise InputError("Se requiere un archivo real de IDs de test, sin symlink.")
    entries = [
        row.strip() for row in file.read_text(encoding="utf-8-sig").splitlines()
        if row.strip() and not row.lstrip().startswith("#")
    ]
    if not entries or len(entries) != len(set(entries)):
        raise InputError("La selección debe tener IDs únicos y no estar vacía.")
    if any(not SAFE_ID.fullmatch(cid) for cid in entries):
        raise InputError("Identificador de contexto inseguro o inválido.")
    return entries


def build_unlabeled(ids_file: Path, raw_dir: Path, ocl_cache: Path,
                    *, blocked_ids: set[str] | None = None) -> tuple[list[dict], dict]:
    ids = selected_ids(ids_file)
    source = load_split_index(raw_dir)
    papers_path = Path(raw_dir) / "papers.json"
    if not papers_path.is_file() or papers_path.is_symlink():
        raise InputError("Falta papers.json original para autenticidad del experimento.")
    papers = json.loads(papers_path.read_text(encoding="utf-8-sig"))
    if not isinstance(papers, dict):
        raise InputError("papers.json debe ser un objeto ACL-200")
    banned = exclusion_ids() if blocked_ids is None else blocked_ids
    rows: list[dict] = []
    for cid in ids:
        if cid in banned:
            raise InputError(f"{cid}: utilizado previamente en práctica, piloto o calibración.")
        if source.by_context.get(cid) != "test":
            raise InputError(f"{cid}: debe pertenecer al test ACL-200 oficial.")
        ctx = source.contexts.get(cid)
        if not isinstance(ctx, dict):
            raise InputError(f"{cid}: context_id sin fuente original.")
        cited = ctx["refid"]
        if not SAFE_ID.fullmatch(cited):
            raise InputError(f"{cid}: cited_id inseguro.")
        try:
            source_data = integrar_contexto(cid, source.contexts, papers, ocl_cache)
            fragments = fragmentar(source_data["paragraphs"])
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            raise InputError(f"{cid}: citado no elegible para fragmentación V1 original: {exc}") from exc
        title = source_data["cited_title"]
        abstract = source_data["cited_abstract"]
        context = source_data["citation_context"]
        if (not isinstance(title, str) or not title.strip()
                or not isinstance(abstract, str) or not abstract.strip()
                or not 3 <= len(fragments) <= 500
                or len(context) > 4000 or len(title) > 600 or len(abstract) > 12000):
            raise InputError(f"{cid}: citado incompleto o fuera de los límites originales.")
        source_file = Path(ocl_cache) / (cited + ".json")
        sha = hash_file(source_file)
        if any(len(f["texto"]) > 5000 for f in fragments):
            raise InputError(f"{cid}: fragmentos incompatibles con el presupuesto A4.")
        rows.append({
            "context_id": cid, "citing_id": source_data["citing_id"],
            "cited_id": cited, "split": "test",
            "citation_context": context,
            "context_sha256": hashlib.sha256(context.encode("utf-8")).hexdigest(),
            "cited_title": title.strip(), "cited_abstract": abstract.strip(),
            "sha256_ocl_citado": sha, "chunks": fragments,
        })
    return rows, {
        "schema_version": 1,
        "status": "ENTRADAS_SIN_ETIQUETAS_CANDIDATAS_NO_GOLD_CERTIFICADO",
        "n_selected": len(ids),
        "n_exported": len(rows),
        "selection_sha256": hash_file(ids_file),
        "acl_sha256": {
            name: hash_file(Path(raw_dir) / name)
            for name in ("contexts.json", "train.json", "val.json", "test.json", "papers.json")
        },
        "contains_gold_labels": False,
        "gold_human_certified": False,
        "heldout_independence_certified": False,
        "note": ("Elegibilidad ACL y exclusiones históricas conocidas verificadas. "
                 "No demuestra ausencia de todos los usos previos en tuning/prompts "
                 "ni reemplaza el Test Gold humano."),
    }


def export(ids_file: Path, raw_dir: Path, ocl_cache: Path, output: Path,
           manifest: Path) -> dict:
    if output.resolve() == manifest.resolve():
        raise InputError("La lista de entradas y el reporte no pueden compartir ruta.")
    for path in (output, manifest):
        if path.exists() or path.is_symlink():
            raise InputError("La salida ya existe o es symlink; no sobrescribir.")
    rows, report = build_unlabeled(ids_file, raw_dir, ocl_cache)
    # Contrastar nuevamente con los lectores definitivos, antes de escribir.
    import tempfile
    with tempfile.TemporaryDirectory(prefix="a4-export-check-") as tmpdir:
        dry = Path(tmpdir) / "generated.jsonl"
        dry.write_text(
            "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
            encoding="utf-8",
        )
        checked, _ = read_unlabeled_inputs(dry)
        if len(checked) != len(rows):
            raise InputError("La selección no coincide con el parser A4.")
        verify_source_papers(checked, raw_dir)
        verify_ocl_sources(checked, ocl_cache)
    output.parent.mkdir(parents=True, exist_ok=True)
    manifest.parent.mkdir(parents=True, exist_ok=True)
    # El nombre nuevo se crea sin reemplazo; si el segundo archivo fallara,
    # se elimina el primero para no dejar una entrega parcialmente preparada.
    try:
        with output.open("x", encoding="utf-8") as stream:
            for row in rows:
                stream.write(json.dumps(row, ensure_ascii=False) + "\n")
        report["unlabeled_file_sha256"] = hash_file(output)
        with manifest.open("x", encoding="utf-8") as stream:
            json.dump(report, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
    except OSError:
        output.unlink(missing_ok=True)
        raise
    return report


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--ids-file", required=True, type=Path)
    p.add_argument("--raw-dir", required=True, type=Path)
    p.add_argument("--ocl-cache", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    p.add_argument("--manifest", required=True, type=Path)
    args = p.parse_args(argv)
    try:
        report = export(
            args.ids_file, args.raw_dir, args.ocl_cache, args.output,
            args.manifest,
        )
    except (InputError, OSError, ValueError, KeyError, TypeError,
            json.JSONDecodeError) as exc:
        p.exit(2, f"Exportación ciega A4 bloqueada: {exc}\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
