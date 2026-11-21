"""Audita métricas históricas M/S sin entrenar, reetiquetar ni usar Gold en inferencia.

Solo consulta agregados CSV ya versionados; no reconstruye predicciones.
Genera informe JSON anónimo con diferencias descriptivas y denominadores.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
METRICAS = ROOT / "proyecto_de_grado/docs/evidencias_experimentos_10/gold_metricas.csv"
GOLD = ROOT / "proyecto_de_grado/anotacion/test_gold_final/test_gold_final.csv"
RESUMEN_TOP3 = ROOT / "proyecto_de_grado/docs/evidencias_recuperacion_densa_a1/resumen.json"
SUBSETS = {"todo_cob": "evaluable", "humano_cob": "origen humano al menos una vez", "concordancia_cob": "concordancia de clase (no necesariamente formularios completos)"}


def leer_csv(path: Path) -> list[dict]:
    with path.open("r", newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def hash_archivo(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def auditar(metricas: list[dict], gold: list[dict], top3: dict) -> dict:
    problemas = []
    contador = {
        "total": len(gold),
        "evaluables": sum(f.get("evaluable", "").strip().lower() == "true" for f in gold),
        "por_fuente": {f: sum(g.get("fuente") == f for g in gold) for f in sorted(set(g.get("fuente") for g in gold))},
    }
    esperados = {
        "todo_cob": contador["evaluables"],
        "humano_cob": sum(g.get("fuente") in ("concordancia", "una_anotacion", "discrepancia_opus")
                          and g.get("evaluable", "").strip().lower() == "true" for g in gold),
        "concordancia_cob": sum(g.get("fuente") == "concordancia" and g.get("evaluable", "").strip().lower() == "true" for g in gold),
    }
    resultados = {}
    for row in metricas:
        pista, sub = row.get("pista"), row.get("subconjunto")
        if pista not in ("M", "S") or sub not in esperados:
            problemas.append("Pista o subconjunto no reconocido")
            continue
        key = f"{pista}:{sub}"
        if key in resultados:
            problemas.append(f"Fila duplicada: {key}")
            continue
        try:
            n = int(row["n"])
            vals = {k: float(row[k]) for k in ("f1_macro", "f1_micro", "f1_weighted", "accuracy")}
            if not all(math.isfinite(v) and 0 <= v <= 1 for v in vals.values()):
                raise ValueError("Métrica fuera de rango")
        except (ValueError, KeyError, TypeError):
            problemas.append(f"Métrica mal formada: {key}")
            continue
        if n > esperados[sub]:
            problemas.append(f"{key}: n excede universo evaluable")
        resultados[key] = {
            "n": n,
            "universo_evaluable_de_fuente": esperados[sub],
            "casos_no_cubiertos": esperados[sub] - n,
            **vals,
            "condicion": SUBSETS[sub],
        }
    if set(resultados) != {f"{p}:{sub}" for p in ("M", "S") for sub in esperados}:
        problemas.append("Faltan combinaciones M/S × subconjunto")
    comparaciones = {}
    for sub in esperados:
        m, s = resultados.get(f"M:{sub}"), resultados.get(f"S:{sub}")
        if m and s:
            if m["n"] != s["n"]:
                problemas.append(f"{sub}: modelos con denominadores distintos")
            comparaciones[sub] = {
                "n_M": m["n"], "n_S": s["n"],
                "diferencia_macro_f1_S_menos_M": round(s["f1_macro"] - m["f1_macro"], 6),
                "diferencia_accuracy_S_menos_M": round(s["accuracy"] - m["accuracy"], 6),
                "nota": "Diferencia de agregados; no estimador pareado ni prueba de significación",
            }
    validacion = top3.get("validacion", {})
    contraste = top3.get("comparacion", {}).get("micro", {})
    recuperacion = {
        "estado": top3.get("estado"),
        "contextos": validacion.get("contextos"),
        "articulos": validacion.get("articulos"),
        "chunks_unicos": validacion.get("chunks_unicos"),
        "solape_top3_scibert_bm25": contraste.get("solape_3"),
        "integridad_violaciones_reportadas": top3.get("integridad", {}).get("violaciones"),
        "metricas_relevancia": top3.get("metricas_relevancia"),
        "advertencia": "El solape de dos recuperadores no representa Recall@3 ni relevancia humana.",
    }
    if recuperacion["estado"] != "comparacion_tecnica_train_sin_gold":
        problemas.append("El experimento Top-3 no declara TRAIN sin Gold")
    return {
        "integridad_agregados": not problemas,
        "errores": problemas,
        "universo_gold": contador,
        "resultados_historicos": dict(sorted(resultados.items())),
        "comparaciones_descriptivas": comparaciones,
        "recuperacion_train_sin_gold": recuperacion,
        "limitaciones": [
            "Métricas existentes, no evaluación regenerada; falta trazabilidad por context_id de las predicciones.",
            "Las etiquetas de una anotación humana y Opus no forman automáticamente un Gold certificado.",
            "No se demuestra independencia de documentos/pairs ni selección previa de hiperparámetros.",
            "Las comparaciones agregadas no permiten prueba de significación pareada.",
            "El subconjunto concordancia no implica dos formularios humanos completos.",
        ],
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--metricas", type=Path, default=METRICAS)
    p.add_argument("--gold", type=Path, default=GOLD)
    p.add_argument("--top3", type=Path, default=RESUMEN_TOP3)
    p.add_argument("--salida", type=Path)
    a = p.parse_args()
    try:
        resultado = auditar(leer_csv(a.metricas), leer_csv(a.gold), json.loads(a.top3.read_text(encoding="utf-8-sig")))
        resultado["sha256_entradas"] = {p.name: hash_archivo(p) for p in (a.metricas, a.gold, a.top3)}
        contenido = json.dumps(resultado, indent=2, ensure_ascii=False)
        if a.salida:
            if a.salida.exists():
                p.error("La salida ya existe, no se sobrescribirá.")
            a.salida.parent.mkdir(parents=True, exist_ok=True)
            a.salida.write_text(contenido + "\n", encoding="utf-8")
        print(contenido)
        return 0 if resultado["integridad_agregados"] else 1
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as e:
        print(json.dumps({"integridad_agregados": False, "errores": [str(e)[:250]]}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
