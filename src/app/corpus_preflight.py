"""Preflight del corpus Top-3 TRAIN para Docker y demos, sin Gold humano."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from src.app.corpus_adapter import CorpusError, leer_corpus
from src.app.settings import DEFAULT_TOP3_CORPUS

_BLOCKED_KEYS = frozenset({
    "gold", "label", "labels", "human_label", "human_labels",
    "citation_function", "citation_function_label", "gold_label",
    "relevance", "relevantes", "evidencia_top3",
    "fragmentos_relevantes_adjudicados", "anotador", "annotator",
})


def _no_labels(entry: dict, level: str) -> None:
    if not isinstance(entry, dict):
        raise CorpusError(f"Estructura inválida en {level}.")
    forbidden = sorted(_BLOCKED_KEYS.intersection(entry))
    if forbidden:
        raise CorpusError(f"Artefacto contiene claves de anotación en {level}; no publicarlo.")


def auditar_train(path: Path) -> dict:
    """Fail closed; el archivo original no se modifica ni se expone en la respuesta."""
    data = leer_corpus(path)
    if (data.get("resumen") or {}).get("tipo") != "muestra_desarrollo_train_no_gold":
        raise CorpusError("No consta la procedencia TRAIN sin Gold del exportador S2.2.")
    _no_labels(data, "raiz")
    _no_labels(data["resumen"], "resumen")
    for case in data["casos"]:
        _no_labels(case, "caso")
        for chunk in case["chunks"]:
            _no_labels(chunk, "fragmento")
    h = hashlib.sha256()
    with path.open("rb") as f:
        for part in iter(lambda: f.read(1 << 20), b""):
            h.update(part)
    return {
        "estado": "train_sin_gold_verificado",
        "version": data["version"],
        "sha256_archivo": h.hexdigest(),
        "casos_train": len(data["casos"]),
        "articulos_citados_unicos": len({x["cited_id"] for x in data["casos"]}),
        "total_chunks_presentados": sum(len(x["chunks"]) for x in data["casos"]),
        "fragmentacion": data["resumen"].get("estrategia_fragmentacion", "v1_historico"),
        "incluye_etiquetas_humanas": False,
        "advertencia": "Es un corpus de demostración TRAIN, no Gold ni validación de relevancia.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archivo", type=Path, default=DEFAULT_TOP3_CORPUS)
    args = parser.parse_args(argv)
    try:
        result = auditar_train(args.archivo)
    except (CorpusError, OSError, ValueError, TypeError, KeyError) as exc:
        parser.exit(2, f"Corpus no publicable: {exc}\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
