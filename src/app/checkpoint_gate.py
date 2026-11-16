"""Gate reproducible para checkpoints A4, sin Torch, secretos ni etiquetas Gold.

Los pesos NO se descargan ni crean; hashes/identidad se contrastan contra los
manifiestos originales versionados. Ejecución estricta devuelve código != 0
si falta un checkpoint o no coincide su SHA-256.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
REGISTRY = REPO / "config/checkpoint_registry.json"
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
ID = re.compile(r"[a-z0-9]+_[AB]_[0-9]+\Z")


def _relative(raw: object) -> Path:
    if not isinstance(raw, str) or not raw or "\\" in raw or ":" in raw or raw.startswith("/"):
        raise ValueError("Ruta de artefacto inválida.")
    path = Path(raw)
    if path.is_absolute() or any(part in (".", "..") for part in raw.split("/")):
        raise ValueError("Las rutas del registro deben ser relativas y seguras.")
    return path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verificar_registro(registro: Path = REGISTRY, base: Path | None = None,
                       repo: Path = REPO) -> dict:
    """Devuelve solo metadatos agregados; nunca texto de citas ni datos humanos."""
    data = json.loads(registro.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("version") != 1:
        raise ValueError("Versión del registro no compatible.")
    items = data.get("models")
    if not isinstance(items, list) or not items:
        raise ValueError("Registro sin modelos.")
    base_dir = (base or repo / _relative(data.get("root"))).resolve()
    ids = set()
    rows = []
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("Entrada del registro inválida.")
        name = item.get("id")
        sha = item.get("expected_sha256")
        if not isinstance(name, str) or not ID.fullmatch(name) or name in ids:
            raise ValueError("ID de modelo inválido o duplicado.")
        ids.add(name)
        if not isinstance(sha, str) or HEX64.fullmatch(sha) is None:
            raise ValueError("SHA-256 de modelo inválido.")
        if item.get("training_labels") != "Haiku" or item.get("validation") != "provisional_not_gold":
            raise ValueError("La procedencia provisional debe ser explícita.")
        if name != f'{item.get("encoder")}_{item.get("entrada")}_{item.get("semilla")}':
            raise ValueError("Identidad A4 inconsistente.")
        relative = _relative(item.get("checkpoint"))
        manifest_relative = _relative(item.get("source_manifest"))
        filename = base_dir / relative
        manifest_file = repo / manifest_relative
        if not manifest_file.is_file() or manifest_file.is_symlink():
            raise ValueError("Falta manifiesto histórico o es un enlace simbólico.")
        manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
        if any((manifest.get(k) != item[k]) for k in ("encoder", "entrada", "semilla")):
            raise ValueError("Configuración del manifiesto A4 incompatible.")
        if manifest.get("checkpoint_sha256") != sha:
            raise ValueError("El registro no corresponde al SHA histórico de A4.")
        if manifest.get("training_labels") != "Haiku":
            raise ValueError("Procedencia de entrenamiento no corresponde.")
        if filename.is_symlink():
            status, found = "unsafe_symlink", None
        elif not filename.is_file():
            status, found = "missing", None
        else:
            found = _sha256(filename)
            status = "verified" if found == sha else "sha_mismatch"
        rows.append({
            "id": name,
            "status": status,
            "encoder": item["encoder"],
            "input": item["entrada"],
            "seed": item["semilla"],
            "expected_sha256": sha,
            "observed_sha256": found,
            "training_labels": "Haiku",
            "certified_gold": False,
        })
    counter = Counter(row["status"] for row in rows)
    return {
        "version": 1,
        "scope": "technical_provisional_checkpoints_no_human_gold",
        "total": len(rows),
        "verified": counter["verified"],
        "missing": counter["missing"],
        "sha_mismatch": counter["sha_mismatch"],
        "unsafe_symlink": counter["unsafe_symlink"],
        "ready": len(rows) == counter["verified"],
        "models": rows,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--registro", type=Path, default=REGISTRY)
    p.add_argument("--base", type=Path, help="Carpeta de corridas A4 que contiene model.safetensors")
    p.add_argument("--reporte", type=Path, help="Archivo JSON NUEVO; nunca sobrescribe.")
    p.add_argument("--permitir-faltantes", action="store_true",
                   help="Para inventario en CI: no falla solo por pesos ausentes.")
    args = p.parse_args(argv)
    try:
        audit = verificar_registro(args.registro, args.base)
        output = json.dumps(audit, indent=2, ensure_ascii=False) + "\n"
        if args.reporte:
            args.reporte.parent.mkdir(parents=True, exist_ok=True)
            with args.reporte.open("x", encoding="utf-8") as handle:
                handle.write(output)
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        p.exit(2, f"Registro inválido: {exc}\n")
    print(output, end="")
    if audit["ready"] or (
        args.permitir_faltantes
        and audit["verified"] + audit["missing"] == audit["total"]
    ):
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
