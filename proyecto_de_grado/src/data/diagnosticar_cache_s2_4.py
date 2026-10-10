"""S2.4 diagnóstico: por qué fallan documentos citados y qué descargar primero.

Solo lee ACL-200, exclusiones y caché ACL OCL local; nunca llama a una red.
Reporta por documento citado de TRAIN sin exportar textos ni IDs de val/test.
No infiere etiquetas, no convierte la caché en estimador de cobertura global.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path

from proyecto_de_grado.src.data.preparar_enriquecimiento_s2_4 import (
    DEFAULT_CACHE,
    REPO,
    _analizar_citado,
    huella_contexto,
)
from proyecto_de_grado.src.data.preparar_preetiquetado import leer_exclusiones
from proyecto_de_grado.src.data.validar_splits import load_split_index


def caracterizar_parrafos(cited_id: str, cache: Path) -> dict:
    """Solo longitudes, índices y tipos. NO almacena textos académicos."""
    path = cache / f"{cited_id}.json"
    if not path.is_file():
        return {"estado_diagnostico": "archivo_ausente"}
    try:
        doc = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {"estado_diagnostico": "json_ilegible"}
    if not isinstance(doc, dict) or doc.get("paper_id") != cited_id:
        return {"estado_diagnostico": "id_ocl_incorrecto"}
    pdf = doc.get("pdf_parse")
    if not isinstance(pdf, dict) or not isinstance(pdf.get("body_text"), list):
        return {"estado_diagnostico": "estructura_pdf_invalida"}
    cuerpo = pdf["body_text"]
    grandes = []
    n_invalidos, n_vacios = 0, 0
    max_palabras, max_caracteres = 0, 0
    for i, parrafo in enumerate(cuerpo):
        if not isinstance(parrafo, dict) or not isinstance(parrafo.get("text"), str):
            n_invalidos += 1
            continue
        texto = parrafo["text"].strip()
        if not texto:
            n_vacios += 1
            continue
        seccion = parrafo.get("section") or ""
        if not isinstance(seccion, str):
            n_invalidos += 1
            continue
        palabras, caracteres = len(texto.split()), len(texto)
        max_palabras = max(max_palabras, palabras)
        max_caracteres = max(max_caracteres, caracteres)
        if palabras > 300 or caracteres > 5000:
            grandes.append({
                "indice_parrafo": i, "palabras": palabras,
                "caracteres": caracteres,
                "supera_300_palabras": palabras > 300,
                "supera_5000_caracteres": caracteres > 5000,
            })
    return {
        "estado_diagnostico": "analizado",
        "parrafos_originales": len(cuerpo),
        "parrafos_invalidos": n_invalidos,
        "parrafos_vacios": n_vacios,
        "parrafos_demasiado_largos": len(grandes),
        "max_palabras_en_parrafo": max_palabras,
        "max_caracteres_en_parrafo": max_caracteres,
        "detalle_excesos": grandes[:20],
        "excesos_adicionales_no_mostrados": max(0, len(grandes) - 20),
    }


def diagnosticar(index, papers: dict, cache: Path, excluidos: set[str],
                 top: int = 12) -> dict:
    if top < 1 or top > 100:
        raise ValueError("--top debe estar entre 1 y 100")

    # Los textos de val/test se usan solo como huellas anti-fuga; sus IDs
    # y contenidos jamás aparecen en el informe.
    huellas_splits: dict[str, set[str]] = defaultdict(set)
    for cid, split in index.by_context.items():
        huellas_splits[huella_contexto(index.contexts[cid]["masked_text"])].add(split)
    cruzadas = {h for h, splits in huellas_splits.items() if len(splits) > 1}

    por_citado = Counter()
    total_train = 0
    excluidos_reales = Counter()
    for cid, split in index.by_context.items():
        if split != "train":
            continue
        total_train += 1
        ctx = index.contexts[cid]
        if cid in excluidos:
            excluidos_reales["exclusion_reservada"] += 1
            continue
        if huella_contexto(ctx["masked_text"]) in cruzadas:
            excluidos_reales["duplicado_exacto_cruzado"] += 1
            continue
        por_citado[ctx["refid"]] += 1

    resumen_documentos = Counter()
    resumen_contextos = Counter()
    inspeccion_cache = []
    faltantes = []
    for citado, n in sorted(por_citado.items()):
        estado = _analizar_citado(citado, cache, papers)["estado"]
        resumen_documentos[estado] += 1
        resumen_contextos[estado] += n
        if estado in ("no_descargado", "no_disponible_404"):
            if estado == "no_descargado":
                faltantes.append({"cited_id": citado, "contextos_train_potenciales": n})
            continue
        info = caracterizar_parrafos(citado, cache)
        inspeccion_cache.append({
            "cited_id": citado,
            "contextos_train_potenciales": n,
            "estado_exportador": estado,
            **info,
        })

    faltantes.sort(key=lambda x: (-x["contextos_train_potenciales"], x["cited_id"]))
    inspeccion_cache.sort(key=lambda x: (
        x["estado_exportador"] != "fragmentacion_invalida",
        -x["contextos_train_potenciales"], x["cited_id"]
    ))
    return {
        "version": 1,
        "tipo": "diagnostico_offline_s2_4_solo_train",
        "contextos_train_originales": total_train,
        "exclusiones": dict(sorted(excluidos_reales.items())),
        "contextos_train_no_excluidos": sum(por_citado.values()),
        "documentos_citados_distintos_train": len(por_citado),
        "estado_documentos_citados": dict(sorted(resumen_documentos.items())),
        "estado_contextos_train": dict(sorted(resumen_contextos.items())),
        "inspeccion_documentos_en_cache": inspeccion_cache,
        "prioridad_descarga_train": faltantes[:top],
        "top_mostrado": top,
        "nota": (
            "La prioridad mide cuantos contextos train se enlazarían potencialmente; "
            "NO garantiza descarga ni parseo utilizable. No se descarga nada, "
            "no se auditan funciones de cita, no se revela val/test."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", type=Path, default=REPO / "data/raw")
    parser.add_argument("--cache", type=Path, default=DEFAULT_CACHE)
    parser.add_argument("--exclude", type=Path, default=REPO / "proyecto_de_grado/anotacion/ids_excluir_test_gold.txt")
    parser.add_argument("--exclude-history", type=Path, default=REPO / "proyecto_de_grado/anotacion/ids_piloto_historico_no_test_final.txt")
    parser.add_argument("--out", type=Path, default=REPO / "proyecto_de_grado/artifacts/enriquecimiento_s2_4/diagnostico_cache_train.json")
    parser.add_argument("--top", type=int, default=12)
    args = parser.parse_args(argv)
    try:
        import json as _json
        index = load_split_index(args.raw)
        papers = _json.loads((args.raw / "papers.json").read_text(encoding="utf-8-sig"))
        excluidos = leer_exclusiones(args.exclude) | leer_exclusiones(args.exclude_history)
        resultado = diagnosticar(index, papers, args.cache, excluidos, top=args.top)
        contenido = json.dumps(resultado, ensure_ascii=False, indent=2) + "\n"
        args.out.parent.mkdir(parents=True, exist_ok=True)
        if args.out.exists() and args.out.read_text(encoding="utf-8") != contenido:
            raise ValueError(f"Diagnóstico anterior diferente en {args.out}. Use otra ruta --out.")
        if not args.out.exists():
            args.out.write_text(contenido, encoding="utf-8")
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        parser.exit(2, f"S2.4 diagnostico: {exc}\n")
    print("=== DIAGNOSTICO DE CACHÉ S2.4 — SOLO TRAIN ===")
    print("Contextos train no excluidos:", resultado["contextos_train_no_excluidos"])
    print("Documentos citados distintos:", resultado["documentos_citados_distintos_train"])
    print("Estados por documento:", json.dumps(resultado["estado_documentos_citados"], ensure_ascii=False))
    print("Estados por contexto train:", json.dumps(resultado["estado_contextos_train"], ensure_ascii=False))
    print("Documentos en caché inspeccionados:", len(resultado["inspeccion_documentos_en_cache"]))
    for fila in resultado["inspeccion_documentos_en_cache"]:
        print("OCL", fila["cited_id"], "estado:", fila["estado_exportador"],
              "contextos:", fila["contextos_train_potenciales"],
              "párrafos demasiado largos:", fila.get("parrafos_demasiado_largos"),
              "máx palabras:", fila.get("max_palabras_en_parrafo"),
              "máx caracteres:", fila.get("max_caracteres_en_parrafo"))
    print("Top documentos faltantes (IDs train):", resultado["prioridad_descarga_train"])
    print("Informe:", args.out)
    print("AVISO: sin descargas, anotaciones ni métricas Gold.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
