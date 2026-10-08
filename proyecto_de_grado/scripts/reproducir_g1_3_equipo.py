"""G1.3: reproduccion INDEPENDIENTE de los cinco casos de desarrollo G1.2.

Sin LLM ni datos de Gold; usa ACL-200 via DVC y unicamente 8 documentos
ACL OCL (4 citantes y 4 citados). Las descargas son OPT-IN.
No modifica datos originales; escribe un reporte local ignorado por Git.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from proyecto_de_grado.src.data.reconstruir_oraciones import reconstruir_caso
from proyecto_de_grado.src.data.validar_splits import load_split_index
from proyecto_de_grado.scripts.spike_enlace_datos.medir_enlace import (
    descargar_ocl,
    ubicar_contexto,
)

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BASELINE = ROOT / "proyecto_de_grado/anotacion/baseline_reconstruccion_g1_2.jsonl"
DEFAULT_CACHE = ROOT / "proyecto_de_grado/scripts/spike_enlace_datos/cache_ocl"
DEFAULT_OUT = ROOT / "proyecto_de_grado/artifacts/auditoria_acl_ocl/reproduccion_g1_3_equipo.jsonl"


def cargar_baseline(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        rows = [json.loads(line) for line in handle if line.strip()]
    if not rows or any(not isinstance(row.get("context_id"), str) for row in rows):
        raise ValueError("Baseline sin IDs válidos")
    ids = [row["context_id"] for row in rows]
    if len(set(ids)) != len(ids):
        raise ValueError("Baseline con IDs repetidos")
    return rows


def comparar_resultado(actual: dict, esperado: dict) -> list[str]:
    """Diferencias relevantes sin adjudicar citas ni funciones humanas."""
    fields = ("split", "estado", "motivo", "citation_ref_id", "oracion_con_targetcit")
    return [field for field in fields if actual.get(field) != esperado.get(field)]


def obtener_documento(cache: Path, acl_id: str, descargar: bool) -> dict:
    filepath = cache / f"{acl_id}.json"
    if not filepath.is_file():
        if not descargar:
            raise FileNotFoundError(
                f"Falta {filepath}. Repetir con --descargar-faltantes para obtener "
                "solo los documentos requeridos de ACL OCL."
            )
        doc = descargar_ocl(acl_id, cache)
    else:
        doc = json.loads(filepath.read_text(encoding="utf-8"))
    if not isinstance(doc, dict) or doc.get("paper_id") != acl_id:
        raise ValueError(f"ACL OCL ausente o ID incoherente para {acl_id}")
    return doc


def ejecutar(raw: Path, cache: Path, baseline: Path, output: Path,
            *, descargar: bool = False) -> tuple[int, int]:
    """Devuelve (evaluados, diferencias) e informa entradas no reproducibles."""
    casos = cargar_baseline(baseline)
    indice = load_split_index(raw)
    papers = json.loads((raw / "papers.json").read_text(encoding="utf-8-sig"))
    citantes = {}
    citados = {}
    for caso in casos:
        cid = caso["context_id"]
        if indice.by_context.get(cid) != caso["split"]:
            raise ValueError(f"Split original ACL-200 incompatible: {cid}")
        ctx = indice.contexts[cid]
        citantes[ctx["citing_id"]] = ctx["citing_id"]
        citados[ctx["refid"]] = ctx["refid"]

    # Comprobar ambos documentos, sin confundirse entre citante/citado.
    docs = {
        acl_id: obtener_documento(cache, acl_id, descargar)
        for acl_id in sorted(set(citantes) | set(citados))
    }
    salida = []
    for esperado in casos:
        cid = esperado["context_id"]
        ctx = indice.contexts[cid]
        doc = docs[ctx["citing_id"]]
        coincidencia = ubicar_contexto(ctx["masked_text"], doc)
        if coincidencia is None:
            raise ValueError(f"No se localizo el contexto en el citante: {cid}")
        score, paragraph_idx = coincidencia
        fila = {
            "context_id": cid, "split": indice.by_context[cid],
            "citing_id": ctx["citing_id"], "cited_id": ctx["refid"],
            "score_texto": str(score), "parrafo_texto": str(paragraph_idx),
        }
        actual = reconstruir_caso(fila, indice.contexts, papers, doc)
        diferencias = comparar_resultado(actual, esperado)
        salida.append({
            "context_id": cid, "split": actual["split"],
            "estado": actual["estado"], "motivo": actual["motivo"],
            "citation_ref_id": actual["citation_ref_id"],
            "oracion_con_targetcit": actual["oracion_con_targetcit"],
            "parrafo_indice": paragraph_idx, "score_texto": score,
            "diferencias_vs_baseline": diferencias,
            "resultado": "coincide" if not diferencias else "difiere",
            "version": "G1.3_reproduccion_equipo_1",
            "nota": "Comparacion tecnica, NO validacion humana ni Gold.",
        })
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in salida),
        encoding="utf-8"
    )
    difieren = sum(bool(row["diferencias_vs_baseline"]) for row in salida)
    print(f"G1.3 | casos={len(salida)} | coinciden={len(salida)-difieren} | difieren={difieren}")
    for row in salida:
        print(row["context_id"], "|", row["estado"], "|",
              row["resultado"], "|", ",".join(row["diferencias_vs_baseline"]) or "-")
    print("Reporte:", output)
    print("AVISO: comparar valores no equivale a validar TARGETCIT humanamente.")
    return len(salida), difieren


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", type=Path, default=ROOT / "data/raw")
    parser.add_argument("--cache", type=Path, default=DEFAULT_CACHE)
    parser.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
    parser.add_argument("--salida", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--descargar-faltantes", action="store_true",
                        help="Descarga solo los 8 documentos ACL OCL de estos casos, si faltan.")
    args = parser.parse_args(argv)
    try:
        _, difieren = ejecutar(
            args.raw, args.cache, args.baseline, args.salida,
            descargar=args.descargar_faltantes,
        )
    except (FileNotFoundError, OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(2, f"Error de reproduccion G1.3: {exc}\n")
    return 1 if difieren else 0


if __name__ == "__main__":
    raise SystemExit(main())
