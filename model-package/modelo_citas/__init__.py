"""Modelo de recomendación local de citas académicas, listo para instalar."""

import logging
from pathlib import Path

# NullHandler para no imponer configuración de logging a quien use la librería.
# https://docs.python.org/3/howto/logging.html#configuring-logging-for-a-library
logging.getLogger(__name__).addHandler(logging.NullHandler())

with open(Path(__file__).resolve().parent / "VERSION", encoding="utf-8") as version_file:
    __version__ = version_file.read().strip()

# Import diferido: predict importa la configuración, que a su vez necesita que
# este módulo ya tenga __file__ y __version__ resueltos.
from modelo_citas.predict import describe, load_model, make_prediction  # noqa: E402

__all__ = ["__version__", "describe", "load_model", "make_prediction"]
