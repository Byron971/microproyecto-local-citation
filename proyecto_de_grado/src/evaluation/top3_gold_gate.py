"""Gate independiente de relevancia Top-3: nunca confundir Gold de artículo con chunk.

NO genera etiquetas ni certifica anotación humana. Entradas privadas suministradas
por operadores; salidas: agregados y hashes, sin textos ni juicios individuales.
La evaluación final exige el universo COMPLETO de chunks, no solo Top-3.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

HEX = re.compile(r"^[0-9a-f]{64}$")
RELEVANCE = {"0", "1", "abstain"}
METHODOLOGIES = ("bm25", "scibert")


class ProtocolError(ValueError):
    """Evidencia insuficiente o contradicción: denegar resultados."""


def digest(path: Path) -> str:
    sha = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            sha.update(block)
    return sha.hexdigest()


def _text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ProtocolError(f"{name}: cadena no vacía obligatoria")
    return value.strip()


def _hash(value: Any, name: str) -> str:
    token = _text(value, name)
    if HEX.fullmatch(token) is None:
        raise ProtocolError(f"{name}: SHA-256 hexadecimal de 64 caracteres obligatorio")
    return token


def _csv(path: Path, columns: tuple[str, ...], *, allow_empty: bool = False) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames is None or set(reader.fieldnames) != set(columns):
            raise ProtocolError(f"{path.name}: encabezados incompatibles; esperados {columns}")
        rows = list(reader)
    if (not rows and not allow_empty) or any(None in row or any(v is None for v in row.values()) for row in rows):
        raise ProtocolError(f"{path.name}: datos ausentes o filas vacías")
    return rows


def load_universe(path: Path) -> tuple[dict[str, dict[str, Any]], set[tuple[str, str]]]:
    with path.open("r", encoding="utf-8") as f:
        source = json.load(f)
    if not isinstance(source, dict) or source.get("schema_version") != 1:
        raise ProtocolError("Manifiesto Top-3: schema_version debe ser 1")
    if source.get("purpose") != "heldout_chunk_relevance" or source.get("used_for_tuning") is not False:
        raise ProtocolError("Solo universo held-out independiente, no usado para tuning")
    cases = source.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ProtocolError("Manifiesto sin consultas")
    indexed: dict[str, dict[str, Any]] = {}
    universe: set[tuple[str, str]] = set()
    for row in cases:
        if not isinstance(row, dict):
            raise ProtocolError("Consulta mal formada")
        if any(k in row for k in ("gold", "relevance", "rankings", "scores", "label")):
            raise ProtocolError("La fuente de consultas no puede contener Gold ni puntajes")
        cid = _text(row.get("context_id"), "context_id")
        citing = _text(row.get("citing_id"), "citing_id")
        cited = _text(row.get("cited_id"), "cited_id")
        _hash(row.get("context_sha256"), "context_sha256")
        if row.get("split") != "test" or cid in indexed:
            raise ProtocolError(f"{cid}: split debe ser test y context_id único")
        chunks = row.get("chunks")
        if not isinstance(chunks, list) or len(chunks) < 3:
            raise ProtocolError(f"{cid}: debe incluir el universo de al menos 3 chunks")
        local: set[str] = set()
        for chunk in chunks:
            if not isinstance(chunk, dict) or set(chunk) != {"chunk_id", "text_sha256", "section"}:
                raise ProtocolError(f"{cid}: chunk solo con ID, hash y sección")
            chunk_id = _text(chunk["chunk_id"], "chunk_id")
            _hash(chunk["text_sha256"], "text_sha256")
            if not isinstance(chunk["section"], (str, type(None))):
                raise ProtocolError(f"{cid}: sección inválida")
            if chunk_id in local:
                raise ProtocolError(f"{cid}: chunk duplicado")
            local.add(chunk_id)
            universe.add((cid, chunk_id))
        indexed[cid] = {"citing_id": citing, "cited_id": cited, "chunks": local}
    return indexed, universe


def check_exclusions(path: Path, cases: dict[str, dict[str, Any]]) -> None:
    """Manifiesto externo de todos los usos para entrenamiento/selección de modelo.

    La declaración sigue necesitando corroboración del equipo; no basta para
    certificar independencia real del held-out.
    """
    with path.open("r", encoding="utf-8") as f:
        record = json.load(f)
    fields = ("train_context_ids", "validation_context_ids", "prompt_selection_context_ids",
              "ranking_tuning_context_ids", "train_citing_ids", "validation_citing_ids",
              "train_pairs", "validation_pairs")
    if not isinstance(record, dict) or record.get("schema_version") != 1:
        raise ProtocolError("Se requiere manifiesto de exclusiones v1 verificable")
    for field in fields:
        values = record.get(field)
        if not isinstance(values, list) or any(not isinstance(v, str) or not v.strip() for v in values):
            raise ProtocolError(f"Exclusiones: falta {field} como lista de strings")
        if len(values) != len(set(values)):
            raise ProtocolError(f"Exclusiones: duplicados en {field}")
    ids = set().union(*(record[k] for k in fields[:4]))
    citings = set(record["train_citing_ids"]) | set(record["validation_citing_ids"])
    pairs = set(record["train_pairs"]) | set(record["validation_pairs"])
    for cid, row in cases.items():
        if cid in ids or row["citing_id"] in citings:
            raise ProtocolError(f"{cid}: posible leakage de contexto o documento citante")
        pair = row["citing_id"] + "::" + row["cited_id"]
        if pair in pairs:
            raise ProtocolError(f"{cid}: posible leakage por par citante-citado")


def load_judgments(path: Path, universe: set[tuple[str, str]]) -> dict[tuple[str, str], dict[str, str]]:
    rows = _csv(path, ("context_id", "chunk_id", "annotator_id", "relevance"))
    result: dict[tuple[str, str], dict[str, str]] = defaultdict(dict)
    for row in rows:
        key = (_text(row["context_id"], "context_id"), _text(row["chunk_id"], "chunk_id"))
        annotator = _text(row["annotator_id"], "annotator_id")
        value = row["relevance"].strip().lower()
        if key not in universe:
            raise ProtocolError("Juicio fuera del universo de chunks")
        if value not in RELEVANCE or annotator in result[key]:
            raise ProtocolError("Juicio inválido o duplicado")
        result[key][annotator] = value
    if set(result) != universe or any(len(v) != 2 for v in result.values()):
        raise ProtocolError("Faltan dos juicios independientes por CADA chunk del universo")
    return dict(result)


def adjudicate(path: Path, judgments: dict[tuple[str, str], dict[str, str]]) -> dict[tuple[str, str], int]:
    rows = _csv(path, ("context_id", "chunk_id", "adjudicator_id", "relevance", "reason"), allow_empty=True)
    decisions: dict[tuple[str, str], int] = {}
    needed = {key for key, labels in judgments.items() if len(set(labels.values())) != 1 or
              "abstain" in labels.values()}
    for row in rows:
        key = (_text(row["context_id"], "context_id"), _text(row["chunk_id"], "chunk_id"))
        adjudicator = _text(row["adjudicator_id"], "adjudicator_id")
        _text(row["reason"], "reason")
        if key not in needed or key in decisions:
            raise ProtocolError("Adjudicación duplicada o no requerida")
        if adjudicator in judgments[key] or row["relevance"].strip() not in {"0", "1"}:
            raise ProtocolError("Adjudicación debe ser binaria y por un tercero distinto")
        decisions[key] = int(row["relevance"].strip())
    if needed != set(decisions):
        raise ProtocolError("Todos los desacuerdos y abstenciones requieren adjudicación")
    result = {}
    for key, labels in judgments.items():
        result[key] = decisions[key] if key in decisions else int(next(iter(labels.values())))
    return result


def _round(n: float) -> float:
    return round(n, 6)


def score_rankings(path: Path, cases: dict[str, dict[str, Any]],
                   labels: dict[tuple[str, str], int],
                   methods: tuple[str, ...] = METHODOLOGIES) -> dict:
    rows = _csv(path, ("context_id", "method", "rank", "chunk_id"))
    groups: dict[tuple[str, str], dict[int, str]] = defaultdict(dict)
    for row in rows:
        cid, method = row["context_id"], row["method"]
        if cid not in cases or method not in methods:
            raise ProtocolError("Ranking con consulta o método desconocido")
        try:
            rank = int(row["rank"])
        except (ValueError, TypeError) as e:
            raise ProtocolError("Rank inválido") from e
        if rank not in (1, 2, 3) or rank in groups[(cid, method)]:
            raise ProtocolError("Ranking sin posiciones 1, 2 y 3 únicas")
        chunk_id = _text(row["chunk_id"], "chunk_id")
        if chunk_id not in cases[cid]["chunks"]:
            raise ProtocolError("Ranking contiene chunk fuera del documento citado")
        groups[(cid, method)][rank] = chunk_id
    expected = {(cid, m) for cid in cases for m in methods}
    if set(groups) != expected or any(set(g) != {1, 2, 3} or len(set(g.values())) != 3
                                      for g in groups.values()):
        raise ProtocolError("Rankings incompletos, duplicados o con candidatos diferentes")
    relevant = {
        cid: {chunk for c, chunk in labels if c == cid and labels[(c, chunk)] == 1}
        for cid in cases
    }
    valid_ids = [cid for cid in cases if relevant[cid]]
    summary = {"queries_total": len(cases), "queries_evaluable": len(valid_ids),
               "queries_sin_chunk_relevante": len(cases) - len(valid_ids), "methods": {}}
    for method in methods:
        measurements = []
        for cid in valid_ids:
            ranked = [groups[(cid, method)][rank] for rank in (1, 2, 3)]
            hits = [i for i, chunk in enumerate(ranked, 1) if chunk in relevant[cid]]
            measurements.append((float(bool(hits)),
                                 len(hits) / len(relevant[cid]),
                                 1 / min(hits) if hits else 0.0))
        if measurements:
            summary["methods"][method] = {
                "hit_at_3": _round(sum(m[0] for m in measurements) / len(measurements)),
                "recall_at_3": _round(sum(m[1] for m in measurements) / len(measurements)),
                "mrr_at_3": _round(sum(m[2] for m in measurements) / len(measurements)),
            }
        else:
            summary["methods"][method] = {"hit_at_3": None, "recall_at_3": None, "mrr_at_3": None}
    return summary


def audit(manifest: Path, exclusions: Path, judgments: Path,
          adjudications: Path, rankings: Path) -> dict:
    cases, universe = load_universe(manifest)
    check_exclusions(exclusions, cases)
    primary = load_judgments(judgments, universe)
    decisions = adjudicate(adjudications, primary)
    summary = score_rankings(rankings, cases, decisions)
    return {
        "schema_version": 1, "status": "METRICAS_PROVISIONALES_HUMANIDAD_NO_CERTIFICADA",
        "human_gold_certified": False, "blindness_certified": False,
        "split_independence_certified": False,
        "universe_pairs": len(universe),
        "pairs_adjudicated": sum(len(set(p.values())) != 1 or "abstain" in p.values()
                                for p in primary.values()),
        "results_from_supplied_judgments_only": summary,
        "sha256": {label: digest(path) for label, path in {
            "manifest": manifest, "exclusions": exclusions, "judgments": judgments,
            "adjudications": adjudications, "rankings": rankings}.items()},
        "warning": ("La integridad del formato NO certifica anotadores humanos, ceguera ni "
                    "independencia: requieren evidencia privada y acta del equipo. "
                    "Nunca usar esto para tuning ni reportar como resultado final."),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("manifest", "exclusions", "judgments", "adjudications", "rankings"):
        parser.add_argument("--" + name, required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        report = audit(args.manifest, args.exclusions, args.judgments,
                       args.adjudications, args.rankings)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as file:
            json.dump(report, file, indent=2, ensure_ascii=False)
            file.write("\n")
    except (ProtocolError, ValueError, OSError, json.JSONDecodeError) as exc:
        parser.exit(2, f"Top-3 Gold bloqueado: {exc}\n")
    print("Validación estructural terminada; Gold humano NO certificado.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
