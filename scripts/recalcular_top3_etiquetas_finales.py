"""Recalcula Top-3 de forma local a partir de relevancias finales y rankings privados.

No inventa etiquetas, no rellena ausentes y no sobrescribe resultados existentes.
Admite rankings JSON: mapa {context_id: [chunk_id,...]} o lista de objetos
con context_id y ranking/top3/chunks. Si el esquema difiere, falla con
las claves de ejemplo sin mostrar contexto ni texto científico.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
from pathlib import Path


def _hash(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def cargar_etiquetas(p: Path) -> dict[str, dict[str, int]]:
    casos: dict[str, dict[str, int]] = defaultdict(dict)
    with p.open("r", encoding="utf-8-sig", newline="") as f:
        lector = csv.DictReader(f)
        esperado = {"context_id", "chunk_id", "relevante_0_1"}
        if not esperado <= set(lector.fieldnames or []):
            raise ValueError("CSV de etiquetas sin columnas obligatorias")
        for num, row in enumerate(lector, 2):
            cid, ch = (row[k].strip() for k in ("context_id", "chunk_id"))
            label = row["relevante_0_1"].strip()
            if not cid or not ch or label not in {"0", "1"}:
                raise ValueError(f"Fila {num} incompleta o etiqueta inválida")
            if ch in casos[cid]:
                raise ValueError(f"Fila {num} duplicada")
            casos[cid][ch] = int(label)
    if not casos:
        raise ValueError("CSV vacío")
    return dict(casos)


def _chunk_id(x) -> str:
    if isinstance(x, str):
        return x
    if isinstance(x, dict):
        for k in ("chunk_id", "id", "fragment_id"):
            if isinstance(x.get(k), str):
                return x[k]
    raise ValueError("Ranking sin chunk_id reconocible")


def _top(x) -> list[str]:
    if isinstance(x, list):
        return [_chunk_id(i) for i in x]
    if isinstance(x, dict):
        for k in ("ranking", "top3", "chunks", "resultados", "candidatos", "items", "ranking_top3"):
            if isinstance(x.get(k), list):
                return _top(x[k])
        raise ValueError(f"Ranking por consulta: esquema desconocido. Campos: {sorted(x)[:16]}")
    raise ValueError("Ranking por consulta debe ser lista u objeto")


def cargar_rankings(p: Path) -> dict[str, list[str]]:
    doc = json.loads(p.read_text(encoding="utf-8-sig"))
    if isinstance(doc, dict):
        for k in ("casos", "consultas", "resultados", "rankings", "items"):
            if isinstance(doc.get(k), list):
                doc = doc[k]
                break
            if isinstance(doc.get(k), dict):
                doc = doc[k]
                break
    if isinstance(doc, list):
        out = {}
        for item in doc:
            if not isinstance(item, dict):
                raise ValueError("Fila de ranking no es objeto")
            cid = item.get("context_id") or item.get("case_id") or item.get("id")
            if not isinstance(cid, str) or not cid:
                raise ValueError(f"Ranking sin context_id; campos: {sorted(item)[:16]}")
            if cid in out:
                raise ValueError("Context_id duplicado en ranking")
            out[cid] = _top(item)
        return out
    if isinstance(doc, dict):
        try:
            return {cid: _top(val) for cid, val in doc.items()}
        except ValueError as ex:
            raise ValueError(f"{ex}; campos raíz: {sorted(doc)[:16]}") from ex
    raise ValueError("Esquema JSON de ranking desconocido")


def evaluar(etiquetas, bm25, scibert):
    ids = set(etiquetas)
    if set(bm25) != ids or set(scibert) != ids:
        raise ValueError(
            f"IDs no coinciden: etiquetas={len(ids)}, BM25={len(bm25)}, SciBERT={len(scibert)}, "
            f"faltan_BM25={len(ids-set(bm25))}, faltan_SciBERT={len(ids-set(scibert))}, "
            f"extra_BM25={len(set(bm25)-ids)}, extra_SciBERT={len(set(scibert)-ids)}"
        )
    scores = {"BM25": [], "SciBERT": []}
    positivos = 0
    for cid in sorted(ids):
        gold = {ch for ch, label in etiquetas[cid].items() if label == 1}
        if not gold:
            continue
        positivos += 1
        for nombre, rank in (("BM25", bm25[cid]), ("SciBERT", scibert[cid])):
            if len(rank) != len(set(rank)):
                raise ValueError(f"{nombre}: ranking con chunks duplicados")
            if any(ch not in etiquetas[cid] for ch in rank[:3]):
                raise ValueError(f"{nombre}: chunk fuera del universo anotado")
            primeros = rank[:3]
            acertados = [i for i, ch in enumerate(primeros, 1) if ch in gold]
            scores[nombre].append({
                "hit_at_3": float(bool(acertados)),
                "recall_at_3": len(acertados) / len(gold),
                "mrr_at_3": 1 / acertados[0] if acertados else 0.0,
            })
    if not positivos:
        raise ValueError("No existen consultas con positivos")
    resultados = {}
    for nombre, filas in scores.items():
        resultados[nombre] = {
            "consultas_elegibles": len(filas),
            **{metric: sum(row[metric] for row in filas) / len(filas)
               for metric in ("hit_at_3", "recall_at_3", "mrr_at_3")},
        }
    comparacion = {}
    for metric in ("hit_at_3", "recall_at_3", "mrr_at_3"):
        cnt = Counter()
        for b, s in zip(scores["BM25"], scores["SciBERT"]):
            if b[metric] > s[metric]: cnt["BM25_mejor"] += 1
            elif b[metric] < s[metric]: cnt["SciBERT_mejor"] += 1
            else: cnt["empates"] += 1
        comparacion[metric] = {k: cnt[k] for k in ("BM25_mejor", "SciBERT_mejor", "empates")}
    return {
        "consultas_totales": len(ids),
        "consultas_elegibles": positivos,
        "consultas_sin_positivos": len(ids) - positivos,
        "juicios": sum(map(len, etiquetas.values())),
        "relevantes": sum(sum(row.values()) for row in etiquetas.values()),
        "resultados": resultados,
        "comparacion_consulta_a_consulta": comparacion,
        "limites": [
            "Reproducción sobre etiquetas consolidadas; no certifica doble anotación independiente.",
            "Validar por separado que los 1005 pares representan el universo exhaustivo de candidatos por consulta.",
            "La evaluación es exploratoria: no sustituye el protocolo final de muestreo.",
        ],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--etiquetas", type=Path, required=True)
    ap.add_argument("--bm25", type=Path, required=True)
    ap.add_argument("--scibert", type=Path, required=True)
    ap.add_argument("--salida", type=Path, required=True)
    args = ap.parse_args()
    if args.salida.exists():
        ap.error("La salida ya existe; no se sobrescribe")
    try:
        gold = cargar_etiquetas(args.etiquetas)
        b = cargar_rankings(args.bm25)
        s = cargar_rankings(args.scibert)
        resultado = evaluar(gold, b, s)
        resultado["sha256"] = {k: _hash(p) for k, p in
            (("etiquetas", args.etiquetas), ("BM25", args.bm25), ("SciBERT", args.scibert))}
        args.salida.parent.mkdir(parents=True, exist_ok=True)
        args.salida.write_text(json.dumps(resultado, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(resultado, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)[:600]}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
