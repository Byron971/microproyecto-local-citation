"""Audita trazabilidad del Test Gold sin adjudicar etiquetas ni modificar archivos.

Uso: python scripts/auditar_certificacion_gold.py
Opcion: --carpeta PATH --salida PATH (solo resumen anonimizado, opt-in).
Codigo 0 = integridad de consolidacion verificable, NO certificacion humana.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT = ROOT / "proyecto_de_grado/anotacion/test_gold_final"
SOURCE_RULES = {
    "concordancia": ("concordancias.csv", "etiqueta_final"),
    "una_anotacion": ("una_anotacion.csv", "etiqueta_unica"),
    "discrepancia_opus": ("discrepancia_opus.csv", "etiqueta_opus"),
    "solo_opus": ("anotado_opus.csv", "Función principal (una)"),
}
CLASES = {
    "Background", "Gap", "Basis", "Comparison", "Application",
    "Improvement / Modification", "Evidence",
    "Identification of the Originator", "Further Reading",
}
NO_EVALUABLE = "No evaluable"


def leer_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames or "context_id" not in reader.fieldnames:
            raise ValueError(f"CSV sin context_id: {path.name}")
        return list(reader)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def contar_estado(filas: list[dict]) -> dict:
    estados = Counter()
    for fila in filas:
        for campo in ("Estado_A", "Estado_B", "Estado"):
            if campo in fila:
                valor = fila.get(campo, "").strip() or "(vacio)"
                estados[f"{campo}:{valor}"] += 1
    return dict(sorted(estados.items()))


def auditar(carpeta: Path) -> dict:
    errores: list[str] = []
    archivos = {}
    try:
        gold_path = carpeta / "test_gold_final.csv"
        gold = leer_csv(gold_path)
        archivos[gold_path.name] = sha256(gold_path)
        fuentes = {}
        origen = {}
        for fuente, (nombre, col) in SOURCE_RULES.items():
            path = carpeta / nombre
            filas = leer_csv(path)
            archivos[nombre] = sha256(path)
            if filas and col not in filas[0]:
                errores.append(f"{nombre}: falta columna {col}")
            ids = [x["context_id"] for x in filas]
            if len(ids) != len(set(ids)):
                errores.append(f"{nombre}: identificadores duplicados")
            fuentes[fuente] = filas
            for row in filas:
                cid = row["context_id"]
                if cid in origen:
                    errores.append("Hay identificadores presentes en varias fuentes")
                origen[cid] = (fuente, row.get(col, ""), row)
    except (OSError, UnicodeError, csv.Error, ValueError) as exc:
        return {"integridad_consolidacion": False, "errores": [f"Lectura fallida: {type(exc).__name__}"],
                "certificacion_humana": "no_demostrada"}

    ids_gold = [x["context_id"] for x in gold]
    if len(ids_gold) != len(set(ids_gold)):
        errores.append("Gold: identificadores duplicados")
    if set(ids_gold) != set(origen):
        errores.append(f"IDs de Gold y fuentes diferentes: faltantes={len(set(origen)-set(ids_gold))}, sobrantes={len(set(ids_gold)-set(origen))}")

    por_fuente = Counter()
    clases = Counter()
    evaluables = 0
    incoherencias = Counter()
    for row in gold:
        cid = row["context_id"]
        fuente = row.get("fuente", "")
        por_fuente[fuente] += 1
        etiqueta = row.get("etiqueta", "")
        evaluable = row.get("evaluable", "").strip().lower()
        clases[etiqueta] += 1
        if etiqueta not in CLASES | {NO_EVALUABLE}:
            incoherencias["etiqueta_fuera_de_vocabulario"] += 1
        if evaluable not in ("true", "false"):
            incoherencias["evaluable_invalido"] += 1
        elif (evaluable == "true") != (etiqueta in CLASES):
            incoherencias["evaluable_etiqueta_incoherente"] += 1
        if evaluable == "true":
            evaluables += 1
        if cid not in origen:
            continue
        procedencia, etiqueta_fuente, _ = origen[cid]
        if fuente != procedencia:
            incoherencias["fuente_incorrecta"] += 1
        if procedencia == "solo_opus":
            f = origen[cid][2]
            etiqueta_fuente = NO_EVALUABLE if f.get("¿Evaluable?") == NO_EVALUABLE else etiqueta_fuente
        if etiqueta != etiqueta_fuente:
            incoherencias["etiqueta_no_coincide_con_fuente"] += 1

    for k, n in sorted(incoherencias.items()):
        if n:
            errores.append(f"{k}: {n}")
    concordancias = fuentes["concordancia"]
    discrepancias = fuentes["discrepancia_opus"]
    sin_acuerdo = sum(1 for x in discrepancias if x.get("acuerdo_opus") == "Ninguno")
    pendientes = sum(1 for x in fuentes["una_anotacion"]
                     if x.get("Estado_A", "").strip().upper() == "PENDIENTE"
                     or x.get("Estado_B", "").strip().upper() == "PENDIENTE")
    reporte = {
        "integridad_consolidacion": not errores,
        "certificacion_humana": "no_demostrada",
        "criterio": "Una fila procedente de anotacion unica o de Opus no equivale a adjudicacion humana independiente.",
        "errores": errores,
        "total_gold": len(gold),
        "evaluable": evaluables,
        "no_evaluable": len(gold) - evaluables,
        "por_fuente": dict(sorted(por_fuente.items())),
        "clases": dict(sorted(clases.items())),
        "fuentes_totales": {k: len(v) for k, v in sorted(fuentes.items())},
        "concordancias_humanas_reportadas": len(concordancias),
        "anotaciones_unicas_con_estado_pendiente": pendientes,
        "discrepancias_opus_sin_acuerdo_humano": sin_acuerdo,
        "estados_por_fuente": {k: contar_estado(v) for k, v in sorted(fuentes.items())},
        "sha256_archivos": dict(sorted(archivos.items())),
        "nota": "Auditoria estructural; no verifica validez semantica, acuerdo interanotador ni leakage entre documentos.",
    }
    return reporte


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--carpeta", type=Path, default=DEFAULT)
    ap.add_argument("--salida", type=Path, help="Ruta opcional para reporte de resumen JSON")
    args = ap.parse_args()
    resultado = auditar(args.carpeta)
    contenido = json.dumps(resultado, indent=2, ensure_ascii=False)
    print(contenido)
    if args.salida:
        args.salida.parent.mkdir(parents=True, exist_ok=True)
        args.salida.write_text(contenido + "\n", encoding="utf-8")
    return 0 if resultado["integridad_consolidacion"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
