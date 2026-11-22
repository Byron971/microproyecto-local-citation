"""Rutas compartidas por inferencia y diagnóstico M/S."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS = Path(os.environ.get("MS_ARTIFACTS_DIR", ROOT / "proyecto_de_grado/artifacts/experimentos_10"))
MANIFEST_SCIBERT = Path(os.environ.get("MS_SCIBERT_MANIFEST", ROOT / "proyecto_de_grado/docs/evidencias_recuperacion_densa_a1/manifiesto_modelo.json"))
