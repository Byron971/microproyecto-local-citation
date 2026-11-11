"""Compara dos carpetas de corrida (p. ej. CPU vs CUDA, o frio vs caliente). Python puro, sin torch.

Uso: python -m recuperacion_densa.comparar_corridas CARPETA_A CARPETA_B [--salida out.json]
La comparacion de rankings se hace sobre los contextos comunes (scibert, top3.csv)."""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path


def _top3(carpeta: Path) -> dict[str, list[tuple[str, float]]]:
    res: dict[str, list[tuple[int, str, float]]] = defaultdict(list)
    with (carpeta / "top3.csv").open(encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            if r["metodo"] == "scibert":
                res[r["context_id"]].append((int(r["posicion"]), r["chunk_id"], float(r["puntaje"])))
    return {c: [(ch, p) for _, ch, p in sorted(v)] for c, v in res.items()}


def _json(carpeta: Path, nombre: str) -> dict:
    return json.loads((carpeta / nombre).read_text(encoding="utf-8"))


def _igual_bytes(a: Path, b: Path, nombre: str) -> bool:
    return (a / nombre).read_bytes() == (b / nombre).read_bytes()


def _latencias(carpeta: Path) -> dict:
    lat = _json(carpeta, "latencias_resumen.json")
    emb = lat["embedding_articulo"]
    return {"embedding_articulo": {k: emb.get(k) for k in ("n", "p50", "p95")},
            "consulta_densa": {k: lat["consulta_densa"].get(k) for k in ("n", "p50", "p95")},
            "bm25": {k: lat["bm25"].get(k) for k in ("n", "p50", "p95")},
            "carga_modelo_s": lat.get("carga_modelo_s"),
            "memoria_gpu_max_mb": lat.get("memoria_gpu_max_mb"),
            "device": lat.get("codificador", {}).get("device"),
            "chunks_en_cache": emb.get("chunks_en_cache")}


def comparar(a: Path, b: Path) -> dict:
    ta, tb = _top3(a), _top3(b)
    comunes = sorted(set(ta) & set(tb))
    if not comunes:
        raise ValueError("Las corridas no comparten contextos.")
    top1 = sum(ta[c][0][0] == tb[c][0][0] for c in comunes)
    conjunto = sum({x for x, _ in ta[c]} == {x for x, _ in tb[c]} for c in comunes)
    orden = sum([x for x, _ in ta[c]] == [x for x, _ in tb[c]] for c in comunes)
    dif = max((abs(pa - pb) for c in comunes for (xa, pa), (xb, pb) in zip(ta[c], tb[c])
               if xa == xb), default=0.0)
    return {
        "contextos": len(comunes),
        "contextos_a": len(ta), "contextos_b": len(tb),
        "mismo_top1": top1, "mismo_conjunto_top3": conjunto, "mismo_orden_top3": orden,
        "max_dif_coseno_abs": dif,
        "resumen_json_identico": _igual_bytes(a, b, "resumen.json") if len(ta) == len(tb) else None,
        "top3_csv_identico": _igual_bytes(a, b, "top3.csv"),
        "latencias_s": {"a": _latencias(a), "b": _latencias(b)},
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("a", type=Path)
    ap.add_argument("b", type=Path)
    ap.add_argument("--salida", type=Path)
    args = ap.parse_args(argv)
    try:
        doc = comparar(args.a, args.b)
    except (OSError, KeyError, ValueError, json.JSONDecodeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    texto = json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.salida:
        with args.salida.open("x", encoding="utf-8") as f:
            f.write(texto)
    else:
        print(texto, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
