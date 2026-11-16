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

REQUIRED_SCIBERT = frozenset(("scibert_A_42", "scibert_B_42"))
REQUIRED_FOUR = frozenset((
    "scibert_A_42", "scibert_B_42", "specter_A_42", "specter_B_42",
))
SPECTER_MANIFEST = (
    REPO / "proyecto_de_grado/docs/evidencias_clasificacion_a4/manifiesto_modelo_specter.json"
)

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


def specter_snapshot_status(*, download: bool = False) -> dict:
    """Verifica encoder SPECTER pinned; nunca descarga sin --download explícito."""
    try:
        from huggingface_hub import snapshot_download
        from recuperacion_densa.descarga_modelo import hash_manifiesto, manifiesto_de
        from clasificacion_funcion.revision import modelo
    except ImportError as exc:
        return {"status": "dependencias_no_instaladas", "detalle": type(exc).__name__}
    model_id, revision = modelo("specter")
    try:
        local = Path(snapshot_download(
            model_id, revision=revision, local_files_only=not download
        ))
    except (OSError, RuntimeError, ValueError) as exc:
        return {"status": "snapshot_no_disponible", "detalle": type(exc).__name__,
                "revision": revision}
    if local.name != revision or local.is_symlink():
        return {"status": "revision_no_coincide", "revision": revision}
    if not SPECTER_MANIFEST.is_file() or SPECTER_MANIFEST.is_symlink():
        return {"status": "manifiesto_ausente", "revision": revision}
    archived = json.loads(SPECTER_MANIFEST.read_text(encoding="utf-8"))
    actual = hash_manifiesto(manifiesto_de(local, model_id, revision))
    correct = (
        archived.get("model_id") == model_id
        and archived.get("revision") == revision
        and archived.get("sha256_manifiesto") == actual
    )
    return {"status": "verified" if correct else "sha_mismatch",
            "revision": revision, "snapshot_sha256": actual}


def _models_verified(models: object, expected: frozenset[str]) -> bool:
    """Evita 'all' vacuamente true si el registro perdió entradas necesarias."""
    if not isinstance(models, list):
        return False
    selected = [m for m in models if isinstance(m, dict) and m.get("id") in expected]
    return (len(selected) == len(expected)
            and {m["id"] for m in selected} == expected
            and all(m.get("status") == "verified" for m in selected))


def preflight(weights: Path | None = None, *, download: bool = False,
              include_specter: bool = False) -> dict:
    inventory = verificar_registro(base=weights)
    snap = snapshot_status(download=download)
    s_snapshot = (
        specter_snapshot_status(download=download) if include_specter
        else {"status": "not_requested"}
    )
    models = inventory.get("models")
    scibert_ready = snap.get("status") == "verified" and _models_verified(
        models, REQUIRED_SCIBERT
    )
    four_ready = (
        scibert_ready
        and s_snapshot.get("status") == "verified"
        and _models_verified(models, REQUIRED_FOUR)
    )
    return {
        "tipo": "preflight_cientifico_no_gold",
        "snapshot_scibert": snap,
        "snapshot_specter": s_snapshot,
        "checkpoints": inventory,
        "required_scibert": sorted(REQUIRED_SCIBERT),
        "required_four": sorted(REQUIRED_FOUR),
        "ready_a_b": scibert_ready,
        "ready_four_a4": four_ready,
        "gold_humano_certificado": False,
        "nota": "Gate de artefactos, NO prueba de inferencia real ni Gold humano.",
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--weights", type=Path,
                   help="Raíz A4 corridas; por defecto registro histórico")
    p.add_argument("--download", action="store_true",
                   help="AUTORIZA explícitamente descargar snapshots fijados")
    p.add_argument("--check-specter", action="store_true",
                   help="Verificar SPECTER pinned además del snapshot SciBERT")
    p.add_argument("--strict", action="store_true",
                   help="Fallar si falta SciBERT o pesos originales A/B")
    p.add_argument("--strict-all", action="store_true",
                   help="Fallar si falta cualquiera de los cuatro pesos o ambos encoders")
    a = p.parse_args(argv)
    try:
        result = preflight(
            a.weights, download=a.download,
            include_specter=a.check_specter or a.strict_all,
        )
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        p.exit(2, f"Preflight falló: {exc}\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if a.strict_all:
        return 0 if result["ready_four_a4"] else 1
    return 0 if (result["ready_a_b"] or not a.strict) else 1


if __name__ == "__main__":
    raise SystemExit(main())
