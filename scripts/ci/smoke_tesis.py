"""Smoke de aceptación: baseline vs inferencia científica REAL, SIN Test Gold.

En modo --cientifico exige SciBERT y A4 cargados en backend; no permite
fallback a BM25. El reporte guarda metadatos, no textos ni etiquetas Gold.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from urllib.parse import urlparse

def validar_url(base: str, permitir_remoto: bool = False) -> str:
    parsed = urlparse(base)
    if (parsed.scheme not in ("http", "https") or not parsed.hostname
            or parsed.username or parsed.password or parsed.query or parsed.fragment
            or parsed.path not in ("", "/")):
        raise ValueError("URL base HTTP(S) inválida.")
    local = parsed.hostname in ("localhost", "127.0.0.1", "::1")
    if not local and (not permitir_remoto or parsed.scheme != "https"):
        raise ValueError("Se requiere HTTPS y --permitir-remoto para servicios externos.")
    return base.rstrip("/")


CONTEXT = "Graph neural networks learn representations TARGETCIT."
CITED_TITLE = "Neural Graph Methods"
CITED_ABSTRACT = "We study and compare graph representation methods."
MANUAL = {
    "contexto": CONTEXT,
    "cited_id": "P14-1001",
    "parrafos": [
        {"chunk_id": "p1", "texto": "Graph networks learn embeddings.", "seccion": "Methods"},
        {"chunk_id": "p2", "texto": "Translation compares language pairs.", "seccion": "Results"},
        {"chunk_id": "p3", "texto": "Graph models are used for science.", "seccion": "Background"},
    ],
}


def _request(base: str, path: str, payload: dict | None, timeout: float) -> dict:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = Request(base + path, data=data,
                  headers={"Content-Type": "application/json"} if data else {},
                  method="POST" if data is not None else "GET")
    with urlopen(req, timeout=timeout) as resp:
        if resp.status != 200:
            raise RuntimeError(f"{path} HTTP {resp.status}.")
        body = json.load(resp)
        if not isinstance(body, dict):
            raise RuntimeError(f"{path}: respuesta no es objeto JSON.")
        return body


def validar_demo(base: str, scientific: bool = False, timeout: float = 20.0,
                 request=_request) -> dict:
    """No se ejecuta inferencia pesada en CI a menos que se solicite explícitamente."""
    if timeout <= 0 or timeout > 120:
        raise ValueError("Timeout permitido: >0 y <=120 segundos.")
    status = request(base, "/api/estado", None, timeout)
    if status.get("listo") is not True:
        raise RuntimeError("Modelo empaquetado base no está listo.")
    rec = request(base, "/api/recomendar", {"contexto": CONTEXT, "top_k": 3}, timeout)
    if rec.get("modelo") != "tfidf_reranker_v1" or not rec.get("recomendaciones"):
        raise RuntimeError("Recomendador base no devolvió resultados genuinos.")
    lexical = request(base, "/api/top3-fragmentos", MANUAL, timeout)
    if lexical.get("metodo") != "BM25_lexico_baseline" or not lexical.get("fragmentos"):
        raise RuntimeError("BM25 no está disponible o devolvió un modelo distinto.")
    result = {
        "estado": "aceptacion_tecnica_sin_gold",
        "fecha_utc": datetime.now(timezone.utc).isoformat(),
        "nivel": "cientifico" if scientific else "baseline",
        "baseline": {"tfidf_model": rec["modelo"], "bm25_method": lexical["metodo"],
                     "recomendaciones": len(rec["recomendaciones"]),
                     "fragmentos_bm25": len(lexical["fragmentos"])},
        "gold_certificado": False,
        "advertencia": "Ejemplos ilustrativos; no son Test Gold ni prueba de relevancia.",
    }
    if scientific:
        capabilities = request(base, "/api/capacidades", None, timeout)
        tasks = capabilities.get("tareas") or {}
        if not tasks.get("top3_scibert", {}).get("disponible"):
            raise RuntimeError("No hay SciBERT real cargado; smoke científico BLOQUEADO.")
        if not tasks.get("clasificacion_nueve_funciones", {}).get("disponible"):
            raise RuntimeError("No hay clasificador A4 real cargado; smoke científico BLOQUEADO.")
        if not tasks.get("clasificacion_nueve_funciones_b", {}).get("disponible"):
            raise RuntimeError("No hay clasificador A4-B real cargado; smoke científico BLOQUEADO.")
        dense = request(base, "/api/top3-scibert", MANUAL, timeout)
        if (dense.get("metodo") != "scibert_base_mean_pooling_cosine"
                or not dense.get("fragmentos")
                or dense.get("revision") != tasks["top3_scibert"].get("revision")):
            raise RuntimeError("SciBERT no produjo ranking real trazable.")
        classification = request(base, "/api/clasificar-cita", {
            "contexto": CONTEXT,
            "cited_title": CITED_TITLE,
            "cited_abstract": CITED_ABSTRACT,
        }, timeout)
        scores = classification.get("puntuaciones_softmax")
        if (classification.get("validacion") != "provisional_no_gold_humano"
                or classification.get("training_labels") != "Haiku"
                or classification.get("entrada") != "A"
                or not isinstance(scores, list) or len(scores) != 9):
            raise RuntimeError("La clasificación científica no conserva el contrato A4.")
        if classification.get("modelo") != tasks["clasificacion_nueve_funciones"].get("modelo"):
            raise RuntimeError("Clasificador respondió con un modelo distinto del cargado.")
        stage_b = request(base, "/api/clasificar-cita-b", MANUAL, timeout)
        dense_b = stage_b.get("recuperacion") or {}
        class_b = stage_b.get("clasificacion") or {}
        if (dense_b.get("metodo") != "scibert_base_mean_pooling_cosine"
                or len(dense_b.get("fragmentos") or []) != 3):
            raise RuntimeError("Entrada B no recuperó tres fragmentos por SciBERT.")
        if (class_b.get("modelo") != tasks["clasificacion_nueve_funciones_b"].get("modelo")
                or class_b.get("entrada") != "B"
                or class_b.get("validacion") != "provisional_no_gold_humano"
                or len(class_b.get("puntuaciones_softmax") or []) != 9):
            raise RuntimeError("La clasificación B real no respetó los nueve roles A4.")
        if stage_b.get("gold_certificado") is not False:
            raise RuntimeError("La salida B no puede presentarse como Gold certificado.")
        result["cientifico"] = {
            "scibert_revision": dense["revision"],
            "scibert_modelo": dense["modelo"],
            "scibert_fragmentos": len(dense["fragmentos"]),
            "clasificador": classification["modelo"],
            "clasificador_entrada": classification["entrada"],
            "num_funciones": len(scores),
            "clasificador_b": class_b["modelo"],
            "entrada_b": class_b["entrada"],
            "fragmentos_b": len(dense_b["fragmentos"]),
            "training_labels": "Haiku",
            "validacion": "provisional_no_gold_humano",
        }
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--cientifico", action="store_true",
                        help="Exige SciBERT y A4 REALMENTE cargados, sin fallback.")
    parser.add_argument("--permitir-remoto", action="store_true")
    parser.add_argument("--timeout", type=float, default=20)
    parser.add_argument("--salida", type=Path, required=True,
                        help="Escribir reporte JSON nuevo, sin sobrescribir.")
    a = parser.parse_args(argv)
    try:
        base = validar_url(a.url, a.permitir_remoto)
        result = validar_demo(base, a.cientifico, a.timeout)
        a.salida.parent.mkdir(parents=True, exist_ok=True)
        with a.salida.open("x", encoding="utf-8") as out:
            json.dump(result, out, indent=2, ensure_ascii=False)
            out.write("\n")
    except (RuntimeError, ValueError, OSError, HTTPError, URLError) as exc:
        parser.exit(2, f"Fallo smoke de demostrador: {exc}\n")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
