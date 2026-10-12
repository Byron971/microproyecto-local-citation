"""S3 C2: clasificación Qwen con evidencia SciBERT Top-3 no validada.

Reutiliza exactamente el prompt C1 (etiqueta directa) del preetiquetado
histórico y agrega solo evidencia del artículo CITADO. No accede a Gold.
El informe S2.8 debe corresponder byte a byte al corpus de entrada.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import sys
import time
from typing import Any

from proyecto_de_grado.src.data.preparar_preetiquetado import ETIQUETAS
from proyecto_de_grado.src.data.preetiquetar_local import (
    PROMPT_ETIQUETA_DIRECTA,
    cargar_candidatos,
    comprobar_modelo,
    interpretar_etiqueta_directa,
    leer_historial,
)

MODO = "scibert_top3"
VERSION = "s3_c2_scibert_top3_v1"
_ANCLA = "\nReturn exactly ONE category name from this list:"
_BLOQUE = (
    "\nCandidate passages from the CITED paper, retrieved by SciBERT "
    "(not human-validated):\n{retrieved_passages}\n"
    "Use this information only if it helps interpret TARGETCIT. "
    "Do not infer a citation function from the section name alone.\n"
    "Return exactly ONE category name from this list:"
)
if PROMPT_ETIQUETA_DIRECTA.count(_ANCLA) != 1:
    raise RuntimeError("Cambió el contrato del prompt C1: revisar S3 antes de continuar")
PLANTILLA_C2 = PROMPT_ETIQUETA_DIRECTA.replace(_ANCLA, _BLOQUE)


def sha256(contenido: bytes) -> str:
    return hashlib.sha256(contenido).hexdigest()


def validar_reporte(casos: list[dict], input_hash: str, informe: dict) -> dict[str, dict]:
    """Valida identidad de consulta, artículo y chunk antes de cualquier inferencia."""
    if informe.get("tipo") != "comparacion_tecnica_train_s2_8_no_gold":
        raise ValueError("El archivo no es un informe de recuperación S2.8")
    if informe.get("sha256_entrada") != input_hash:
        raise ValueError("Huella del corpus no coincide con el informe SciBERT")
    if informe.get("resumen", {}).get("metricas_gold_calculadas") is not False:
        raise ValueError("El informe debe ser técnico, sin métricas Gold")
    if informe.get("parametros", {}).get("query_sin_marcadores") is not True:
        raise ValueError("No consta la política de consulta sin marcadores S2.8")
    filas = informe.get("resultados")
    if not isinstance(filas, list):
        raise ValueError("Falta lista de resultados S2.8")
    indice = {}
    for fila in filas:
        if not isinstance(fila, dict):
            raise ValueError("Resultado S2.8 no es objeto")
        cid = fila.get("context_id")
        if not isinstance(cid, str) or not cid or cid in indice:
            raise ValueError("IDs vacíos o repetidos en SciBERT")
        indice[cid] = fila
    if set(indice) != {c["id"] for c in casos}:
        raise ValueError("Los IDs del corpus y del informe S2.8 no coinciden exactamente")

    for caso in casos:
        cid = caso["id"]
        fila = indice[cid]
        if caso.get("split") != "train" or fila.get("split") != "train":
            raise ValueError(f"Se detectó otro split en {cid}")
        if not isinstance(caso.get("cited_id"), str) or not caso["cited_id"]:
            raise ValueError(f"Falta cited_id en {cid}")
        if fila.get("cited_id") != caso["cited_id"]:
            raise ValueError(f"Artículo citado distinto en {cid}")
        fragmentos = caso.get("cited_chunks")
        if not isinstance(fragmentos, list) or not fragmentos:
            raise ValueError(f"Faltan chunks del artículo citado en {cid}")
        chunk_por_id = {}
        for c in fragmentos:
            if not isinstance(c, dict):
                raise ValueError(f"Chunk no válido en {cid}")
            ck = c.get("chunk_id")
            if not isinstance(ck, str) or not ck or ck in chunk_por_id:
                raise ValueError(f"chunk_id vacío o duplicado en {cid}")
            if not isinstance(c.get("texto"), str) or not c["texto"].strip():
                raise ValueError(f"Chunk sin texto en {cid}")
            chunk_por_id[ck] = c
        seleccion = fila.get("scibert_top3")
        if not isinstance(seleccion, list) or not 1 <= len(seleccion) <= 3:
            raise ValueError(f"Top-3 faltante o fuera de rango en {cid}")
        ids = []
        for r in seleccion:
            if not isinstance(r, dict):
                raise ValueError(f"Ranking no válido en {cid}")
            ck = r.get("chunk_id")
            valor = r.get("similitud_coseno")
            if ck not in chunk_por_id:
                raise ValueError(f"Chunk SciBERT ajeno al artículo citado en {cid}: {ck}")
            if (not isinstance(valor, (int, float)) or isinstance(valor, bool)
                    or not math.isfinite(valor) or abs(valor) > 1.000001):
                raise ValueError(f"Similitud SciBERT no válida en {cid}")
            ids.append(ck)
        if len(ids) != len(set(ids)):
            raise ValueError(f"Ranking SciBERT contiene chunks repetidos en {cid}")
    return indice


def evidencia_c2(caso: dict, fila: dict) -> tuple[str, list[dict]]:
    """Construye evidencia sin incluir secciones: C3 las tratará por separado."""
    por_id = {c["chunk_id"]: c for c in caso["cited_chunks"]}
    bloques, trazas = [], []
    for posicion, seleccionado in enumerate(fila["scibert_top3"], 1):
        ck = seleccionado["chunk_id"]
        chunk = por_id[ck]
        texto = chunk["texto"]
        bloques.append(f"[{ck} | cited_id={caso['cited_id']}]\n{texto}")
        trazas.append({
            "posicion": posicion,
            "chunk_id": ck,
            "cited_id": caso["cited_id"],
            "text_sha256": sha256(texto.encode("utf-8")),
            "similitud_coseno_no_calibrada": seleccionado["similitud_coseno"],
        })
    return "\n\n".join(bloques), trazas


def crear_prompt_c2(caso: dict, fila: dict) -> str:
    pasajes, _ = evidencia_c2(caso, fila)
    return PLANTILLA_C2.format(
        context=caso["citation_context"],
        title=caso["cited_title"],
        abstract=caso["cited_abstract"],
        retrieved_passages=pasajes,
    )


def huella_ejecucion(modelo: str, input_hash: str, report_hash: str,
                     modelo_scibert_revision: str | None) -> str:
    conf = {
        "version": VERSION,
        "model_qwen": modelo,
        "input_sha256": input_hash,
        "reporte_s2_8_sha256": report_hash,
        "modelo_scibert_commit": modelo_scibert_revision,
        "prompt_plantilla_sha256": sha256(PLANTILLA_C2.encode("utf-8")),
        "codigo_s3_sha256": sha256(Path(__file__).read_bytes()),
        "format": "label",
        "evidence": MODO,
    }
    return sha256(json.dumps(conf, sort_keys=True, ensure_ascii=False).encode("utf-8"))


def ejecutar(casos: list[dict], indice: dict[str, dict], *, cliente: Any,
             salida: Path, run_id: str, limite: int, retry_errors: bool = False) -> dict:
    if limite <= 0 or limite > len(casos):
        raise ValueError("El límite debe estar entre 1 y la longitud del corpus")
    previos = leer_historial(salida, run_id)
    desconocidos = set(previos) - {c["id"] for c in casos}
    if desconocidos:
        raise ValueError("El historial contiene IDs ajenos al corpus")
    salida.parent.mkdir(parents=True, exist_ok=True)
    nuevas, omitidas = 0, 0
    with salida.open("a", encoding="utf-8", newline="\n") as f:
        for caso in casos[:limite]:
            cid = caso["id"]
            previa = previos.get(cid)
            if previa and (not retry_errors or previa.get("status") == "ok"):
                omitidas += 1
                continue
            inicio = time.perf_counter()
            _, trazas = evidencia_c2(caso, indice[cid])
            prompt = crear_prompt_c2(caso, indice[cid])
            bruto = etiqueta = error = None
            entradas = salidas = None
            status = "provider_error"
            try:
                respuesta = cliente.generate(prompt)
                bruto = respuesta.text
                entradas = getattr(respuesta, "input_tokens", None)
                salidas = getattr(respuesta, "output_tokens", None)
            except Exception as exc:
                error = f"{type(exc).__name__}: {str(exc)[:350]}"
            else:
                try:
                    etiqueta = interpretar_etiqueta_directa(bruto)
                    status = "ok"
                except (ValueError, TypeError) as exc:
                    status = "parse_error"
                    error = f"{type(exc).__name__}: {str(exc)[:350]}"
            registro = {
                "id": cid, "split": "train", "model": getattr(cliente, "model", "unknown"),
                "run_fingerprint": run_id, "prompt_sha256": sha256(prompt.encode("utf-8")),
                "response_format": "label", "evidence_mode": MODO, "retrieved_chunks": trazas,
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "status": status, "suggested_label": etiqueta,
                "scores": None, "top1_top2_margin_uncalibrated": None,
                "raw_response": bruto, "input_tokens": entradas, "output_tokens": salidas,
                "latency_seconds": round(time.perf_counter() - inicio, 3),
                "error": error, "is_human_label": False,
            }
            f.write(json.dumps(registro, ensure_ascii=False) + "\n")
            f.flush()
            previos[cid] = registro
            nuevas += 1
            print(f"{nuevas:>2}. {cid}: {status} | {etiqueta or '-'} | {registro['latency_seconds']} s", flush=True)
    seleccionados = [previos[c["id"]] for c in casos[:limite] if c["id"] in previos]
    counts = Counter(r["status"] for r in seleccionados)
    labels = Counter(r["suggested_label"] for r in seleccionados if r["status"] == "ok")
    return {
        "seleccionados": limite,
        "procesados_en_historial": len(seleccionados),
        "nuevas_inferencias": nuevas,
        "omitidos_por_reanudacion": omitidas,
        "estados": dict(sorted(counts.items())),
        "distribucion_sugerida_no_validada": {k: labels.get(k, 0) for k in ETIQUETAS},
        "response_format": "label", "evidence_mode": MODO,
        "nota": "Predicciones automáticas NO Gold, sin calidad de clasificación medida.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--retrieval", type=Path, required=True,
                        help="Informe S2.8 generado exactamente sobre el --input indicado")
    parser.add_argument("--out", type=Path, required=True,
                        help="Carpeta nueva y exclusiva para C2")
    parser.add_argument("--model", default="qwen3:4b-instruct")
    parser.add_argument("--base-url", default="http://localhost:11434/v1")
    parser.add_argument("--limit", type=int, default=2)
    parser.add_argument("--retry-errors", action="store_true")
    parser.add_argument("--solo-validar", action="store_true")
    args = parser.parse_args(argv)
    try:
        casos, input_hash = cargar_candidatos(args.input)
        raw_reporte = args.retrieval.read_bytes()
        informe = json.loads(raw_reporte.decode("utf-8-sig"))
        indice = validar_reporte(casos, input_hash, informe)
        if not 1 <= args.limit <= len(casos):
            raise ValueError(f"El límite debe estar entre 1 y {len(casos)}")
        report_hash = sha256(raw_reporte)
        run_id = huella_ejecucion(args.model, input_hash, report_hash,
                                  informe.get("modelo_commit_resuelto"))
        if args.solo_validar:
            print("S3 C2 VALIDACION APROBADA:", json.dumps({
                "casos": len(casos), "articulos": len({c["cited_id"] for c in casos}),
                "modelo_scibert_commit": informe.get("modelo_commit_resuelto"),
                "input_sha256": input_hash, "reporte_s2_8_sha256": report_hash,
                "run_fingerprint": run_id,
                "sin_gold": True,
            }, ensure_ascii=False))
            return 0
        resultados = args.out / re.sub(r"[^A-Za-z0-9._-]", "_", args.model) / VERSION / "predicciones.jsonl"
        leer_historial(resultados, run_id)
        comprobar_modelo(args.base_url, args.model)
        from src.evaluation.commercial.providers_openweight import OpenWeightClient
        cliente = OpenWeightClient(base_url=args.base_url, model=args.model)
        resumen = ejecutar(casos, indice, cliente=cliente, salida=resultados,
                           run_id=run_id, limite=args.limit, retry_errors=args.retry_errors)
        resumen.update({
            "model": args.model,
            "input": str(args.input), "input_sha256": input_hash,
            "reporte_s2_8": str(args.retrieval), "reporte_s2_8_sha256": report_hash,
            "scibert_model": informe.get("modelo"),
            "scibert_model_commit": informe.get("modelo_commit_resuelto"),
            "prompt_plantilla_sha256": sha256(PLANTILLA_C2.encode("utf-8")),
            "run_fingerprint": run_id,
            "resultados": str(resultados),
        })
        resumen_path = resultados.parent / "resumen.json"
        resumen_path.write_text(json.dumps(resumen, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print("\n=== RESUMEN S3 C2 ===")
        print(json.dumps(resumen, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
