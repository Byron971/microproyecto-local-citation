"""Gate de disponibilidad SciBERT + A4 sin red por defecto.

La verificación científica real necesita snapshot completo con hashes A1/A4
y checkpoints A4 originales. No descarga nada sin --download explícito.
"""
from __future__ import annotations

import argparse
import importlib
import json
from pathlib import Path

from src.app.checkpoint_gate import REPO, verificar_registro

MODEL_MANIFESTS = (
    REPO / "proyecto_de_grado/docs/evidencias_recuperacion_densa_a1/manifiesto_modelo.json",
    REPO / "proyecto_de_grado/docs/evidencias_clasificacion_a4/manifiesto_modelo_scibert.json",
)


def snapshot_status(*, download: bool = False) -> dict:
    """No comprueba inferencia ni Torch; verifica TODO el snapshot offline."""
    try:
        from huggingface_hub import snapshot_download
        revision = importlib.import_module("recuperacion_densa.revision")
        hashing = importlib.import_module("recuperacion_densa.descarga_modelo")
    except ImportError as exc:
        return {"status": "dependencias_no_instaladas", "detalle": type(exc).__name__}
    expected = revision.REVISION_SCIBERT
    try:
        # Por defecto nunca solicita conexión a internet.
        local = Path(snapshot_download(revision.MODEL_ID, revision=expected,
                                       local_files_only=not download))
    except (OSError, RuntimeError, ValueError) as exc:
        return {"status": "snapshot_no_disponible", "detalle": type(exc).__name__,
                "revision": expected}
    if local.name != expected or local.is_symlink():
        return {"status": "revision_no_coincide", "revision": expected}
    actual = hashing.hash_manifiesto(hashing.manifiesto_de(local, revision.MODEL_ID, expected))
    mismatches = []
    for path in MODEL_MANIFESTS:
        if not path.is_file() or path.is_symlink():
            mismatches.append(path.name + "_ausente")
            continue
        expected_sha = json.loads(path.read_text(encoding="utf-8")).get("sha256_manifiesto")
        if actual != expected_sha:
            mismatches.append(path.name + "_sha_incorrecto")
    return {"status": "verified" if not mismatches else "sha_mismatch",
            "revision": expected, "snapshot_sha256": actual, "errores": mismatches}


def preflight(weights: Path | None = None, *, download: bool = False) -> dict:
    inventory = verificar_registro(base=weights)
    snap = snapshot_status(download=download)
    return {
        "tipo": "preflight_cientifico_no_gold",
        "snapshot_scibert": snap,
        "checkpoints": inventory,
        "ready_a_b": (
            snap["status"] == "verified" and
            all(m["status"] == "verified" for m in inventory["models"]
                if m["id"] in ("scibert_A_42", "scibert_B_42"))
        ),
        "nota": "Gate de artefactos, NO prueba de inferencia real ni Gold humano.",
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--weights", type=Path,
                   help="Raíz A4 corridas; por defecto registro histórico")
    p.add_argument("--download", action="store_true",
                   help="AUTORIZA explícitamente internet para obtener SciBERT fijado")
    p.add_argument("--strict", action="store_true",
                   help="Fallar si falta SciBERT o pesos reales A/B")
    a = p.parse_args(argv)
    try:
        result = preflight(a.weights, download=a.download)
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        p.exit(2, f"Preflight falló: {exc}\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if (result["ready_a_b"] or not a.strict) else 1


if __name__ == "__main__":
    raise SystemExit(main())
