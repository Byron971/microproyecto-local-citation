"""Prepara candidatos SIN ETIQUETAS del split train de ACL-200.

No consulta modelos, no descarga artículos ni toca los datos de entrada.
Los candidatos son insumo para pre-etiquetado posterior; no son Test Gold.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import random

from proyecto_de_grado.src.data.validar_splits import (
    build_split_index,
    check_train_candidates,
)

ETIQUETAS = (
    "Background",
    "Gap",
    "Basis",
    "Comparison",
    "Application",
    "Improvement / Modification",
    "Evidence",
    "Identification of the Originator",
    "Further Reading",
)


def leer_json(ruta: Path):
    return json.loads(ruta.read_text(encoding="utf-8-sig"))


def leer_exclusiones(ruta: Path) -> set[str]:
    if not ruta.exists():
        raise FileNotFoundError(f"Falta el archivo de exclusiones: {ruta}")
    return {
        linea.strip()
        for linea in ruta.read_text(encoding="utf-8-sig").splitlines()
        if linea.strip() and not linea.lstrip().startswith("#")
    }


def construir_candidatos(
    contextos: dict,
    papers: dict,
    train: list,
    excluidos: set[str],
    limite: int = 300,
    semilla: int = 42,
) -> tuple[list[dict], dict]:
    """Selecciona candidatos válidos sin introducir etiquetas ni usar val/test."""
    if limite < 1:
        raise ValueError("--limit debe ser mayor que cero")
    motivos = Counter()
    candidatos = []
    vistos = set()
    for entrada in train:
        cid = entrada.get("context_id") if isinstance(entrada, dict) else None
        if not isinstance(cid, str) or not cid:
            motivos["id_invalido"] += 1
            continue
        if cid in vistos:
            motivos["duplicado_en_train"] += 1
            continue
        vistos.add(cid)
        if cid in excluidos:
            motivos["reservado_practica_calibracion"] += 1
            continue
        contexto = contextos.get(cid)
        if not isinstance(contexto, dict):
            motivos["contexto_ausente"] += 1
            continue
        texto = contexto.get("masked_text")
        if not isinstance(texto, str) or texto.count("TARGETCIT") != 1:
            motivos["marcador_targetcit_invalido"] += 1
            continue
        citado = contexto.get("refid")
        citante = contexto.get("citing_id")
        if not isinstance(citado, str) or not isinstance(citante, str) or not citado or not citante:
            motivos["identificadores_invalidos"] += 1
            continue
        paper = papers.get(citado)
        if not isinstance(paper, dict) or not str(paper.get("title") or "").strip():
            motivos["titulo_citado_ausente"] += 1
            continue
        positivos = entrada.get("positive_ids")
        if isinstance(positivos, list) and positivos and citado not in positivos:
            motivos["refid_no_esta_en_positivos"] += 1
            continue
        candidatos.append({
            "id": cid,
            "split": "train",
            "citing_id": citante,
            "cited_id": citado,
            "citation_context": texto,
            "cited_title": str(paper["title"]),
            "cited_abstract": str(paper.get("abstract") or ""),
        })
    # Sort antes de aleatorizar: independiente del orden físico de train.json
    candidatos.sort(key=lambda x: x["id"])
    random.Random(semilla).shuffle(candidatos)
    muestra = candidatos[:limite]
    resumen = {
        "split": "train",
        "semilla": semilla,
        "limite_solicitado": limite,
        "registros_train": len(train),
        "candidatos_validos": len(candidatos),
        "seleccionados": len(muestra),
        "motivos_exclusion": dict(sorted(motivos.items())),
        "taxonomia": list(ETIQUETAS),
        "tipo_etiqueta": "una_clase_principal_por_caso",
        "etiquetas_generadas": 0,
        "nota": "Muestra aleatoria de entrenamiento sin etiquetas. No estima cuotas de nueve clases ni representa un Test Gold.",
    }
    return muestra, resumen


def guardar(candidatos: list[dict], resumen: dict, salida: Path) -> tuple[Path, Path]:
    salida.mkdir(parents=True, exist_ok=True)
    destino = salida / f"candidatos_train_{len(candidatos)}.jsonl"
    contenido = "".join(json.dumps(x, ensure_ascii=False) + "\n" for x in candidatos)
    destino.write_text(contenido, encoding="utf-8")
    resumen = dict(resumen)
    resumen["archivo_candidatos"] = destino.name
    resumen["sha256_candidatos"] = hashlib.sha256(contenido.encode("utf-8")).hexdigest()
    info = salida / "resumen_preparacion.json"
    info.write_text(json.dumps(resumen, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return destino, info


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", type=Path, default=Path("data/raw"))
    parser.add_argument("--exclude", type=Path, default=Path("proyecto_de_grado/anotacion/ids_excluir_test_gold.txt"))
    parser.add_argument(
        "--exclude-history", type=Path,
        default=Path("proyecto_de_grado/anotacion/ids_piloto_historico_no_test_final.txt"),
    )
    parser.add_argument("--out", type=Path, default=Path("proyecto_de_grado/artifacts/preetiquetado"))
    parser.add_argument("--limit", type=int, default=300)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args(argv)
    data = args.raw
    contextos = leer_json(data / "contexts.json")
    papers = leer_json(data / "papers.json")
    splits = {name: leer_json(data / f"{name}.json") for name in ("train", "val", "test")}
    index = build_split_index(contextos, splits)
    excluidos = leer_exclusiones(args.exclude) | leer_exclusiones(args.exclude_history)
    candidatos, resumen = construir_candidatos(
        contextos, papers, splits["train"], excluidos,
        limite=args.limit, semilla=args.seed,
    )
    errores = check_train_candidates(candidatos, index)
    if errores:
        raise ValueError("Candidatos invalidos: " + "; ".join(errores))
    ruta, info = guardar(candidatos, resumen, args.out)
    print("=== PREPARACION PARA PRE-ETIQUETADO (SIN MODELOS) ===")
    print("Particion:", resumen["split"])
    print("Registros train:", resumen["registros_train"])
    print("Candidatos validos:", resumen["candidatos_validos"])
    print("Seleccionados:", resumen["seleccionados"])
    print("Motivos de exclusion:", resumen["motivos_exclusion"])
    print("Etiquetas generadas: 0 (intencional)")
    print("Candidatos:", ruta)
    print("Resumen:", info)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
