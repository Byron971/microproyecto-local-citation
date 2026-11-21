"""Auditoría pareada M/S por context_id sin alterar el Test Gold.

Exige DOS JSONL individuales explícitos de los checkpoints M/S (no asume que
las predicciones A4 antiguas corresponden a los checkpoints actuales).
No publica IDs ni texto: únicamente agregados y hashes. Sin archivos, no
inventa métricas ni hace inferencia.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path

CLASES = (
    "Background", "Gap", "Basis", "Comparison", "Application",
    "Improvement / Modification", "Evidence",
    "Identification of the Originator", "Further Reading",
)
ORIGENES = {"concordancia", "una_anotacion", "discrepancia_opus", "solo_opus"}


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def cargar_predicciones(path: Path, campo: str = "pred_label") -> dict[str, str]:
    pred = {}
    with path.open("r", encoding="utf-8-sig") as f:
        for num, linea in enumerate(f, 1):
            if not linea.strip():
                continue
            obj = json.loads(linea)
            if not isinstance(obj, dict):
                raise ValueError(f"{path.name}: línea {num} no es objeto")
            cid = obj.get("context_id", obj.get("case_id"))
            if campo in ("pred", "pred_ph"):
                indice = obj.get(campo)
                if type(indice) is not int or not 0 <= indice < len(CLASES):
                    raise ValueError(f"{path.name}: línea {num} sin índice válido {campo}")
                etiqueta = CLASES[indice]
            else:
                etiqueta = obj.get(campo)
                if etiqueta is None and campo == "pred_label":
                    etiqueta = obj.get("clase")
            if not isinstance(cid, str) or not cid:
                raise ValueError(f"{path.name}: línea {num} sin context_id")
            if etiqueta not in CLASES:
                raise ValueError(f"{path.name}: línea {num} sin clase válida")
            if obj.get("status", "ok") != "ok":
                raise ValueError(f"{path.name}: línea {num} no reporta status ok")
            if cid in pred:
                raise ValueError(f"{path.name}: context_id duplicado")
            pred[cid] = etiqueta
    if not pred:
        raise ValueError(f"{path.name}: sin predicciones")
    return pred


def cargar_gold(path: Path) -> dict[str, dict]:
    with path.open(newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    ids = [r.get("context_id") for r in rows]
    if any(not i for i in ids) or len(ids) != len(set(ids)):
        raise ValueError("Gold con context_id vacíos o duplicados")
    return {r["context_id"]: r for r in rows}


def metricas(etiquetas: list[str], pred: list[str]) -> dict:
    if len(etiquetas) != len(pred) or not etiquetas:
        raise ValueError("Se requiere evaluación pareada no vacía")
    matriz = [[0] * 9 for _ in range(9)]
    index = {c: i for i, c in enumerate(CLASES)}
    for y, p in zip(etiquetas, pred):
        matriz[index[y]][index[p]] += 1
    por_clase = {}
    for i, c in enumerate(CLASES):
        tp = matriz[i][i]
        soporte = sum(matriz[i])
        predichos = sum(fila[i] for fila in matriz)
        precision = tp / predichos if predichos else 0
        recall = tp / soporte if soporte else 0
        f1 = 2 * tp / (soporte + predichos) if soporte + predichos else 0
        por_clase[c] = {"soporte": soporte, "precision": round(precision, 6),
                        "recall": round(recall, 6), "f1": round(f1, 6)}
    n = len(etiquetas)
    return {
        "n": n,
        "accuracy": round(sum(matriz[i][i] for i in range(9)) / n, 6),
        "macro_f1_9_clases": round(sum(x["f1"] for x in por_clase.values()) / 9, 6),
        "weighted_f1": round(sum(x["f1"] * x["soporte"] for x in por_clase.values()) / n, 6),
        "matriz_confusion": matriz,
        "por_clase": por_clase,
        "nota": "Se incluyen las nueve clases aun si alguna tiene soporte cero.",
    }


def comparar(gold: dict, m: dict, s: dict) -> dict:
    ids_gold = {cid for cid, r in gold.items()
                if r.get("evaluable", "").lower() == "true" and r.get("etiqueta") in CLASES}
    comun = ids_gold & set(m) & set(s)
    if not comun:
        raise ValueError("No hay contextos evaluables emparejados")
    grupos = {"todo_evaluable_emparejado": sorted(comun)}
    for fuente in sorted(ORIGENES):
        grupos[fuente] = sorted(cid for cid in comun if gold[cid].get("fuente") == fuente)
    resultado = {
        "universo_gold_evaluable": len(ids_gold),
        "predicciones_M_total": len(m),
        "predicciones_S_total": len(s),
        "ids_pareados_evaluables": len(comun),
        "solo_M_evaluables": len((ids_gold & set(m)) - set(s)),
        "solo_S_evaluables": len((ids_gold & set(s)) - set(m)),
        "ninguna_prediccion_evaluable": len(ids_gold - (set(m) | set(s))),
        "pred_M_fuera_gold": len(set(m) - set(gold)),
        "pred_S_fuera_gold": len(set(s) - set(gold)),
        "resultados": {},
        "interpretacion": "Métricas descriptivas provisionales condicionadas a etiquetas consolidadas no certificadas.",
    }
    for fuente, ids in grupos.items():
        if not ids:
            resultado["resultados"][fuente] = {"n": 0, "no_calculable": True}
            continue
        y = [gold[cid]["etiqueta"] for cid in ids]
        resultados = {"n": len(ids)}
        for nombre, p in (("M", m), ("S", s)):
            resultados[nombre] = metricas(y, [p[cid] for cid in ids])
        resultados["delta_macro_f1_S_menos_M"] = round(
            resultados["S"]["macro_f1_9_clases"] - resultados["M"]["macro_f1_9_clases"], 6)
        resultados["desacuerdos_predicciones_M_S"] = sum(m[cid] != s[cid] for cid in ids)
        resultado["resultados"][fuente] = resultados
    return resultado


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--gold", type=Path, default=Path("proyecto_de_grado/anotacion/test_gold_final/test_gold_final.csv"))
    ap.add_argument("--pred-m", type=Path, required=True)
    ap.add_argument("--pred-s", type=Path, required=True)
    ap.add_argument("--campo-m", choices=("pred_label", "pred", "pred_ph"), default="pred_label", help="M del notebook 10 usa pred_ph por ajuste PH")
    ap.add_argument("--campo-s", choices=("pred_label", "pred", "pred_ph"), default="pred_label", help="S del notebook 10 usa pred sin ajuste PH")
    ap.add_argument("--salida", type=Path)
    args = ap.parse_args()
    try:
        if args.pred_m.resolve() == args.pred_s.resolve():
            raise ValueError("M y S deben ser dos archivos diferentes")
        gold, m, s = cargar_gold(args.gold), cargar_predicciones(args.pred_m, args.campo_m), cargar_predicciones(args.pred_s, args.campo_s)
        informe = comparar(gold, m, s)
        informe["campos_prediccion"] = {"M": args.campo_m, "S": args.campo_s}
        informe["hashes"] = {"gold": sha(args.gold), "M": sha(args.pred_m), "S": sha(args.pred_s)}
        informe["advertencias"] = [
            "Verificar externamente que M y S provienen de los checkpoints declarados; el nombre del archivo no certifica procedencia.",
            "El reporte no verifica leakage documental ni valida Gold humano.",
            "No reentrena, no selecciona modelo con TEST y no calcula significación estadística.",
        ]
        salida = json.dumps(informe, indent=2, ensure_ascii=False)
        if args.salida:
            if args.salida.exists():
                raise ValueError("Salida existente, no se sobrescribe")
            args.salida.parent.mkdir(parents=True, exist_ok=True)
            args.salida.write_text(salida + "\n", encoding="utf-8")
        print(salida)
        return 0
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as err:
        print(json.dumps({"ok": False, "error": str(err)[:200]}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
