"""Controles preventivos del Test Gold; no certifica por si solo la calidad humana.

Sin E/S externa: solo consulta archivos locales del repositorio. El archivo
historico `test_gold.jsonl` fue utilizado durante la seleccion de prompts.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parents[3]
EXCLUSION_FILES = (
    "proyecto_de_grado/anotacion/ids_excluir_test_gold.txt",
    "proyecto_de_grado/anotacion/ids_piloto_historico_no_test_final.txt",
)
LEGACY_GOLD_NAMES = frozenset(("test_gold.jsonl", "provisional_test_gold.jsonl"))


@dataclass(frozen=True)
class GoldAudit:
    provisional: bool
    reasons: tuple[str, ...]
    excluded_ids: int


def exclusion_ids(root: Path = REPO_ROOT) -> set[str]:
    """La ausencia de un manifiesto es un fallo, nunca una exclusion vacia."""
    ids: set[str] = set()
    for relative in EXCLUSION_FILES:
        path = root / relative
        if not path.is_file():
            raise FileNotFoundError(f"Falta manifiesto obligatorio: {path}")
        ids.update(
            line.strip()
            for line in path.read_text(encoding="utf-8-sig").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        )
    return ids


def inspect_gold(
    gold_path: str | Path,
    cases: Iterable[object],
    *,
    root: Path = REPO_ROOT,
    raw_dir: Path | None = None,
) -> GoldAudit:
    """Separa material historico/insuficiente de posibles candidatos a Gold.

    Esta es una barrera *minima*. Un Gold nuevo no queda cientificamente
    aprobado solo por superar estas comprobaciones: faltan manifiesto de
    adjudicacion, validacion de splits y control de duplicados textuales.
    """
    cases = list(cases)
    if not cases:
        raise ValueError("El conjunto de evaluacion esta vacio")
    case_ids = [str(c.id) for c in cases]
    if len(set(case_ids)) != len(case_ids):
        raise ValueError("Hay identificadores de evaluacion duplicados")

    banned = exclusion_ids(root)
    reasons: list[str] = []
    name = Path(gold_path).name.casefold()
    if name in LEGACY_GOLD_NAMES or "provisional" in name:
        reasons.append("nombre asociado al piloto historico o provisional")

    overlap = set(case_ids) & banned
    if overlap:
        reasons.append(f"{len(overlap)} identificadores usados en practica, calibracion o desarrollo")

    invalid_target = sum(
        not isinstance(c.input, str) or c.input.count("TARGETCIT") != 1
        for c in cases
    )
    if invalid_target:
        reasons.append(f"{invalid_target} contextos sin exactamente un TARGETCIT")

    without_label = sum(getattr(c, "gold", None) is None for c in cases)
    if without_label:
        reasons.append(f"{without_label} registros sin etiqueta humana de referencia")

    if raw_dir is not None:
        from proyecto_de_grado.src.data.validar_splits import (
            check_gold_membership, load_split_index,
        )
        try:
            index = load_split_index(raw_dir)
        except (OSError, ValueError, TypeError) as exc:
            reasons.append(
                f"No se pudo verificar particion ACL-200: {type(exc).__name__}: {exc}"
            )
        else:
            reasons.extend(check_gold_membership(cases, index))

    return GoldAudit(bool(reasons), tuple(reasons), len(banned))
