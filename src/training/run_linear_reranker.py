"""Entrena con YAML o evalúa un modelo guardado, sin reentrenarlo."""

import argparse
from pathlib import Path

from src.config import DEFAULT_CONFIG, load_config
from src.training.experiment import evaluate_saved, train


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    training = commands.add_parser("train", help="Entrenar y evaluar en validación")
    training.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    evaluation = commands.add_parser("evaluate", help="Evaluar un modelo congelado")
    evaluation.add_argument("--model", type=Path, required=True)
    evaluation.add_argument("--split", choices=("val", "test"), default="val")
    args = parser.parse_args()
    if args.command == "train":
        train(load_config(args.config))
    else:
        evaluate_saved(args.model, args.split)


if __name__ == "__main__":
    main()
