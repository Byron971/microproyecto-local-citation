"""Servidor local para los archivos estáticos de la maqueta.

Sirve el contenido de la carpeta `maqueta` en el puerto 3000.
"""

import pathlib
import subprocess
import sys

MAQUETA_DIR = pathlib.Path(__file__).resolve().parent


def run_frontend() -> None:
    """Inicia el servidor local del frontend en el puerto 3000."""
    subprocess.run(
        [sys.executable, "-m", "http.server", "3000"],
        cwd=MAQUETA_DIR,
        check=True,
    )