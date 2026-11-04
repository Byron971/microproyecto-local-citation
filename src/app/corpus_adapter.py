"""S2.2: lector estricto del artefacto local de desarrollo ACL-200 + ACL OCL.

Solo admite el formato creado por exportar_corpus_top3.py. Los datos crudos
DVC y la cache OCL nunca se leen ni descargan desde peticiones HTTP.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from src.app.fragment_retrieval import recuperar_top3

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CORPUS = ROOT / "proyecto_de_grado/artifacts/top3_s2/casos_train.json"


class CorpusError(ValueError):
    """Artefacto ausente, inconsistente o incompatible."""


def ruta_corpus() -> Path:
    return Path(os.environ.get("TOP3_CORPUS_PATH") or DEFAULT_CORPUS)


def leer_corpus(ruta: Path | None = None) -> dict:
    archivo = ruta or ruta_corpus()
    if not archivo.is_file():
        raise CorpusError(
            "No existe un artefacto local S2.2. Genere la muestra train "
            "con proyecto_de_grado.src.data.exportar_corpus_top3."
        )
    try:
        doc = json.loads(archivo.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CorpusError("Artefacto local ilegible.") from exc

    if not isinstance(doc, dict) or doc.get("version") != 1:
        raise CorpusError("Version de artefacto incorrecta.")
    if not isinstance(doc.get("casos"), list) or not doc["casos"]:
        raise CorpusError("Artefacto sin casos.")
    ids = set()
    for caso in doc["casos"]:
        if not isinstance(caso, dict):
            raise CorpusError("Caso mal formado.")
        cid = caso.get("context_id")
        cited_id = caso.get("cited_id")
        context = caso.get("citation_context")
        chunks = caso.get("chunks")
        if (
            not isinstance(cid, str) or not cid
            or cid in ids or caso.get("split") != "train"
            or not isinstance(cited_id, str) or not cited_id
            or not isinstance(context, str) or context.count("TARGETCIT") != 1
            or not isinstance(chunks, list) or not chunks
            or not isinstance(caso.get("sha256_ocl_citado"), str)
            or len(caso["sha256_ocl_citado"]) != 64
        ):
            raise CorpusError("Caso inconsistente con el contrato de desarrollo.")
        ids.add(cid)
        chunk_ids = set()
        for c in chunks:
            if (
                not isinstance(c, dict)
                or not isinstance(c.get("chunk_id"), str)
                or not c["chunk_id"] or c["chunk_id"] in chunk_ids
                or not isinstance(c.get("texto"), str)
                or not c["texto"].strip()
                or len(c["texto"]) > 10000
                or len(c["texto"].split()) > 300
                or not isinstance(c.get("paragraph_indices"), list)
                or len(c["paragraph_indices"]) not in (1, 2)
                or not isinstance(c.get("seccion"), str)
            ):
                raise CorpusError("Chunk incompatible con las reglas S2.2.")
            chunk_ids.add(c["chunk_id"])
    return doc


def ejemplos_disponibles(datos: dict) -> list[dict]:
    return [
        {"context_id": c["context_id"], "cited_id": c["cited_id"],
         "cited_title": c["cited_title"], "total_chunks": len(c["chunks"])}
        for c in datos["casos"]
    ]


def top3_de_corpus(datos: dict, context_id: str) -> dict | None:
    caso = next((x for x in datos["casos"] if x["context_id"] == context_id), None)
    if caso is None:
        return None
    ranking = recuperar_top3(caso["citation_context"], caso["chunks"])
    return {
        "context_id": caso["context_id"],
        "contexto": caso["citation_context"],
        "cited_id": caso["cited_id"],
        "cited_title": caso["cited_title"],
        "split": "train",
        "fuente": "ACL-200 + ACL OCL local",
        "sha256_ocl_citado": caso["sha256_ocl_citado"],
        "metodo": "BM25_lexico_baseline",
        "total_fragmentos_analizados": len(caso["chunks"]),
        "total_resultados": len(ranking),
        "fragmentos": ranking,
        "clasificacion": {"estado": "no_ejecutada"},
        "aviso": (
            "Muestra de desarrollo TRAIN: sin validacion humana de relevancia, "
            "sin reconstruccion adjudicada y sin metricas cientificas Top3."
        ),
    }
