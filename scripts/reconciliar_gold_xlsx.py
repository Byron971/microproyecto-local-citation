"""Reconcilia cinco hojas TestGold_v3 con el Gold sin modificar los originales.

Produce únicamente resumen agregado por defecto. Opcionalmente guarda un CSV
PRIVADO con identificadores y estado del par (sin texto ni justificaciones).
No convierte ninguna etiqueta en certificada por el mero acuerdo de clase.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
from pathlib import Path

from openpyxl import load_workbook

NOMBRES = ("Arias", "Caicedo", "Duque", "Pinzon", "Zambrana")
CLASES = {
    "Background", "Gap", "Basis", "Comparison", "Application",
    "Improvement / Modification", "Evidence",
    "Identification of the Originator", "Further Reading",
}
GOLD_DEFAULT = Path(__file__).resolve().parents[1] / "proyecto_de_grado/anotacion/test_gold_final/test_gold_final.csv"


def leer_gold(path: Path) -> dict[str, dict]:
    with path.open(newline="", encoding="utf-8-sig") as fh:
        filas = list(csv.DictReader(fh))
    ids = [f.get("context_id", "") for f in filas]
    if len(ids) != len(set(ids)) or not all(ids):
        raise ValueError("Gold contiene context_id duplicados o vacíos")
    return {f["context_id"]: f for f in filas}


def strval(x: object) -> str:
    return str(x).strip() if x is not None else ""


def extraer_hoja(path: Path, nombre: str) -> dict[str, dict]:
    wb = load_workbook(path, read_only=True, data_only=True)
    try:
        if "Mis_anotaciones" not in wb:
            raise ValueError(f"{nombre}: falta hoja Mis_anotaciones")
        sh = wb["Mis_anotaciones"]
        headers = next(sh.iter_rows(min_row=5, max_row=5, values_only=True))
        columnas = {
            "context_id": 1, "¿Evaluable?": 8,
            "Función principal (una)": 9, "Confianza": 10,
            "Justificación / duda": 11, "Estado": 12,
        }
        for k, i in columnas.items():
            if i >= len(headers) or strval(headers[i]) != k:
                raise ValueError(f"{nombre}: columna {i+1} no es {k!r}")
        rows = {}
        for cells in sh.iter_rows(min_row=6, values_only=True):
            cid = strval(cells[1]) if len(cells) > 1 else ""
            if not cid:
                continue
            if cid in rows:
                raise ValueError(f"{nombre}: context_id duplicado")
            campo = lambda i: strval(cells[i]) if len(cells) > i else ""
            evaluabilidad = campo(8)
            etiqueta = campo(9)
            confianza = campo(10)
            justificacion = campo(11)
            estado_excel = campo(12)
            # Independiente de fórmulas y caches de Estado: campos realmente diligenciados.
            etiqueta_valida = (etiqueta in CLASES
                              if evaluabilidad in ("Evaluable", "Ambiguo")
                              else not etiqueta and evaluabilidad == "No evaluable")
            completo = bool(etiqueta_valida and justificacion and (
                confianza if evaluabilidad in ("Evaluable", "Ambiguo") else True
            ))
            rows[cid] = {
                "anotador": nombre,
                "evaluabilidad": evaluabilidad,
                "etiqueta": etiqueta,
                "confianza": confianza,
                "completo_por_campos": completo,
                "estado_excel": estado_excel,
                "justificacion_presente": bool(justificacion),
            }
        return rows
    finally:
        wb.close()


def inspeccionar(xlsx_dir: Path, gold_path: Path) -> tuple[dict, list[dict]]:
    gold = leer_gold(gold_path)
    anotaciones: dict[str, list[dict]] = defaultdict(list)
    por_anotador = {}
    h = {}
    for nombre in NOMBRES:
        archivo = xlsx_dir / f"TestGold_v3_{nombre}.xlsx"
        if not archivo.is_file():
            raise FileNotFoundError(f"Falta {archivo.name}")
        rows = extraer_hoja(archivo, nombre)
        h[nombre] = hashlib.sha256(archivo.read_bytes()).hexdigest()
        por_anotador[nombre] = {
            "asignados": len(rows),
            "completos_por_campos": sum(x["completo_por_campos"] for x in rows.values()),
            "estado_excel_completo": sum(x["estado_excel"] == "COMPLETO" for x in rows.values()),
            "id_fuera_gold": sum(cid not in gold for cid in rows),
        }
        for cid, x in rows.items():
            if cid in gold:
                anotaciones[cid].append(x)
    tareas = []
    agregados = Counter()
    por_fuente = defaultdict(Counter)
    for cid, g in gold.items():
        entries = anotaciones.get(cid, [])
        completos = [e for e in entries if e["completo_por_campos"]]
        origen = g["fuente"]
        etiquetas = [(e["etiqueta"] if e["evaluabilidad"] != "No evaluable" else "No evaluable")
                     for e in completos]
        if len(entries) != 2:
            categoria = "asignacion_incompleta_o_duplicada"
        elif len(completos) < 2:
            categoria = "requiere_completar_anotaciones"
        elif etiquetas[0] != etiquetas[1]:
            categoria = "doble_completa_en_desacuerdo"
        elif etiquetas[0] != g["etiqueta"]:
            categoria = "doble_acuerdo_difiere_gold"
        else:
            categoria = "doble_completa_acuerda_gold"
        agregados[categoria] += 1
        por_fuente[origen][categoria] += 1
        tareas.append({
            "context_id": cid,
            "fuente_gold": origen,
            "anotadores_asignados": "|".join(e["anotador"] for e in entries),
            "n_registros_excel": len(entries),
            "n_completos_por_campos": len(completos),
            "categoria": categoria,
            "etiqueta_final_verificada_por_humano": "",
            "estado_revision": "PENDIENTE",
        })
    reporte = {
        "universo_gold": len(gold),
        "criterio_completo": "Evaluable/Ambiguo: clase valida, confianza y justificacion; No evaluable: sin clase y con justificacion; Estado Excel no basta.",
        "por_anotador": por_anotador,
        "por_categoria": dict(sorted(agregados.items())),
        "por_fuente_y_categoria": {k: dict(sorted(v.items())) for k, v in sorted(por_fuente.items())},
        "sha256_excel": h,
        "sin_certificar": True,
        "nota": "Coincidir en la etiqueta no certifica independencia del voto ni validez semantica; revisar adjudicaciones y procedencia.",
    }
    return reporte, tareas


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--xlsx-dir", type=Path, required=True)
    p.add_argument("--gold", type=Path, default=GOLD_DEFAULT)
    p.add_argument("--reporte", type=Path, help="JSON agregado, sin texto ni IDs")
    p.add_argument("--cola", type=Path, help="CSV PRIVADO con IDs, no subir a Git")
    a = p.parse_args()
    try:
        reporte, tareas = inspeccionar(a.xlsx_dir, a.gold)
        if a.reporte and a.reporte.exists():
            p.error("El reporte ya existe; no sobrescribir")
        if a.cola and a.cola.exists():
            p.error("La cola ya existe; no sobrescribir")
        if a.reporte:
            a.reporte.parent.mkdir(parents=True, exist_ok=True)
            a.reporte.write_text(json.dumps(reporte, ensure_ascii=False, indent=2), encoding="utf-8")
        if a.cola:
            a.cola.parent.mkdir(parents=True, exist_ok=True)
            with a.cola.open("x", encoding="utf-8-sig", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=list(tareas[0]))
                writer.writeheader()
                writer.writerows(tareas)
        print(json.dumps(reporte, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, OSError) as exc:
        print(json.dumps({"error": f"{type(exc).__name__}: {exc}"}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
