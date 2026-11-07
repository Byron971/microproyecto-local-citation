"""Puntuacion y comparacion de corridas (solo stdlib).

Todo resultado es PROVISIONAL: etiquetas de entrenamiento y de eval de Haiku; el Gold humano v2
no esta congelado (#100). Los deltas se calculan sobre exactamente los mismos ids."""
import json
import math
import re

from . import dominio

ENCODERS = {"scibert": "SciBERT", "specter": "SPECTER"}
ENTRADAS_MATRIZ = ("A", "B")
ABLACIONES = ("B_sin_seccion", "B_barajada")
PATRON_CORRIDA = re.compile(r"^(scibert|specter)_(A|B|B_sin_seccion|B_barajada)_(\d+)$")
METRICAS_CSV = ("f1_macro", "f1_micro", "accuracy", "precision_macro", "recall_macro",
                "f1_weighted")


def leer_jsonl(texto: str, nombre: str = "archivo") -> list[dict]:
    filas = []
    for n, linea in enumerate(texto.splitlines(), 1):
        if not linea.strip():
            continue
        try:
            fila = json.loads(linea)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{nombre}, linea {n}: JSON invalido") from exc
        if not isinstance(fila, dict):
            raise ValueError(f"{nombre}, linea {n}: se esperaba un objeto")
        filas.append(fila)
    if not filas:
        raise ValueError(f"{nombre}: archivo vacio")
    return filas


def indexar_gold(filas: list[dict]) -> tuple[dict[str, int], dict[str, int]]:
    """(id -> indice de clase, abstenciones por motivo). Las abstenciones no se puntuan."""
    gold, abstenciones = {}, {}
    for f in filas:
        cid = f.get("id", f.get("context_id"))
        if not isinstance(cid, str) or not cid.strip():
            raise ValueError("Gold: id ausente.")
        if cid in gold or cid in abstenciones:
            raise ValueError(f"Gold: id duplicado {cid}")
        indice = dominio.normalizar_etiqueta(f.get("gold"))
        if indice is None:
            motivo = dominio.motivo_abstencion(f.get("gold"))
            abstenciones[cid] = motivo
        else:
            gold[cid] = indice
    resumen: dict[str, int] = {}
    for motivo in abstenciones.values():
        resumen[motivo] = resumen.get(motivo, 0) + 1
    return gold, dict(sorted(resumen.items()))


def indexar_predicciones(filas: list[dict]) -> dict[str, int]:
    pred = {}
    for f in filas:
        cid = f.get("case_id")
        if not isinstance(cid, str) or not cid.strip():
            raise ValueError("Prediccion sin case_id.")
        if cid in pred:
            raise ValueError(f"Prediccion duplicada: {cid}")
        if f.get("status") != "ok":
            raise ValueError(f"Prediccion incompleta en {cid}: {f.get('status')}")
        indice = dominio.normalizar_etiqueta(f["pred_index"])
        if indice is None or ("pred_label" in f and dominio.normalizar_etiqueta(f["pred_label"]) != indice):
            raise ValueError(f"pred_label y pred_index discrepan en {cid}")
        pred[cid] = indice
    return pred


def puntuar(gold: dict[str, int], pred: dict[str, int], *, exacto: bool = True) -> dict:
    """Metricas 9 clases. exacto=True: pred y gold deben tener los mismos ids. exacto=False
    (Gold v2): se puntuan los ids predichos que tengan gold evaluable; el resto se cuenta."""
    if exacto:
        if set(pred) != set(gold):
            raise ValueError(f"IDs no comparables (faltantes={len(set(gold) - set(pred))}, "
                             f"extras={len(set(pred) - set(gold))})")
        ids = sorted(gold)
    else:
        ids = sorted(set(pred) & set(gold))
        if not ids:
            raise ValueError("Ningun id predicho tiene gold evaluable.")
    m = dominio.metricas([gold[i] for i in ids], [pred[i] for i in ids])
    m["ids_predichos"] = len(pred)
    m["ids_sin_gold_evaluable"] = len(set(pred) - set(gold))
    return m


def _media_desv(valores: list[float]) -> dict:
    media = math.fsum(valores) / len(valores)
    desv = (math.sqrt(math.fsum((v - media) ** 2 for v in valores) / (len(valores) - 1))
            if len(valores) > 1 else 0.0)
    return {"media": media, "desv": desv}


def delta(base: dict[int, dict], variante: dict[int, dict], **meta) -> dict | None:
    """Delta variante - base de las metricas, por semilla comun y agregado (media y desv)."""
    semillas = sorted(set(base) & set(variante))
    if not semillas:
        return None
    por_semilla = {s: {k: variante[s][k] - base[s][k] for k in METRICAS_CSV} for s in semillas}
    return {**meta, "semillas": semillas, "por_semilla": {str(s): v for s, v in por_semilla.items()},
            "agregado": {k: _media_desv([por_semilla[s][k] for s in semillas]) for k in METRICAS_CSV}}


def comparar(metricas: dict[tuple[str, str, int], dict],
             sondeo: dict[tuple[str, int], dict] | None = None) -> dict:
    """`metricas`: (encoder, entrada, semilla) -> metricas. `sondeo`: (encoder, semilla) ->
    metricas del modelo B evaluado con las secciones barajadas (sin reentrenar)."""
    def por(encoder, entrada):
        return {s: m for (e, i, s), m in metricas.items() if e == encoder and i == entrada}

    celdas = {}
    for (encoder, entrada) in sorted({(e, i) for e, i, _ in metricas}):
        corridas = por(encoder, entrada)
        celdas[f"{encoder}|{entrada}"] = {
            "encoder": ENCODERS[encoder], "entrada": entrada, "semillas": sorted(corridas),
            "n": next(iter(corridas.values()))["n"],
            "agregado": dominio.agregar_semillas([corridas[s] for s in sorted(corridas)])}
    deltas = []
    candidatos = [
        *[("entrada", e, f"{e}|A->B", por(e, "A"), por(e, "B"), {"encoder": ENCODERS[e], "a": "A", "b": "B"})
          for e in ENCODERS],
        *[("encoder", i, f"SciBERT->SPECTER|{i}", por("scibert", i), por("specter", i),
           {"entrada": i, "a": "SciBERT", "b": "SPECTER"}) for i in ENTRADAS_MATRIZ],
        *[("ablacion", "scibert", f"B->{ab}", por("scibert", "B"), por("scibert", ab),
           {"encoder": "SciBERT", "a": "B", "b": ab}) for ab in ABLACIONES],
    ]
    for factor, _, nombre, base, variante, meta in candidatos:
        d = delta(base, variante, factor=factor, nombre=nombre, **meta)
        if d:
            deltas.append(d)
    if sondeo:
        for encoder in ENCODERS:
            barajado = {s: m for (e, s), m in sondeo.items() if e == encoder}
            d = delta(por(encoder, "B"), barajado, factor="sondeo_secciones_barajadas",
                      nombre=f"{encoder}|B->B_con_eval_barajado", encoder=ENCODERS[encoder],
                      a="B", b="B (eval con secciones barajadas)")
            if d:
                deltas.append(d)
    return {"estado": "provisional_etiquetas_haiku_no_gold_humano", "celdas": celdas,
            "deltas": deltas,
            "advertencias": [
                "Etiquetas Haiku: no es Gold humano; el Gold v2 no esta congelado (#100).",
                "Con 3 semillas la desviacion es indicativa; no hay prueba de significacion.",
                "La intersección A/B excluye ~46% de los casos (parrafos largos): "
                "no es una muestra aleatoria."]}


def filas_csv(comp: dict) -> list[dict]:
    filas = []
    for clave, c in comp["celdas"].items():
        a = c["agregado"]
        filas.append({"tipo": "celda", "nombre": clave, "semillas": len(c["semillas"]), "n": c["n"],
                      **{f"{k}_{s}": a[k][{"media": "media", "desv": "desv"}[s]]
                         for k in METRICAS_CSV for s in ("media", "desv")}})
    for d in comp["deltas"]:
        filas.append({"tipo": f"delta_{d['factor']}", "nombre": d["nombre"],
                      "semillas": len(d["semillas"]), "n": "",
                      **{f"{k}_{s}": d["agregado"][k][s] for k in METRICAS_CSV
                         for s in ("media", "desv")}})
    return filas


COLUMNAS_CSV = ["tipo", "nombre", "semillas", "n",
                *[f"{k}_{s}" for k in METRICAS_CSV for s in ("media", "desv")]]
