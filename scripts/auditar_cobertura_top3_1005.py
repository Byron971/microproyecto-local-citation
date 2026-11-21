"""Audita cobertura exhaustiva de pares (context_id, chunk_id) Top-3.

Lee corpus privado y etiquetas, sin mostrar textos/IDs ni modificar originales.
Valida que el universo anotado sea exactamente el universo de chunks del
corpus exportado, no solo el pool Top-3 de los recuperadores.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

from scripts.recalcular_top3_etiquetas_finales import cargar_etiquetas, cargar_rankings


def hash_archivo(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def auditar(corpus: dict, etiquetas: dict, rankings: dict[str, dict] | None = None) -> dict:
    if not isinstance(corpus, dict) or not isinstance(corpus.get("casos"), list):
        raise ValueError("Corpus sin lista de casos")
    casos = corpus["casos"]
    if not casos:
        raise ValueError("Corpus sin consultas")
    corpus_pares = set()
    corpus_ids = set()
    n_ch = []
    for caso in casos:
        if not isinstance(caso, dict):
            raise ValueError("Caso inválido")
        cid = caso.get("context_id")
        chunks = caso.get("chunks")
        if not isinstance(cid, str) or not cid or cid in corpus_ids:
            raise ValueError("Context_id ausente o duplicado en corpus")
        if not isinstance(chunks, list) or not chunks:
            raise ValueError("Caso sin lista de chunks")
        corpus_ids.add(cid)
        vistos = set()
        for ch in chunks:
            chunk_id = ch.get("chunk_id") if isinstance(ch, dict) else None
            if not isinstance(chunk_id, str) or not chunk_id or chunk_id in vistos:
                raise ValueError("Chunk inválido o duplicado en corpus")
            vistos.add(chunk_id)
            corpus_pares.add((cid, chunk_id))
        n_ch.append(len(vistos))
    etiqueta_pares = {(cid, chunk_id) for cid, chunks in etiquetas.items() for chunk_id in chunks}
    faltan = corpus_pares - etiqueta_pares
    sobran = etiqueta_pares - corpus_pares
    positivos_por_caso = Counter(cid for cid, chunks in etiquetas.items() for v in chunks.values() if v == 1)
    salida = {
        "estado": "exhaustivo" if not faltan and not sobran else "incompleto",
        "consultas_corpus": len(corpus_ids),
        "consultas_etiquetas": len(etiquetas),
        "pares_corpus": len(corpus_pares),
        "pares_etiquetas": len(etiqueta_pares),
        "pares_sin_etiqueta": len(faltan),
        "etiquetas_fuera_corpus": len(sobran),
        "min_chunks_consulta": min(n_ch),
        "max_chunks_consulta": max(n_ch),
        "consultas_con_positivos": sum(bool(positivos_por_caso[cid]) for cid in corpus_ids),
        "consultas_sin_positivos": sum(not positivos_por_caso[cid] for cid in corpus_ids),
        "relevantes": sum(sum(chunks.values()) for chunks in etiquetas.values()),
        "relevancia_exhaustiva_en_corpus": not faltan and not sobran,
        "nota": "Exhaustividad con respecto a chunks de este corpus, no al texto OCL original fuera del fragmentador.",
    }
    if rankings:
        detalles = {}
        for modelo, pred in rankings.items():
            validos = 0
            fuera = 0
            faltan_consultas = len(corpus_ids - set(pred))
            extra_consultas = len(set(pred) - corpus_ids)
            repetidos = 0
            for cid, rank in pred.items():
                if len(rank) != len(set(rank)):
                    repetidos += 1
                if cid not in corpus_ids:
                    continue
                permitidos = {ch for ctx, ch in corpus_pares if ctx == cid}
                for ch in rank[:3]:
                    if ch in permitidos:
                        validos += 1
                    else:
                        fuera += 1
            detalles[modelo] = {
                "consultas": len(pred),
                "faltan_consultas": faltan_consultas,
                "sobran_consultas": extra_consultas,
                "top3_chunks_validos": validos,
                "top3_chunks_fuera_corpus": fuera,
                "consultas_con_rankings_duplicados": repetidos,
            }
        salida["rankings"] = detalles
        salida["rankings_validos"] = all(
            v["faltan_consultas"] == 0 and v["sobran_consultas"] == 0
            and v["top3_chunks_fuera_corpus"] == 0 and v["consultas_con_rankings_duplicados"] == 0
            for v in detalles.values()
        )
    return salida


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--corpus", type=Path, required=True)
    p.add_argument("--etiquetas", type=Path, required=True)
    p.add_argument("--bm25", type=Path)
    p.add_argument("--scibert", type=Path)
    p.add_argument("--salida", type=Path, required=True)
    args = p.parse_args()
    if args.salida.exists():
        p.error("La salida ya existe, no se sobrescribe")
    try:
        doc = json.loads(args.corpus.read_text(encoding="utf-8-sig"))
        labels = cargar_etiquetas(args.etiquetas)
        ranks = {}
        for nombre, path in (("BM25", args.bm25), ("SciBERT", args.scibert)):
            if path:
                ranks[nombre] = cargar_rankings(path)
        resultado = auditar(doc, labels, ranks or None)
        resultado["sha256"] = {
            "corpus": hash_archivo(args.corpus),
            "etiquetas": hash_archivo(args.etiquetas),
            **{nombre: hash_archivo(path) for nombre, path in
               (("BM25", args.bm25), ("SciBERT", args.scibert)) if path},
        }
        args.salida.parent.mkdir(parents=True, exist_ok=True)
        args.salida.write_text(json.dumps(resultado, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(resultado, ensure_ascii=False, indent=2))
        return 0 if resultado["relevancia_exhaustiva_en_corpus"] and resultado.get("rankings_validos", True) else 2
    except (ValueError, TypeError, KeyError, OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)[:400]}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
