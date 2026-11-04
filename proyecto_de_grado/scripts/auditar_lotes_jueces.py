"""Auditoría de procedencia de lotes de jueces sobre ACL-200, sin inferencia.

Solo lee entradas; ningún lote se considera Gold ni validado automáticamente.
Permite TXT (un context_id por línea), CSV, JSONL o JSON. Exportar XLSX a CSV.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
import re
from typing import Any

SPLITS = ("train", "val", "test")
ID_FIELDS = ("context_id", "id", "citation_id", "citation_context_id")
QLORA_NAMES = ("qlora_citas_adapter", "qlora_split.json", "qlora_val_preds.jsonl")
YEAR_RE = re.compile(r"^[A-Za-z](\d{2})-")


def acl_year(paper_id: Any) -> int | None:
    """Convención de IDs ACL usada por cifras_informe.py (corte en 1979)."""
    match = YEAR_RE.match(paper_id) if isinstance(paper_id, str) else None
    if not match:
        return None
    yy = int(match.group(1))
    return 1900 + yy if yy >= 79 else 2000 + yy


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def extract_id(row: Any) -> str:
    if isinstance(row, str):
        return row.strip()
    if isinstance(row, dict):
        for field in ID_FIELDS:
            value = row.get(field)
            if isinstance(value, str) and value.strip():
                return value.strip()
        if len(row) == 1:
            value = next(iter(row.values()))
            if isinstance(value, str):
                return value.strip()
    raise ValueError("Fila sin context_id/id/citation_id reconocible")


def read_ids(path: Path) -> list[str]:
    if not path.is_file():
        raise FileNotFoundError(path)
    suffix = path.suffix.lower()
    if suffix == ".csv":
        with path.open(encoding="utf-8-sig", newline="") as file:
            rows: list[Any] = list(csv.DictReader(file))
    elif suffix == ".jsonl":
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
    elif suffix == ".json":
        rows = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(rows, list):
            raise ValueError("JSON debe contener una lista de identificadores u objetos")
    elif suffix == ".txt":
        rows = [line.strip() for line in path.read_text(encoding="utf-8-sig").splitlines()
                if line.strip() and not line.lstrip().startswith("#")]
    else:
        raise ValueError(f"Formato no soportado: {suffix}. Exporta Excel a CSV.")
    return [extract_id(row) for row in rows]


def load_acl(raw: Path) -> tuple[dict[str, dict], dict[str, str], dict[str, int]]:
    contexts = json.loads((raw / "contexts.json").read_text(encoding="utf-8-sig"))
    if not isinstance(contexts, dict):
        raise ValueError("contexts.json debe ser un objeto")
    index: dict[str, str] = {}
    sizes: dict[str, int] = {}
    for split in SPLITS:
        rows = json.loads((raw / f"{split}.json").read_text(encoding="utf-8-sig"))
        sizes[split] = len(rows)
        for row in rows:
            cid = row.get("context_id")
            if not isinstance(cid, str) or not cid:
                raise ValueError(f"ID inválido en split {split}")
            if cid in index:
                raise ValueError(f"Contexto duplicado entre/dentro de splits: {cid}")
            if cid not in contexts:
                raise ValueError(f"Contexto del split no existe en contexts.json: {cid}")
            index[cid] = split
    return contexts, index, sizes


def summarize(ids: list[str], contexts: dict[str, dict], index: dict[str, str],
              excluded: set[str] | None = None) -> dict[str, Any]:
    counts = Counter(ids)
    split_counts: Counter[str] = Counter()
    cited_old: Counter[str] = Counter()
    citing_old: Counter[str] = Counter()
    unknown: list[str] = []
    markers_invalid: list[str] = []
    excluded_found: list[str] = []
    for cid in sorted(counts):
        split = index.get(cid)
        if split is None:
            unknown.append(cid)
            continue
        split_counts[split] += 1
        ctx = contexts[cid]
        if (ctx.get("masked_text") or "").count("TARGETCIT") != 1:
            markers_invalid.append(cid)
        cited_year = acl_year(ctx.get("refid"))
        citing_year = acl_year(ctx.get("citing_id"))
        if cited_year is not None and 1980 <= cited_year <= 1999:
            cited_old[split] += 1
        if citing_year is not None and 1980 <= citing_year <= 1999:
            citing_old[split] += 1
        if excluded and cid in excluded:
            excluded_found.append(cid)
    return {
        "filas": len(ids), "ids_unicos": len(counts),
        "ids_duplicados": sum(n - 1 for n in counts.values()),
        "por_split_ids_unicos": {s: split_counts[s] for s in SPLITS},
        "fuera_de_splits_o_desconocidos": len(unknown),
        "ejemplos_fuera_de_splits": unknown[:20],
        "targetcit_invalido": len(markers_invalid),
        "citado_1980_1999_por_split": {s: cited_old[s] for s in SPLITS},
        "citante_1980_1999_por_split": {s: citing_old[s] for s in SPLITS},
        "ids_en_exclusiones_gold": len(excluded_found),
        "ejemplos_en_exclusiones_gold": excluded_found[:20],
    }


def audit(raw: Path, files: dict[str, Path | None], qlora_dir: Path | None = None,
          excluded_files: list[Path] | None = None,
          manifest: Path | None = None) -> dict[str, Any]:
    contexts, index, split_sizes = load_acl(raw)
    excluded: set[str] = set()
    for path in excluded_files or []:
        if path.is_file():
            excluded.update(read_ids(path))
    result: dict[str, Any] = {
        "criterio_split": "año y partición del CITANTE en ACL-200, no del citado",
        "acl_supervisado": split_sizes,
        "total_contextos_contexts_json": len(contexts),
        "exclusiones_gold_ids_unicos": len(excluded),
        "lotes": {},
        "cruces_entre_lotes": {},
        "qlora": {},
    }
    loaded_ids: dict[str, set[str]] = {}
    for name, path in files.items():
        if path is None:
            result["lotes"][name] = {"estado": "no_aportado; no se infiere el método de selección"}
            continue
        ids = read_ids(path)
        loaded_ids[name] = set(ids)
        result["lotes"][name] = {
            "ruta": str(path), "sha256_archivo": sha256_file(path),
            **summarize(ids, contexts, index, excluded),
        }
    if "lote_18000" in loaded_ids and "etiquetas_2700" in loaded_ids:
        base, revisados = loaded_ids["lote_18000"], loaded_ids["etiquetas_2700"]
        result["cruces_entre_lotes"]["etiquetas_2700_vs_lote_18000"] = {
            "en_lote": len(revisados & base),
            "fuera_de_lote": len(revisados - base),
            "ejemplos_fuera_de_lote": sorted(revisados - base)[:20],
        }
    if "antiguas_595" in loaded_ids and "lote_18000" in loaded_ids:
        antiguos, base = loaded_ids["antiguas_595"], loaded_ids["lote_18000"]
        result["cruces_entre_lotes"]["antiguas_595_vs_lote_18000"] = {
            "en_lote": len(antiguos & base), "fuera_de_lote": len(antiguos - base),
        }
    if "gold_nuevo" in loaded_ids and "lote_18000" in loaded_ids:
        result["cruces_entre_lotes"]["gold_nuevo_en_lote_18000"] = len(
            loaded_ids["gold_nuevo"] & loaded_ids["lote_18000"]
        )
    if manifest is not None:
        if not manifest.is_file():
            raise FileNotFoundError(manifest)
        data = json.loads(manifest.read_text(encoding="utf-8-sig"))
        if not isinstance(data, dict):
            raise ValueError("El manifiesto de jueces debe ser un objeto JSON")
        result["manifiesto_jueces"] = {"ruta": str(manifest),
            "sha256_archivo": sha256_file(manifest),
            "campos_declarados": sorted(k for k, v in data.items() if v not in (None, "", [], {})),
            "campos_pendientes": sorted(k for k, v in data.items() if v in (None, "", [], {}))}
    else:
        result["manifiesto_jueces"] = {"estado": "no aportado; versión Haiku, prompt y GPU no verificados"}
    if qlora_dir is not None:
        for name in QLORA_NAMES:
            path = qlora_dir / name
            result["qlora"][name] = {
                "existe_en_ruta_consultada": path.exists(),
                "tipo": "directorio" if path.is_dir() else "archivo" if path.is_file() else None,
                "sha256": sha256_file(path) if path.is_file() else None,
            }
    else:
        result["qlora"] = {"estado": "ruta no proporcionada; no auditado"}
    return result


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--raw", type=Path, default=Path("data/raw"))
    ap.add_argument("--lote-18000", type=Path)
    ap.add_argument("--etiquetas-2700", type=Path)
    ap.add_argument("--antiguas-595", type=Path)
    ap.add_argument("--gold-nuevo", type=Path)
    ap.add_argument("--qlora-dir", type=Path)
    ap.add_argument("--manifest-jueces", type=Path)
    ap.add_argument("--out", type=Path, help="JSON opcional de auditoría (sin contenidos de citas)")
    args = ap.parse_args(argv)
    exclusions = [
        Path("proyecto_de_grado/anotacion/ids_excluir_test_gold.txt"),
        Path("proyecto_de_grado/anotacion/ids_piloto_historico_no_test_final.txt"),
    ]
    report = audit(args.raw, {
        "lote_18000": args.lote_18000,
        "etiquetas_2700": args.etiquetas_2700,
        "antiguas_595": args.antiguas_595,
        "gold_nuevo": args.gold_nuevo,
    }, args.qlora_dir, exclusions, args.manifest_jueces)
    text = json.dumps(report, ensure_ascii=False, indent=2)
    print(text)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
