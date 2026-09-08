"""Entrena el modelo y lo guarda dentro del paquete, listo para empaquetar.

El seguimiento de experimentos (MLflow) y la evaluación en val/test siguen
siendo responsabilidad del repositorio; aquí solo se produce el artefacto.

    python -m modelo_citas.train_pipeline --data-dir ../data/raw
"""

import argparse
import hashlib
import os
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from modelo_citas import __version__
from modelo_citas.config.core import config
from modelo_citas.models.citation_model import CitationArtifact
from modelo_citas.models.linear_reranker import LinearReranker
from modelo_citas.models.tfidf_baseline import TfidfBaseline
from modelo_citas.processing.data_manager import load_json, paper_metadata, save_artifact
from modelo_citas.processing.features import PairFeatureExtractor
from modelo_citas.processing.pairs import build_hard_pairs, build_pairs, retrieve_candidates

DATA_DIR_ENV = "MODELO_CITAS_DATA_DIR"


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


def training_pairs(
    retriever: TfidfBaseline,
    papers: dict,
    contexts: dict,
    split: list[dict],
) -> list[dict]:
    """Arma los pares etiquetados según la estrategia de negativos configurada."""
    settings = config.model_settings

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


def run_training(data_dir: Path | None = None) -> Path:
    """Entrena las tres etapas y guarda el artefacto versionado."""
    raw = resolve_data_dir(data_dir)
    papers = load_json(raw / "papers.json")
    contexts = load_json(raw / "contexts.json")
    split = load_json(raw / "train.json")

    if not split:
        raise ValueError("train.json debe contener consultas de entrenamiento.")

    settings = config.model_settings

    print("Ajustando TF-IDF sobre el corpus...", flush=True)
    retriever = TfidfBaseline(
        max_features=settings.max_features, min_df=settings.min_df
    ).fit(papers)
    extractor = PairFeatureExtractor(
        max_features=settings.max_features, min_df=settings.min_df
    ).fit(papers)

    print("Construyendo pares de entrenamiento...", flush=True)
    pairs = training_pairs(retriever, papers, contexts, split)
    features = extractor.transform(pairs, contexts)
    labels = np.asarray([int(pair["label"]) for pair in pairs], dtype=int)

    print(f"Entrenando el reordenador con {len(pairs)} pares...", flush=True)
    reranker = LinearReranker(c=settings.c, random_state=settings.seed).fit(
        features, labels
    )

    artifact = CitationArtifact(
        retriever=retriever,
        extractor=extractor,
        reranker=reranker,
        papers=paper_metadata(papers),
        settings=settings.model_dump(mode="json"),
        metadata={
            "entrenado_en": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "n_pares_entrenamiento": len(pairs),
            "n_consultas_entrenamiento": len(split),
            "coeficientes": dict(
                zip(
                    extractor.feature_names,
                    reranker.coefficients.tolist(),
                    strict=True,
                )
            ),
            "intercepto": reranker.intercept,
            "hashes_datos": {
                name: file_hash(raw / f"{name}.json")
                for name in ("papers", "contexts", "train")
            },
        },
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
