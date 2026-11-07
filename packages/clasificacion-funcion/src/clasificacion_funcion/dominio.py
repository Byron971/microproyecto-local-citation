"""Dominio puro (solo stdlib): taxonomia, metricas y verificacion de fugas."""
import hashlib
import json
import math

CATEGORIAS = (
    "Background",
    "Gap",
    "Basis",
    "Comparison",
    "Application",
    "Improvement / Modification",
    "Evidence",
    "Identification of the Originator",
    "Further Reading",
)
N_CLASES = len(CATEGORIAS)

_ALIAS = {
    "background": 0,
    "gap": 1,
    "basis": 2,
    "comparison": 3,
    "application": 4,
    "improvement / modification": 5,
    "improvement/modification": 5,
    "improvement": 5,
    "modification": 5,
    "evidence": 6,
    "identification of the originator": 7,
    "identification of originator": 7,
    "originator": 7,
    "further reading": 8,
}
# Abstenciones: se cuentan y se reportan, nunca forman una clase 10.
_ABSTENCIONES = {"ambiguo": "Ambiguo", "ambiguous": "Ambiguo",
                 "no evaluable": "No evaluable", "not evaluable": "No evaluable"}


def _limpiar(etiqueta: str) -> str:
    return " ".join(etiqueta.strip().casefold().split())


def normalizar_etiqueta(etiqueta) -> int | None:
    """Indice 0..8 de la categoria; None si es una abstencion (Ambiguo/No evaluable).

    Una etiqueta desconocida lanza ValueError (fail-closed)."""
    if isinstance(etiqueta, bool) or not isinstance(etiqueta, (str, int)):
        raise ValueError(f"Tipo de etiqueta no soportado: {type(etiqueta).__name__}")
    if isinstance(etiqueta, int):
        if 0 <= etiqueta < N_CLASES:
            return etiqueta
        raise ValueError(f"Indice de etiqueta fuera de rango: {etiqueta}")
    limpia = _limpiar(etiqueta)
    if limpia in _ALIAS:
        return _ALIAS[limpia]
    if limpia in _ABSTENCIONES:
        return None
    raise ValueError(f"Etiqueta desconocida: {etiqueta!r}")


def motivo_abstencion(etiqueta) -> str | None:
    """'Ambiguo' | 'No evaluable' si la etiqueta es una abstencion; si no, None."""
    if isinstance(etiqueta, str):
        return _ABSTENCIONES.get(_limpiar(etiqueta))
    return None


def separar_abstenciones(filas: list[dict], clave: str = "etiqueta") -> tuple[list[dict], dict]:
    """Devuelve (filas evaluables con `indice`, conteo de abstenciones por motivo)."""
    evaluables, abstenciones = [], {}
    for fila in filas:
        indice = normalizar_etiqueta(fila[clave])
        if indice is None:
            motivo = motivo_abstencion(fila[clave])
            abstenciones[motivo] = abstenciones.get(motivo, 0) + 1
        else:
            evaluables.append({**fila, "indice": indice})
    return evaluables, dict(sorted(abstenciones.items()))


# ---- hashes
def _sha(obj) -> str:
    return hashlib.sha256(
        json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def sha_ids(ids) -> str:
    """SHA-256 de los ids ordenados (independiente del orden de entrada)."""
    ids = list(ids)
    if len(set(ids)) != len(ids):
        raise ValueError("Ids duplicados.")
    return _sha(sorted(ids))


def sha_etiquetas(etiquetas: dict[str, int]) -> str:
    """SHA-256 de los pares (id, indice de clase) ordenados por id."""
    for indice in etiquetas.values():
        if isinstance(indice, bool) or not isinstance(indice, int) or not 0 <= indice < N_CLASES:
            raise ValueError(f"Indice de clase invalido: {indice!r}")
    return _sha(sorted(etiquetas.items()))


# ---- metricas
def _prf(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return p, r, f


def metricas(verdad: list[int], predicho: list[int]) -> dict:
    """P/R/F1 macro, micro y ponderado, por clase, soporte y matriz 9x9.

    Mismas claves y convencion que `paired_benchmark.model_metrics`
    (zero_division=0; el macro promedia las 9 clases, tambien las sin soporte)."""
    if len(verdad) != len(predicho):
        raise ValueError("verdad y predicho deben tener la misma longitud.")
    if not verdad:
        raise ValueError("Se necesita al menos un caso.")
    for v in (*verdad, *predicho):
        if isinstance(v, bool) or not isinstance(v, int) or not 0 <= v < N_CLASES:
            raise ValueError(f"Indice de clase invalido: {v!r}")
    matriz = [[0] * N_CLASES for _ in range(N_CLASES)]
    for t, p in zip(verdad, predicho):
        matriz[t][p] += 1
    n = len(verdad)
    por_clase, soportes = [], []
    for i in range(N_CLASES):
        tp = matriz[i][i]
        fn = sum(matriz[i]) - tp
        fp = sum(matriz[t][i] for t in range(N_CLASES)) - tp
        p, r, f = _prf(tp, fp, fn)
        soportes.append(tp + fn)
        por_clase.append({"label": CATEGORIAS[i], "support": tp + fn,
                          "precision": p, "recall": r, "f1": f})
    aciertos = sum(matriz[i][i] for i in range(N_CLASES))
    exactitud = aciertos / n
    macro = tuple(math.fsum(c[k] for c in por_clase) / N_CLASES
                  for k in ("precision", "recall", "f1"))
    pond = tuple(math.fsum(c[k] * c["support"] for c in por_clase) / n
                 for k in ("precision", "recall", "f1"))
    # Con las 9 clases y una prediccion por caso, micro P = R = F1 = exactitud.
    return {
        "n": n,
        "accuracy": exactitud,
        "precision_macro": macro[0], "recall_macro": macro[1], "f1_macro": macro[2],
        "precision_micro": exactitud, "recall_micro": exactitud, "f1_micro": exactitud,
        "precision_weighted": pond[0], "recall_weighted": pond[1], "f1_weighted": pond[2],
        "per_class": por_clase,
        "confusion_matrix": matriz,
    }


def pesos_clase(etiquetas: list[int]) -> list[float]:
    """Pesos inversos a la frecuencia: n / (9 * conteo). Clase ausente: 0.0."""
    if not etiquetas:
        raise ValueError("Se necesitan etiquetas.")
    conteo = [0] * N_CLASES
    for e in etiquetas:
        if isinstance(e, bool) or not isinstance(e, int) or not 0 <= e < N_CLASES:
            raise ValueError(f"Indice de clase invalido: {e!r}")
        conteo[e] += 1
    n = len(etiquetas)
    return [n / (N_CLASES * c) if c else 0.0 for c in conteo]


def agregar_semillas(corridas: list[dict]) -> dict:
    """Media y desviacion estandar muestral (ddof=1; 0.0 con una sola semilla)
    de cada metrica escalar y del F1 por clase."""
    if not corridas:
        raise ValueError("Se necesita al menos una corrida.")

    def ms(valores: list[float]) -> dict:
        m = math.fsum(valores) / len(valores)
        sd = (math.sqrt(math.fsum((v - m) ** 2 for v in valores) / (len(valores) - 1))
              if len(valores) > 1 else 0.0)
        return {"media": m, "desv": sd}

    escalares = [k for k, v in corridas[0].items()
                 if k != "n" and isinstance(v, float)]
    for c in corridas:
        if [k for k, v in c.items() if k != "n" and isinstance(v, float)] != escalares:
            raise ValueError("Las corridas no tienen las mismas metricas.")
    salida = {"semillas": len(corridas), **{k: ms([c[k] for c in corridas]) for k in escalares}}
    salida["f1_por_clase"] = [
        {"label": CATEGORIAS[i], **ms([c["per_class"][i]["f1"] for c in corridas])}
        for i in range(N_CLASES)
    ]
    return salida


# ---- fugas
def _sha_texto(caso: dict) -> str:
    return hashlib.sha256(" ".join(caso["citation_context"].split()).encode("utf-8")).hexdigest()


def _claves(caso: dict) -> dict[str, object]:
    return {
        "context_id": caso["context_id"],
        "citing_id": caso["citing_id"],
        "par_citante_citado": (caso["citing_id"], caso["cited_id"]),
        "sha_texto_targetcit": _sha_texto(caso),
    }


def verificar_fugas(
    conjuntos: dict[str, list[dict]],
    excluidos: set[str] | frozenset[str] = frozenset(),
    gold_v2: set[str] | frozenset[str] = frozenset(),
) -> dict:
    """Compara train/val/eval por context_id, citing_id, par (citante, citado) y SHA del
    texto; ademas exclusiones y Gold v2. Cualquier interseccion > 0 lanza ValueError.
    El `cited_id` compartido solo se reporta (no bloquea)."""
    nombres = list(conjuntos)
    indices: dict[str, dict[str, set]] = {}
    for nombre, casos in conjuntos.items():
        ids = [c["context_id"] for c in casos]
        if len(set(ids)) != len(ids):
            raise ValueError(f"context_id duplicado dentro de {nombre}.")
        for c in casos:
            if not isinstance(c.get("citation_context"), str) or not c.get("citing_id") \
                    or not c.get("cited_id"):
                raise ValueError(f"Caso incompleto en {nombre}: {c.get('context_id')}")
        filas = [_claves(c) for c in casos]
        indices[nombre] = {k: {f[k] for f in filas}
                           for k in ("context_id", "citing_id", "par_citante_citado",
                                     "sha_texto_targetcit")}
        indices[nombre]["cited_id"] = {c["cited_id"] for c in casos}
    fugas: dict[str, int] = {}
    for i, a in enumerate(nombres):
        for b in nombres[i + 1:]:
            for clave in ("context_id", "citing_id", "par_citante_citado", "sha_texto_targetcit"):
                fugas[f"{a}~{b}:{clave}"] = len(indices[a][clave] & indices[b][clave])
    for nombre in nombres:
        fugas[f"{nombre}~excluidos:context_id"] = len(indices[nombre]["context_id"] & set(excluidos))
        fugas[f"{nombre}~gold_v2:context_id"] = len(indices[nombre]["context_id"] & set(gold_v2))
    compartidos = {
        f"{a}~{b}": len(indices[a]["cited_id"] & indices[b]["cited_id"])
        for i, a in enumerate(nombres) for b in nombres[i + 1:]
    }
    reporte = {
        "conjuntos": {n: len(c) for n, c in conjuntos.items()},
        "fugas": fugas,
        "total_fugas": sum(fugas.values()),
        "cited_id_compartidos_no_bloqueante": compartidos,
    }
    if reporte["total_fugas"]:
        detalle = {k: v for k, v in fugas.items() if v}
        raise ValueError(f"Fuga entre conjuntos: {detalle}")
    return reporte
