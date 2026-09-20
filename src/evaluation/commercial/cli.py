from __future__ import annotations

import argparse
import importlib
import json
import sys
from pathlib import Path
from typing import Any, Callable

from .io import load_gold_jsonl, load_prompts_json, write_results_jsonl, write_summary_csv
from .runner import ModelPricing, run_evaluation


def _load_object(spec: str) -> Any:
    if ":" not in spec:
        raise ValueError(f"invalid object spec {spec!r}; expected module:object")
    module_name, object_name = spec.split(":", 1)
    module = importlib.import_module(module_name)
    return getattr(module, object_name)


def _load_pricing(path: str | None) -> dict[tuple[str, str], ModelPricing]:
    if path is None:
        return {}
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("pricing JSON must be an object")
    result: dict[tuple[str, str], ModelPricing] = {}
    for key, values in payload.items():
        if ":" not in key or not isinstance(values, dict):
            raise ValueError("pricing keys must use provider:model")
        provider, model = key.split(":", 1)
        result[(provider, model)] = ModelPricing(
            input_usd_per_million=float(values["input_usd_per_million"]),
            output_usd_per_million=float(values["output_usd_per_million"]),
        )
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Ejecuta evaluación reproducible de modelos comerciales")
    parser.add_argument("--gold", required=True, help="Test Gold en formato JSONL")
    parser.add_argument("--prompts", required=True, help="Prompts versionados en formato JSON")
    parser.add_argument(
        "--client",
        action="append",
        default=[],
        help="Factory de cliente como module:factory; se puede repetir",
    )
    parser.add_argument("--parser", dest="response_parser", help="Parser opcional como module:function")
    parser.add_argument("--pricing", help="JSON opcional con tarifas explícitas por provider:model")
    parser.add_argument(
        "--output-dir",
        default="artifacts/commercial_eval",
        help="Directorio de resultados",
    )
    parser.add_argument("--max-retries", type=int, default=2)
    parser.add_argument("--check-only", action="store_true", help="Valida entradas sin llamar proveedores")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        cases = load_gold_jsonl(args.gold)
        prompts = load_prompts_json(args.prompts)
    except (OSError, ValueError) as exc:
        print(f"Error de entrada: {exc}", file=sys.stderr)
        return 2

    if args.check_only:
        print(f"Entradas válidas: {len(cases)} casos, {len(prompts)} prompts")
        return 0

    if not args.client:
        print("Se requiere al menos un --client module:factory para ejecutar modelos.", file=sys.stderr)
        return 2

    try:
        clients = []
        for spec in args.client:
            factory = _load_object(spec)
            clients.append(factory())
        response_parser: Callable[[str], Any] | None = None
        if args.response_parser:
            response_parser = _load_object(args.response_parser)
        pricing = _load_pricing(args.pricing)
        records = run_evaluation(
            cases,
            prompts,
            clients,
            max_retries=args.max_retries,
            parser=response_parser,
            pricing=pricing,
        )
    except (AttributeError, ImportError, KeyError, TypeError, ValueError, RuntimeError) as exc:
        print(f"Error de configuración: {exc}", file=sys.stderr)
        return 2

    output_dir = Path(args.output_dir)
    write_results_jsonl(output_dir / "results.jsonl", records)
    write_summary_csv(output_dir / "summary.csv", records)
    print(f"Evaluación completada: {len(records)} ejecuciones en {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
