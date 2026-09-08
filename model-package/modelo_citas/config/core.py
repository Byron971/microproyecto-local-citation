"""Configuración del paquete, resuelta contra la ubicación instalada."""

from pathlib import Path
from typing import Literal, Self

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

import modelo_citas

# Las rutas salen del paquete instalado, no del directorio de trabajo: así el
# wheel funciona igual dentro del repositorio que en site-packages.
PACKAGE_ROOT = Path(modelo_citas.__file__).resolve().parent
CONFIG_FILE_PATH = PACKAGE_ROOT / "config.yml"
TRAINED_MODEL_DIR = PACKAGE_ROOT / "trained"


class AppConfig(BaseModel):
    """Nombres del paquete y del artefacto que produce."""

    model_config = ConfigDict(frozen=True)

    package_name: str
    pipeline_save_file: str
    data_dir: Path
    abstract_preview_chars: int = Field(gt=0)


class ModelConfig(BaseModel):
    """Decisiones del modelo: recuperación, características y clasificador."""

    model_config = ConfigDict(frozen=True)

    top_n: int = Field(gt=0)
    k: int = Field(gt=0)
    max_features: int = Field(gt=0)
    min_df: int = Field(gt=0)
    c: float = Field(gt=0, allow_inf_nan=False)
    seed: int = Field(ge=0)
    negative_strategy: Literal["random", "hard"]
    negatives_per_positive: int = Field(gt=0)

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


class Config(BaseModel):
    """Configuración completa del paquete."""

    model_config = ConfigDict(frozen=True)

    app_config: AppConfig
    model_settings: ModelConfig


def find_config_file() -> Path:
    """Localiza el archivo de configuración empaquetado."""
    if CONFIG_FILE_PATH.is_file():
        return CONFIG_FILE_PATH
    raise OSError(f"No se encontró la configuración en {CONFIG_FILE_PATH!r}")


def fetch_config_from_yaml(cfg_path: Path | None = None) -> dict:
    """Lee el YAML de configuración de forma segura."""
    path = cfg_path or find_config_file()

    with path.open(encoding="utf-8") as config_file:
        return yaml.safe_load(config_file)


def create_and_validate_config(parsed_config: dict | None = None) -> Config:
    """Valida el YAML y construye la configuración; ambas vistas del mismo dict."""
    parsed = parsed_config if parsed_config is not None else fetch_config_from_yaml()

    return Config(
        app_config=AppConfig.model_validate(parsed),
        model_settings=ModelConfig.model_validate(parsed),
    )


config = create_and_validate_config()
