"""S2.2: exportar casos ACL-200 train y fragmentos del articulo CITADO en ACL OCL.

Transformacion sin red, sin etiquetas humanas y sin escribir datos originales.
Produce un pequeno artefacto local NO versionado. Su proposito es comprobar
la integracion de datos reales con BM25, NO medir Recall@3 o MRR@3.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from proyecto_de_grado.src.data.integrar_acl import integrar_contexto
from proyecto_de_grado.src.data.preparar_preetiquetado import leer_exclusiones
from proyecto_de_grado.src.data.validar_splits import load_split_index

REPO = Path(__file__).resolve().parents[3]
CACHE = REPO / "proyecto_de_grado/scripts/spike_enlace_datos/cache_ocl"
SALIDA = REPO / "proyecto_de_grado/artifacts/top3_s2/casos_train.json"
MAX_PALABRAS = 300
MAX_PARRAFOS_CHUNK = 2
MAX_CARACTERES = 5000


def fragmentar(parrafos: list[dict]) -> list[dict]:
    """Agrupa hasta dos parrafos contiguos de la MISMA seccion, <=300 palabras.

    No trunca ni omite texto largo: el articulo completo se declara no
    apto para este prototipo si algun parrafo supera el presupuesto.
    """
    if not parrafos:
        raise ValueError("Articulo sin parrafos.")
    chunks = []
    pendientes: list[dict] = []
    palabras = 0
    seccion_anterior = None

    def cerrar() -> None:
        nonlocal pendientes, palabras
        if not pendientes:
            return
        chunks.append({
            "chunk_id": f"p{pendientes[0]['numero']:05d}-p{pendientes[-1]['numero']:05d}",
            "texto": "\n".join(p["texto"] for p in pendientes),
            "seccion": seccion_anterior,
            "paragraph_indices": [p["numero"] for p in pendientes],
            "palabras": palabras,
        })
        pendientes = []
        palabras = 0

    numeros = set()
    for p in parrafos:
        numero, texto, seccion = p["numero"], p["texto"], p["seccion"]
        if not isinstance(numero, int) or numero < 0 or numero in numeros:
            raise ValueError("Indice de parrafo invalido o duplicado.")
        numeros.add(numero)
        if not isinstance(texto, str) or not texto.strip():
            raise ValueError("Parrafo sin texto.")
        if not isinstance(seccion, str):
            raise ValueError("Seccion invalida.")
        n = len(texto.split())
        if n > MAX_PALABRAS or len(texto) > MAX_CARACTERES:
            raise ValueError("Parrafo demasiado largo: requiere division por oraciones.")
        if pendientes and (
            len(pendientes) >= MAX_PARRAFOS_CHUNK
            or palabras + n > MAX_PALABRAS
            or seccion != seccion_anterior
            or numero != pendientes[-1]["numero"] + 1
        ):
            cerrar()
        pendientes.append(p)
        palabras += n
        seccion_anterior = seccion
    cerrar()
    if not chunks:
        raise ValueError("Articulo sin fragmentos.")
    return chunks


def preparar(
    contextos: dict, papers: dict, by_context: dict[str, str],
    cache: Path, excluidos: set[str], limite: int = 5,
) -> tuple[list[dict], dict]:
    """Solo train; unico articulo citado por caso; sin fuga de IDs reservados."""
    if limite < 1:
        raise ValueError("limite debe ser positivo")
    registros, motivos = [], Counter()
    citados_vistos = set()
    for cid, split in sorted(by_context.items()):
        if len(registros) >= limite:
            break
        if split != "train" or cid in excluidos:
            continue
        ctx = contextos[cid]
        citado = ctx["refid"]
        if citado in citados_vistos:
            continue
        ruta = cache / f"{citado}.json"
        if not ruta.is_file():
            motivos["sin_cache_citado"] += 1
            continue
        try:
            registro = integrar_contexto(cid, contextos, papers, cache)
            chunks = fragmentar(registro["paragraphs"])
        except (KeyError, TypeError, ValueError, OSError, json.JSONDecodeError) as exc:
            motivos[type(exc).__name__] += 1
            continue
        if registro["cited_id"] != registro["ocl_paper_id"] or registro["citation_context"].count("TARGETCIT") != 1:
            raise ValueError("Invariante de cita/articulo rota.")
        citados_vistos.add(citado)
        registros.append({
            "context_id": cid,
            "split": "train",
            "citing_id": registro["citing_id"],
            "cited_id": citado,
            "cited_title": registro["cited_title"],
            "citation_context": registro["citation_context"],
            "sha256_ocl_citado": hashlib.sha256(ruta.read_bytes()).hexdigest(),
            "chunks": chunks,
            "reconstruccion": "contexto_acl200_original_sin_adjudicacion",
        })

    return registros, {
        "tipo": "muestra_desarrollo_train_no_gold",
        "total": len(registros),
        "limite": limite,
        "exclusiones_suministradas": len(excluidos),
        "motivos_no_seleccion": dict(sorted(motivos.items())),
        "regla_chunks": "hasta 2 parrafos contiguos por seccion y maximo 300 palabras",
        "nota": "No contiene etiquetas humanas ni relevancia Top3; no reportar metricas cientificas.",
    }


def exportar(
    raw: Path, cache: Path, salida: Path, excluidos: set[str], limite: int
) -> dict:
    indice = load_split_index(raw)
    papers = json.loads((raw / "papers.json").read_text(encoding="utf-8-sig"))
    registros, resumen = preparar(indice.contexts, papers, indice.by_context, cache, excluidos, limite)
    if not registros:
        raise ValueError("No hay casos train con ACL OCL en cache; no se creo archivo.")
    payload = {"version": 1, "resumen": resumen, "casos": registros}
    salida.parent.mkdir(parents=True, exist_ok=True)
    salida.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"S2.2 | casos train: {len(registros)} | archivo local: {salida}")
    print("IDs:", ", ".join(r["context_id"] for r in registros))
    print("No es Gold ni validacion de calidad cientifica.")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", type=Path, default=REPO / "data/raw")
    parser.add_argument("--cache", type=Path, default=CACHE)
    parser.add_argument("--salida", type=Path, default=SALIDA)
    parser.add_argument("--limite", type=int, default=5)
    parser.add_argument("--exclude", type=Path, default=REPO / "proyecto_de_grado/anotacion/ids_excluir_test_gold.txt")
    parser.add_argument("--exclude-history", type=Path, default=REPO / "proyecto_de_grado/anotacion/ids_piloto_historico_no_test_final.txt")
    args = parser.parse_args(argv)
    excluidos = leer_exclusiones(args.exclude) | leer_exclusiones(args.exclude_history)
    try:
        exportar(args.raw, args.cache, args.salida, excluidos, args.limite)
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        parser.exit(2, f"Error S2.2: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
