"""Formatos de salida compatibles con `paired_benchmark` (solo stdlib).

- Gold JSONL recortado a la interseccion: `index_gold` (id, citing_id, cited_id, input, gold).
- Predicciones JSONL: `index_predictions` (case_id, status, pred_label/pred_index).
Las predicciones NUNCA llevan la etiqueta verdadera."""
import json
import math

from . import dominio

ESQUEMA_PREDICCION = ("case_id", "status", "pred_label", "pred_index", "model_id",
                      "model_version", "experiment_id", "scores_9", "latency_ms",
                      "gold_manifest_sha256")


def fila_gold(entrada: dict) -> dict:
    """Fila de Gold provisional (etiqueta Haiku) para una entrada etiquetada."""
    indice = entrada.get("indice")
    if indice is None:
        raise ValueError(f"Entrada sin etiqueta: {entrada.get('context_id')}")
    return {"id": entrada["context_id"], "citing_id": entrada["citing_id"],
            "cited_id": entrada["cited_id"], "input": entrada["citation_context"],
            "gold": dominio.CATEGORIAS[indice]}


def filas_gold(entradas: list[dict]) -> list[dict]:
    return [fila_gold(e) for e in sorted(entradas, key=lambda e: e["context_id"])]


def fila_prediccion(case_id: str, scores: list[float], *, model_id: str, model_version: str,
                    experiment_id: str, latency_ms: float, gold_manifest_sha256: str | None) -> dict:
    """Fila de prediccion. `scores` son las 9 probabilidades (softmax); empate -> menor indice."""
    if not isinstance(case_id, str) or not case_id.strip():
        raise ValueError("case_id vacio.")
    if not isinstance(scores, (list, tuple)) or len(scores) != dominio.N_CLASES:
        raise ValueError("scores debe tener exactamente 9 valores.")
    for s in scores:
        if isinstance(s, bool) or not isinstance(s, (int, float)) or not math.isfinite(s) \
                or not 0.0 <= s <= 1.0:
            raise ValueError("scores debe contener numeros finitos entre 0 y 1.")
    indice = max(range(dominio.N_CLASES), key=lambda i: (scores[i], -i))
    return {"case_id": case_id, "status": "ok", "pred_label": dominio.CATEGORIAS[indice],
            "pred_index": indice, "model_id": model_id, "model_version": model_version,
            "experiment_id": experiment_id, "scores_9": [float(s) for s in scores],
            "latency_ms": float(latency_ms), "gold_manifest_sha256": gold_manifest_sha256}


def jsonl_texto(filas: list[dict]) -> str:
    return "".join(json.dumps(f, ensure_ascii=False, sort_keys=True) + "\n" for f in filas)
