"""Configuración del experimento: el modelo del paquete más las rutas del repo."""

from pathlib import Path

import yaml
from modelo_citas.config.core import ModelConfig
from pydantic import ConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = PROJECT_ROOT / "config/model.yaml"


class ExperimentConfig(ModelConfig):
    """Las decisiones del modelo, heredadas del paquete, más dónde viven los datos.

    Hereda de ``modelo_citas.config.core.ModelConfig`` en lugar de repetir sus
    campos y su validación: el artefacto que se despliega y el que se mide deben
    aceptar exactamente los mismos hiperparámetros. Aquí solo se añade lo que es
    propio del repositorio —de dónde se leen los datos y dónde se guarda el
    artefacto de cada run—, que no tiene sentido dentro de un wheel instalado.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    data_dir: Path
    output_dir: Path

    def resolve_path(self, path: Path) -> Path:
        return path if path.is_absolute() else PROJECT_ROOT / path


def load_config(path: Path = DEFAULT_CONFIG) -> ExperimentConfig:
    """Lee YAML seguro y rechaza claves desconocidas o valores inválidos."""
    with path.open(encoding="utf-8") as file:
        return ExperimentConfig.model_validate(yaml.safe_load(file))
