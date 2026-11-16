r"""Localiza los pesos A4 originales por bytes SHA-256, sin red ni Gold.

Uso (Windows PowerShell, desde el repo):
  uv run python -m scripts.locate_a4_weights --roots "$env:USERPROFILE\Documents" "D:\" --show-paths

Por defecto no modifica ningún archivo, no sube datos, no descarga pesos
ni invoca servicios de red. La búsqueda puede leer archivos grandes; acota
la carpeta y usa --max-candidates para establecer presupuesto explícito.

Códigos de salida: 0 cuatro modelos encontrados; 1 hallazgo parcial/ausente;
2 entrada inválida, directorio no seguro o error de lectura.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any

from src.app.checkpoint_gate import REGISTRY, REPO, verificar_registro

REQUIRED = frozenset(("scibert_A_42", "scibert_B_42",
                      "specter_A_42", "specter_B_42"))
VALID_SUFFIXES = frozenset((".safetensors",))
DEFAULT_PRUNE = frozenset((".git", ".venv", "node_modules", "__pycache__", ".tox"))


def sha256_file(path: Path) -> str:
    checksum = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            checksum.update(block)
    return checksum.hexdigest()


def locate(roots: list[Path], *, registry: Path = REGISTRY, repo: Path = REPO,
           max_depth: int = 12, max_candidates: int = 300,
           show_paths: bool = False) -> dict[str, Any]:
    """Inspecciona sólo archivos safetensors sin seguir symlinks.

    Compara SHA bytes-a-bytes con los manifiestos versionados, no con el nombre
    del archivo. No se concede certificación a coincidencias por nombre.
    """
    if not roots or not 0 <= max_depth <= 30 or not 1 <= max_candidates <= 100000:
        raise ValueError("Indique raíces locales y límites válidos.")
    if not registry.is_file() or registry.is_symlink():
        raise ValueError("Registro A4 ausente o es symlink.")
    if repo.is_symlink():
        raise ValueError("Repo no puede ser symlink.")
    # Verificar coherencia entre registro y manifiestos aun SIN tener los pesos.
    historical = verificar_registro(
        registro=registry,
        base=repo / "artifacts" / "no-a4-pesos-en-esta-auditoria",
        repo=repo,
    )
    models = historical["models"]
    if len(models) != 4 or {row["id"] for row in models} != REQUIRED:
        raise ValueError("Se exigen exactamente cuatro registros históricos A4.")
    expected = {row["expected_sha256"]: row["id"] for row in models}
    if len(expected) != 4:
        raise ValueError("Los cuatro pesos deben tener SHA independientes.")

    normalized: list[Path] = []
    for root in roots:
        root = Path(root).expanduser()
        if root.is_symlink() or not root.is_dir():
            raise ValueError("Cada raíz debe ser directorio local real, no symlink.")
        resolved = root.resolve()
        if resolved not in normalized:
            normalized.append(resolved)

    matches: dict[str, list[Path]] = {name: [] for name in sorted(REQUIRED)}
    files_seen = 0
    candidates_hashed = 0
    symlinks_skipped = 0
    hash_errors = 0
    stopped_by_limit = False
    for root in normalized:
        if stopped_by_limit:
            break
        for dirname, directories, filenames in os.walk(root, topdown=True, followlinks=False):
            current = Path(dirname)
            relative_depth = len(current.relative_to(root).parts)
            allowed_dirs = []
            for sub in sorted(directories):
                child = current / sub
                if child.is_symlink():
                    symlinks_skipped += 1
                elif sub not in DEFAULT_PRUNE and relative_depth < max_depth:
                    allowed_dirs.append(sub)
            directories[:] = allowed_dirs
            for filename in sorted(filenames):
                files_seen += 1
                if Path(filename).suffix.lower() not in VALID_SUFFIXES:
                    continue
                fullpath = current / filename
                if fullpath.is_symlink():
                    symlinks_skipped += 1
                    continue
                if not fullpath.is_file():
                    continue
                if candidates_hashed >= max_candidates:
                    stopped_by_limit = True
                    break
                candidates_hashed += 1
                try:
                    sha = sha256_file(fullpath)
                except OSError:
                    hash_errors += 1
                    continue
                found = expected.get(sha)
                if found:
                    matches[found].append(fullpath)
            if stopped_by_limit:
                break

    entries = []
    for model in models:
        name = model["id"]
        found_paths = sorted(set(matches[name]), key=lambda path: str(path).lower())
        info: dict[str, Any] = {
            "id": name, "status": "verified" if found_paths else "not_found",
            "expected_sha256": model["expected_sha256"],
            "number_of_matching_files": len(found_paths),
        }
        if show_paths:
            info["local_paths"] = [str(path) for path in found_paths]
        entries.append(info)

    verified = sum(item["status"] == "verified" for item in entries)
    return {
        "schema_version": 1,
        "type": "a4_local_checkpoint_discovery_without_gold",
        "roots_count": len(normalized),
        "files_seen": files_seen,
        "candidate_safetensors_hashed": candidates_hashed,
        "symlinks_skipped": symlinks_skipped,
        "file_read_errors": hash_errors,
        "search_complete": not stopped_by_limit and hash_errors == 0,
        "stopped_by_candidate_budget": stopped_by_limit,
        "verified_model_count": verified,
        "all_four_found": verified == 4,
        "ready_to_prepare_staging": verified == 4,
        "weights_loaded_in_torch": False,
        "human_gold_certified": False,
        "models": entries,
        "note": ("Coincidencia SHA no significa inferencia Torch ejecutada. "
                 "No publica pesos ni los mueve. Si faltan modelos, revisar "
                 "otros discos, backups, S3 o plan de reentrenamiento explícito."),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--roots", required=True, type=Path, nargs="+",
                        help="Directorios locales que desea examinar (sin acceso remoto).")
    parser.add_argument("--max-depth", type=int, default=12,
                        help="Profundidad máxima de subcarpetas, por defecto 12.")
    parser.add_argument("--max-candidates", type=int, default=300,
                        help="Máximo de archivos safetensors a hashear, por defecto 300.")
    parser.add_argument("--show-paths", action="store_true",
                        help="Incluir las rutas locales auténticas en salida/reportes.")
    parser.add_argument("--report", type=Path,
                        help="JSON NUEVO, nunca sobrescribir; preferir artifacts/ privado.")
    parser.add_argument("--allow-missing", action="store_true",
                        help="Salida cero con inventario incompleto; NO certifica pesos.")
    arguments = parser.parse_args(argv)
    try:
        result = locate(
            arguments.roots, max_depth=arguments.max_depth,
            max_candidates=arguments.max_candidates,
            show_paths=arguments.show_paths,
        )
        output = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
        if arguments.report:
            if arguments.report.is_symlink():
                raise ValueError("Reporte no puede ser un symlink.")
            arguments.report.parent.mkdir(parents=True, exist_ok=True)
            with arguments.report.open("x", encoding="utf-8") as handle:
                handle.write(output)
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        parser.exit(2, f"Descubrimiento de pesos A4 bloqueado: {exc}\n")
    print(output, end="")
    if result["file_read_errors"] or result["stopped_by_candidate_budget"]:
        return 1
    return 0 if result["all_four_found"] or arguments.allow_missing else 1


if __name__ == "__main__":
    raise SystemExit(main())
