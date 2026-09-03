"""Exporta a JSON los Top-100 candidatos TF-IDF de un split.

Uso:
    python -m src.training.export_top100
    python -m src.training.export_top100 --splits train val

El archivo resultante es el insumo del reordenador supervisado: de él se toman
los negativos duros, que son los candidatos que la primera etapa coloca arriba
sin ser citas correctas.
"""

import argparse
from pathlib import Path

from src.data.load_data import load_json
from src.training.run_tfidf_baseline import export_top100

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RAW_DIR = REPO_ROOT / "data" / "raw"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "data" / "processed"


def export_split_top100(
    raw_dir: str | Path,
    output_dir: str | Path,
    split_name: str,
) -> Path:
    """Genera y guarda el Top-100 TF-IDF para un split."""
    raw_path = Path(raw_dir)
    output_path = Path(output_dir) / f"{split_name}_tfidf_top100.json"

    papers = load_json(raw_path / "papers.json")
    contexts = load_json(raw_path / "contexts.json")
    split = load_json(raw_path / f"{split_name}.json")

    export_top100(
        papers=papers,
        contexts=contexts,
        split=split,
        output_path=output_path,
    )

    return output_path


def main() -> None:
    """Punto de entrada: regenera los candidatos desde la línea de comandos.

    Sin esto el módulo solo era importable, y el comando documentado en el
    README no habría producido nada.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--splits",
        nargs="+",
        default=["train"],
        choices=["train", "val", "test"],
        help="Particiones a exportar. Por omisión solo train, que es la que "
        "consume el entrenamiento del modelo supervisado.",
    )
    args = parser.parse_args()

    for split_name in args.splits:
        print(f"Generando Top-100 para {split_name}...")

        output_path = export_split_top100(
            raw_dir=args.raw_dir,
            output_dir=args.output_dir,
            split_name=split_name,
        )

        print(f"  {output_path} ({output_path.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()

    