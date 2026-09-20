"""Entrena el modelo y lo guarda dentro del paquete, listo para empaquetar.

El ajuste de las tres etapas vive en ``fit_artifact`` y es el único del
proyecto: ``src/training/experiment.py`` lo reutiliza y solo añade lo que
depende de este repositorio —el seguimiento en MLflow y la evaluación en
val/test—. Mientras hubo dos entrenadores, el artefacto que servía el tablero y
el que producía las métricas del reporte podían divergir sin que nada fallara.

    python -m modelo_citas.train_pipeline --data-dir ../data/raw
"""

import argparse
import hashlib
import os
import subprocess
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any

from modelo_citas import __version__
from modelo_citas.config.core import ModelConfig, config
from modelo_citas.models.citation_model import CitationArtifact
from modelo_citas.models.linear_reranker import LinearReranker
from modelo_citas.models.tfidf_baseline import TfidfBaseline
from modelo_citas.processing.data_manager import load_json, paper_metadata, save_artifact
from modelo_citas.processing.features import PairFeatureExtractor
from modelo_citas.processing.pairs import (
    build_hard_pairs,
    build_pairs,
    labels_from_pairs,
    retrieve_candidates,
)

DATA_DIR_ENV = "MODELO_CITAS_DATA_DIR"

# Archivos que alimentan el entrenamiento y cuya huella queda en el artefacto.
TRAINING_FILES = ("papers", "contexts", "train")


def resolve_data_dir(data_dir: Path | None = None) -> Path:
    """Prioriza el argumento, luego la variable de entorno, luego el config."""
    if data_dir is not None:
        return Path(data_dir)
    if os.environ.get(DATA_DIR_ENV):
        return Path(os.environ[DATA_DIR_ENV])
    return Path(config.app_config.data_dir)


def file_hash(path: Path) -> str:
    """Huella sha256 del archivo de datos, para trazar de dónde salió el modelo."""
    with path.open("rb") as data_file:
        return hashlib.file_digest(data_file, "sha256").hexdigest()


def data_hashes(
    data_dir: Path, names: Iterable[str] = TRAINING_FILES
) -> dict[str, str]:
    """Huellas de los JSON usados, para detectar datos cambiados al reevaluar."""
    return {name: file_hash(Path(data_dir) / f"{name}.json") for name in names}


def current_git_sha() -> str | None:
    """Commit desde el que se entrenó, o ``None`` fuera de un repositorio git."""
    try:
        return (
            subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True,
                check=True,
                text=True,
            )
            .stdout.strip()
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def citation_counts_from_split(split: list[dict]) -> dict[str, int]:
    """Cuenta cuántas veces se cita cada artículo dentro de un split.

    Alimenta la característica ``citation_prior``. Se le pasa **siempre** el
    split de entrenamiento: contarlo sobre validación le filtraría al modelo la
    respuesta que después se le pregunta, y el resultado se vería mejor de lo
    que es.
    """
    counts: dict[str, int] = {}

    for record in split:
        for paper_id in record.get("positive_ids", ()):
            counts[paper_id] = counts.get(paper_id, 0) + 1

    return counts


def training_pairs(
    retriever: TfidfBaseline,
    papers: dict,
    contexts: dict,
    split: list[dict],
    settings: ModelConfig | None = None,
) -> list[dict]:
    """Arma los pares etiquetados según la estrategia de negativos configurada."""
    settings = settings or config.model_settings

    if settings.negative_strategy == "hard":
        return build_hard_pairs(
            retrieve_candidates(retriever, contexts, split, settings.top_n),
            settings.negatives_per_positive,
            contexts,
        )

    return build_pairs(
        split,
        list(papers),
        settings.negatives_per_positive,
        settings.seed,
        excluded_paper_ids={
            row["context_id"]: {contexts[row["context_id"]].get("citing_id")}
            for row in split
        },
    )


def fit_artifact(
    papers: dict,
    contexts: dict,
    split: list[dict],
    settings: ModelConfig | None = None,
    metadata: dict[str, Any] | None = None,
) -> CitationArtifact:
    """Ajusta las tres etapas y devuelve el artefacto, sin guardarlo ni evaluarlo.

    Parameters
    ----------
    settings:
        Hiperparámetros a usar. Por defecto los del paquete; el experimento del
        repositorio pasa los suyos, leídos de ``config/model.yaml``.
    metadata:
        Traza adicional, que se superpone a la calculada aquí. Sirve para lo que
        solo conoce quien llama, como el ``run_id`` de MLflow o las huellas de
        los archivos de datos.
    """
    if not split:
        raise ValueError("train.json debe contener consultas de entrenamiento.")

    settings = settings or config.model_settings

    print("Ajustando TF-IDF sobre el corpus...", flush=True)
    start = perf_counter()
    retriever = TfidfBaseline(
        max_features=settings.max_features, min_df=settings.min_df
    ).fit(papers)
    extractor = PairFeatureExtractor(
        max_features=settings.max_features,
        min_df=settings.min_df,
        include_metadata=settings.include_metadata,
        citation_counts=citation_counts_from_split(split),
    ).fit(papers)

    print("Construyendo pares de entrenamiento...", flush=True)
    pairs = training_pairs(retriever, papers, contexts, split, settings)
    features = extractor.transform(pairs, contexts)
    feature_seconds = perf_counter() - start

    print(f"Entrenando el reordenador con {len(pairs)} pares...", flush=True)
    start = perf_counter()
    reranker = LinearReranker(c=settings.c, random_state=settings.seed).fit(
        features, labels_from_pairs(pairs)
    )
    training_seconds = perf_counter() - start

    return CitationArtifact(
        retriever=retriever,
        extractor=extractor,
        reranker=reranker,
        papers=paper_metadata(papers),
        settings=settings.model_dump(mode="json"),
        metadata={
            "run_id": None,
            "git_sha": current_git_sha(),
            "entrenado_en": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "n_pares_entrenamiento": len(pairs),
            "n_consultas_entrenamiento": len(split),
            "segundos_caracteristicas": feature_seconds,
            "segundos_entrenamiento": training_seconds,
            "coeficientes": dict(
                zip(
                    extractor.feature_names,
                    reranker.coefficients.tolist(),
                    strict=True,
                )
            ),
            "intercepto": reranker.intercept,
            **(metadata or {}),
        },
    )


def run_training(data_dir: Path | None = None) -> Path:
    """Entrena con los datos indicados y congela el artefacto en el paquete."""
    raw = resolve_data_dir(data_dir)
    artifact = fit_artifact(
        papers=load_json(raw / "papers.json"),
        contexts=load_json(raw / "contexts.json"),
        split=load_json(raw / "train.json"),
        metadata={"hashes_datos": data_hashes(raw)},
    )

    path = save_artifact(artifact)
    print(f"Modelo {__version__} guardado en: {path}")

    return path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=None,
        help=f"Carpeta con papers/contexts/train.json (o {DATA_DIR_ENV}).",
    )
    run_training(parser.parse_args().data_dir)


if __name__ == "__main__":
    main()
