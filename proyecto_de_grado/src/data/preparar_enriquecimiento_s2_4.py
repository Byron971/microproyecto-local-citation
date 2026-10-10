"""S2.4: cobertura ACL-200 + ACL OCL y candidatos multifuente sin etiquetas.

Lee exclusivamente ACL-200 versionado y ACL OCL ya disponible en caché.
Audita los tres splits SOLO en agregado; exporta textos de entrenamiento.
No descarga documentos, no predice clases y no crea Test Gold.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import random
import re

from proyecto_de_grado.src.data.exportar_corpus_top3 import fragmentar
from proyecto_de_grado.src.data.integrar_acl import integrar_contexto
from proyecto_de_grado.src.data.preparar_preetiquetado import ETIQUETAS, leer_exclusiones
from proyecto_de_grado.src.data.validar_splits import SPLITS, load_split_index

REPO = Path(__file__).resolve().parents[3]
DEFAULT_CACHE = REPO / "proyecto_de_grado/scripts/spike_enlace_datos/cache_ocl"
DEFAULT_OUTPUT = REPO / "proyecto_de_grado/artifacts/enriquecimiento_s2_4"
ALLOWED_PAPER_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")


def huella_contexto(texto: str) -> str:
    """Hash de texto normalizado, solo para detectar duplicados EXACTOS."""
    compacto = " ".join(texto.casefold().split())
    return hashlib.sha256(compacto.encode("utf-8")).hexdigest()


def _analizar_citado(cited_id: str, cache: Path, papers: dict) -> dict:
    """Una sola lectura por artículo citado, con trazabilidad OCL verificable."""
    if not ALLOWED_PAPER_ID.fullmatch(cited_id):
        return {"estado": "id_inseguro"}
    if cited_id not in papers or not isinstance(papers[cited_id], dict):
        return {"estado": "sin_metadata_acl200"}
    ruta = cache / f"{cited_id}.json"
    if not ruta.is_file():
        return {"estado": "no_disponible_404" if (cache / f"{cited_id}.404").is_file()
                else "no_descargado"}
    try:
        datos = ruta.read_bytes()
        documento = json.loads(datos.decode("utf-8-sig"))
        if not isinstance(documento, dict) or documento.get("paper_id") != cited_id:
            return {"estado": "id_ocl_incorrecto"}
        pdf_parse = documento.get("pdf_parse")
        if not isinstance(pdf_parse, dict):
            return {"estado": "estructura_ocl_invalida"}
        cuerpo = pdf_parse.get("body_text")
        if not isinstance(cuerpo, list) or not cuerpo:
            return {"estado": "sin_parrafos"}
        parrafos = []
        for indice, p in enumerate(cuerpo):
            if not isinstance(p, dict):
                return {"estado": "estructura_parrafos_invalida"}
            texto = p.get("text")
            if not isinstance(texto, str):
                return {"estado": "estructura_parrafos_invalida"}
            if not texto.strip():
                continue
            seccion = p.get("section") or ""
            if not isinstance(seccion, str):
                return {"estado": "estructura_parrafos_invalida"}
            parrafos.append({"numero": indice, "texto": texto.strip(),
                             "seccion": seccion.strip()})
        if not parrafos:
            return {"estado": "sin_parrafos"}
        chunks = fragmentar(parrafos)
        return {
            "estado": "utilizable",
            "sha256_ocl": hashlib.sha256(datos).hexdigest(),
            "chunks": chunks,
            "num_parrafos": len(parrafos),
        }
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {"estado": "archivo_ocl_invalido"}
    except (TypeError, KeyError, ValueError):
        return {"estado": "fragmentacion_invalida"}


def auditar_y_seleccionar(
    index, papers: dict, cache: Path, excluidos: set[str],
    limite: int = 40, semilla: int = 42, max_por_citado: int = 4,
) -> tuple[list[dict], dict]:
    """Audita TODO el ACL-200 supervisado y exporta SOLO un lote de train.

    Los duplicados textuales exactos entre splits se usan solo como
    huellas de exclusión: nunca exportamos textos val/test.
    """
    if limite < 1 or max_por_citado < 1:
        raise ValueError("limite y max_por_citado deben ser positivos")

    huellas_splits: dict[str, set[str]] = defaultdict(set)
    for cid, split in index.by_context.items():
        huellas_splits[huella_contexto(index.contexts[cid]["masked_text"])].add(split)
    cruzadas = {h for h, s in huellas_splits.items() if len(s) > 1}

    cache_status: dict[str, dict] = {}
    por_split = {split: Counter() for split in SPLITS}
    posibles = []
    for cid, split in sorted(index.by_context.items()):
        ctx = index.contexts[cid]
        citado = ctx["refid"]
        citante = ctx["citing_id"]
        if citado not in cache_status:
            cache_status[citado] = _analizar_citado(citado, cache, papers)
        dato = cache_status[citado]
        c = por_split[split]
        c["contextos"] += 1
        c[f"estado_citado_{dato['estado']}"] += 1
        if ALLOWED_PAPER_ID.fullmatch(citante) and (cache / f"{citante}.json").is_file():
            c["citante_en_cache_sin_validar"] += 1
            if (cache / f"{citado}.json").is_file():
                c["ambos_en_cache_sin_alineacion"] += 1
        if huella_contexto(ctx["masked_text"]) in cruzadas:
            c["texto_exacto_compartido_entre_splits"] += 1
            if split == "train":
                c["train_excluido_texto_cruzado"] += 1
            continue
        if split != "train":
            continue
        if cid in excluidos:
            c["train_excluido_reservado"] += 1
            continue
        if dato["estado"] != "utilizable":
            continue
        if not str(papers[citado].get("title") or "").strip():
            c["train_sin_titulo_citado"] += 1
            continue
        c["train_elegibles_desarrollo"] += 1
        posibles.append(cid)

    random.Random(semilla).shuffle(posibles)
    por_citado = Counter()
    seleccionados = []
    omisiones = Counter()
    for cid in posibles:
        if len(seleccionados) >= limite:
            break
        ctx = index.contexts[cid]
        citado = ctx["refid"]
        if por_citado[citado] >= max_por_citado:
            omisiones["limite_por_articulo_citado"] += 1
            continue
        # Segundo validador independiente: reutiliza la integración ya probada.
        registro = integrar_contexto(cid, index.contexts, papers, cache)
        fuente = cache_status[citado]
        if registro["cited_id"] != registro["ocl_paper_id"] or registro["citation_context"].count("TARGETCIT") != 1:
            raise ValueError(f"Identidad/cita incongruente en {cid}")
        seleccionados.append({
            "id": cid, "split": "train",
            "citing_id": registro["citing_id"],
            "cited_id": citado,
            "citation_context": registro["citation_context"],
            "cited_title": registro["cited_title"],
            "cited_abstract": registro["cited_abstract"],
            "cited_chunks": fuente["chunks"],
            "citante_reconstruido": False,
            "fuentes": {
                "contexto": {"nombre": "ACL-200", "context_id": cid},
                "texto_citado": {"nombre": "ACL OCL", "paper_id": citado,
                                 "sha256": fuente["sha256_ocl"]},
                "otras_fuentes_integradas": [],
            },
            "funcion_cita": {
                "etiqueta_principal": None, "etiqueta_secundaria": None,
                "estado": "no_etiquetado", "origen_etiqueta": None,
                "validacion_humana": False,
            },
            "evidencia_top3": {"fragmentos_relevantes_adjudicados": None},
        })
        por_citado[citado] += 1

    resumen = {
        "version": 1,
        "tipo": "auditoria_cobertura_y_candidatos_train_no_gold",
        "base": "ACL-200",
        "fuente_texto_completo": "ACL OCL",
        "fuentes_externas_fusionadas": [],
        "referencias_metodologicas_no_fusionadas": ["MultiCite", "ILCiteR"],
        "taxonomia_funcion_cita": list(ETIQUETAS),
        "clases_funcion_cita_con_etiquetas_verificadas": 0,
        "casos_etiquetados": 0,
        "total_contextos_supervisados": len(index.by_context),
        "articulos_citados_distintos_examinados": len(cache_status),
        "documentos_citados_utilizables": sum(d["estado"] == "utilizable" for d in cache_status.values()),
        "textos_exactos_cruzados_distintos": len(cruzadas),
        "por_split": {k: dict(sorted(v.items())) for k, v in por_split.items()},
        "candidatos_train_eligibles": len(posibles),
        "solicitados": limite,
        "seleccionados": len(seleccionados),
        "articulos_citados_en_seleccion": len(por_citado),
        "semilla": semilla, "max_por_citado": max_por_citado,
        "omision_por_equilibrio": dict(omisiones),
        "nota": (
            "Solo disponibilidad de cache local, NO cobertura global OCL; "
            "sin descargas, etiquetas, funciones verificadas o relevancia humana. "
            "La seleccion no es representativa del corpus general."
        ),
    }
    return seleccionados, resumen


def _guardar_sin_sobrescribir(path: Path, contenido: str) -> None:
    """Idempotente si es idéntico; protege evidencia si el corpus cambió."""
    nuevos = contenido.encode("utf-8")
    if path.exists():
        if path.read_bytes() != nuevos:
            raise ValueError(f"Archivo ya existente con otros datos: {path}. Use otra carpeta --out.")
        return
    path.write_bytes(nuevos)


def ejecutar(raw: Path, cache: Path, salida: Path, excluidos: set[str],
            limite: int = 40, semilla: int = 42, max_por_citado: int = 4) -> dict:
    index = load_split_index(raw)
    papers = json.loads((raw / "papers.json").read_text(encoding="utf-8-sig"))
    candidatos, resumen = auditar_y_seleccionar(
        index, papers, cache, excluidos, limite, semilla, max_por_citado,
    )
    contenido = "".join(json.dumps(c, ensure_ascii=False) + "\n" for c in candidatos)
    resumen["sha256_candidatos"] = hashlib.sha256(contenido.encode("utf-8")).hexdigest()
    texto_resumen = json.dumps(resumen, ensure_ascii=False, indent=2) + "\n"
    salida.mkdir(parents=True, exist_ok=True)
    archivo = salida / "candidatos_train_enriquecidos.jsonl"
    informe = salida / "resumen_cobertura.json"
    # No escribir ningún archivo si otro artefacto preexistente es incompatible.
    for ruta, datos in ((archivo, contenido), (informe, texto_resumen)):
        if ruta.exists() and ruta.read_bytes() != datos.encode("utf-8"):
            raise ValueError(f"No se sobrescriben resultados previos: {ruta}")
    _guardar_sin_sobrescribir(archivo, contenido)
    _guardar_sin_sobrescribir(informe, texto_resumen)
    return resumen


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", type=Path, default=REPO / "data/raw")
    parser.add_argument("--cache", type=Path, default=DEFAULT_CACHE)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--limit", type=int, default=40)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-per-cited", type=int, default=4)
    parser.add_argument("--exclude", type=Path, default=REPO / "proyecto_de_grado/anotacion/ids_excluir_test_gold.txt")
    parser.add_argument("--exclude-history", type=Path, default=REPO / "proyecto_de_grado/anotacion/ids_piloto_historico_no_test_final.txt")
    args = parser.parse_args(argv)
    try:
        excluidos = leer_exclusiones(args.exclude) | leer_exclusiones(args.exclude_history)
        resumen = ejecutar(args.raw, args.cache, args.out, excluidos,
                          args.limit, args.seed, args.max_per_cited)
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        parser.exit(2, f"S2.4: {exc}\n")
    print("=== S2.4 | COBERTURA Y ENRIQUECIMIENTO SIN ETIQUETAS ===")
    print("Contextos supervisados:", resumen["total_contextos_supervisados"])
    print("Documentos citados utilizables en cache:", resumen["documentos_citados_utilizables"])
    print("Textos exactos compartidos entre splits:", resumen["textos_exactos_cruzados_distintos"])
    print("Candidatos train elegibles:", resumen["candidatos_train_eligibles"])
    print("Seleccionados:", resumen["seleccionados"])
    print("Por split:", json.dumps(resumen["por_split"], ensure_ascii=False))
    print("Archivos:", args.out)
    print("AVISO: ninguna funcion ni relevancia de cita fue etiquetada.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
