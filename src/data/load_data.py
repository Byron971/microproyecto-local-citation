"""Funciones para cargar los archivos de datos del proyecto."""

import json
from pathlib import Path
from typing import Any


DATASET_FILES = {
    "contexts": "contexts.json",
    "papers": "papers.json",
    "train": "train.json",
    "val": "val.json",
    "test": "test.json",
}


def load_json(file_path: str | Path) -> Any:
    """Carga y devuelve el contenido de un archivo JSON."""
    path = Path(file_path)

    with path.open(encoding="utf-8") as file:
        return json.load(file)


def load_dataset(data_dir: str | Path) -> dict[str, Any]:
    """Carga los cinco archivos principales del dataset."""
    data_path = Path(data_dir)

    return {
        name: load_json(data_path / filename)
        for name, filename in DATASET_FILES.items()
    }
