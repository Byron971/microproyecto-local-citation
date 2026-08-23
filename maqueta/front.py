"""Entry point for `uv run maqueta-front`.

Serves the mock-up's static files (index.html) on port 3000
"""

import pathlib
import subprocess
import sys

MAQUETA_DIR = pathlib.Path(__file__).resolve().parent

def run_frontend() -> None:
    subprocess.run(
        [sys.executable, "-m", "http.server", "3000"],
        cwd=MAQUETA_DIR,
        check=True,
    )
