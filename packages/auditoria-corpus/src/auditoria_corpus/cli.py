"""Composition root: ejecuta la auditoria SIN red sobre la cache local.

Uso (desde la raiz del repo):
  uv run --project packages/auditoria-corpus python -m auditoria_corpus.cli
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from . import adaptador_proyecto_grado as ad
from .servicio import Auditoria, auditar_corpus

SALIDA = ad.REPO / "proyecto_de_grado/artifacts/auditoria_a1"
COLUMNAS_CHUNKS = ["cited_id", "chunk_id", "seccion", "perfil_seccion", "palabras", "n_parrafos"]
COLUMNAS_MUESTRAS = [
    "context_id", "cited_id", "citation_context", "cited_title", "chunk_id", "seccion",
    "palabras", "texto", "verificado_por", "texto_ok", "seccion_ok", "chunk_ok", "nota",
]


def _csv(ruta: Path, columnas: list[str], filas: list[dict]) -> None:
    with ruta.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=columnas, lineterminator="\n")
        w.writeheader()
        w.writerows(filas)


def escribir(a: Auditoria, salida: Path) -> None:
    salida.mkdir(parents=True, exist_ok=True)
    _csv(salida / "auditoria_chunks.csv", COLUMNAS_CHUNKS, a.filas_chunks)
    _csv(salida / "muestras_train.csv", COLUMNAS_MUESTRAS, a.muestras)
    (salida / "resumen.json").write_text(
        json.dumps(a.resumen, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--raw", type=Path, default=ad.RAW)
    ap.add_argument("--cache", type=Path, default=ad.CACHE)
    ap.add_argument("--salida", type=Path, default=SALIDA)
    ap.add_argument("--muestras", type=int, default=20)
    ap.add_argument("--semilla", type=int, default=101)
    args = ap.parse_args(argv)
    try:
        indice = ad.cargar_indice(args.raw)
        papers = json.loads((args.raw / "papers.json").read_text(encoding="utf-8-sig"))
        a = auditar_corpus(
            indice, papers, args.cache, ad.integrar, ad.fragmentar, ad.REGLAS,
            ad.cargar_exclusiones(), args.muestras, args.semilla,
        )
    except (OSError, KeyError, TypeError, ValueError) as exc:
        ap.exit(2, f"Error auditoria A1: {exc}\n")
    escribir(a, args.salida)
    r = a.resumen
    print(f"Auditoria A1 | citados ok: {r['citados_ok']}/{r['citados_resueltos_en_cache']} (cache) | "
          f"violaciones: {r['violaciones_total']} | salida: {args.salida}")
    print("Cobertura SOBRE LA CACHE LOCAL. No es Gold ni metrica Top-3.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
