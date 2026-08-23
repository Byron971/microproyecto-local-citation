"""Entry point for `uv run maqueta-front`.

Serves the mock-up's static files (index.html) on port 3000
"""

import pathlib
import subprocess

MAQUETA_DIR = pathlib.Path(__file__).resolve().parent

def run_frontend() -> None:
    subprocess.run(
        ["python3", "-m", "http.server", "3000"],
        cwd=MAQUETA_DIR,
        check=True,
    )
