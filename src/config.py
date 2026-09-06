"""Configuración única del experimento, validada antes de cargar los datos."""

from pathlib import Path
from typing import Literal, Self

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = PROJECT_ROOT / "config/model.yaml"


class ModelConfig(BaseModel):
    """Solo las decisiones del experimento; sin opciones de infraestructura."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    data_dir: Path
    output_dir: Path
    seed: int = Field(ge=0)
    negative_strategy: Literal["random", "hard"]
    negatives_per_positive: int = Field(gt=0)
    top_n: int = Field(gt=0)
    k: int = Field(gt=0)
    max_features: int = Field(gt=0)
    min_df: int = Field(gt=0)
    c: float = Field(gt=0, allow_inf_nan=False)

    @model_validator(mode="after")
    def check_ranking_limits(self) -> Self:
        if self.k > self.top_n:
            raise ValueError("k no puede superar top_n")
        if (
            self.negative_strategy == "hard"
            and self.negatives_per_positive >= self.top_n
        ):
            raise ValueError("top_n debe dejar espacio para positivos y negativos")
        return self

    def resolve_path(self, path: Path) -> Path:
        return path if path.is_absolute() else PROJECT_ROOT / path


def load_config(path: Path = DEFAULT_CONFIG) -> ModelConfig:
    """Lee YAML seguro y rechaza claves desconocidas o valores inválidos."""
    with path.open(encoding="utf-8") as file:
        return ModelConfig.model_validate(yaml.safe_load(file))
