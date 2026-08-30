"""Generación reproducible de los datasets supervisados procesados."""

import json
from pathlib import Path

from src.data.build_pairs import build_pairs
from src.data.load_data import load_dataset


NEGATIVES_PER_POSITIVE = 2
RANDOM_STATE = 42
SPLITS = ("train", "val", "test")


def save_json(data: list[dict], output_path: str | Path) -> None:
    """Guarda una lista de registros en formato JSON."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False)


def generate_processed_datasets(
    raw_dir: str | Path = "data/raw",
    output_dir: str | Path = "data/processed",
) -> dict[str, int]:
    """Genera los pares supervisados para train, validation y test."""
    dataset = load_dataset(raw_dir)

    paper_ids = list(dataset["papers"].keys())
    output_path = Path(output_dir)

    generated_counts = {}

    for split_name in SPLITS:
        pairs = build_pairs(
            split=dataset[split_name],
            paper_ids=paper_ids,
            negatives_per_positive=NEGATIVES_PER_POSITIVE,
            random_state=RANDOM_STATE,
        )

        file_path = output_path / f"{split_name}_pairs.json"

        save_json(
            data=pairs,
            output_path=file_path,
        )

        generated_counts[split_name] = len(pairs)

    return generated_counts


def main() -> None:
    """Ejecuta la generación de los datasets procesados."""
    counts = generate_processed_datasets()

    print("Datasets procesados generados correctamente.")
    print(f"train_pairs: {counts['train']}")
    print(f"val_pairs: {counts['val']}")
    print(f"test_pairs: {counts['test']}")


if __name__ == "__main__":
    main()