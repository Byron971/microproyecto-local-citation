"""Genera cola de revisión humana SIN copiar texto ni modificar Test Gold.

Uso: python scripts/generar_cola_certificacion_gold.py --salida artifacts/cola_gold_privada.csv
La salida contiene solo IDs, origen, tarea y estados; debe mantenerse privada.
No sobrescribe archivos existentes.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from scripts.auditar_certificacion_gold import DEFAULT, leer_csv, SOURCE_RULES


def generar(carpeta: Path) -> list[dict]:
    tareas = []
    for fuente, (nombre, _) in SOURCE_RULES.items():
        for r in leer_csv(carpeta / nombre):
            estado_a = r.get("Estado_A", "")
            estado_b = r.get("Estado_B", "")
            if fuente == "una_anotacion":
                prioridad, tarea = "P1", "segunda_anotacion_humana_independiente"
            elif fuente == "discrepancia_opus":
                prioridad, tarea = "P1", "adjudicacion_humana_desacuerdo"
            elif fuente == "solo_opus":
                prioridad, tarea = "P1", "anotacion_humana_independiente"
            elif estado_a != "COMPLETO" or estado_b != "COMPLETO":
                prioridad, tarea = "P2", "revisar_completitud_humana"
            else:
                continue
            tareas.append({
                "context_id": r["context_id"],
                "fuente": fuente,
                "prioridad": prioridad,
                "tarea": tarea,
                "estado_A": estado_a,
                "estado_B": estado_b,
                "acuerdo_opus": r.get("acuerdo_opus", ""),
                "etiqueta_adjudicada": "",
                "revisor": "",
                "fecha_revision": "",
                "justificacion_revision": "",
                "estado_revision": "PENDIENTE",
            })
    return sorted(tareas, key=lambda x: (x["prioridad"], x["fuente"], x["context_id"]))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--carpeta", type=Path, default=DEFAULT)
    ap.add_argument("--salida", required=True, type=Path)
    a = ap.parse_args()
    if a.salida.exists():
        ap.error("La salida ya existe: no se sobrescribe una revision previa.")
    if a.salida.resolve().is_relative_to((Path(__file__).resolve().parents[1] / "proyecto_de_grado/anotacion/test_gold_final").resolve()):
        ap.error("La cola no puede escribirse dentro de la carpeta de fuentes Gold.")
    auditoria = generar(a.carpeta)
    ids = [x["context_id"] for x in auditoria]
    if len(ids) != len(set(ids)):
        ap.error("Hay IDs duplicados en las fuentes: auditar primero.")
    a.salida.parent.mkdir(parents=True, exist_ok=True)
    with a.salida.open("x", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(auditoria[0]) if auditoria else [
            "context_id", "fuente", "prioridad", "tarea", "estado_A", "estado_B",
            "acuerdo_opus", "etiqueta_adjudicada", "revisor", "fecha_revision",
            "justificacion_revision", "estado_revision"])
        w.writeheader()
        w.writerows(auditoria)
    from collections import Counter
    print(json.dumps({"registros_para_revision": len(auditoria),
                      "por_tarea": dict(sorted(Counter(x["tarea"] for x in auditoria).items())),
                      "salida_privada_generada": True}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
