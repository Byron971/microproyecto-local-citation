"""Auditoría del jurado de pesos abiertos sobre las 18.000 citas (issues #93 y #94).

Recalcula desde los archivos de cada juez el voto, el nivel de acuerdo y los κ,
y los compara con `jurado_18000_v3.csv`. No ejecuta modelos ni modifica las entradas.

Uso, desde la raíz del repositorio:
    python -m proyecto_de_grado.src.data.auditar_jurado --jurado data/jurado/v3/jurado_18000_v3.csv \
        --jueces data/jurado/v3 --raw data/raw --salida data/jurado/v3/auditoria \
        --reporte proyecto_de_grado/docs/auditoria_jurado_v3.md
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from itertools import combinations
from pathlib import Path

CLASES = ["Background", "Gap", "Basis", "Comparison", "Application", "Improvement / Modification",
          "Evidence", "Identification of the Originator", "Further Reading"]
ETIQUETAS = CLASES + ["Ambiguo", "No evaluable"]          # las 11 opciones que puede elegir un juez
VOTANTES = ["qlora", "qwen", "llama"]                     # columnas del CSV, en el orden del cuaderno
ABIERTOS = ["qwen", "llama"]                              # jueces con archivo propio (el QLoRA viene en el CSV)
SIN_CONSENSO = "SIN_CONSENSO"


def voto_mayoritario(etiquetas: list[str]) -> tuple[str, int]:
    """Etiqueta elegida por al menos 2 jueces; si todas difieren, SIN_CONSENSO (misma regla del cuaderno)."""
    etiqueta, votos = Counter(etiquetas).most_common(1)[0]
    return (etiqueta, votos) if votos >= 2 else (SIN_CONSENSO, 1)


def kappa_cohen(a: list[str], b: list[str]) -> float:
    """Acuerdo entre dos jueces corregido por el acuerdo que se daría al azar."""
    n = len(a)
    po = sum(x == y for x, y in zip(a, b)) / n            # acuerdo observado
    ca, cb = Counter(a), Counter(b)
    pe = sum(ca[k] * cb[k] for k in set(ca) | set(cb)) / (n * n)   # acuerdo esperado por azar
    return (po - pe) / (1 - pe) if pe < 1 else 1.0


def kappa_fleiss(listas: list[list[str]]) -> float:
    """Acuerdo de varios jueces corregido por azar; listas = una lista de etiquetas por juez."""
    m, n = len(listas), len(listas[0])                    # jueces y citas
    total = Counter()
    p_i = 0.0
    for i in range(n):
        c = Counter(l[i] for l in listas)                 # cuántos jueces eligieron cada etiqueta en la cita i
        total.update(c)
        p_i += (sum(v * v for v in c.values()) - m) / (m * (m - 1))
    p_bar = p_i / n
    p_e = sum((v / (n * m)) ** 2 for v in total.values())
    return (p_bar - p_e) / (1 - p_e) if p_e < 1 else 1.0


def leer_csv(ruta: str | Path) -> list[dict]:
    with open(ruta, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def leer_juez(ruta: str | Path) -> tuple[dict[str, dict], int]:
    """Una fila por cita; devuelve también cuántas líneas tenía el archivo (para detectar repetidas)."""
    filas, lineas = {}, 0
    with open(ruta, encoding="utf-8") as f:
        for linea in f:
            if linea.strip():
                lineas += 1
                r = json.loads(linea)
                filas[r["context_id"]] = r
    return filas, lineas


def auditar_entradas(jurado: list[dict], jueces: dict[str, tuple[dict, int]],
                     contextos: dict | None = None) -> dict:
    """Issue #93: identificadores, cobertura de cada juez, etiquetas válidas y coherencia con el CSV."""
    ids = [r["context_id"] for r in jurado]
    res = {"filas_csv": len(ids), "ids_unicos": len(set(ids)), "repetidos_csv": len(ids) - len(set(ids))}
    if contextos is not None:                             # que cada cita exista en ACL-200
        res["fuera_de_acl200"] = sum(cid not in contextos for cid in set(ids))
    res["jueces"] = {}
    for nombre, (filas, lineas) in jueces.items():
        faltan = set(ids) - set(filas)
        sobran = set(filas) - set(ids)
        distinta = sum(filas[r["context_id"]]["etiqueta"] != r[nombre] for r in jurado if r["context_id"] in filas)
        res["jueces"][nombre] = {
            "lineas": lineas, "repetidas": lineas - len(filas), "faltan": len(faltan), "sobran": len(sobran),
            "etiqueta_invalida": sum(f["etiqueta"] not in ETIQUETAS for f in filas.values()),
            "distinta_al_csv": distinta,                  # la columna del CSV debe copiar la etiqueta del archivo
            "estables": sum(bool(f.get("estable")) for f in filas.values()),
        }
    res["qlora_invalida"] = sum(r["qlora"] not in ETIQUETAS for r in jurado)
    recalculo = [voto_mayoritario([r[v] for v in VOTANTES]) for r in jurado]
    res["voto_distinto"] = sum(v != r["voto"] for (v, _), r in zip(recalculo, jurado))
    res["acuerdo_distinto"] = sum(str(k) != r["jueces_de_acuerdo"] for (_, k), r in zip(recalculo, jurado))
    return res


def medir_consenso(jurado: list[dict]) -> dict:
    """Issue #94: niveles de acuerdo, votos por clase, κ y quién queda en minoría."""
    listas = {v: [r[v] for r in jurado] for v in VOTANTES}
    res = {
        "niveles": Counter(int(r["jueces_de_acuerdo"]) for r in jurado),
        "votos": Counter(r["voto"] for r in jurado),
        "votos_3de3": Counter(r["voto"] for r in jurado if r["jueces_de_acuerdo"] == "3"),
        "kappa_fleiss": kappa_fleiss(list(listas.values())),
        "parejas": {},
        "minoria": Counter(),                             # en las citas 2 de 3, qué juez votó distinto
        "por_juez": {v: Counter(listas[v]) for v in VOTANTES},
    }
    for a, b in combinations(VOTANTES, 2):
        coinciden = sum(x == y for x, y in zip(listas[a], listas[b]))
        res["parejas"][(a, b)] = {"acuerdo": coinciden / len(jurado), "kappa": kappa_cohen(listas[a], listas[b])}
    for r in jurado:
        if r["jueces_de_acuerdo"] == "2":
            res["minoria"].update(v for v in VOTANTES if r[v] != r["voto"])
    return res


def matriz(jurado: list[dict], a: str, b: str) -> Counter:
    """Matriz de confusión entre dos jueces: (etiqueta de a, etiqueta de b) -> número de citas."""
    return Counter((r[a], r[b]) for r in jurado)


def escribir_salidas(jurado: list[dict], salida: Path) -> None:
    """CSV de desacuerdos (citas sin consenso) y matrices entre parejas de jueces, en formato largo."""
    salida.mkdir(parents=True, exist_ok=True)
    with open(salida / "desacuerdos_jurado_v3.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["context_id", "particion", *VOTANTES])
        for r in jurado:
            if r["voto"] == SIN_CONSENSO:
                w.writerow([r["context_id"], r["particion"], *(r[v] for v in VOTANTES)])
    with open(salida / "matrices_jueces_v3.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["juez_a", "juez_b", "etiqueta_a", "etiqueta_b", "citas"])
        for a, b in combinations(VOTANTES, 2):
            for (ea, eb), k in sorted(matriz(jurado, a, b).items()):
                w.writerow([a, b, ea, eb, k])


def fmt(n: int | float) -> str:
    """Números con punto de miles y coma decimal, como en el informe."""
    if isinstance(n, float):
        return f"{n:.3f}".replace(".", ",")
    return f"{n:,}".replace(",", ".")


def pct(x: float) -> str:
    """Porcentaje con coma decimal."""
    return f"{x:.1%}".replace(".", ",")


def reporte(aud: dict, con: dict, metas: dict[str, dict], jurado: list[dict]) -> str:
    """Resumen en Markdown con todas las cifras calculadas por este módulo."""
    n = aud["filas_csv"]
    l = ["# Auditoría del jurado de pesos abiertos (v3)", "",
         "Generado por `proyecto_de_grado/src/data/auditar_jurado.py` a partir de `data/jurado/v3/`. "
         "Son pre-etiquetas de modelos, no etiquetas humanas. Esa carpeta se publica con DVC al cerrar la anotación del Test Gold, porque trae el voto del jurado de esas citas y los anotadores trabajan a ciegas.", "",
         "## Entradas (issue #93)", "",
         f"- `jurado_18000_v3.csv`: {fmt(n)} filas, {fmt(aud['ids_unicos'])} identificadores únicos, "
         f"{fmt(aud['repetidos_csv'])} repetidos."]
    if "fuera_de_acl200" in aud:
        l.append(f"- Citas que no existen en `data/raw/contexts.json` (ACL-200): {fmt(aud['fuera_de_acl200'])}.")
    l += [f"- Etiquetas del QLoRA fuera de las 11 opciones: {fmt(aud['qlora_invalida'])}.",
          f"- Voto recalculado con la regla de mayoría que no coincide con el CSV: {fmt(aud['voto_distinto'])}; "
          f"nivel de acuerdo que no coincide: {fmt(aud['acuerdo_distinto'])}.", "",
          "| Juez | Modelo | Líneas | Repetidas | Faltan | Sobran | Etiqueta inválida | Distinta al CSV | Misma etiqueta en las 3 rotaciones |",
          "|---|---|---|---|---|---|---|---|---|"]
    for nombre, d in aud["jueces"].items():
        m = metas.get(nombre, {})
        l.append(f"| {nombre} | {m.get('modelo', '')} | {fmt(d['lineas'])} | {fmt(d['repetidas'])} | {fmt(d['faltan'])} | "
                 f"{fmt(d['sobran'])} | {fmt(d['etiqueta_invalida'])} | {fmt(d['distinta_al_csv'])} | "
                 f"{pct(d['estables'] / max(d['lineas'], 1))} |")
    l.append("| qlora | Qwen2.5-7B-Instruct + adaptador LoRA (columna del CSV) | | | | | | | |")
    l += ["", "Configuración registrada por el cuaderno en cada `juez_<juez>_v3_meta.json`:", ""]
    for nombre, m in metas.items():
        l.append(f"- **{nombre}:** {m.get('cuantizacion', '')}, {m.get('gpu', '')}, rotaciones {m.get('rotaciones', '')}, "
                 f"huella del prompt `{m.get('hash_prompt', '')}`, {m.get('fecha', '')}.")
    niv = con["niveles"]
    l += ["", "## Consenso (issue #94)", "",
          "Regla: la etiqueta final es la que eligen al menos dos de los tres jueces. Si los tres eligen distinto, "
          "la cita queda **sin consenso** y no entra al dataset. Si el consenso es Ambiguo o No evaluable, tampoco entra.", "",
          f"- Tres de tres: {fmt(niv[3])} ({pct(niv[3] / n)}). Dos de tres: {fmt(niv[2])} ({pct(niv[2] / n)}). "
          f"Las tres distintas: {fmt(niv[1])} ({pct(niv[1] / n)}).",
          f"- κ de Fleiss entre los tres: {fmt(con['kappa_fleiss'])}.", "",
          "| Pareja | Coinciden | κ de Cohen |", "|---|---|---|"]
    for (a, b), d in con["parejas"].items():
        l.append(f"| {a} y {b} | {pct(d['acuerdo'])} | {fmt(d['kappa'])} |")
    minoria = con["minoria"]
    l += ["", f"En las {fmt(niv[2])} citas de dos de tres, el juez que votó distinto fue: "
          + ", ".join(f"{v} {fmt(minoria[v])}" for v in VOTANTES) + ".", "",
          "| Etiqueta | Voto final | De ellos 3 de 3 | " + " | ".join(f"Elegida por {v}" for v in VOTANTES) + " |",
          "|---|---|---|" + "---|" * len(VOTANTES)]
    for e in ETIQUETAS + [SIN_CONSENSO]:
        l.append(f"| {e} | {fmt(con['votos'][e])} | {fmt(con['votos_3de3'][e])} | "
                 + " | ".join(fmt(con["por_juez"][v][e]) for v in VOTANTES) + " |")
    pares = matriz(jurado, "qlora", "qwen") + matriz(jurado, "qlora", "llama") + matriz(jurado, "qwen", "llama")
    confusas = Counter()
    for (x, y), k in pares.items():
        if x != y:
            confusas[tuple(sorted((x, y)))] += k
    l += ["", "Parejas de etiquetas que más se confunden entre jueces (suma de las tres parejas de jueces):", ""]
    for (x, y), k in confusas.most_common(8):
        l.append(f"- {x} / {y}: {fmt(k)}")
    mas = minoria.most_common(1)[0][0]                    # el juez que más veces queda en minoría
    sesgo = max(ETIQUETAS, key=lambda e: con["por_juez"][mas][e] - con["votos"][e])
    estable = {nombre: d["estables"] / max(d["lineas"], 1) for nombre, d in aud["jueces"].items()}
    unanime = {c: con["votos_3de3"][c] / con["votos"][c] for c in CLASES if con["votos"][c]}   # parte de 3 de 3 por clase
    orden = sorted(unanime, key=unanime.get, reverse=True)
    l += ["", "Lectura:", "",
          f"- {mas} es el juez que más veces queda en minoría ({pct(minoria[mas] / niv[2])} de las citas de dos de tres). "
          f"Elige {sesgo} {fmt(con['por_juez'][mas][sesgo])} veces, frente a {fmt(con['votos'][sesgo])} en el voto final.",
          "- Misma etiqueta en las tres rotaciones de las opciones: "
          + ", ".join(f"{nombre} {pct(v)}" for nombre, v in estable.items())
          + ". Por debajo de 100 % significa que el orden de las opciones todavía influye en cada juez por separado.",
          "- Parte de los votos que son tres de tres, por clase: mayor en "
          + ", ".join(f"{c} ({pct(unanime[c])})" for c in orden[:3])
          + "; menor en " + ", ".join(f"{c} ({pct(unanime[c])})" for c in orden[-2:]) + "."]
    l += ["", "Archivos de detalle (en `data/jurado/v3/auditoria/`): "
          "`desacuerdos_jurado_v3.csv` (las citas sin consenso con la etiqueta de cada juez) y "
          "`matrices_jueces_v3.csv` (matriz de confusión de cada pareja de jueces)."]
    return "\n".join(l) + "\n"


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--jurado", required=True, help="jurado_18000_v3.csv")
    p.add_argument("--jueces", required=True, help="carpeta con juez_<juez>_v3.jsonl y _meta.json")
    p.add_argument("--raw", help="data/raw de ACL-200, para comprobar que cada cita exista")
    p.add_argument("--salida", required=True, help="carpeta para los CSV de detalle")
    p.add_argument("--reporte", required=True, help="ruta del resumen en Markdown")
    a = p.parse_args()
    jurado = leer_csv(a.jurado)
    jueces = {n: leer_juez(Path(a.jueces) / f"juez_{n}_v3.jsonl") for n in ABIERTOS}
    metas = {n: json.loads((Path(a.jueces) / f"juez_{n}_v3_meta.json").read_text(encoding="utf-8")) for n in ABIERTOS}
    contextos = json.loads((Path(a.raw) / "contexts.json").read_text(encoding="utf-8")) if a.raw else None
    aud = auditar_entradas(jurado, jueces, contextos)
    con = medir_consenso(jurado)
    escribir_salidas(jurado, Path(a.salida))
    Path(a.reporte).write_text(reporte(aud, con, metas, jurado), encoding="utf-8")
    print(f"voto distinto al CSV: {aud['voto_distinto']} | κ Fleiss {con['kappa_fleiss']:.3f} | reporte en {a.reporte}")


if __name__ == "__main__":
    main()
