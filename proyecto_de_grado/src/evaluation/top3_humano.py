"""S2.3: calibración humana ciega y métricas de fragmentos (NO Test Gold).

Modo preparar: genera dos hojas independientes sin ranking ni puntajes BM25.
Modo evaluar: requiere anotación exhaustiva de ambos evaluadores; adjudica
solo desacuerdos explícitos y NO permite informar un test definitivo.
Solo admite artefactos train de S2.2. Sin red ni servicios externos.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
from collections import Counter
from pathlib import Path
from typing import Any

from src.app.fragment_retrieval import recuperar_top3

REPO = Path(__file__).resolve().parents[3]
DEFAULT_INPUT = REPO / "proyecto_de_grado/artifacts/top3_s2/casos_train.json"
DEFAULT_OUT = REPO / "proyecto_de_grado/artifacts/top3_s2/anotacion"
COLUMNS = (
    "context_id", "cited_id", "cited_title", "citation_context",
    "chunk_id", "seccion", "texto", "relevante_0_1", "notas",
)
LABEL_COLUMNS = ("context_id", "chunk_id")


class ProtocoloError(ValueError):
    """Entrada, anotación, adjudicación o manifiesto incompletos."""


def leer_casos(path: Path) -> tuple[dict[str, Any], str]:
    try:
        contenido = path.read_bytes()
        doc = json.loads(contenido.decode("utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ProtocoloError(f"Artefacto de desarrollo ilegible: {path}") from exc
    if (
        not isinstance(doc, dict) or doc.get("version") != 1
        or not isinstance(doc.get("resumen"), dict)
        or doc["resumen"].get("tipo") != "muestra_desarrollo_train_no_gold"
        or not isinstance(doc.get("casos"), list) or not doc["casos"]
    ):
        raise ProtocoloError("Solo se admite una muestra S2.2 train de desarrollo, no Test Gold.")
    context_ids = set()
    for caso in doc["casos"]:
        if not isinstance(caso, dict):
            raise ProtocoloError("Caso mal formado.")
        cid, cited, contexto = (
            caso.get("context_id"), caso.get("cited_id"), caso.get("citation_context")
        )
        if (
            caso.get("split") != "train"
            or not isinstance(cid, str) or not cid or cid in context_ids
            or not isinstance(cited, str) or not cited
            or not isinstance(caso.get("cited_title"), str)
            or not isinstance(contexto, str) or contexto.count("TARGETCIT") != 1
            or not isinstance(caso.get("chunks"), list) or not caso["chunks"]
        ):
            raise ProtocoloError("Identidad/split/fragmentos incompatibles con S2.2.")
        context_ids.add(cid)
        chunk_ids = set()
        for ch in caso["chunks"]:
            if (
                not isinstance(ch, dict)
                or not isinstance(ch.get("chunk_id"), str) or not ch["chunk_id"]
                or ch["chunk_id"] in chunk_ids
                or not isinstance(ch.get("texto"), str) or not ch["texto"].strip()
                or not isinstance(ch.get("seccion"), str)
                or not isinstance(ch.get("paragraph_indices"), list)
                or len(ch["paragraph_indices"]) not in (1, 2)
            ):
                raise ProtocoloError("Chunk sin identidad o procedencia suficiente.")
            chunk_ids.add(ch["chunk_id"])
    return doc, hashlib.sha256(contenido).hexdigest()


def _filas(doc: dict) -> list[dict[str, str]]:
    filas = []
    for caso in doc["casos"]:
        for chunk in caso["chunks"]:
            filas.append({
                "context_id": caso["context_id"],
                "cited_id": caso["cited_id"],
                "cited_title": caso["cited_title"],
                "citation_context": caso["citation_context"],
                "chunk_id": chunk["chunk_id"],
                "seccion": chunk["seccion"],
                "texto": chunk["texto"],
                "relevante_0_1": "",
                "notas": "",
            })
    return filas


def _escribir_csv(path: Path, filas: list[dict], *, reemplazar: bool = False) -> None:
    if path.exists() and not reemplazar:
        raise ProtocoloError(f"No sobrescribir anotaciones existentes: {path}")
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(filas)


def preparar_hojas(origen: Path, salida: Path, semilla: int = 42) -> dict:
    doc, digest = leer_casos(origen)
    destinos = (
        salida / "anotador_a.csv",
        salida / "anotador_b.csv",
        salida / "adjudicacion_plantilla.csv",
        salida / "manifiesto.json",
    )
    if any(p.exists() for p in destinos):
        raise ProtocoloError("Ya existen archivos de anotación: no se sobrescriben.")
    filas = _filas(doc)
    salida.mkdir(parents=True, exist_ok=True)
    for i, ruta in enumerate(destinos[:2]):
        orden = list(filas)
        random.Random(semilla + i).shuffle(orden)
        _escribir_csv(ruta, orden)
    # Plantilla sin revelación del modelo; solo discrepancias necesitarán juicio final.
    _escribir_csv(destinos[2], sorted(
        filas, key=lambda row: (row["context_id"], row["chunk_id"])
    ))
    manifest = {
        "version": 1,
        "estado": "calibracion_train_no_gold",
        "sha256_fuente": digest,
        "semilla": semilla,
        "casos": len(doc["casos"]),
        "juicios_por_anotador": len(filas),
        "nota": "Dos anotadores ciegos. Ningún ranking ni puntaje BM25 en sus hojas.",
    }
    destinos[3].write_text(json.dumps(manifest, indent=2, ensure_ascii=False)+"\n", encoding="utf-8")
    return manifest


def _leer_etiquetas(path: Path, esperado: set[tuple[str, str]], *, parcial: bool) -> dict:
    try:
        with path.open(encoding="utf-8-sig", newline="") as fh:
            reader = csv.DictReader(fh)
            if not reader.fieldnames or not set((*LABEL_COLUMNS, "relevante_0_1")).issubset(reader.fieldnames):
                raise ProtocoloError(f"Columnas de anotación faltantes: {path}")
            etiquetas = {}
            for fila in reader:
                key = (fila["context_id"].strip(), fila["chunk_id"].strip())
                if key in etiquetas or key not in esperado:
                    raise ProtocoloError(f"Juicio duplicado o no perteneciente al corpus: {key}")
                raw = (fila["relevante_0_1"] or "").strip()
                if raw not in ("0", "1", "") or (not parcial and raw == ""):
                    raise ProtocoloError(f"Etiqueta binaria incompleta/incorrecta en {path}: {key}")
                etiquetas[key] = None if raw == "" else int(raw)
    except (OSError, UnicodeError, csv.Error) as exc:
        raise ProtocoloError(f"No se pudo leer el CSV de {path}") from exc
    if set(etiquetas) != esperado:
        raise ProtocoloError(f"Anotación incompleta en {path}: faltan {len(esperado - set(etiquetas))} juicios.")
    return etiquetas


def puntajes_top3(ranking: list[str], gold: set[str]) -> dict | None:
    """Un Gold no vacío proporciona denominador; sin Gold se excluye el caso."""
    if len(ranking) != len(set(ranking)):
        raise ProtocoloError("Ranking con chunk_id duplicado.")
    if not gold:
        return None
    top = ranking[:3]
    hit = [i for i, item in enumerate(top, start=1) if item in gold]
    return {
        "hit_3": float(bool(hit)),
        "recall_3": len(set(top) & gold) / len(gold),
        "rr_3": 1.0 / hit[0] if hit else 0.0,
        "n_relevantes": len(gold),
    }


def evaluar_calibracion(
    origen: Path, carpeta: Path, *, archivo_a: Path | None = None,
    archivo_b: Path | None = None, archivo_adjudicacion: Path | None = None,
) -> dict:
    doc, digest = leer_casos(origen)
    try:
        manifest = json.loads((carpeta / "manifiesto.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ProtocoloError("Falta manifiesto de anotación.") from exc
    if manifest.get("estado") != "calibracion_train_no_gold" or manifest.get("sha256_fuente") != digest:
        raise ProtocoloError("El corpus ha cambiado después de preparar las hojas.")
    archivo_a = archivo_a or carpeta / "anotador_a.csv"
    archivo_b = archivo_b or carpeta / "anotador_b.csv"
    archivo_adjudicacion = archivo_adjudicacion or carpeta / "adjudicacion_plantilla.csv"
    if archivo_a.resolve() == archivo_b.resolve():
        raise ProtocoloError("Los anotadores no pueden usar el mismo archivo.")
    esperado = {(c["context_id"], ch["chunk_id"]) for c in doc["casos"] for ch in c["chunks"]}
    a = _leer_etiquetas(archivo_a, esperado, parcial=False)
    b = _leer_etiquetas(archivo_b, esperado, parcial=False)
    adj = _leer_etiquetas(archivo_adjudicacion, esperado, parcial=True)

    discrepancias = [key for key in sorted(esperado) if a[key] != b[key]]
    if any(adj[key] is None for key in discrepancias):
        raise ProtocoloError(f"Faltan {sum(adj[key] is None for key in discrepancias)} adjudicaciones de desacuerdos.")
    if any(adj[key] is not None and a[key] == b[key] and adj[key] != a[key] for key in esperado):
        raise ProtocoloError("La adjudicación contradice un acuerdo entre dos anotadores.")
    consenso = {key: a[key] if a[key] == b[key] else adj[key] for key in esperado}
    acuerdo = 1 - len(discrepancias) / len(esperado)
    proporcion_a = sum(a.values()) / len(a)
    proporcion_b = sum(b.values()) / len(b)
    acuerdo_azar = proporcion_a * proporcion_b + (1 - proporcion_a) * (1 - proporcion_b)
    kappa = (acuerdo - acuerdo_azar) / (1 - acuerdo_azar) if acuerdo_azar < 1 else None

    casos = []
    for caso in doc["casos"]:
        cid = caso["context_id"]
        validos = {ch["chunk_id"] for ch in caso["chunks"]}
        relevantes = {chunk for (ctx, chunk), label in consenso.items() if ctx == cid and label == 1}
        ranking = [x["chunk_id"] for x in recuperar_top3(caso["citation_context"], caso["chunks"])]
        if any(x not in validos for x in ranking):
            raise ProtocoloError("Ranking incluye fragmentos ajenos al artículo citado.")
        m = puntajes_top3(ranking, relevantes)
        casos.append({"context_id": cid, "cited_id": caso["cited_id"],
                      "n_chunks_juzgados": len(validos), "n_relevantes": len(relevantes),
                      "estado": "sin_relevantes_anotados" if m is None else "evaluable",
                      "metricas": m})
    elegibles = [c["metricas"] for c in casos if c["metricas"] is not None]
    media = (lambda key: sum(m[key] for m in elegibles) / len(elegibles) if elegibles else None)
    return {
        "estado": "calibracion_train_no_gold", "corpus_sha256": digest,
        "juicios_por_anotador": len(esperado), "desacuerdos": len(discrepancias),
        "acuerdo_observado": round(acuerdo, 6),
        "cohen_kappa": round(kappa, 6) if kappa is not None else None,
        "total_casos": len(casos), "casos_elegibles": len(elegibles),
        "casos_sin_relevantes": len(casos) - len(elegibles),
        "hit_3": round(media("hit_3"), 6) if elegibles else None,
        "recall_3": round(media("recall_3"), 6) if elegibles else None,
        "mrr_3": round(media("rr_3"), 6) if elegibles else None,
        "casos": casos, "advertencia": (
            "Calibracion con train; NO constituye Test Gold independiente, "
            "ni resultados finales sobre la poblacion."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="accion", required=True)
    p = sub.add_parser("preparar", help="Crear hojas ciegas sin resultados de modelo")
    p.add_argument("--origen", type=Path, default=DEFAULT_INPUT)
    p.add_argument("--salida", type=Path, default=DEFAULT_OUT)
    p.add_argument("--semilla", type=int, default=42)
    e = sub.add_parser("evaluar", help="Validar anotaciones dobles y adjudicación")
    e.add_argument("--origen", type=Path, default=DEFAULT_INPUT)
    e.add_argument("--carpeta", type=Path, default=DEFAULT_OUT)
    e.add_argument("--salida", type=Path, default=DEFAULT_OUT / "resumen_calibracion.json")
    args = parser.parse_args(argv)
    try:
        if args.accion == "preparar":
            resumen = preparar_hojas(args.origen, args.salida, args.semilla)
        else:
            resumen = evaluar_calibracion(args.origen, args.carpeta)
            if args.salida.exists():
                raise ProtocoloError("No sobrescribir el resumen de calibración existente.")
            args.salida.parent.mkdir(parents=True, exist_ok=True)
            args.salida.write_text(
                json.dumps(resumen, ensure_ascii=False, indent=2)+"\n", encoding="utf-8"
            )
        print(json.dumps(resumen, ensure_ascii=False, indent=2))
    except (ProtocoloError, OSError, ValueError) as exc:
        parser.exit(2, f"S2.3: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
