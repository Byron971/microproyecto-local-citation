"""Inferencia auténtica SciBERT base contra snapshot SHA A1, sin Gold/A4.

Requiere Torch y snapshot pinned real. Nunca utiliza falsos encoders.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.app.scibert_runtime import SciBERTRuntime

DEFAULT_MANIFEST = (
    Path(__file__).resolve().parents[2]
    / "proyecto_de_grado/docs/evidencias_recuperacion_densa_a1/manifiesto_modelo.json"
)


def run(manifest: Path = DEFAULT_MANIFEST) -> dict:
    model = SciBERTRuntime.load(manifest, device="cpu", max_chunks=5,
                                max_cached_papers=2, max_cache_mb=8)
    chunks = [
        {"chunk_id": "p1", "texto": "Graph learning uses neural node representations.",
         "seccion": "Methods"},
        {"chunk_id": "p2", "texto": "Statistical translation of language pairs.",
         "seccion": "Results"},
        {"chunk_id": "p3", "texto": "Graphs support scientific citation networks.",
         "seccion": "Introduction"},
    ]
    ranking = model.top3("We apply graph representations TARGETCIT.", chunks)
    if len(ranking) != 3 or {x["chunk_id"] for x in ranking} != {"p1", "p2", "p3"}:
        raise RuntimeError("SciBERT real no devolvió tres fragmentos únicos.")
    if any(not -1.00001 <= x["similitud_coseno"] <= 1.00001 for x in ranking):
        raise RuntimeError("Coseno SciBERT real fuera del rango esperado.")
    return {
        "estado": "inferencia_scibert_cpu_real",
        "modelo": model.model,
        "revision": model.revision,
        "total_fragmentos": len(ranking),
        "ids_top3": [r["chunk_id"] for r in ranking],
        "similitudes_coseno": [r["similitud_coseno"] for r in ranking],
        "gold": "no_utilizado",
        "clasificacion_a4": "no_ejecutada_sin_checkpoint_original",
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--manifiesto", type=Path, default=DEFAULT_MANIFEST)
    a = p.parse_args(argv)
    try:
        result = run(a.manifiesto)
    except (RuntimeError, ValueError, OSError, ImportError) as exc:
        p.exit(2, f"SciBERT auténtico no disponible: {exc}\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
