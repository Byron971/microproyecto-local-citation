"""Dataset de nueve funciones de cita a partir del voto del jurado (issue #95).

Asigna a cada una de las 18.000 citas un uso (entrenamiento, validación, Test Gold, reserva
de test o excluida) según la partición oficial de ACL-200 y el manifiesto del Test Gold, y
mide cuánto falta por clase para llegar a 2.000. No cambia etiquetas ni completa clases.

Uso, desde la raíz del repositorio:
    python -m proyecto_de_grado.src.data.curar_dataset_funciones --jurado data/jurado/v3/jurado_18000_v3.csv \
        --raw data/raw --manifiesto proyecto_de_grado/anotacion/test_gold_v2/manifiesto_ids.csv \
        --prueba-jurado data/jurado/v3/prueba_200/referencia_gpt_200.jsonl \
        --salida data/dataset_funciones/v1/dataset_funciones_v1.csv \
        --reporte proyecto_de_grado/docs/dataset_funciones_v1.md
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path

from proyecto_de_grado.src.data.auditar_jurado import CLASES, SIN_CONSENSO, fmt, leer_csv, pct
from proyecto_de_grado.src.data.validar_splits import load_split_index

META_POR_CLASE = 2000                                     # tamaño por clase que pide el enunciado
USOS_MODELO = ("entrenamiento", "validacion")             # lo único que puede ver un modelo al entrenar


def a_ciegas(filas: list[dict]) -> list[dict]:
    """Copia para publicar: sin el voto del jurado en las citas que anotan personas (Test Gold y calibración)."""
    humanas = lambda f: f["uso"].startswith("test_gold") or f["uso"] == "calibracion"
    return [{**f, "etiqueta_jurado": "", "jueces_de_acuerdo": ""} if humanas(f) else f for f in filas]


def anio_citante(cid: str) -> int:
    """Año del artículo citante a partir del identificador ACL (P15-1122 -> 2015, W99-0101 -> 1999)."""
    yy = int(cid[1:3])
    return 1900 + yy if yy >= 79 else 2000 + yy


def asignar_uso(voto: str, particion: str, anio: int, grupo: str = "", tanda: str = "") -> str:
    """Uso de una cita. El orden importa: primero lo humano, luego lo excluido y al final la partición."""
    if grupo == "testgold":
        return f"test_gold_t{tanda}"
    if grupo == "calibracion3":
        return "calibracion"
    if voto == SIN_CONSENSO:
        return "excluida_sin_consenso"
    if voto not in CLASES:                                # consenso en Ambiguo o No evaluable
        return "excluida_ambigua"
    if particion == "test" or anio == 2015:
        return "reserva_test"                            # test que no está en el Test Gold: nunca se entrena con ella
    if particion == "val" or anio == 2014:
        return "validacion"
    return "entrenamiento"                                # train oficial o fuera de partición (2013 o antes)


def curar(jurado: list[dict], por_contexto: dict[str, str], contextos: dict[str, dict],
          manifiesto: dict[str, dict], prueba_jurado: set[str]) -> list[dict]:
    """Una fila por cita con su procedencia completa."""
    filas = []
    for r in jurado:
        cid = r["context_id"]
        ctx = contextos.get(cid, {})
        m = manifiesto.get(cid, {})
        particion = por_contexto.get(cid, "sin_particion")
        anio = anio_citante(cid)
        filas.append({
            "context_id": cid, "citing_id": ctx.get("citing_id", ""), "cited_id": ctx.get("refid", ""),
            "anio_citante": anio, "particion_oficial": particion,
            "etiqueta_jurado": r["voto"], "jueces_de_acuerdo": r["jueces_de_acuerdo"],
            "uso": asignar_uso(r["voto"], particion, anio, m.get("grupo", ""), m.get("tanda", "")),
            "prueba_jurado_200": int(cid in prueba_jurado),   # citas con que se escogió el jurado: no evaluar con ellas
        })
    return filas


def fugas(filas: list[dict]) -> dict[str, int]:
    """Artículos citantes y pares citante-citado que aparecen a la vez en entrenamiento/validación y en el Test Gold."""
    modelo = [f for f in filas if f["uso"] in USOS_MODELO]
    gold = [f for f in filas if f["uso"].startswith("test_gold")]
    return {
        "citantes": len({f["citing_id"] for f in modelo} & {f["citing_id"] for f in gold}),
        "pares": len({(f["citing_id"], f["cited_id"]) for f in modelo} & {(f["citing_id"], f["cited_id"]) for f in gold}),
        "contextos": len({f["context_id"] for f in modelo} & {f["context_id"] for f in gold}),
    }


def tabla(filas: list[dict]) -> dict[str, Counter]:
    """Conteo por clase de cada uso y del total con consenso."""
    t = {c: Counter() for c in CLASES}
    for f in filas:
        c = f["etiqueta_jurado"]
        if c in t:
            t[c]["total"] += 1
            t[c][f["uso"]] += 1
            if f["jueces_de_acuerdo"] == "3":
                t[c]["3de3"] += 1
            if f["uso"] == "entrenamiento" and f["particion_oficial"] == "sin_particion":
                t[c]["entrenamiento_fuera"] += 1
    return t


def reporte(filas: list[dict], contextos: dict, por_contexto: dict[str, str], fug: dict[str, int]) -> str:
    t = tabla(filas)
    usos = Counter(f["uso"] for f in filas)
    l = ["# Dataset de funciones de cita v1", "",
         "Generado por `proyecto_de_grado/src/data/curar_dataset_funciones.py`. La etiqueta es el voto del jurado "
         "(al menos dos de tres jueces); no se cambió ninguna etiqueta ni se completó ninguna clase. "
         "El archivo por cita es `data/dataset_funciones/v1/dataset_funciones_v1.csv` (DVC). En las citas del Test Gold "
         "y de la calibración la etiqueta del jurado va vacía, porque las anotan personas a ciegas; su etiqueta final será la humana.", "",
         "## Uso de cada cita", "",
         "| Uso | Citas | Qué significa |", "|---|---|---|"]
    significado = {
        "entrenamiento": "train oficial de ACL-200 o fuera de partición con citante de 2013 o antes",
        "validacion": "partición val (2014)",
        "test_gold_t1": "tanda 1 del Test Gold (anotación humana en curso)",
        "test_gold_t2": "tanda 2 del Test Gold (escogida, sin repartir)",
        "test_gold_t3": "tanda 3 del Test Gold (escogida, sin repartir)",
        "reserva_test": "partición test fuera del Test Gold: no se usa para entrenar",
        "calibracion": "calibración 3 (opcional)",
        "excluida_sin_consenso": "los tres jueces eligieron distinto",
        "excluida_ambigua": "consenso en Ambiguo o No evaluable",
    }
    for u in significado:
        l.append(f"| {u} | {fmt(usos[u])} | {significado[u]} |")
    l += ["", "## Citas por clase y brecha frente a 2.000", "",
          "| Clase | Con consenso | 3 de 3 | Entrenamiento | (fuera de partición) | Validación | Test Gold (3 tandas) | Reserva test | Faltan para 2.000 |",
          "|---|---|---|---|---|---|---|---|---|"]
    for c in CLASES:
        d = t[c]
        gold = d["test_gold_t1"] + d["test_gold_t2"] + d["test_gold_t3"]
        l.append(f"| {c} | {fmt(d['total'])} | {fmt(d['3de3'])} | {fmt(d['entrenamiento'])} | {fmt(d['entrenamiento_fuera'])} | "
                 f"{fmt(d['validacion'])} | {fmt(gold)} | {fmt(d['reserva_test'])} | {fmt(max(0, META_POR_CLASE - d['total']))} |")
    deficit = [c for c in CLASES if t[c]["total"] < META_POR_CLASE]
    usadas = {f["context_id"] for f in filas}
    libres = Counter(por_contexto.get(cid, "sin_particion") for cid in contextos if cid not in usadas)
    l += ["", f"**Clases por debajo de 2.000:** {len(deficit)} de 9 ({', '.join(deficit)}).", "",
          f"**Citas de ACL-200 que todavía no pasaron por el jurado:** {fmt(sum(libres.values()))} "
          f"(train {fmt(libres['train'])}, val {fmt(libres['val'])}, test {fmt(libres['test'])}, "
          f"fuera de partición {fmt(libres['sin_particion'])}). Pasar por el mismo jurado las que no son de test acercaría "
          "las clases escasas a 2.000 sin cambiar el método. El PR #92 ya trae un cuaderno que las clasifica con el QLoRA; "
          "faltarían Qwen y Llama. En las 2.700 con que se entrenó el QLoRA, ese modelo no puede ser juez porque ya las vio. "
          "Es una decisión del equipo.", "",
          "## Controles", "",
          f"- Artículos citantes compartidos entre entrenamiento/validación y el Test Gold: {fmt(fug['citantes'])}.",
          f"- Pares citante-citado compartidos: {fmt(fug['pares'])}. Citas compartidas: {fmt(fug['contextos'])}.",
          f"- Citas de la prueba de 200 con que se escogió el jurado: {fmt(sum(f['prueba_jurado_200'] for f in filas))} "
          f"(columna `prueba_jurado_200`), de ellas en el Test Gold: "
          f"{fmt(sum(f['prueba_jurado_200'] for f in filas if f['uso'].startswith('test_gold')))}. No deben usarse para evaluar.",
          f"- Parte del entrenamiento que viene de fuera de las particiones oficiales: "
          f"{pct(sum(t[c]['entrenamiento_fuera'] for c in CLASES) / max(1, sum(t[c]['entrenamiento'] for c in CLASES)))}. "
          "Se reporta aparte de la partición train oficial."]
    return "\n".join(l) + "\n"


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--jurado", required=True)
    p.add_argument("--raw", required=True, help="data/raw de ACL-200")
    p.add_argument("--manifiesto", required=True, help="manifiesto_ids.csv del Test Gold (sin etiquetas)")
    p.add_argument("--prueba-jurado", required=True, help="cualquier archivo de la prueba de 200 (para sus context_id)")
    p.add_argument("--salida", required=True)
    p.add_argument("--reporte", required=True)
    a = p.parse_args()
    indice = load_split_index(a.raw)                      # valida ACL-200 y da la partición oficial de cada cita
    manifiesto = {r["context_id"]: r for r in leer_csv(a.manifiesto)}
    prueba = {json.loads(x)["context_id"] for x in open(a.prueba_jurado, encoding="utf-8") if x.strip()}
    filas = curar(leer_csv(a.jurado), indice.by_context, indice.contexts, manifiesto, prueba)
    fug = fugas(filas)
    salida = Path(a.salida)
    salida.parent.mkdir(parents=True, exist_ok=True)
    with open(salida, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(filas[0]))
        w.writeheader()
        w.writerows(a_ciegas(filas))
    Path(a.reporte).write_text(reporte(filas, indice.contexts, indice.by_context, fug), encoding="utf-8")
    print(f"{len(filas)} citas | usos {dict(Counter(f['uso'] for f in filas))} | fugas {fug}")


if __name__ == "__main__":
    main()
