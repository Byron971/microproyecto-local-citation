"""G1.2: reconstruccion CONSERVADORA de la oracion que contiene TARGETCIT.

Se rehusa a producir una reconstruccion candidata cuando la bibliografia, los
offsets, la ubicacion del contexto o la unicidad de la cita no son confiables.
Incluso una salida candidata requiere revision humana: NO es un Test Gold.

Solo usa ACL-200 y la cache ACL OCL local. Sin red, sin escrituras.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path

from proyecto_de_grado.src.data.inspeccionar_alineacion import inspeccionar_caso
from proyecto_de_grado.scripts.spike_enlace_datos.medir_enlace import ubicar_contexto

REPO = Path(__file__).resolve().parents[3]
MIN_MATCH = 0.5
MAX_SENTENCE_WORDS = 120


def grupo_ambiguo(texto_masked: str, ventana: int = 38) -> bool:
    """Un OTHERCIT cercano al TARGETCIT obliga a revision manual.

    Heuristica prudente: no supone que el orden de las citas en un grupo
    bibliografico se pueda inferir automaticamente por similitud textual.
    """
    pos = texto_masked.index("TARGETCIT")
    inicio = max(0, pos - ventana)
    fin = min(len(texto_masked), pos + len("TARGETCIT") + ventana)
    return "OTHERCIT" in texto_masked[inicio:fin]


def limites_oracion(texto: str, inicio_cita: int, fin_cita: int) -> tuple[int, int]:
    """Segmentacion ligera alrededor del span; no divide dentro del span.

    Evita limites dentro de parentesis y abreviaturas comunes. Se aplican
    controles de longitud y se deja el resultado como candidato humano.
    """
    cortes = [0]
    for hallazgo in re.finditer(r"[.!?][\]\)}\u201d\u2019\"']*\s+(?=[A-Z\u00c0-\u00de])", texto):
        antes = texto[max(0, hallazgo.start() - 12):hallazgo.start() + 1].lower()
        if re.search(r"(?:et\s+al|e\.g|i\.e|fig|dr|mr|mrs)\.$", antes):
            continue
        pos = hallazgo.end()
        cortes.append(pos)
    cortes.append(len(texto))
    limites = [
        (a, b) for a, b in zip(cortes, cortes[1:])
        if a <= inicio_cita and fin_cita <= b
    ]
    if len(limites) != 1:
        raise ValueError("No se encontro un limite de oracion unico para el span")
    return limites[0]


def enmascarar_span_de_cita(texto_span: str) -> str | None:
    """Conserva parentesis externos solo si abarcan UNA referencia.

    Si los offsets capturan un grupo o parentesis incompletos, abstenerse.
    La salida es una representacion de trabajo, NO una adjudicacion humana.
    """
    if not isinstance(texto_span, str):
        return None
    fragmento = texto_span.strip()
    if not fragmento or "TARGETCIT" in fragmento or "OTHERCIT" in fragmento:
        return None
    if fragmento.startswith("(") and fragmento.endswith(")"):
        interior = fragmento[1:-1].strip()
        if not interior or any(c in interior for c in "();"):
            return None
        return "(TARGETCIT)"
    if any(c in fragmento for c in "();"):
        return None
    return "TARGETCIT"


def reconstruir_caso(fila: dict, contextos: dict, papers: dict, doc: dict | None) -> dict:
    """Construye evidencia auditable; nunca certifica la reconstruccion."""
    evidencia = inspeccionar_caso(fila, contextos, papers, doc)
    result = {
        "context_id": fila["context_id"],
        "split": fila.get("split"),
        "citing_id": evidencia["citing_id"],
        "cited_id": evidencia["cited_id"],
        "contexto_acl200": contextos[fila["context_id"]]["masked_text"],
        "parrafo_indice": evidencia["parrafo_indice"],
        "bibliografia_candidata": evidencia["refs_candidatas"],
        "estado": "revision_manual",
        "motivo": None,
        "oracion_ocl_original": None,
        "oracion_con_targetcit": None,
        "citation_span_text": None,
        "citation_ref_id": None,
        "nota": "CANDIDATO; requiere verificacion humana de identidad TARGETCIT",
    }
    if doc is None or evidencia["estado"] != "cita_bibliografica_candidata_en_parrafo":
        result["motivo"] = evidencia["estado"]
        return result

    texto_masked = result["contexto_acl200"]
    if grupo_ambiguo(texto_masked):
        result["motivo"] = "TARGETCIT_cerca_de_OTHERCIT_grupo_potencial"
        return result

    spans = evidencia["spans_candidatos"]
    if len(spans) != 1:
        result["motivo"] = "referencia_candidata_no_unica_en_parrafo"
        return result
    span = spans[0]
    if not span["posicion_valida"]:
        result["motivo"] = "offset_de_cita_invalido"
        return result
    marcador = enmascarar_span_de_cita(span["texto_en_posicion"])
    if marcador is None:
        result["motivo"] = "grupo_o_envoltura_de_cita_no_segura"
        return result
    try:
        idx = int(fila["parrafo_texto"])
        coincidencia = ubicar_contexto(texto_masked, doc)
        if coincidencia is None or coincidencia[1] != idx or coincidencia[0] < MIN_MATCH:
            result["motivo"] = "contexto_no_alineado_con_parrafo"
            return result
        cuerpo = doc["pdf_parse"]["body_text"][idx]["text"]
        inicio, fin = span["start"], span["end"]
        if cuerpo[inicio:fin] != span["texto_en_posicion"]:
            result["motivo"] = "span_incoherente_con_texto"
            return result
        a, b = limites_oracion(cuerpo, inicio, fin)
        oracion = cuerpo[a:b].strip()
        enmascarada = (
            cuerpo[a:inicio] + marcador + cuerpo[fin:b]
        ).strip()
        # GROBID suele dejar un espacio antes del punto final.
        # Solo se ajusta la copia enmascarada, nunca la evidencia OCL original.
        enmascarada = re.sub(r"\\s+([.!?])$", r"\\1", enmascarada)
    except (KeyError, TypeError, IndexError, ValueError, AttributeError) as exc:
        result["motivo"] = "reconstruccion_no_confiable_" + type(exc).__name__
        return result

    if (
        not oracion or len(oracion.split()) > MAX_SENTENCE_WORDS
        or enmascarada.count("TARGETCIT") != 1
    ):
        result["motivo"] = "oracion_demasiado_larga_o_marcador_invalido"
        return result

    result.update({
        "estado": "reconstruccion_candidata_revision_humana",
        "motivo": None,
        "oracion_ocl_original": oracion,
        "oracion_con_targetcit": enmascarada,
        "citation_span_text": span["texto_en_posicion"],
        "citation_ref_id": span["ref_id"],
    })
    return result


def reconstruir_reporte(raw: Path, cache: Path, csv_path: Path, limite: int = 5) -> list[dict]:
    if limite < 1:
        raise ValueError("limite debe ser >= 1")
    contextos = json.loads((raw / "contexts.json").read_text(encoding="utf-8-sig"))
    papers = json.loads((raw / "papers.json").read_text(encoding="utf-8-sig"))
    with csv_path.open(encoding="utf-8-sig", newline="") as fh:
        filas = [f for f in csv.DictReader(fh) if f.get("estado") == "alineacion_candidata"][:limite]
    resultado = []
    for fila in filas:
        archivo = cache / f"{fila['citing_id']}.json"
        if archivo.is_file():
            try:
                doc = json.loads(archivo.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, json.JSONDecodeError):
                doc = None
        else:
            doc = None
        resultado.append(reconstruir_caso(fila, contextos, papers, doc))
    return resultado


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", type=Path, default=REPO / "data/raw")
    parser.add_argument("--cache", type=Path, default=REPO / "proyecto_de_grado/scripts/spike_enlace_datos/cache_ocl")
    parser.add_argument("--csv", type=Path, default=REPO / "proyecto_de_grado/artifacts/auditoria_acl_ocl/auditoria_contextos.csv")
    parser.add_argument("--limite", type=int, default=5)
    args = parser.parse_args(argv)
    try:
        casos = reconstruir_reporte(args.raw, args.cache, args.csv, args.limite)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(2, f"Error G1.2: {exc}\n")
    print(f"G1.2 | {len(casos)} contextos | SOLO LECTURA | NO TEST GOLD")
    for c in casos:
        print("\n" + "=" * 60)
        print("ID:", c["context_id"], "| split:", c["split"])
        print("Estado:", c["estado"], "| motivo:", c["motivo"])
        print("Citante:", c["citing_id"], "| citado:", c["cited_id"])
        print("Referencia bib:", c["citation_ref_id"] or c["bibliografia_candidata"])
        print("Contexto original ACL-200:", c["contexto_acl200"])
        if c["oracion_ocl_original"] is not None:
            print("Oracion original OCL:", c["oracion_ocl_original"])
            print("Oracion con TARGETCIT:", c["oracion_con_targetcit"])
    print("\nAVISO: ningun resultado queda validado sin revision humana.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
