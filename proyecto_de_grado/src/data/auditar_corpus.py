"""Auditoría reproducible de ACL-200 y documentos ACL OCL descargados.

NO descarga artículos y NO reconstruye automáticamente la cita objetivo.
Cada fila es un contexto de las particiones supervisadas cuyo artículo
citado dispone de un archivo JSON en la caché local. La selección por caché
NO constituye una muestra representativa del corpus completo.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from functools import lru_cache
from pathlib import Path

from proyecto_de_grado.src.data.integrar_acl import integrar_contexto
from proyecto_de_grado.scripts.spike_enlace_datos.medir_enlace import (
    normalizar,
    perfil_texto_completo,
    ubicar_contexto,
)


@lru_cache(maxsize=256)
def leer_ocl(cache: Path, acl_id: str) -> tuple[dict | None, str]:
    """Distingue documentos no descargados, 404, corruptos e IDs inválidos."""
    ruta = cache / f"{acl_id}.json"
    if not ruta.is_file():
        if (cache / f"{acl_id}.404").exists():
            return None, "no_disponible_404"
        return None, "no_descargado"
    try:
        doc = json.loads(ruta.read_text(encoding="utf-8"))
        if not isinstance(doc, dict) or doc.get("paper_id") != acl_id:
            return None, "id_incorrecto"
        return doc, "disponible"
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None, "archivo_invalido"


def referencias_candidatas(doc: dict, titulo: str) -> set[str]:
    """Encuentra entradas bibliográficas por similitud de título; no prueba identidad."""
    objetivo = set(normalizar(titulo or "").split())
    if len(objetivo) < 3:
        return set()
    bibliografia = ((doc.get("pdf_parse") or {}).get("bib_entries") or {})
    candidatas = set()
    for ref, entrada in bibliografia.items():
        palabras = set(normalizar((entrada or {}).get("title") or "").split())
        if len(palabras) < 3:
            continue
        union = objetivo | palabras
        if union and len(objetivo & palabras) / len(union) >= 0.80:
            candidatas.add(ref)
    return candidatas


def apariciones_cita(doc: dict, referencias: set[str]) -> list[int]:
    """Párrafos con una cita enlazada a una bibliografía candidata."""
    if not referencias:
        return []
    resultado = []
    cuerpo = ((doc.get("pdf_parse") or {}).get("body_text") or [])
    for indice, parrafo in enumerate(cuerpo):
        if any(cita.get("ref_id") in referencias for cita in (parrafo.get("cite_spans") or [])):
            resultado.append(indice)
    return resultado


def particiones(raw: Path) -> dict[str, str]:
    indice = {}
    for nombre in ("train", "val", "test"):
        entradas = json.loads((raw / f"{nombre}.json").read_text(encoding="utf-8"))
        for entrada in entradas:
            cid = entrada["context_id"]
            if cid in indice:
                raise ValueError(f"Contexto repetido entre particiones: {cid}")
            indice[cid] = nombre
    return indice


def auditar(raw: Path, cache: Path, salida: Path, limite: int = 0) -> list[dict]:
    if limite < 0:
        raise ValueError("limite debe ser >= 0; 0 procesa todos los candidatos")

    contextos = json.loads((raw / "contexts.json").read_text(encoding="utf-8"))
    papers = json.loads((raw / "papers.json").read_text(encoding="utf-8"))
    splits = particiones(raw)
    citados_en_cache = {p.stem for p in cache.glob("*.json")}
    candidatos = sorted(
        cid for cid, contexto in contextos.items()
        if cid in splits and contexto.get("refid") in citados_en_cache
    )
    if limite:
        candidatos = candidatos[:limite]

    filas = []
    for cid in candidatos:
        contexto = contextos[cid]
        citado_id, citante_id = contexto["refid"], contexto["citing_id"]
        fila = {
            "context_id": cid, "split": splits[cid],
            "citing_id": citante_id, "cited_id": citado_id,
            "citado_usable": 0, "citante_en_cache": 0,
            "texto_localizado": 0, "score_texto": "",
            "parrafo_texto": "", "bibliografia_candidata": 0,
            "apariciones_cita": 0, "estado": "",
        }
        doc_citado, estado_citado = leer_ocl(cache, citado_id)
        if doc_citado is None:
            fila["estado"] = f"citado_{estado_citado}"
            filas.append(fila)
            continue
        try:
            # Reutiliza el validador previamente probado; no descarga documentos.
            integrar_contexto(cid, contextos, papers, cache)
            perfil = perfil_texto_completo(doc_citado)
            fila["citado_usable"] = int(perfil["usable"])
        except (ValueError, KeyError, TypeError, OSError, json.JSONDecodeError) as error:
            fila["estado"] = "error_integracion_" + type(error).__name__
            filas.append(fila)
            continue

        if not fila["citado_usable"]:
            fila["estado"] = "citado_no_utilizable"
            filas.append(fila)
            continue

        doc_citante, estado_citante = leer_ocl(cache, citante_id)
        if doc_citante is None:
            fila["estado"] = "citante_" + estado_citante
            filas.append(fila)
            continue
        fila["citante_en_cache"] = 1
        try:
            refs = referencias_candidatas(doc_citante, papers[citado_id].get("title", ""))
            spans = apariciones_cita(doc_citante, refs)
            fila["bibliografia_candidata"] = int(bool(refs))
            fila["apariciones_cita"] = len(spans)
            coincidencia = ubicar_contexto(contexto["masked_text"], doc_citante)
            if coincidencia is not None:
                fila["texto_localizado"] = 1
                fila["score_texto"] = round(float(coincidencia[0]), 4)
                fila["parrafo_texto"] = coincidencia[1]
            if coincidencia is not None and coincidencia[1] in spans:
                fila["estado"] = "alineacion_candidata"
            elif coincidencia is not None:
                fila["estado"] = "contexto_textual_localizado"
            elif spans:
                fila["estado"] = "cita_bibliografica_localizada"
            elif refs:
                fila["estado"] = "solo_bibliografia"
            else:
                fila["estado"] = "requiere_revision"
        except (KeyError, TypeError, ValueError, AttributeError, ZeroDivisionError):
            fila["estado"] = "error_analisis_citante"
        filas.append(fila)

    salida.mkdir(parents=True, exist_ok=True)
    campos = [
        "context_id", "split", "citing_id", "cited_id", "citado_usable",
        "citante_en_cache", "texto_localizado", "score_texto",
        "parrafo_texto", "bibliografia_candidata", "apariciones_cita", "estado",
    ]
    with (salida / "auditoria_contextos.csv").open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=campos)
        writer.writeheader()
        writer.writerows(filas)

    estados = Counter(f["estado"] for f in filas)
    por_split = Counter(f["split"] for f in filas)
    lineas = [
        "# Auditoría local ACL-200 + ACL OCL", "",
        f"- Contextos supervisados con artículo citado en caché evaluados: **{len(filas)}**",
        f"- Archivos JSON disponibles en caché: **{len(citados_en_cache)}**",
        f"- Límite aplicado: **{limite or 'ninguno'}**", "",
        "## Distribución por partición", "",
        *[f"- {s}: {por_split[s]}" for s in ("train", "val", "test")],
        "", "## Estado de procesamiento", "",
        *[f"- {estado}: {n}" for estado, n in sorted(estados.items())],
        "", "## Límites de interpretación", "",
        "- La muestra depende de los documentos ya descargados: **no es representativa del corpus completo**.",
        "- 'citante_no_descargado' significa ausencia en caché local, no ausencia en ACL OCL.",
        "- Los vínculos bibliográficos son candidatos, no una verificación de la cita TARGETCIT.",
        "- 'alineacion_candidata' no significa reconstrucción definitiva de la oración o la cita objetivo.",
        "- La clasificación de las nueve funciones y sus cuotas NO se evalúan aquí.",
    ]
    (salida / "resumen_auditoria.md").write_text("\n".join(lineas) + "\n", encoding="utf-8")
    return filas


def main() -> None:
    repo = Path(__file__).resolve().parents[3]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", type=Path, default=repo / "data" / "raw")
    parser.add_argument("--cache", type=Path, default=repo / "proyecto_de_grado" / "scripts" / "spike_enlace_datos" / "cache_ocl")
    parser.add_argument("--salida", type=Path, default=repo / "proyecto_de_grado" / "artifacts" / "auditoria_acl_ocl")
    parser.add_argument("--limite", type=int, default=0, help="0 = todos los contextos elegibles de la caché")
    args = parser.parse_args()
    filas = auditar(args.raw, args.cache, args.salida, args.limite)
    print("Contextos examinados:", len(filas))
    print("Estados:", dict(sorted(Counter(f["estado"] for f in filas).items())))
    print("CSV:", args.salida / "auditoria_contextos.csv")
    print("Informe:", args.salida / "resumen_auditoria.md")
    print("AVISO: auditoría de caché, NO cobertura global del corpus")


if __name__ == "__main__":
    main()
