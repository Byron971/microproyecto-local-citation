"""Pre-etiquetado LOCAL y reanudable para candidatos de entrenamiento.

Reutiliza OpenWeightClient y parse_score_array de src/evaluation/commercial.
No consume gold, no modifica ACL-200 y no ejecuta inferencia al importar.
Las predicciones son sugerencias automáticas, NO anotaciones humanas.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import inspect
import json
from pathlib import Path
import re
import sys
import time
from typing import Any, Callable

from proyecto_de_grado.src.data.preparar_preetiquetado import ETIQUETAS
from src.app.fragment_retrieval import recuperar_top3

DEFAULT_INPUT = Path("proyecto_de_grado/artifacts/preetiquetado/candidatos_train_300.jsonl")
DEFAULT_OUT_DIR = Path("proyecto_de_grado/artifacts/preetiquetado")

# Una sola etiqueta principal. Puntajes NO calibrados: solo ranking interno.
PROMPT = """You are an expert annotator of citation functions in academic papers.
Classify ONLY the citation marked TARGETCIT in the citing context. OTHERCIT
marks other references, which must not determine the target's function.
Choose EXACTLY ONE predominant rhetorical function, using these categories
in the following fixed order:
1. Background: general context, prior literature or field history.
2. Gap: limitation or missing work, motivating the present research.
3. Basis: conceptual foundation directly informing the present research.
4. Comparison: explicit contrast of methods, results or prior work.
5. Application: direct use of a cited method, dataset or tool unmodified.
6. Improvement / Modification: adaptation, extension or modification of cited work.
7. Evidence: citation directly supports a claim or finding.
8. Identification of the Originator: attribution of an original idea/method.
9. Further Reading: pointer to additional reading or supplementary detail.

Citation context (TARGETCIT identifies the cited work to classify):
{context}

Cited paper title: {title}
Cited paper abstract: {abstract}

Reply ONLY with a JSON array of EXACTLY 9 numbers from 0.0 to 1.0, one score per
category in the order above. The highest score must indicate your ONE selected
main function. Avoid equal top scores. These scores are comparative rankings,
not calibrated probabilities. No explanation, no Markdown, no extra text."""

# Réplica EXPLÍCITA del protocolo exploratorio de 10-oct-2026:
# mismo preámbulo y datos, sustituyendo solamente el formato de respuesta.
# Mantener PROMPT intacto: su hash identifica los experimentos históricos.
PROMPT_ETIQUETA_DIRECTA = PROMPT.partition("Reply ONLY with a JSON array")[0] + (
    "\nReturn exactly ONE category name from this list:\n"
    + "\n".join(ETIQUETAS)
    + "\nNo scores. No explanation. No additional text."
)
FORMATOS = ("scores", "label")
EVIDENCIAS = ("none", "bm25_top2")
_BM25_TOP_K = 2
# Mismo prompt de etiqueta directa y un bloque nuevo de evidencia. La
# relevancia de los fragmentos BM25 NO está adjudicada por humanos.
_PROMPT_CON_EVIDENCIA = PROMPT_ETIQUETA_DIRECTA.replace(
    "\nReturn exactly ONE category name from this list:",
    "\nCandidate passages from the CITED paper, retrieved by BM25 (not human-validated):\n"
    "{retrieved_passages}\n"
    "Use this information only if it helps interpret TARGETCIT. "
    "Do not infer a citation function from the section name alone.\n"
    "Return exactly ONE category name from this list:",
)




def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def cargar_candidatos(ruta: Path) -> tuple[list[dict], str]:
    raw = ruta.read_bytes()
    if not raw.strip():
        raise ValueError("Archivo de candidatos vacío")
    candidatos: list[dict] = []
    vistos: set[str] = set()
    for num, linea in enumerate(raw.decode("utf-8-sig").splitlines(), start=1):
        if not linea.strip():
            continue
        try:
            r = json.loads(linea)
        except json.JSONDecodeError as exc:
            raise ValueError(f"JSON inválido, línea {num}") from exc
        if not isinstance(r, dict):
            raise ValueError(f"Línea {num}: se esperaba un objeto")
        cid = r.get("id")
        if not isinstance(cid, str) or not cid or cid in vistos:
            raise ValueError(f"Línea {num}: ID vacío o repetido")
        vistos.add(cid)
        if r.get("split") != "train" or any(k in r for k in ("gold", "label", "suggested_label")):
            raise ValueError(f"Línea {num}: contiene otra partición o etiquetas previas")
        texto = r.get("citation_context")
        if not isinstance(texto, str) or texto.count("TARGETCIT") != 1:
            raise ValueError(f"Línea {num}: TARGETCIT no aparece exactamente una vez")
        for k in ("cited_title", "cited_abstract"):
            if not isinstance(r.get(k), str):
                raise ValueError(f"Línea {num}: {k} no es texto")
        if not r["cited_title"].strip():
            raise ValueError(f"Línea {num}: título citado vacío")
        candidatos.append(r)
    if not candidatos:
        raise ValueError("No hay candidatos válidos")
    return candidatos, sha256_bytes(raw)


def _seleccionar_prompt(formato: str) -> str:
    if formato == "scores":
        return PROMPT
    if formato == "label":
        return PROMPT_ETIQUETA_DIRECTA
    raise ValueError(f"Formato no válido: {formato!r}")


def _evidencia_bm25(caso: dict) -> tuple[str, list[dict]]:
    if caso.get("split") != "train" or not isinstance(caso.get("cited_chunks"), list):
        raise ValueError("Evidencia OCL requiere fragmentos del cited paper y split train")
    chunks = caso["cited_chunks"]
    if not chunks:
        raise ValueError("No hay fragmentos OCL disponibles para recuperación")
    ids = [x.get("chunk_id") for x in chunks if isinstance(x, dict)]
    if (len(ids) != len(chunks) or any(not isinstance(i, str) or not i for i in ids)
            or len(set(ids)) != len(ids)):
        raise ValueError("Fragmentos OCL sin IDs únicos")
    if any(not isinstance(ch.get("texto"), str) or not ch["texto"].strip()
           or not isinstance(ch.get("paragraph_indices"), list)
           or len(ch["paragraph_indices"]) not in (1, 2)
           or len(ch["texto"].split()) > 300 for ch in chunks):
        raise ValueError("Fragmentos OCL no cumplen contrato S2.4")
    seleccion = recuperar_top3(caso["citation_context"], chunks)[:_BM25_TOP_K]
    if not seleccion:
        raise ValueError("Sin coincidencias léxicas BM25: caso no pareado")
    texto = "\n\n".join(
        f"[{x['chunk_id']} | cited_id={caso['cited_id']} | "
        f"section={x.get('seccion') or 'unknown'}]\n{x['texto']}"
        for x in seleccion
    )
    trazas = [{
        "chunk_id": x["chunk_id"],
        "paragraph_indices": x.get("paragraph_indices", []),
        "bm25_score_uncalibrated": x["puntaje_bm25"],
        "text_sha256": sha256_bytes(x["texto"].encode("utf-8")),
    } for x in seleccion]
    return texto, trazas


def crear_prompt(
    caso: dict, *, formato: str = "scores", evidencia: str = "none",
) -> str:
    if evidencia == "none":
        plantilla = _seleccionar_prompt(formato)
        fragmentos = None
    elif evidencia == "bm25_top2" and formato == "label":
        plantilla = _PROMPT_CON_EVIDENCIA
        fragmentos, _ = _evidencia_bm25(caso)
    else:
        raise ValueError("Combinación de formato/evidencia no admitida")
    return plantilla.format(
        context=caso["citation_context"],
        title=caso["cited_title"],
        abstract=caso["cited_abstract"],
        retrieved_passages=fragmentos,
    )


def interpretar_etiqueta_directa(texto: str) -> str:
    """Solo acepta una clase completa: nunca adivina ni extrae subcadenas.

    En particular, rechaza explicaciones, listas de varias categorías y
    números. Conservar el texto original permite auditar fallos de formato.
    """
    if not isinstance(texto, str):
        raise ValueError("Respuesta de etiqueta no textual")
    etiqueta = texto.strip()
    if etiqueta not in ETIQUETAS:
        raise ValueError("La respuesta no es una de las nueve etiquetas exactas")
    return etiqueta


def interpretar_puntajes(puntajes: list[float]) -> tuple[str | None, float, str]:
    """Si la salida no tiene un ganador único, no inventa una clase."""
    if len(puntajes) != len(ETIQUETAS):
        raise ValueError("Se necesitan nueve puntajes")
    if any(not isinstance(x, (int, float)) or isinstance(x, bool) or not 0 <= x <= 1 for x in puntajes):
        raise ValueError("Los puntajes deben ser números en [0,1]")
    indices = sorted(range(len(puntajes)), key=lambda i: puntajes[i], reverse=True)
    margen = float(puntajes[indices[0]] - puntajes[indices[1]])
    if puntajes[indices[0]] == 0 or margen < 1e-8:
        return None, margen, "ambiguo"
    return ETIQUETAS[indices[0]], margen, "ok"


def _plantilla(formato: str, evidencia: str) -> str:
    if evidencia == "none":
        return _seleccionar_prompt(formato)
    if evidencia == "bm25_top2" and formato == "label":
        return _PROMPT_CON_EVIDENCIA
    raise ValueError("Combinación de formato/evidencia no admitida")


def fingerprint(
    modelo: str, input_hash: str, *, formato: str = "scores", evidencia: str = "none",
) -> str:
    # Compatibilidad bit a bit con scores y label SIN evidencia ya ejecutados.
    prompt = _plantilla(formato, evidencia)
    configuracion = {
        "modelo": modelo,
        "input_sha256": input_hash,
        "prompt_sha256": sha256_bytes(prompt.encode("utf-8")),
    }
    if formato == "label":
        configuracion["response_format"] = "label"
        configuracion["prompt_version"] = "etiqueta_directa_v1"
    if evidencia == "bm25_top2":
        configuracion["retrieval_method"] = evidencia
        configuracion["retrieval_top_k"] = _BM25_TOP_K
        configuracion["retriever_sha256"] = sha256_bytes(
            inspect.getsource(recuperar_top3).encode("utf-8")
        )
    return sha256_bytes(
        json.dumps(configuracion, sort_keys=True, ensure_ascii=False).encode("utf-8")
    )


def leer_historial(ruta: Path, id_run: str) -> dict[str, dict]:
    recientes = {}
    if not ruta.exists():
        return recientes
    for i, linea in enumerate(ruta.read_text(encoding="utf-8").splitlines(), start=1):
        if not linea.strip():
            continue
        try:
            registro = json.loads(linea)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Historial corrupto en línea {i}") from exc
        if registro.get("run_fingerprint") != id_run:
            raise ValueError("Salida incompatible con modelo, prompt o muestra. Usa otra carpeta --out")
        recientes[registro["id"]] = registro
    return recientes


def ejecutar(
    casos: list[dict],
    *,
    cliente: Any,
    parser: Callable[[str], list[float]],
    ruta_resultados: Path,
    id_run: str,
    limite: int,
    reintentar_errores: bool = False,
    formato: str = "scores",
    evidencia: str = "none",
) -> dict:
    prompt_usado = _plantilla(formato, evidencia)
    if limite <= 0:
        raise ValueError("El límite debe ser positivo")
    if limite > len(casos):
        raise ValueError(f"La muestra tiene solo {len(casos)} casos; solicitado: {limite}")
    recientes = leer_historial(ruta_resultados, id_run)
    ruta_resultados.parent.mkdir(parents=True, exist_ok=True)
    nuevas = 0
    saltadas = 0
    with ruta_resultados.open("a", encoding="utf-8", newline="\n") as out:
        for caso in casos[:limite]:
            cid = caso["id"]
            anterior = recientes.get(cid)
            if anterior and (not reintentar_errores or anterior.get("status") == "ok"):
                saltadas += 1
                continue
            inicio = time.perf_counter()
            bruto = None
            puntajes = None
            sugerida = None
            margen = None
            tokens_entrada = None
            tokens_salida = None
            estado = "provider_error"
            error = None
            traza_evidencia = []
            try:
                if evidencia == "bm25_top2":
                    _, traza_evidencia = _evidencia_bm25(caso)
                respuesta = cliente.generate(
                    crear_prompt(caso, formato=formato, evidencia=evidencia)
                )
                bruto = respuesta.text
                tokens_entrada = getattr(respuesta, "input_tokens", None)
                tokens_salida = getattr(respuesta, "output_tokens", None)
            except Exception as exc:
                error = f"{type(exc).__name__}: {str(exc)[:350]}"
            else:
                try:
                    if formato == "label":
                        sugerida = interpretar_etiqueta_directa(bruto)
                        estado = "ok"
                    else:
                        puntajes = parser(bruto)
                        sugerida, margen, estado = interpretar_puntajes(puntajes)
                except (ValueError, TypeError) as exc:
                    estado = "parse_error"
                    error = f"{type(exc).__name__}: {str(exc)[:350]}"
            registro = {
                "id": cid,
                "split": "train",
                "model": getattr(cliente, "model", "unknown"),
                "run_fingerprint": id_run,
                "prompt_sha256": sha256_bytes(prompt_usado.encode("utf-8")),
                "response_format": formato,
                "evidence_mode": evidencia,
                "retrieved_chunks": traza_evidencia,

                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "status": estado,
                "suggested_label": sugerida,
                "scores": puntajes,
                "top1_top2_margin_uncalibrated": margen,
                "raw_response": bruto,
                "input_tokens": tokens_entrada,
                "output_tokens": tokens_salida,
                "latency_seconds": round(time.perf_counter() - inicio, 3),
                "error": error,
                "is_human_label": False,
            }
            out.write(json.dumps(registro, ensure_ascii=False) + "\n")
            out.flush()
            recientes[cid] = registro
            nuevas += 1
            print(f"{nuevas:>2}. {cid}: {estado} | {sugerida or '-'} | {registro['latency_seconds']} s", flush=True)
    seleccionados = {r["id"] for r in casos[:limite]}
    ultimo = [recientes[cid] for cid in seleccionados if cid in recientes]
    conteos = Counter(r["status"] for r in ultimo)
    clases = Counter(r["suggested_label"] for r in ultimo if r["status"] == "ok")
    return {
        "seleccionados": limite,
        "procesados_en_historial": len(ultimo),
        "nuevas_inferencias": nuevas,
        "omitidos_por_reanudacion": saltadas,
        "estados": dict(sorted(conteos.items())),
        "distribucion_sugerida_no_validada": {k: clases.get(k, 0) for k in ETIQUETAS},
        "response_format": formato,
        "evidence_mode": evidencia,
        "nota": "Predicciones automáticas NO calibradas y NO validadas por humanos; no representan cuotas reales por clase.",
    }


def comprobar_modelo(base_url: str, modelo: str) -> None:
    """Verifica Ollama/OpenAI-compatible antes de procesar el lote completo."""
    from urllib.request import urlopen
    url = base_url.rstrip("/") + "/models"
    try:
        with urlopen(url, timeout=5) as resp:
            payload = json.loads(resp.read())
    except Exception as exc:
        raise RuntimeError(f"No se pudo consultar el servidor local ({url}): {exc}") from exc
    modelos = [m.get("id") for m in payload.get("data", []) if isinstance(m, dict)]
    if modelo not in modelos:
        raise RuntimeError(f"Modelo {modelo!r} no disponible en {url}. Modelos: {modelos}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT_DIR)
    ap.add_argument("--model", default="qwen3:4b-instruct")
    ap.add_argument("--base-url", default="http://localhost:11434/v1")
    ap.add_argument("--limit", type=int, default=10)
    ap.add_argument("--retry-errors", action="store_true")
    ap.add_argument(
        "--format", dest="formato", choices=FORMATOS, default="scores",
        help="scores: nueve puntajes históricos; label: una clase literal sin puntuaciones",
    )
    ap.add_argument(
        "--evidence", choices=EVIDENCIAS, default="none",
        help="none: historial intacto; bm25_top2: dos fragmentos del cited paper",
    )
    args = ap.parse_args(argv)
    try:
        casos, input_hash = cargar_candidatos(args.input)
        id_run = fingerprint(
            args.model, input_hash, formato=args.formato, evidencia=args.evidence
        )
        carpeta = args.out / re.sub(r"[^A-Za-z0-9._-]", "_", args.model)
        if args.formato == "label":
            carpeta = carpeta / "etiqueta_directa_v1"
        if args.evidence == "bm25_top2":
            carpeta = carpeta / "evidencia_bm25_top2_v1"
        resultados = carpeta / "predicciones.jsonl"
        # Fallar antes de ejecutar si un historial previo corresponde a otro experimento.
        leer_historial(resultados, id_run)
        if args.limit < 1 or args.limit > len(casos):
            raise ValueError(f"--limit debe estar entre 1 y {len(casos)}")
        comprobar_modelo(args.base_url, args.model)
        from src.evaluation.commercial.providers_openweight import OpenWeightClient
        from src.evaluation.commercial.stability import parse_score_array
        cliente = OpenWeightClient(model=args.model, base_url=args.base_url)
        resumen = ejecutar(
            casos, cliente=cliente, parser=parse_score_array,
            ruta_resultados=resultados, id_run=id_run, limite=args.limit,
            reintentar_errores=args.retry_errors,
            formato=args.formato,
            evidencia=args.evidence,
        )
        resumen.update({
            "model": args.model,
            "response_format": args.formato,
            "evidence_mode": args.evidence,
            "prompt_sha256": sha256_bytes(_plantilla(args.formato, args.evidence).encode("utf-8")),
            "input": str(args.input),
            "input_sha256": input_hash,
            "run_fingerprint": id_run,
            "resultados": str(resultados),
        })
        resumen_path = carpeta / "resumen.json"
        resumen_path.write_text(json.dumps(resumen, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print("\n=== RESUMEN ===")
        print(json.dumps(resumen, ensure_ascii=False, indent=2))
        print("Resultados:", resultados)
        return 0
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
