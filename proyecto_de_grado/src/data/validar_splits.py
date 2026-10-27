"""Comprobaciones de particiones ACL-200 para evitar fugas entre conjuntos.

No descarga datos, no ejecuta modelos ni reescribe archivos.
Los articulos CITADOS compartidos no constituyen fuga por si solos.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

SPLITS = ("train", "val", "test")


@dataclass(frozen=True)
class SplitIndex:
    by_context: dict[str, str]
    contexts: dict[str, dict]


def build_split_index(contexts: dict[str, dict], splits: dict[str, list]) -> SplitIndex:
    """Valida origen de cada contexto, TARGETCIT y cruces de citante/par."""
    if not isinstance(contexts, dict):
        raise ValueError("contexts.json debe ser un objeto")
    if set(splits) != set(SPLITS):
        raise ValueError("Se requieren exactamente los splits train, val y test")

    by_context: dict[str, str] = {}
    citing_split: dict[str, str] = {}
    pair_split: dict[tuple[str, str], str] = {}

    for split in SPLITS:
        entries = splits[split]
        if not isinstance(entries, list):
            raise ValueError(f"{split}.json debe ser una lista")
        for row in entries:
            if not isinstance(row, dict):
                raise ValueError(f"Entrada invalida en {split}")
            cid = row.get("context_id")
            if not isinstance(cid, str) or not cid:
                raise ValueError(f"Context ID invalido en {split}")
            if cid in by_context:
                raise ValueError(f"Contexto repetido entre/ dentro de splits: {cid}")
            ctx = contexts.get(cid)
            if not isinstance(ctx, dict):
                raise ValueError(f"Contexto ausente de contexts.json: {cid}")
            citing, cited, text = ctx.get("citing_id"), ctx.get("refid"), ctx.get("masked_text")
            if not isinstance(citing, str) or not citing:
                raise ValueError(f"Citante invalido: {cid}")
            if not isinstance(cited, str) or not cited:
                raise ValueError(f"Citado invalido: {cid}")
            if not isinstance(text, str) or text.count("TARGETCIT") != 1:
                raise ValueError(f"TARGETCIT invalido: {cid}")
            positives = row.get("positive_ids")
            if not isinstance(positives, list) or cited not in positives:
                raise ValueError(f"Refid no coincide con positive_ids: {cid}")
            if citing in citing_split and citing_split[citing] != split:
                raise ValueError(f"Citante compartido entre splits: {citing}")
            pair = (citing, cited)
            if pair in pair_split and pair_split[pair] != split:
                raise ValueError(f"Par citante-citado compartido entre splits: {pair}")
            by_context[cid] = split
            citing_split[citing] = split
            pair_split[pair] = split

    return SplitIndex(by_context, contexts)


def load_split_index(raw_dir: str | Path) -> SplitIndex:
    """Lee exclusivamente los datos crudos versionados; falla si faltan."""
    raw = Path(raw_dir)
    contexts = json.loads((raw / "contexts.json").read_text(encoding="utf-8-sig"))
    splits = {
        name: json.loads((raw / f"{name}.json").read_text(encoding="utf-8-sig"))
        for name in SPLITS
    }
    return build_split_index(contexts, splits)


def check_gold_membership(cases: list[Any], index: SplitIndex) -> list[str]:
    """Reporta casos ajenos al test; no interpreta valores como etiquetas humanas."""
    missing, wrong, conflict = [], [], []
    for case in cases:
        cid = str(case.id)
        part = index.by_context.get(cid)
        if part is None:
            missing.append(cid)
        elif part != "test":
            wrong.append(cid)
        ctx = index.contexts.get(cid)
        metadata = getattr(case, "metadata", {}) or {}
        if ctx and isinstance(metadata, dict):
            if "citing_id" in metadata and metadata["citing_id"] != ctx.get("citing_id"):
                conflict.append(cid)
            if "cited_id" in metadata and metadata["cited_id"] != ctx.get("refid"):
                conflict.append(cid)
    reasons = []
    if missing:
        reasons.append(f"{len(missing)} casos Gold fuera de los splits supervisados")
    if wrong:
        reasons.append(f"{len(wrong)} casos Gold fuera de la particion test")
    if conflict:
        reasons.append(f"{len(set(conflict))} casos Gold con citante/citado incoherente")
    return reasons


def check_train_candidates(cases: list[dict], index: SplitIndex) -> list[str]:
    """Valida contra ACL-200, nunca contra el valor split declarado por el candidato."""
    invalid = []
    for case in cases:
        cid = case.get("id")
        ctx = index.contexts.get(cid)
        if (
            index.by_context.get(cid) != "train"
            or not isinstance(ctx, dict)
            or case.get("split") != "train"
            or case.get("citing_id") != ctx.get("citing_id")
            or case.get("cited_id") != ctx.get("refid")
            or case.get("citation_context") != ctx.get("masked_text")
        ):
            invalid.append(str(cid))
    return [f"{len(invalid)} candidatos inconsistentes con train ACL-200"] if invalid else []
