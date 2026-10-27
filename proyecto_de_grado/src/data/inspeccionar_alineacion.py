"""Inspeccion manual asistida de posibles alineaciones ACL-200 / ACL OCL.

Solo LECTURA. Usa resultados de auditar_corpus.py; no descarga, no modifica
datos y nunca declara automaticamente que TARGETCIT esta reconstruido.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from proyecto_de_grado.src.data.auditar_corpus import referencias_candidatas

REPO = Path(__file__).resolve().parents[3]


def extracto(texto: str, posicion: int | None = None, caracteres: int = 280) -> str:
    """Ventana corta para inspeccion: nunca transforma la evidencia en Gold."""
    if not isinstance(texto, str) or not texto:
        return ""
    if posicion is None or not 0 <= posicion < len(texto):
        return texto[:caracteres] + ("..." if len(texto) > caracteres else "")
    inicio = max(0, posicion - caracteres // 2)
    fin = min(len(texto), inicio + caracteres)
    inicio = max(0, fin - caracteres)
    return ("..." if inicio else "") + texto[inicio:fin] + ("..." if fin < len(texto) else "")


def inspeccionar_caso(fila: dict, contextos: dict, papers: dict, doc: dict | None) -> dict:
    """Evalua evidencias de un unico contexto y conserva su identidad."""
    cid = fila["context_id"]
    ctx = contextos.get(cid)
    if not isinstance(ctx, dict):
        raise ValueError(f"Contexto inexistente en ACL-200: {cid}")
    citante, citado = ctx.get("citing_id"), ctx.get("refid")
    if (fila.get("citing_id"), fila.get("cited_id")) != (citante, citado):
        raise ValueError(f"ID de citante/citado incoherente en CSV: {cid}")
    texto = ctx.get("masked_text", "")
    if not isinstance(texto, str) or texto.count("TARGETCIT") != 1:
        raise ValueError(f"TARGETCIT invalido: {cid}")
    base = {
        "context_id": cid, "split": fila.get("split"), "citing_id": citante,
        "cited_id": citado, "score_texto": fila.get("score_texto"),
        "contexto_ac200": extracto(texto, caracteres=500),
        "parrafo_indice": fila.get("parrafo_texto"),
        "estado": None, "seccion_citante": "", "parrafo_extracto": "",
        "refs_candidatas": [], "refs_en_parrafo": [], "spans_candidatos": [],
        "n_spans_total": 0, "nota": "NO ES VALIDACION DE TARGETCIT",
    }
    if doc is None:
        base["estado"] = "citante_no_descargado_o_invalido"
        return base
    if doc.get("paper_id") != citante:
        base["estado"] = "id_citante_incorrecto"
        return base
    cuerpo = (doc.get("pdf_parse") or {}).get("body_text") or []
    try:
        numero = int(fila["parrafo_texto"])
    except (TypeError, ValueError):
        base["estado"] = "parrafo_indice_invalido"
        return base
    if not isinstance(cuerpo, list) or not 0 <= numero < len(cuerpo):
        base["estado"] = "parrafo_fuera_de_rango"
        return base
    parrafo = cuerpo[numero]
    if not isinstance(parrafo, dict):
        base["estado"] = "parrafo_invalido"
        return base
    cuerpo_texto = parrafo.get("text") or ""
    if not isinstance(cuerpo_texto, str):
        base["estado"] = "texto_parrafo_invalido"
        return base

    titulo = (papers.get(citado) or {}).get("title") or ""
    refs = referencias_candidatas(doc, titulo)
    citas = parrafo.get("cite_spans") or []
    if not isinstance(citas, list):
        citas = []
    base["seccion_citante"] = parrafo.get("section") or ""
    base["refs_candidatas"] = sorted(refs)
    base["refs_en_parrafo"] = sorted({
        s.get("ref_id") for s in citas
        if isinstance(s, dict) and isinstance(s.get("ref_id"), str)
    })
    base["n_spans_total"] = len(citas)
    for s in citas:
        if not isinstance(s, dict) or s.get("ref_id") not in refs:
            continue
        inicio = s.get("start")
        fin = s.get("end")
        valido = isinstance(inicio, int) and isinstance(fin, int) and (
            not isinstance(inicio, bool) and not isinstance(fin, bool)
        ) and 0 <= inicio < fin <= len(cuerpo_texto)
        base["spans_candidatos"].append({
            "ref_id": s.get("ref_id"), "text_span": s.get("text", ""),
            "start": inicio, "end": fin,
            "posicion_valida": valido,
            "texto_en_posicion": cuerpo_texto[inicio:fin] if valido else None,
            "ventana": extracto(cuerpo_texto, inicio if valido else None, 300),
        })
    if base["spans_candidatos"]:
        base["estado"] = "cita_bibliografica_candidata_en_parrafo"
        base["parrafo_extracto"] = base["spans_candidatos"][0]["ventana"]
    elif refs:
        base["estado"] = "bibliografia_candidata_sin_cita_en_parrafo"
        base["parrafo_extracto"] = extracto(cuerpo_texto, caracteres=300)
    else:
        base["estado"] = "sin_bibliografia_candidata"
        base["parrafo_extracto"] = extracto(cuerpo_texto, caracteres=300)
    return base


def inspeccionar_reporte(raw: Path, cache: Path, csv_path: Path, limite: int = 5) -> list[dict]:
    if limite < 1:
        raise ValueError("El limite debe ser >= 1")
    contextos = json.loads((raw / "contexts.json").read_text(encoding="utf-8-sig"))
    papers = json.loads((raw / "papers.json").read_text(encoding="utf-8-sig"))
    with csv_path.open(encoding="utf-8-sig", newline="") as fh:
        filas = [f for f in csv.DictReader(fh) if f.get("estado") == "alineacion_candidata"][:limite]
    resultados = []
    for fila in filas:
        citante = fila["citing_id"]
        ruta = cache / f"{citante}.json"
        if ruta.is_file():
            try:
                doc = json.loads(ruta.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, json.JSONDecodeError):
                doc = None
        else:
            doc = None
        resultados.append(inspeccionar_caso(fila, contextos, papers, doc))
    return resultados


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", type=Path, default=REPO / "data/raw")
    parser.add_argument("--cache", type=Path, default=REPO / "proyecto_de_grado/scripts/spike_enlace_datos/cache_ocl")
    parser.add_argument("--csv", type=Path, default=REPO / "proyecto_de_grado/artifacts/auditoria_acl_ocl/auditoria_contextos.csv")
    parser.add_argument("--limite", type=int, default=5)
    args = parser.parse_args(argv)
    try:
        resultados = inspeccionar_reporte(args.raw, args.cache, args.csv, args.limite)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(2, f"Error de inspeccion: {exc}\n")
    if not resultados:
        print("Sin alineaciones candidatas en el CSV. No se realizo ninguna descarga.")
        return 0
    print(f"INSPECCION G1.1 | {len(resultados)} contextos | SOLO LECTURA")
    for registro in resultados:
        print("\n" + "=" * 60)
        print("ID:", registro["context_id"], "|", registro["split"])
        print("Citante:", registro["citing_id"], "| citado:", registro["cited_id"])
        print("Parrafo:", registro["parrafo_indice"], "| similitud:", registro["score_texto"])
        print("Estado:", registro["estado"], "| seccion:", registro["seccion_citante"])
        print("Contexto ACL-200:", registro["contexto_ac200"])
        print("Ref(s) candidata(s):", registro["refs_candidatas"])
        print("Ref(s) en parrafo:", registro["refs_en_parrafo"])
        print("Total cite_spans:", registro["n_spans_total"])
        for span in registro["spans_candidatos"]:
            print("SPAN:", span["ref_id"], "|", repr(span["text_span"]),
                  "| offsets_validos:", span["posicion_valida"],
                  "| texto:", repr(span["texto_en_posicion"]))
        print("Parrafo alrededor de la cita:", registro["parrafo_extracto"])
    print("\nAVISO: la similitud y bibliografia solo generan candidatos; falta adjudicar TARGETCIT.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
