"""Auditoría de la tanda 1 del Test Gold: IDs, reparto, doble anotación y anotación a ciegas (issue #97).

Lee el manifiesto del Test Gold y las hojas de Excel repartidas a los anotadores. No lee ninguna
etiqueta del jurado ni las anotaciones de nadie más allá de si la fila está llena: el reporte
cuenta avance, no respuestas. Publica el reparto (qué cita anota cada pareja) sin etiquetas.

Uso, desde la raíz del repositorio:
    python -m proyecto_de_grado.src.data.auditar_tanda1 \
        --manifiesto proyecto_de_grado/anotacion/test_gold_v2/manifiesto_ids.csv \
        --hojas "<carpeta con TestGold_T1_v2_*.xlsx>" \
        --ejemplos proyecto_de_grado/anotacion/taller/items_meta.json \
        --excluir proyecto_de_grado/anotacion/ids_excluir_test_gold.txt \
        --reparto proyecto_de_grado/anotacion/test_gold_v2/reparto_tanda1.csv \
        --reporte proyecto_de_grado/docs/auditoria_tanda1.md
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import zipfile
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime
from itertools import combinations
from pathlib import Path

from proyecto_de_grado.src.data.auditar_jurado import fmt, leer_csv, pct

ENCABEZADOS = ["N°", "context_id", "Contexto original (inglés)", "Contexto en español (ayuda)", "Título citado",
               "Título en español", "Resumen citado", "Resumen en español", "¿Evaluable?", "Función principal (una)",
               "Confianza", "Justificación / duda", "Estado"]   # columnas del cuaderno anotacion_test_gold.ipynb
HOJAS_LIBRO = ["Mis_anotaciones", "Control", "Guia_rapida", "9_funciones", "Ejemplos_explicados"]
ANOTADORES_POR_CITA = 2
PATRON_HOJA = re.compile(r"TestGold_T1_v2_(\w+)\.xlsx$")
PATRON_ID = re.compile(r"[A-Z]\d\d-\d{4}_[A-Z]\d\d-\d{4}_\d+")
M = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
REL = "{http://schemas.openxmlformats.org/package/2006/relationships}Relationship"


def columna(ref: str) -> tuple[int, int]:
    """'J12' -> (12, 9): fila y columna (desde 0) de una celda."""
    letras, fila = re.match(r"([A-Z]+)(\d+)", ref).groups()
    col = 0
    for l in letras:
        col = col * 26 + ord(l) - 64
    return int(fila), col - 1


def leer_xlsx(ruta: str | Path) -> dict[str, list[list[str]]]:
    """Texto de cada hoja de un .xlsx con la librería estándar (el proyecto no depende de openpyxl)."""
    with zipfile.ZipFile(ruta) as z:
        compartidos = []
        if "xl/sharedStrings.xml" in z.namelist():
            compartidos = ["".join(t.text or "" for t in si.iter(f"{M}t"))
                           for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall(f"{M}si")]
        rels = {r.get("Id"): r.get("Target") for r in ET.fromstring(z.read("xl/_rels/workbook.xml.rels")).iter(REL)}
        libro = {}
        for hoja in ET.fromstring(z.read("xl/workbook.xml")).iter(f"{M}sheet"):
            destino = rels[hoja.get(f"{R}id")].lstrip("/")
            celdas = {}
            for c in ET.fromstring(z.read(destino if destino.startswith("xl/") else "xl/" + destino)).iter(f"{M}c"):
                v = c.find(f"{M}v")
                if c.get("t") == "s":
                    valor = compartidos[int(v.text)]
                elif c.get("t") == "inlineStr":
                    valor = "".join(t.text or "" for t in c.iter(f"{M}t"))
                else:
                    valor = v.text if v is not None and v.text else ""   # números y resultados de fórmula
                celdas[columna(c.get("r"))] = valor.strip()
            n_filas = max((f for f, _ in celdas), default=0)
            n_cols = max((c for _, c in celdas), default=-1) + 1
            libro[hoja.get("name")] = [[celdas.get((f, c), "") for c in range(n_cols)] for f in range(1, n_filas + 1)]
        return libro


def tabla_anotacion(filas: list[list[str]]) -> tuple[list[str], list[dict]]:
    """Encabezado de Mis_anotaciones y una fila por cita, con los campos que llena el anotador."""
    i = next(k for k, f in enumerate(filas) if "context_id" in f)
    encabezado = [x for x in filas[i] if x]
    registros = []
    for f in filas[i + 1:]:
        f = f + [""] * (len(ENCABEZADOS) - len(f))
        if f[1]:
            registros.append({"context_id": f[1], "evaluable": f[8], "funcion": f[9], "confianza": f[10],
                              "justificacion": f[11]})
    return encabezado, registros


def estado(r: dict) -> str:
    """La misma regla de la columna Estado de las hojas repartidas."""
    if not r["evaluable"]:
        return "PENDIENTE"
    if r["evaluable"] == "No evaluable":
        return "REGISTRADO" if r["justificacion"] else "REVISAR"
    if r["evaluable"] == "Ambiguo":
        return "COMPLETO" if r["funcion"] and r["justificacion"] else "INCOMPLETO"
    return "COMPLETO" if r["funcion"] and r["confianza"] else "INCOMPLETO"


def auditar(manifiesto: list[dict], libros: dict[str, dict], ejemplos: set[str], excluir: set[str]) -> dict:
    """Comprobaciones del #97 sobre el manifiesto y los libros de cada anotador."""
    tanda1 = [r["context_id"] for r in manifiesto if r["grupo"] == "testgold" and r["tanda"] == "1"]
    gold = {r["context_id"] for r in manifiesto if r["grupo"] == "testgold"}
    asignadas, por_persona, ciego = {}, {}, {}
    for persona, libro in libros.items():
        encabezado, registros = tabla_anotacion(libro["Mis_anotaciones"])
        ids = [r["context_id"] for r in registros]
        estados = Counter(estado(r) for r in registros)
        asignadas[persona] = ids
        por_persona[persona] = {
            "citas": len(ids), "repetidas": len(ids) - len(set(ids)), "fuera_de_tanda1": len(set(ids) - set(tanda1)),
            "terminadas": estados["COMPLETO"] + estados["REGISTRADO"], "pendientes": estados["PENDIENTE"],
            "por_corregir": estados["INCOMPLETO"] + estados["REVISAR"],
            "evaluables_sin_justificacion": sum(1 for r in registros if r["evaluable"] == "Evaluable" and not r["justificacion"]),
        }
        otras = " ".join(" ".join(f) for n, h in libro.items() if n != "Mis_anotaciones" for f in h)
        ciego[persona] = {
            "columnas_esperadas": encabezado == ENCABEZADOS,
            "columnas_extra": [c for c in encabezado if c not in ENCABEZADOS],
            "hojas_extra": [n for n in libro if n not in HOJAS_LIBRO],
            "gold_en_otras_hojas": len(set(PATRON_ID.findall(otras)) & gold),
        }
    cobertura = Counter(cid for ids in asignadas.values() for cid in set(ids))
    parejas = Counter(tuple(sorted(p for p, ids in asignadas.items() if cid in ids)) for cid in cobertura)
    return {
        "tanda1": len(tanda1), "tanda1_unicas": len(set(tanda1)), "asignadas": asignadas, "por_persona": por_persona,
        "cobertura": Counter(cobertura[cid] for cid in tanda1), "sin_hoja": len(set(tanda1) - set(cobertura)),
        "parejas": parejas, "parejas_posibles": list(combinations(sorted(libros), ANOTADORES_POR_CITA)),
        "ciego": ciego, "ejemplos": len(ejemplos), "ejemplos_en_gold": len(ejemplos & gold),
        "excluidas": len(excluir), "excluidas_en_gold": len(excluir & gold), "gold": len(gold),
    }


def reparto(a: dict) -> list[dict]:
    """Qué pareja anota cada cita de la tanda 1, sin ninguna etiqueta."""
    filas = {}
    for persona in sorted(a["asignadas"]):
        for cid in a["asignadas"][persona]:
            filas.setdefault(cid, []).append(persona)
    return [{"context_id": cid, "anotador_1": p[0], "anotador_2": p[1] if len(p) > 1 else ""}
            for cid, p in sorted(filas.items())]


def reporte(a: dict, huellas: dict[str, tuple[str, str]]) -> str:
    si = lambda ok: "sí" if ok else "**no**"
    doble = a["cobertura"][ANOTADORES_POR_CITA] == a["tanda1"] and a["sin_hoja"] == 0
    l = ["# Auditoría de la tanda 1 del Test Gold", "",
         "Generado por `proyecto_de_grado/src/data/auditar_tanda1.py` (issue #97). Lee el manifiesto del Test Gold y las "
         "hojas de Excel repartidas a cada anotador; no lee el voto del jurado. El reparto por cita está en "
         "`proyecto_de_grado/anotacion/test_gold_v2/reparto_tanda1.csv`, sin etiquetas.", "",
         "## Citas de la tanda 1", "",
         f"- Citas en el manifiesto: {fmt(a['tanda1'])}; únicas: {fmt(a['tanda1_unicas'])}.",
         f"- Cada cita está en exactamente {ANOTADORES_POR_CITA} hojas: {si(doble)} "
         f"({', '.join(f'{fmt(v)} citas en {k} hojas' for k, v in sorted(a['cobertura'].items()))}).",
         f"- Citas del manifiesto que no están en ninguna hoja: {fmt(a['sin_hoja'])}.", "",
         "## Reparto por anotador", "",
         "| Anotador | Citas | Repetidas en su hoja | Fuera de la tanda 1 |", "|---|---|---|---|"]
    for p, d in sorted(a["por_persona"].items()):
        l.append(f"| {p} | {fmt(d['citas'])} | {fmt(d['repetidas'])} | {fmt(d['fuera_de_tanda1'])} |")
    total = sum(d["citas"] for d in a["por_persona"].values())
    l += [f"| Total | {fmt(total)} | | |", "",
          f"Cada cita la anotan dos personas distintas, así que el total es {fmt(a['tanda1'])} × {ANOTADORES_POR_CITA} "
          f"= {fmt(a['tanda1'] * ANOTADORES_POR_CITA)}.", "",
          "### Citas por pareja", "",
          "El acuerdo entre anotadores se mide por pareja, sobre las citas que comparten.", "",
          "| Pareja | Citas compartidas |", "|---|---|"]
    for p in a["parejas_posibles"]:
        l.append(f"| {' y '.join(p)} | {fmt(a['parejas'][p])} |")
    l += ["", "## Anotación a ciegas", "",
          "| Anotador | Columnas iguales a las del cuaderno | Columnas de más | Hojas de más | Citas del Test Gold en las hojas de guía |",
          "|---|---|---|---|---|"]
    for p, c in sorted(a["ciego"].items()):
        l.append(f"| {p} | {si(c['columnas_esperadas'])} | {', '.join(c['columnas_extra']) or 'ninguna'} | "
                 f"{', '.join(c['hojas_extra']) or 'ninguna'} | {fmt(c['gold_en_otras_hojas'])} |")
    limpias = all(c["columnas_esperadas"] and not c["hojas_extra"] and not c["gold_en_otras_hojas"] for c in a["ciego"].values())
    l += ["", "Ninguna hoja tiene una columna con el voto del jurado ni de un modelo." if limpias else
          "**Hay hojas con columnas u hojas distintas a las del cuaderno: revisar antes de seguir anotando.**", "",
          f"- Casos del taller que se usan como ejemplos explicados en la guía: {fmt(a['ejemplos'])}; de ellos en el "
          f"Test Gold (tres tandas, {fmt(a['gold'])} citas): {fmt(a['ejemplos_en_gold'])}.",
          f"- Citas que el equipo ya había visto y se excluyeron del muestreo: {fmt(a['excluidas'])}; de ellas en el "
          f"Test Gold: {fmt(a['excluidas_en_gold'])}.", "",
          "## Avance de la anotación", "",
          f"Estado de las hojas al {max((f for f, _ in huellas.values()), default='—')} (última modificación). "
          "Una fila está terminada si la columna Estado de la hoja dice COMPLETO o REGISTRADO. Se cuenta si la fila "
          "está llena, no qué respondió cada persona.", "",
          "| Anotador | Terminadas | Pendientes | Por corregir | Evaluables sin justificación | Avance |",
          "|---|---|---|---|---|---|"]
    for p, d in sorted(a["por_persona"].items()):
        l.append(f"| {p} | {fmt(d['terminadas'])} | {fmt(d['pendientes'])} | {fmt(d['por_corregir'])} | "
                 f"{fmt(d['evaluables_sin_justificacion'])} | {pct(d['terminadas'] / max(1, d['citas']))} |")
    terminadas = sum(d["terminadas"] for d in a["por_persona"].values())
    l += [f"| Total | {fmt(terminadas)} | | | | {pct(terminadas / max(1, total))} |", "",
          "## Versión de las hojas auditadas", "",
          "Las hojas están en la carpeta privada del equipo. La huella SHA-256 permite comprobar que se audita la misma "
          "versión; cambia cada vez que alguien guarda su hoja.", "",
          "| Hoja | Modificada | SHA-256 |", "|---|---|---|"]
    for nombre, (fecha, huella) in sorted(huellas.items()):
        l.append(f"| {nombre} | {fecha} | `{huella}` |")
    return "\n".join(l) + "\n"


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--manifiesto", required=True, help="manifiesto_ids.csv del Test Gold (sin etiquetas)")
    p.add_argument("--hojas", required=True, help="carpeta con TestGold_T1_v2_<Apellido>.xlsx")
    p.add_argument("--ejemplos", required=True, help="items_meta.json del taller (ejemplos de la guía)")
    p.add_argument("--excluir", required=True, help="ids_excluir_test_gold.txt")
    p.add_argument("--reparto", required=True)
    p.add_argument("--reporte", required=True)
    a = p.parse_args()
    rutas = sorted(r for r in Path(a.hojas).iterdir() if PATRON_HOJA.search(r.name))
    libros = {PATRON_HOJA.search(r.name).group(1): leer_xlsx(r) for r in rutas}
    huellas = {r.name: (datetime.fromtimestamp(r.stat().st_mtime).strftime("%Y-%m-%d %H:%M"),
                        hashlib.sha256(r.read_bytes()).hexdigest()) for r in rutas}
    ejemplos = {e["id"] for e in json.loads(Path(a.ejemplos).read_text(encoding="utf-8"))}
    excluir = {x.strip() for x in Path(a.excluir).read_text(encoding="utf-8").splitlines() if x.strip() and not x.startswith("#")}
    res = auditar(leer_csv(a.manifiesto), libros, ejemplos, excluir)
    salida = Path(a.reparto)
    salida.parent.mkdir(parents=True, exist_ok=True)
    with open(salida, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["context_id", "anotador_1", "anotador_2"])
        w.writeheader()
        w.writerows(reparto(res))
    Path(a.reporte).write_text(reporte(res, huellas), encoding="utf-8")
    print(f"{res['tanda1']} citas | cobertura {dict(res['cobertura'])} | "
          f"terminadas {sum(d['terminadas'] for d in res['por_persona'].values())}")


if __name__ == "__main__":
    main()
