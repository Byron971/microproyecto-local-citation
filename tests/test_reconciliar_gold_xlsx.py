"""Pruebas sintéticas de reconciliación de hojas, sin usar Gold humano real."""
import csv
from pathlib import Path
from openpyxl import Workbook

from scripts.reconciliar_gold_xlsx import extraer_hoja, inspeccionar, NOMBRES


def crear_excel(path, filas):
    wb = Workbook()
    ws = wb.active
    ws.title = "Mis_anotaciones"
    headers = [None, "context_id", None, None, None, None, None, None,
               "¿Evaluable?", "Función principal (una)", "Confianza",
               "Justificación / duda", "Estado"]
    for i, item in enumerate(headers, start=1):
        ws.cell(5, i, item)
    for row, (cid, eval_, label, conf, just, estado) in enumerate(filas, start=6):
        for col, value in ((2, cid), (9, eval_), (10, label), (11, conf),
                           (12, just), (13, estado)):
            ws.cell(row, col, value)
    wb.save(path)


def test_detecta_completitud_sin_confiar_en_estado(tmp_path):
    p = tmp_path / "TestGold_v3_Arias.xlsx"
    crear_excel(p, [("a", "Evaluable", "Background", "Alta", "Justificado", None),
                    ("b", "Evaluable", "Evidence", "", "", "COMPLETO"),
                    ("c", "No evaluable", None, "", "Contexto imposible", None)])
    r = extraer_hoja(p, "Arias")
    assert r["a"]["completo_por_campos"]
    assert not r["b"]["completo_por_campos"]
    assert r["c"]["completo_por_campos"]


def test_reconciliacion_y_desacuerdo(tmp_path):
    d = tmp_path / "xlsx"
    d.mkdir()
    crear_excel(d / "TestGold_v3_Arias.xlsx",
                [("a", "Evaluable", "Background", "Alta", "Justificación A", "COMPLETO"),
                 ("b", "Evaluable", "Background", "Alta", "Justificación A", None)])
    crear_excel(d / "TestGold_v3_Caicedo.xlsx",
                [("a", "Evaluable", "Background", "Media", "Justificación B", "COMPLETO"),
                 ("b", "Evaluable", "Evidence", "Media", "Justificación B", None)])
    for n in NOMBRES[2:]:
        crear_excel(d / f"TestGold_v3_{n}.xlsx", [])
    g = tmp_path / "gold.csv"
    with g.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["context_id", "fuente", "etiqueta"])
        w.writeheader()
        w.writerows([{"context_id": "a", "fuente": "concordancia", "etiqueta": "Background"},
                     {"context_id": "b", "fuente": "discrepancia_opus", "etiqueta": "Background"}])
    resumen, cola = inspeccionar(d, g)
    assert resumen["por_categoria"]["doble_completa_acuerda_gold"] == 1
    assert resumen["por_categoria"]["doble_completa_en_desacuerdo"] == 1
    assert all(x["etiqueta_final_verificada_por_humano"] == "" for x in cola)
