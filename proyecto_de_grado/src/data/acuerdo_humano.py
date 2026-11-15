"""Acuerdo entre anotadores humanos del Test Gold y de la calibración (issue #99).

Lee las hojas de Excel de los anotadores y mide cuánto coinciden entre personas: κ de Cohen por
pareja y α de Krippendorff para todo el grupo. No lee el voto del jurado: es acuerdo entre humanos.
Solo cuenta filas terminadas (columna Estado en COMPLETO o REGISTRADO).

Etiqueta de cada fila: la función elegida si la cita es Evaluable o Ambiguo (la guía pide elegir la
más probable aunque haya duda) y «No evaluable» si no lo es. Son 10 categorías.

Uso, desde la raíz del repositorio:
    python -m proyecto_de_grado.src.data.acuerdo_humano --hojas "<carpeta con las hojas>" \
        --reporte proyecto_de_grado/docs/acuerdo_humano_tanda1.md \
        [--desacuerdos "<carpeta privada>/desacuerdos_tanda1.csv"]

El archivo de desacuerdos trae las etiquetas de cada persona: va a la carpeta privada, no al repositorio.
"""
from __future__ import annotations

import argparse
import csv
import re
from collections import Counter
from itertools import combinations
from pathlib import Path

from proyecto_de_grado.src.data.auditar_jurado import CLASES, fmt, pct
from proyecto_de_grado.src.data.auditar_tanda1 import estado, leer_xlsx, tabla_anotacion

NO_EVALUABLE = "No evaluable"
CATEGORIAS = CLASES + [NO_EVALUABLE]
TERMINADA = ("COMPLETO", "REGISTRADO")
ALFA_CONFIABLE, ALFA_PROVISIONAL = 0.800, 0.667      # umbrales de Krippendorff (2004) para α
PAREJA_MINIMA = 30                                   # con menos citas compartidas el κ de una pareja es muy inestable
CONJUNTOS = {"tanda1": re.compile(r"^TestGold_T1_v2_(\w+)\.xlsx$"), "calibracion3": re.compile(r"^Calibracion3_(\w+)\.xlsx$")}


def etiqueta(r: dict) -> str | None:
    """Etiqueta de una fila terminada; None si la fila no está terminada."""
    if estado(r) not in TERMINADA:
        return None
    return NO_EVALUABLE if r["evaluable"] == NO_EVALUABLE else r["funcion"]


def cargar(carpeta: str | Path, patron: re.Pattern) -> tuple[dict[str, dict[str, str]], dict[str, Counter], dict[str, set[str]]]:
    """Etiquetas terminadas por persona y cita, cómo llenó cada persona su hoja y qué citas tiene asignadas."""
    etiquetas, perfil, asignadas = {}, {}, {}
    for ruta in sorted(Path(carpeta).iterdir()):
        m = patron.search(ruta.name)
        if not m:
            continue
        _, registros = tabla_anotacion(leer_xlsx(ruta)["Mis_anotaciones"])
        persona = m.group(1)
        asignadas[persona] = {r["context_id"] for r in registros}
        etiquetas[persona] = {r["context_id"]: e for r in registros if (e := etiqueta(r))}
        perfil[persona] = Counter({"asignadas": len(registros), "terminadas": len(etiquetas[persona]),
                                   "ambiguas": sum(r["evaluable"] == "Ambiguo" and etiqueta(r) is not None for r in registros),
                                   "no_evaluables": sum(e == NO_EVALUABLE for e in etiquetas[persona].values())})
    return etiquetas, perfil, asignadas


def cohen(pares: list[tuple[str, str]]) -> dict:
    """κ de Cohen de dos anotadores sobre las mismas citas."""
    n = len(pares)
    if n == 0:
        return {"n": 0, "po": None, "pe": None, "kappa": None}
    po = sum(a == b for a, b in pares) / n
    m1, m2 = Counter(a for a, _ in pares), Counter(b for _, b in pares)
    pe = sum(m1[c] * m2[c] for c in m1) / n ** 2
    return {"n": n, "po": po, "pe": pe, "kappa": None if pe == 1 else (po - pe) / (1 - pe)}


def alfa(unidades: list[list[str]]) -> float | None:
    """α de Krippendorff nominal; admite citas con distinto número de anotadores (las de uno solo no cuentan)."""
    o = Counter()                                    # matriz de coincidencias
    for valores in unidades:
        m = len(valores)
        if m < 2:
            continue
        for i, j in ((i, j) for i in range(m) for j in range(m) if i != j):
            o[valores[i], valores[j]] += 1 / (m - 1)
    n_c = Counter()
    for (c, _), v in o.items():
        n_c[c] += v
    n = sum(n_c.values())
    if n <= 1:
        return None
    d_o = 1 - sum(v for (c, k), v in o.items() if c == k) / n
    d_e = 1 - sum(v * (v - 1) for v in n_c.values()) / (n * (n - 1))
    return None if d_e == 0 else 1 - d_o / d_e


def acuerdo_especifico(pares: list[tuple[str, str]]) -> dict[str, tuple[float | None, int]]:
    """Por categoría: 2 × coincidencias / veces que la usaron ambos anotadores, y cuántas veces se usó."""
    usos, iguales = Counter(), Counter()
    for a, b in pares:
        usos[a] += 1
        usos[b] += 1
        if a == b:
            iguales[a] += 1
    return {c: (2 * iguales[c] / usos[c] if usos[c] else None, usos[c]) for c in CATEGORIAS}


def medir(etiquetas: dict[str, dict[str, str]], asignadas: dict[str, set[str]] | None = None) -> dict:
    """Acuerdo por pareja, global y por categoría. `asignadas` da el denominador de citas compartidas."""
    asignadas = asignadas or {p: set(e) for p, e in etiquetas.items()}
    parejas, todos = {}, []
    for p1, p2 in combinations(sorted(etiquetas), 2):
        comunes = sorted(set(etiquetas[p1]) & set(etiquetas[p2]))
        pares = [(etiquetas[p1][c], etiquetas[p2][c]) for c in comunes]
        parejas[p1, p2] = cohen(pares) | {"compartidas": len(asignadas[p1] & asignadas[p2])}
        todos += pares
    citas = {c for e in etiquetas.values() for c in e}
    unidades = [[e[c] for e in etiquetas.values() if c in e] for c in sorted(citas)]
    kappas = [d["kappa"] for d in parejas.values() if d["kappa"] is not None]
    return {
        "parejas": parejas, "alfa": alfa(unidades), "citas_con_dos": sum(len(u) >= 2 for u in unidades),
        "acuerdo_observado": sum(a == b for a, b in todos) / len(todos) if todos else None,
        "kappa_promedio": sum(kappas) / len(kappas) if kappas else None,
        "especifico": acuerdo_especifico(todos),
        "confusiones": Counter(tuple(sorted((a, b))) for a, b in todos if a != b),
    }


def veredicto(a: float | None) -> str:
    if a is None:
        return "sin datos suficientes"
    if a >= ALFA_CONFIABLE:
        return "confiable"
    if a >= ALFA_PROVISIONAL:
        return "aceptable para conclusiones provisionales"
    return "bajo: conviene discutir los desacuerdos y recalibrar antes de seguir"


def desacuerdos(etiquetas: dict[str, dict[str, str]]) -> list[dict]:
    """Citas en que dos personas eligieron distinto, para la adjudicación (#100)."""
    filas = []
    for p1, p2 in combinations(sorted(etiquetas), 2):
        for c in sorted(set(etiquetas[p1]) & set(etiquetas[p2])):
            if etiquetas[p1][c] != etiquetas[p2][c]:
                filas.append({"context_id": c, "anotador_1": p1, "etiqueta_1": etiquetas[p1][c],
                              "anotador_2": p2, "etiqueta_2": etiquetas[p2][c]})
    return filas


def num(x: float | None) -> str:
    return "—" if x is None else fmt(float(x))


def seccion(titulo: str, res: dict, perfil: dict[str, Counter]) -> list[str]:
    asignadas = sum(p["asignadas"] for p in perfil.values())
    terminadas = sum(p["terminadas"] for p in perfil.values())
    l = [f"## {titulo}", "",
         f"Filas terminadas: {fmt(terminadas)} de {fmt(asignadas)} ({pct(terminadas / max(1, asignadas))}). "
         f"Citas con al menos dos anotaciones terminadas: {fmt(res['citas_con_dos'])}.", "",
         f"- **α de Krippendorff:** {num(res['alfa'])}, {veredicto(res['alfa'])}.",
         f"- Acuerdo observado (proporción de pares que coinciden): "
         f"{'—' if res['acuerdo_observado'] is None else pct(res['acuerdo_observado'])}.",
         f"- κ de Cohen promedio entre parejas: {num(res['kappa_promedio'])}.", "",
         "| Anotador | Asignadas | Terminadas | Ambiguas | No evaluables |", "|---|---|---|---|---|"]
    for p, d in sorted(perfil.items()):
        l.append(f"| {p} | {fmt(d['asignadas'])} | {fmt(d['terminadas'])} | {fmt(d['ambiguas'])} | {fmt(d['no_evaluables'])} |")
    l += ["", "| Pareja | Compartidas | Terminadas por ambos | Acuerdo observado | κ de Cohen |", "|---|---|---|---|---|"]
    for (p1, p2), d in res["parejas"].items():
        aviso = " (pocas citas)" if 0 < d["n"] < PAREJA_MINIMA else ""
        po = "—" if d["po"] is None else pct(d["po"])
        l.append(f"| {p1} y {p2} | {fmt(d['compartidas'])} | {fmt(d['n'])} | {po} | {num(d['kappa'])}{aviso} |")
    l += ["", "| Categoría | Veces usada | Acuerdo específico |", "|---|---|---|"]
    for c, (v, usos) in res["especifico"].items():
        l.append(f"| {c} | {fmt(usos)} | {'—' if v is None else pct(v)} |")
    l += ["", "Confusiones más frecuentes (pares de categorías en que dos personas eligieron distinto):", ""]
    l += [f"- {a} / {b}: {fmt(n)}" for (a, b), n in res["confusiones"].most_common(10)] or ["- ninguna todavía"]
    return l + [""]


def reporte(secciones: list[tuple[str, dict, dict]]) -> str:
    l = ["# Acuerdo entre anotadores humanos", "",
         "Generado por `proyecto_de_grado/src/data/acuerdo_humano.py` (issue #99). Mide cuánto coinciden las personas "
         "entre sí, sin el jurado. La etiqueta de cada fila es la función elegida (también en las Ambiguas, como pide la "
         "guía) o «No evaluable»: 10 categorías. Solo cuentan filas terminadas.", "",
         f"Cómo leer el α (Krippendorff, 2004): desde {fmt(ALFA_CONFIABLE)} es confiable; entre {fmt(ALFA_PROVISIONAL)} y "
         f"{fmt(ALFA_CONFIABLE)} sirve para conclusiones provisionales; por debajo conviene recalibrar. El κ de Cohen se "
         "lee igual, pareja por pareja. El acuerdo específico de una categoría dice qué tan seguido coinciden dos personas "
         "cuando alguna de las dos la eligió.", ""]
    for titulo, res, perfil in secciones:
        l += seccion(titulo, res, perfil)
    return "\n".join(l)


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--hojas", required=True, help="carpeta con TestGold_T1_v2_*.xlsx y Calibracion3_*.xlsx")
    p.add_argument("--reporte", required=True)
    p.add_argument("--desacuerdos", help="CSV con las citas en desacuerdo de la tanda 1 (solo en la carpeta privada)")
    a = p.parse_args()
    secciones = []
    for nombre, titulo in (("tanda1", "Tanda 1 del Test Gold (dos anotadores por cita)"),
                           ("calibracion3", "Calibración 3 (las cinco personas, mismas 20 citas)")):
        etiquetas, perfil, asignadas = cargar(a.hojas, CONJUNTOS[nombre])
        res = medir(etiquetas, asignadas)
        secciones.append((titulo, res, perfil))
        if nombre == "tanda1" and a.desacuerdos:
            with open(a.desacuerdos, "w", encoding="utf-8", newline="") as f:
                w = csv.DictWriter(f, fieldnames=["context_id", "anotador_1", "etiqueta_1", "anotador_2", "etiqueta_2"])
                w.writeheader()
                w.writerows(desacuerdos(etiquetas))
        print(f"{nombre}: α {num(res['alfa'])} | citas con dos {res['citas_con_dos']}")
    Path(a.reporte).write_text(reporte(secciones), encoding="utf-8")


if __name__ == "__main__":
    main()
