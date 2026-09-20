from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from .cli import _load_pricing
from .io import (
    load_gold_jsonl,
    load_prompts_json,
    write_results_jsonl,
    write_summary_csv,
)
from .metrics import evaluate_records, write_evaluation_artifacts
from .providers_gemini import GeminiClient
from .providers_openai import OpenAIClient
from .providers_openweight import OpenWeightClient
from .runner import run_evaluation
from .schema import RunRecord
from .stability import parse_score_array

DEFAULT_PROMPTS = Path("config/prompts/citation_function_prompts.json")
DEFAULT_FINAL_GOLD = Path("annotations/citation_function/test_gold.jsonl")
DEFAULT_PROVISIONAL_GOLD = Path(
    "annotations/citation_function/provisional_test_gold.jsonl"
)


def resolve_gold(explicit: str | None) -> Path:
    if explicit:
        return Path(explicit)
    if DEFAULT_FINAL_GOLD.exists():
        return DEFAULT_FINAL_GOLD
    return DEFAULT_PROVISIONAL_GOLD


def is_provisional_gold(path: str | Path) -> bool:
    path = Path(path)
    return "provisional" in path.name.casefold()


def build_clients(mode: str) -> list[object]:
    clients: list[object] = []
    if mode in {"openai", "commercial", "all"}:
        clients.append(OpenAIClient())
    if mode in {"gemini", "commercial", "all"}:
        clients.append(GeminiClient())
    if mode in {"openweight", "all"}:
        clients.append(OpenWeightClient())
    return clients


def validate_environment(mode: str) -> list[str]:
    errors: list[str] = []

    if mode in {"openai", "commercial", "all"}:
        if not os.environ.get("OPENAI_API_KEY"):
            errors.append("Falta OPENAI_API_KEY para la corrida OpenAI.")

    if mode in {"gemini", "commercial", "all"}:
        if not os.environ.get("GEMINI_API_KEY"):
            errors.append("Falta GEMINI_API_KEY para la corrida Gemini.")
        if not os.environ.get("GEMINI_MODEL"):
            errors.append("Falta GEMINI_MODEL para la corrida Gemini.")

    if mode in {"openweight", "all"}:
        if not os.environ.get("OPENWEIGHT_MODEL"):
            errors.append("Falta OPENWEIGHT_MODEL para la corrida open-weight.")

    return errors


def _records_as_dicts(records: Iterable[RunRecord]) -> list[dict]:
    return [record.to_dict() for record in records]


def write_run_metadata(
    output_dir: Path,
    *,
    gold_path: Path,
    provisional: bool,
    mode: str,
    clients: list[object],
    n_cases: int,
    n_prompts: int,
) -> None:
    payload = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "gold_path": str(gold_path),
        "provisional_gold": provisional,
        "mode": mode,
        "n_cases": n_cases,
        "n_prompts": n_prompts,
        "clients": [
            {
                "provider": getattr(client, "provider", "unknown"),
                "model": getattr(client, "model", "unknown"),
            }
            for client in clients
        ],
        "warning": (
            "Resultados preliminares: el conjunto usado es provisional y no debe "
            "presentarse como Test Gold definitivo."
            if provisional
            else None
        ),
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "run_metadata.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Ejecuta de punta a punta la evaluación de función de cita con "
            "OpenAI, Gemini y/o un modelo open-weight."
        )
    )
    parser.add_argument(
        "--mode",
        choices=["openai", "gemini", "openweight", "commercial", "all"],
        required=True,
        help=(
            "commercial ejecuta OpenAI+Gemini; all ejecuta "
            "OpenAI+Gemini+open-weight."
        ),
    )
    parser.add_argument(
        "--gold",
        help=(
            "Test Gold JSONL. Si se omite, usa test_gold.jsonl cuando exista; "
            "de lo contrario usa provisional_test_gold.jsonl."
        ),
    )
    parser.add_argument(
        "--prompts",
        default=str(DEFAULT_PROMPTS),
        help="Archivo JSON con prompts versionados.",
    )
    parser.add_argument(
        "--output-dir",
        default="artifacts/citation_function_eval",
    )
    parser.add_argument("--pricing", help="JSON opcional de tarifas explícitas.")
    parser.add_argument("--max-retries", type=int, default=2)
    parser.add_argument(
        "--allow-provisional",
        action="store_true",
        help=(
            "Permite una corrida real sobre el gold provisional. "
            "Los artefactos quedarán marcados como preliminares."
        ),
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Valida datos y configuración sin llamar proveedores.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    gold_path = resolve_gold(args.gold)
    prompts_path = Path(args.prompts)
    provisional = is_provisional_gold(gold_path)

    try:
        cases = load_gold_jsonl(gold_path)
        prompts = load_prompts_json(prompts_path)
    except (OSError, ValueError) as exc:
        print(f"Error de entrada: {exc}", file=sys.stderr)
        return 2

    if provisional and not args.allow_provisional and not args.check_only:
        print(
            "El conjunto seleccionado es provisional. Usa --allow-provisional "
            "solo para corridas preliminares o espera el Test Gold definitivo.",
            file=sys.stderr,
        )
        return 2

    env_errors = validate_environment(args.mode)
    clients = build_clients(args.mode)

    print(f"Gold: {gold_path}")
    print(f"Casos: {len(cases)}")
    print(f"Prompts: {len(prompts)}")
    print(f"Provisional: {'sí' if provisional else 'no'}")
    for client in clients:
        print(
            "Cliente: "
            f"{getattr(client, 'provider', 'unknown')}/"
            f"{getattr(client, 'model', 'unknown')}"
        )

    if env_errors:
        for error in env_errors:
            print(f"Configuración: {error}", file=sys.stderr)
        return 2

    if args.check_only:
        print("Preflight completado sin llamadas de red.")
        return 0

    try:
        pricing = _load_pricing(args.pricing)
        records = run_evaluation(
            cases,
            prompts,
            clients,
            max_retries=args.max_retries,
            parser=parse_score_array,
            pricing=pricing,
        )
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"Error de ejecución: {exc}", file=sys.stderr)
        return 2

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    write_results_jsonl(output_dir / "results.jsonl", records)
    write_summary_csv(output_dir / "summary.csv", records)

    dict_records = _records_as_dicts(records)
    summaries, predictions, matrices = evaluate_records(dict_records)
    write_evaluation_artifacts(
        output_dir / "metrics",
        summaries,
        predictions,
        matrices,
    )
    write_run_metadata(
        output_dir,
        gold_path=gold_path,
        provisional=provisional,
        mode=args.mode,
        clients=clients,
        n_cases=len(cases),
        n_prompts=len(prompts),
    )

    print(
        f"Evaluación terminada: {len(records)} ejecuciones. "
        f"Artefactos: {output_dir}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
