"""Lectura de la información precalculada del tablero.

El cálculo en sí vive en ``src/training/build_insights``, del lado de
investigación: depende de sklearn y de ``data/raw``, y tarda cerca de un
minuto. Este módulo solo lee el JSON ya generado, para que la imagen de la API
no necesite ni el dataset ni las dependencias de cómputo científico.
"""

import json
from pathlib import Path
from typing import Any

DEFAULT_INSIGHTS_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "processed" / "dashboard_insights.json"
)


def load_insights(path: str | Path = DEFAULT_INSIGHTS_PATH) -> dict[str, Any]:
    """Lee los insights del tablero desde disco.

    Parameters
    ----------
    path:
        Archivo generado por ``python -m src.training.build_insights``.

    Returns
    -------
    dict
        Información del tablero, tal como la sirve ``/api/insights``.

    Raises
    ------
    FileNotFoundError
        Si el archivo no existe. El mensaje indica cómo generarlo.
    """
    file = Path(path)

    if not file.exists():
        raise FileNotFoundError(
            f"No se encontró {file}. Genérelo con "
            "'python -m src.training.build_insights'."
        )

    with file.open(encoding="utf-8") as insights_file:
        return json.load(insights_file)
