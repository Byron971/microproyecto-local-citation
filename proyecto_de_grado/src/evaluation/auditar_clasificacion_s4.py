"""S4.1: auditoría SOLO LECTURA de C1, C2 y SciBERT sobre train.

No hace inferencia, no consulta modelos, no asigna etiquetas humanas ni mide F1.
Los artefactos de salida son exploratorios y se guardan fuera del repositorio Git.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
import math
from pathlib import Path

ETIQUETAS = (
    "Background", "Gap", "Basis", "Comparison", "Application",
    "Improvement / Modification", "Evidence",
    "Identification of the Originator", "Further Reading",
)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def leer_objeto(path: Path) -> tuple[dict, str]:
    raw = path.read_bytes()
    obj = json.loads(raw.decode("utf-8-sig"))
    if not isinstance(obj, dict):
        raise ValueError(f"Se esperaba un objeto JSON en {path}")
    return obj, digest(raw)


def leer_jsonl(path: Path, *, campo: str) -> tuple[dict[str, dict], str]:
    raw = path.read_bytes()
    rows: dict[str, dict] = {}
    for num, line in enumerate(raw.decode("utf-8-sig").splitlines(), 1):
        if not line.strip():
            continue
        r = json.loads(line)
        if not isinstance(r, dict):
            raise ValueError(f"Registro no válido en {path}:{num}")
        cid = r.get(campo)
        if not isinstance(cid, str) or not cid or cid in rows:
            raise ValueError(f"ID inválido o repetido en {path}:{num}: {cid!r}")
        rows[cid] = r
    if not rows:
        raise ValueError(f"No hay registros en {path}")
    return rows, digest(raw)


def _validar_ids(indexes: dict[str, dict[str, dict]]) -> set[str]:
    referencia = set(next(iter(indexes.values())))
    for nombre, indice in indexes.items():
        if set(indice) != referencia:
            raise ValueError(f"IDs no coinciden en {nombre}; no hacer comparación parcial")
    return referencia


def _revisar_registro(r: dict, nombre: str, cid: str, huella: str, modelo: str, modo: str) -> None:
    if r.get("id") != cid or r.get("split") != "train":
        raise ValueError(f"{nombre}: ID o split inválido en {cid}")
    if r.get("response_format") != "label" or r.get("evidence_mode") != modo:
        raise ValueError(f"{nombre}: configuración no corresponde a {modo} en {cid}")
    if r.get("model") != modelo or r.get("run_fingerprint") != huella:
        raise ValueError(f"{nombre}: modelo o fingerprint incorrecto en {cid}")
    if r.get("is_human_label") is not False:
        raise ValueError(f"{nombre}: no se admiten etiquetas humanas en S4.1")
    if r.get("status") == "ok" and r.get("suggested_label") not in ETIQUETAS:
        raise ValueError(f"{nombre}: etiqueta automática fuera de taxonomía en {cid}")
    if r.get("status") != "ok" and r.get("suggested_label") is not None:
        raise ValueError(f"{nombre}: no atribuir etiqueta a una predicción fallida en {cid}")
    if r.get("status") not in ("ok", "parse_error", "provider_error", "ambiguo"):
        raise ValueError(f"{nombre}: estado desconocido en {cid}")


def auditar(*, corpus: Path, retrieval: Path, c1: Path, c2: Path,
            resumen_c1: Path, resumen_c2: Path) -> tuple[dict, list[dict]]:
    casos, hash_corpus = leer_jsonl(corpus, campo="id")
    r1, hash_c1 = leer_jsonl(c1, campo="id")
    r2, hash_c2 = leer_jsonl(c2, campo="id")
    rep, hash_rep = leer_objeto(retrieval)
    s1, hash_s1 = leer_objeto(resumen_c1)
    s2, hash_s2 = leer_objeto(resumen_c2)
    if rep.get("tipo") != "comparacion_tecnica_train_s2_8_no_gold":
        raise ValueError("Informe de recuperación incompatible con S2.8")
    if rep.get("sha256_entrada") != hash_corpus:
        raise ValueError("El SHA256 del corpus no coincide con el informe S2.8")
    if rep.get("resumen", {}).get("metricas_gold_calculadas") is not False:
        raise ValueError("El informe S2.8 debe declarar ausencia de métricas Gold")
    if not isinstance(rep.get("resultados"), list):
        raise ValueError("Informe S2.8 sin lista de resultados")
    ranking = {}
    for fila in rep["resultados"]:
        if not isinstance(fila, dict):
            raise ValueError("Fila de S2.8 no es objeto")
        cid = fila.get("context_id")
        if not isinstance(cid, str) or not cid or cid in ranking:
            raise ValueError("Informe S2.8 con context_id repetido o ausente")
        ranking[cid] = fila
    ids = _validar_ids({"corpus": casos, "C1": r1, "C2": r2, "SciBERT": ranking})
    if s1.get("input_sha256") != hash_corpus or s2.get("input_sha256") != hash_corpus:
        raise ValueError("Los resúmenes C1/C2 no provienen del mismo corpus")
    if s2.get("reporte_s2_8_sha256") != hash_rep:
        raise ValueError("El resumen C2 no corresponde al informe S2.8 exacto")
    if s1.get("response_format") != "label" or s1.get("evidence_mode") != "none":
        raise ValueError("El resumen C1 no corresponde a etiqueta directa sin evidencia")
    if s2.get("response_format") != "label" or s2.get("evidence_mode") != "scibert_top3":
        raise ValueError("El resumen C2 no corresponde a SciBERT Top-3")
    modelo = s1.get("model")
    if not isinstance(modelo, str) or not modelo or modelo != s2.get("model"):
        raise ValueError("C1 y C2 no usaron el mismo identificador de modelo")
    huella1, huella2 = s1.get("run_fingerprint"), s2.get("run_fingerprint")
    if not isinstance(huella1, str) or not isinstance(huella2, str) or not huella1 or not huella2:
        raise ValueError("Faltan fingerprints de los experimentos")

    estados1, estados2 = Counter(), Counter()
    clases1, clases2 = Counter(), Counter()
    transiciones = Counter()
    por_articulo = defaultdict(lambda: {"total": 0, "pareados_validos": 0, "basis_c1": 0, "basis_c2": 0, "cambios": 0})
    diferencias = []
    iguales = pareados = 0
    for cid in sorted(ids):
        caso, a, b, f = casos[cid], r1[cid], r2[cid], ranking[cid]
        if caso.get("split") != "train" or str(caso.get("citation_context", "")).count("TARGETCIT") != 1:
            raise ValueError(f"Contexto sin split train/TARGETCIT único: {cid}")
        paper = caso.get("cited_id")
        if not isinstance(paper, str) or not paper or f.get("cited_id") != paper or f.get("split") != "train":
            raise ValueError(f"Artículo/split SciBERT incoherente en {cid}")
        _revisar_registro(a, "C1", cid, huella1, modelo, "none")
        _revisar_registro(b, "C2", cid, huella2, modelo, "scibert_top3")
        if a.get("retrieved_chunks") not in (None, []):
            raise ValueError(f"C1 incorporó evidencia Top-3 inesperada en {cid}")
        chunks = caso.get("cited_chunks")
        if not isinstance(chunks, list) or not chunks:
            raise ValueError(f"Faltan chunks para {cid}")
        por_id = {}
        for ch in chunks:
            if not isinstance(ch, dict) or not isinstance(ch.get("chunk_id"), str) or not ch["chunk_id"] or ch["chunk_id"] in por_id or not isinstance(ch.get("texto"), str):
                raise ValueError(f"Chunks inválidos o duplicados en {cid}")
            por_id[ch["chunk_id"]] = ch
        top = f.get("scibert_top3")
        trazas = b.get("retrieved_chunks")
        if not isinstance(top, list) or not isinstance(trazas, list) or len(top) != len(trazas) or not (1 <= len(top) <= 3):
            raise ValueError(f"Ranking/evidencias incompletas en {cid}")
        vistos = set()
        for position, (sel, tra) in enumerate(zip(top, trazas), 1):
            ck = sel.get("chunk_id")
            if ck not in por_id or ck in vistos or tra.get("chunk_id") != ck or tra.get("cited_id") != paper or tra.get("posicion") != position:
                raise ValueError(f"C2 recuperó fragmentos ajenos, repetidos o desordenados en {cid}")
            if tra.get("text_sha256") != digest(por_id[ck]["texto"].encode("utf-8")):
                raise ValueError(f"C2 tiene huella de texto distinta en {cid}")
            if tra.get("similitud_coseno_no_calibrada") != sel.get("similitud_coseno"):
                raise ValueError(f"C2 tiene una similitud diferente al informe S2.8 en {cid}")
            vistos.add(ck)
        estados1[a["status"]] += 1
        estados2[b["status"]] += 1
        pa = por_articulo[paper]
        pa["total"] += 1
        if a["status"] != "ok" or b["status"] != "ok":
            continue
        pareados += 1
        pa["pareados_validos"] += 1
        la, lb = a["suggested_label"], b["suggested_label"]
        clases1[la] += 1
        clases2[lb] += 1
        pa["basis_c1"] += int(la == "Basis")
        pa["basis_c2"] += int(lb == "Basis")
        if la == lb:
            iguales += 1
        else:
            transiciones[(la, lb)] += 1
            pa["cambios"] += 1
            diferencias.append({
                "context_id": cid, "cited_id": paper,
                "etiqueta_c1": la, "etiqueta_c2": lb,
                "top3_chunk_ids": ";".join(r["chunk_id"] for r in top),
            })

    def concentracion(counts: Counter) -> dict:
        n = sum(counts.values())
        if not n:
            return {"basis_count": 0, "basis_pct": None, "entropia_bits": None, "clases_predichas": 0}
        values = [counts.get(et, 0) / n for et in ETIQUETAS]
        entropy = -sum(p * math.log2(p) for p in values if p)
        return {"basis_count": counts["Basis"], "basis_pct": round(100 * counts["Basis"] / n, 2),
                "entropia_bits": round(entropy, 4), "clases_predichas": sum(bool(x) for x in values)}

    resultado = {
        "tipo": "auditoria_exploratoria_train_s4_1_no_gold",
        "total_contextos_train": len(ids),
        "articulos_citados": len(por_articulo),
        "modelo_clasificador": modelo,
        "model_scibert": rep.get("modelo"),
        "revision_scibert": rep.get("modelo_commit_resuelto"),
        "fuentes_sha256": {"corpus": hash_corpus, "scibert_retrieval": hash_rep, "c1": hash_c1,
                           "c2": hash_c2, "c1_resumen": hash_s1, "c2_resumen": hash_s2},
        "estados_c1": dict(sorted(estados1.items())),
        "estados_c2": dict(sorted(estados2.items())),
        "casos_pareados_validos": pareados,
        "casos_cambiados": len(diferencias),
        "casos_iguales": iguales,
        "cambio_pct_sobre_pareados": round(100 * len(diferencias) / pareados, 2) if pareados else None,
        "distribucion_c1": {e: clases1.get(e, 0) for e in ETIQUETAS},
        "distribucion_c2": {e: clases2.get(e, 0) for e in ETIQUETAS},
        "concentracion_c1": concentracion(clases1),
        "concentracion_c2": concentracion(clases2),
        "transiciones": [ {"desde": a, "hacia": b, "cantidad": n} for (a, b), n in sorted(transiciones.items(), key=lambda kv: (-kv[1], kv[0])) ],
        "por_articulo_citado": {pid: por_articulo[pid] for pid in sorted(por_articulo)},
        "metricas_gold_calculadas": False,
        "f1_macro": None,
        "observacion": "Concordancia entre salidas automáticas: NO equivale a precisión, F1 ni acuerdo entre anotadores. Corpus solo train; artículos pueden repetirse entre consultas.",
    }
    return resultado, diferencias


def guardar(result: dict, diferencias: list[dict], outdir: Path) -> list[Path]:
    paths = [outdir / "auditoria_s4.json", outdir / "transiciones_s4.csv", outdir / "resumen_s4.md"]
    if any(p.exists() for p in paths):
        raise FileExistsError("Existen salidas S4: elija --out distinto; nunca sobrescribir evidencia histórica")
    outdir.mkdir(parents=True, exist_ok=True)
    with paths[0].open("x", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
        f.write("\n")
    with paths[1].open("x", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=("context_id", "cited_id", "etiqueta_c1", "etiqueta_c2", "top3_chunk_ids"))
        w.writeheader()
        w.writerows(diferencias)
    n=result["total_contextos_train"]
    m=result["casos_pareados_validos"]
    with paths[2].open("x", encoding="utf-8") as f:
        f.write("# S4.1 — Auditoría exploratoria C1/C2 (NO Gold)\n\n")
        f.write(f"- Contextos train: {n}; artículos citados: {result['articulos_citados']}.\n")
        f.write(f"- Respuestas pareadas válidas: {m}/{n}.\n")
        f.write(f"- Etiquetas diferentes: {result['casos_cambiados']} ({result['cambio_pct_sobre_pareados']} % sobre los pares válidos).\n")
        f.write(f"- Basis C1: {result['concentracion_c1']['basis_count']} ({result['concentracion_c1']['basis_pct']} %).\n")
        f.write(f"- Basis C2: {result['concentracion_c2']['basis_count']} ({result['concentracion_c2']['basis_pct']} %).\n")
        f.write("\n## Por artículo citado (posible concentración documental)\n\n")
        f.write("| Artículo | Casos | Basis C1 | Basis C2 | Cambios |\n|---|---:|---:|---:|---:|\n")
        for pid, d in result["por_articulo_citado"].items():
            f.write(f"| `{pid}` | {d['total']} | {d['basis_c1']} | {d['basis_c2']} | {d['cambios']} |\n")
        f.write("\n## Límites científicos\n\n")
        f.write("- Solo se auditan predicciones automáticas de `train`; no hay evaluación independiente de generalización.\n")
        f.write("- El desacuerdo C1/C2 y la entropía de predicciones son descriptivos, no F1 ni precisión.\n")
        f.write("- Los contextos de un mismo artículo citado pueden estar relacionados: no asumir independencia estadística.\n")
        f.write("- La muestra es de conveniencia y puede estar sesgada por disponibilidad de ACL OCL.\n")
        f.write("- La política G0.5 mantiene pendiente la revisión humana del 15 % y un Test Gold independiente ratificado.\n")
        f.write("- La mejora de recuperación Top-3 requiere relevancias humanas exhaustivas por consulta/chunk.\n")
        f.write("- Sin inferencias nuevas ni textos de corpus en este informe.\n")
    return paths


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--retrieval", type=Path, required=True)
    parser.add_argument("--c1", type=Path, required=True)
    parser.add_argument("--c2", type=Path, required=True)
    parser.add_argument("--resumen-c1", type=Path, required=True)
    parser.add_argument("--resumen-c2", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    r, dif = auditar(corpus=args.corpus, retrieval=args.retrieval, c1=args.c1, c2=args.c2,
                     resumen_c1=args.resumen_c1, resumen_c2=args.resumen_c2)
    files = guardar(r, dif, args.out)
    print("S4.1 AUDITORIA COMPLETADA — NO GOLD")
    print("Contextos:", r["total_contextos_train"])
    print("Pares válidos:", r["casos_pareados_validos"])
    print("Cambios:", r["casos_cambiados"])
    print("Artículos citados:", r["articulos_citados"])
    for file in files:
        print("Archivo:", file)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
