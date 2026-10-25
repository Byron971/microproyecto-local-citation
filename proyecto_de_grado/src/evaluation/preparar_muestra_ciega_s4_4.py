"""S4.4: preselección determinista de val ACL-200 para calibración ciega (NO Gold).

No lee predicciones, no llama modelos, no anota automáticamente y no abre test Gold.
Los CSV producidos incluyen texto de citas y se guardan solo como artefactos locales.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import random
import re
from collections import Counter

from proyecto_de_grado.src.data.validar_splits import build_split_index
from proyecto_de_grado.src.data.preparar_preetiquetado import leer_exclusiones

VERSION = "s4_4_preseleccion_val_v1"
RAW_NAMES = ("contexts.json", "papers.json", "train.json", "val.json", "test.json")
COLS = (
    "context_id", "citation_context", "cited_title", "cited_abstract",
    "primary_label", "secondary_label", "annotation_status", "ambiguity_notes",
    "annotation_guide_version", "annotator_id", "annotation_date_utc",
)
REVIEW_COLS = ("context_id", "citing_id", "cited_id", "targetcit_count",
               "othercit_count", "revision_contexto", "motivo", "revisor", "fecha_utc")
ADJ_COLS = ("context_id", "label_a", "label_b", "final_label", "decision_status",
            "justificacion", "adjudicador", "fecha_utc")


def _read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().casefold()


def _write_csv(path: Path, cols: tuple[str, ...], rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def preparar(raw: Path, exclude: Path, history: Path, out: Path,
             *, limit: int = 12, seed: int = 44, extra_exclude: Path | None = None) -> dict:
    """Construye ficheros ciegos nuevos sin sobrescribir ni modificar los originales."""
    if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
        raise ValueError("--limit debe ser entero positivo")
    if not isinstance(seed, int) or isinstance(seed, bool) or seed < 0:
        raise ValueError("--seed debe ser entero >= 0")
    if out.exists():
        raise FileExistsError(f"La salida ya existe: {out}. Usar una ruta nueva; no sobrescribir.")
    files = {name: raw / name for name in RAW_NAMES}
    for name, p in files.items():
        if not p.is_file():
            raise FileNotFoundError(f"No existe ACL-200 original {name}: {p}")
    for p in (exclude, history):
        if not p.is_file():
            raise FileNotFoundError(f"Falta lista obligatoria de exclusiones: {p}")
    if extra_exclude is not None and not extra_exclude.is_file():
        raise FileNotFoundError(f"Falta lista adicional indicada: {extra_exclude}")

    # La verificación de TODOS los splits se hace antes de acceder al conjunto de val.
    contexts, papers = _read_json(files["contexts.json"]), _read_json(files["papers.json"])
    splits = {s: _read_json(files[f"{s}.json"]) for s in ("train", "val", "test")}
    index = build_split_index(contexts, splits)
    if not isinstance(papers, dict):
        raise ValueError("papers.json debe ser un objeto")
    excluded = leer_exclusiones(exclude) | leer_exclusiones(history)
    if extra_exclude is not None:
        excluded |= leer_exclusiones(extra_exclude)

    # Detecta duplicados exactos entre particiones. No garantiza ausencia de casi-duplicados.
    used_text = set()
    for s in ("train", "test"):
        for row in splits[s]:
            used_text.add(_normalize(contexts[row["context_id"]]["masked_text"]))

    reasons: Counter[str] = Counter()
    audit_rows: list[dict] = []
    candidates: list[dict] = []
    seen_val_text: set[str] = set()
    for row in splits["val"]:
        cid = row["context_id"]
        ctx = contexts[cid]
        txt = ctx["masked_text"]
        citing, cited = ctx["citing_id"], ctx["refid"]
        title = papers.get(cited, {}).get("title") if isinstance(papers.get(cited), dict) else None
        norm = _normalize(txt)
        reason = ""
        if cid in excluded:
            reason = "excluido_piloto_calibracion"
        elif norm in used_text:
            reason = "texto_duplicado_en_train_o_test"
        elif norm in seen_val_text:
            reason = "texto_duplicado_en_val"
        elif not isinstance(title, str) or not title.strip():
            reason = "titulo_citado_ausente"
        elif not norm:
            reason = "contexto_vacio"
        # El índice verifica un TARGETCIT, IDs y positive_ids de todos los splits.
        seen_val_text.add(norm)
        if reason:
            reasons[reason] += 1
        else:
            p = papers[cited]
            abstract = p.get("abstract", "")
            candidates.append({
                "context_id": cid, "citing_id": citing, "cited_id": cited,
                "citation_context": txt, "cited_title": title,
                "cited_abstract": abstract if isinstance(abstract, str) else "",
            })
        audit_rows.append({"context_id": cid, "estado": "descartado" if reason else "elegible_automaticamente",
                           "motivo": reason})

    # Primero ordenar para independizar el sorteo del orden físico de val.json.
    candidates.sort(key=lambda r: r["context_id"])
    rng = random.Random(seed)
    rng.shuffle(candidates)
    selected: list[dict] = []
    chosen_ids: set[str] = set()
    chosen_citing: set[str] = set()
    chosen_cited: set[str] = set()
    # Primera pasada, diversidad de artículos citados y citantes.
    for row in candidates:
        if len(selected) == limit:
            break
        if row["citing_id"] in chosen_citing or row["cited_id"] in chosen_cited:
            continue
        selected.append(row)
        chosen_ids.add(row["context_id"])
        chosen_citing.add(row["citing_id"])
        chosen_cited.add(row["cited_id"])
    # Segunda pasada: no repetir citantes aunque sea necesario repetir citados.
    for row in candidates:
        if len(selected) == limit:
            break
        if row["context_id"] in chosen_ids or row["citing_id"] in chosen_citing:
            continue
        selected.append(row)
        chosen_ids.add(row["context_id"])
        chosen_citing.add(row["citing_id"])
        chosen_cited.add(row["cited_id"])
    if len(selected) != limit:
        raise ValueError(f"Solo hay {len(selected)} contextos elegibles distintos por citante, se pidieron {limit}.")
    assert all(index.by_context[r["context_id"]] == "val" for r in selected)

    # Todos los productos son locales; ningún Gold se crea en esta fase.
    out.mkdir(parents=True, exist_ok=False)
    sample_rows = []
    for row in selected:
        sample_rows.append({**row, "primary_label": "", "secondary_label": "",
                            "annotation_status": "", "ambiguity_notes": "",
                            "annotation_guide_version": "", "annotator_id": "",
                            "annotation_date_utc": ""})
    ids = [r["context_id"] for r in selected]
    for which, offset in (("a", 111), ("b", 222)):
        reordered = list(sample_rows)
        random.Random(seed + offset).shuffle(reordered)
        _write_csv(out / f"anotador_{which}.csv", COLS, reordered)
    _write_csv(out / "revision_elegibilidad.csv", REVIEW_COLS, [
        {"context_id": r["context_id"], "citing_id": r["citing_id"],
         "cited_id": r["cited_id"], "targetcit_count": 1,
         "othercit_count": r["citation_context"].count("OTHERCIT"),
         "revision_contexto": "", "motivo": "", "revisor": "", "fecha_utc": ""}
        for r in selected
    ])
    _write_csv(out / "adjudicacion_plantilla.csv", ADJ_COLS,
               [{"context_id": cid} for cid in ids])
    _write_csv(out / "auditoria_marco_val.csv", ("context_id", "estado", "motivo"), audit_rows)
    (out / "ids_preseleccionados.txt").write_text("\n".join(ids) + "\n", encoding="utf-8")
    sources = {name: sha(path) for name, path in files.items()}
    sources.update({"ids_excluir_test_gold.txt": sha(exclude),
                    "ids_piloto_historico_no_test_final.txt": sha(history)})
    if extra_exclude is not None:
        sources["exclusiones_adicionales"] = sha(extra_exclude)
    generated = ["anotador_a.csv", "anotador_b.csv", "revision_elegibilidad.csv",
                 "adjudicacion_plantilla.csv", "auditoria_marco_val.csv", "ids_preseleccionados.txt"]
    manifest = {
        "version": VERSION, "estado": "preseleccion_val_no_gold_pendiente_revision_humana",
        "fecha_generacion_utc": datetime.now(timezone.utc).isoformat(),
        "split": "val", "seed": seed, "limit": limit,
        "marco_val": len(splits["val"]), "elegibles_automaticos": len(candidates),
        "exclusiones_por_motivo": dict(sorted(reasons.items())),
        "unicos_citing": len(chosen_citing), "unicos_cited": len(chosen_cited),
        "excluidos_ids_union": len(excluded),
        "exposiciones_adicionales_incluidas": extra_exclude is not None,
        "sha256_fuentes": sources, "ids_preseleccionados": ids,
        "sha256_archivos_generados": {n: sha(out / n) for n in generated},
        "etiquetas_humanas_generadas": 0,
        "advertencia": (
            "Preseleccion NO aprobada para anotacion sin revisar manualmente truncacion, "
            "citas agrupadas, OTHERCIT, atribucion y posibles casi duplicados. "
            "No es Test Gold, no genera F1 ni valida el 15%."
        ),
    }
    (out / "manifiesto.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--raw", type=Path, default=Path("data/raw"))
    ap.add_argument("--exclude", type=Path, default=Path("proyecto_de_grado/anotacion/ids_excluir_test_gold.txt"))
    ap.add_argument("--exclude-history", type=Path, default=Path("proyecto_de_grado/anotacion/ids_piloto_historico_no_test_final.txt"))
    ap.add_argument("--extra-exclude", type=Path, help="Archivo adicional con IDs expuestos; se une a exclusiones.")
    ap.add_argument("--out", type=Path, default=Path("proyecto_de_grado/artifacts/evaluacion_s4/muestra_val_12_v1"))
    ap.add_argument("--limit", type=int, default=12)
    ap.add_argument("--seed", type=int, default=44)
    args = ap.parse_args(argv)
    try:
        m = preparar(args.raw, args.exclude, args.exclude_history, args.out,
                     limit=args.limit, seed=args.seed, extra_exclude=args.extra_exclude)
    except (ValueError, FileNotFoundError, FileExistsError, OSError, json.JSONDecodeError) as exc:
        ap.exit(2, f"S4.4 ERROR: {exc}\n")
    print("S4.4 PRESELECCION GENERADA — NO GOLD")
    print(f"Split: {m['split']} | preseleccionados: {m['limit']} | marco val: {m['marco_val']}")
    print(f"Elegibles automáticos: {m['elegibles_automaticos']} | descartes: {m['exclusiones_por_motivo']}")
    print(f"Exclusiones ID: {m['excluidos_ids_union']} | etiquetas humanas generadas: 0")
    print("Salida:", args.out)
    print("PASO OBLIGATORIO: revisar manualmente revision_elegibilidad.csv ANTES de distribuir las hojas.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
