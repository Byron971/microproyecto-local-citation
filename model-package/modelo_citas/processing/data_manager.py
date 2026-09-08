"""Lectura de datos y persistencia versionada del artefacto entrenado."""

import json
from pathlib import Path
from typing import Any

import joblib

from modelo_citas import __version__
from modelo_citas.config.core import TRAINED_MODEL_DIR, config
from modelo_citas.models.citation_model import CitationArtifact


def artifact_file_name(version: str = __version__) -> str:
    """Nombre del artefacto para una versión del paquete."""
    return f"{config.app_config.pipeline_save_file}{version}.pkl"


def load_json(path: str | Path) -> Any:
    """Carga un archivo JSON del dataset."""
    with Path(path).open(encoding="utf-8") as data_file:
        return json.load(data_file)


def paper_metadata(
    papers: dict[str, dict[str, Any]],
    preview_chars: int = config.app_config.abstract_preview_chars,
) -> dict[str, dict[str, str]]:
    """Extrae título y un extracto del resumen de cada artículo.

    Se recorta el resumen porque es lo único que muestra el cliente y guardar
    los textos completos multiplicaría el tamaño del artefacto.
    """
    metadata: dict[str, dict[str, str]] = {}

    for paper_id, paper in papers.items():
        abstract = (paper.get("abstract") or "").strip()
        truncated = len(abstract) > preview_chars
        metadata[paper_id] = {
            "title": (paper.get("title") or "").strip(),
            "abstract": abstract[:preview_chars] + ("…" if truncated else ""),
        }

    return metadata


def remove_old_artifacts(files_to_keep: list[str]) -> None:
    """Deja un solo artefacto en trained/, para no ambigüedad de versión."""
    do_not_delete = [*files_to_keep, "__init__.py"]

    for model_file in TRAINED_MODEL_DIR.iterdir():
        if model_file.name not in do_not_delete:
            model_file.unlink()


def save_artifact(artifact: CitationArtifact) -> Path:
    """Guarda el artefacto con el nombre de la versión actual del paquete."""
    save_file_name = artifact_file_name()
    save_path = TRAINED_MODEL_DIR / save_file_name

    TRAINED_MODEL_DIR.mkdir(parents=True, exist_ok=True)
    remove_old_artifacts(files_to_keep=[save_file_name])
    joblib.dump(artifact, save_path)

    return save_path


def load_artifact(file_name: str | None = None) -> CitationArtifact:
    """Carga el artefacto empaquetado."""
    file_path = TRAINED_MODEL_DIR / (file_name or artifact_file_name())

    if not file_path.is_file():
        raise FileNotFoundError(
            f"No se encontró el modelo entrenado en {file_path}. "
            "Genérelo con: python -m modelo_citas.train_pipeline --data-dir <data/raw>"
        )

    return joblib.load(file_path)
