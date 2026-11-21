"""Preflight reproducible de checkpoints M/S (sin importar torch ni tocar Gold).

Uso desde la raiz del repositorio:
    python scripts/verificar_artefactos_ms.py

Salida JSON; codigo 0 solo si ambos pesos y manifiestos locales son correctos.
No descarga ni copia modelos. Evita publicar rutas absolutas y contenidos privados.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def sha256_archivo(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verificar(root: Path, manifest_path: Path) -> dict:
    root = root.resolve()
    errors: list[str] = []
    outputs: list[dict] = []
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {"listo": False, "errores": ["No se pudo leer el manifiesto de distribucion"], "checkpoints": []}
    checks = manifest.get("checkpoints")
    if not isinstance(checks, list) or {x.get("pista") for x in checks if isinstance(x, dict)} != {"M", "S"} or len(checks) != 2:
        return {"listo": False, "errores": ["Se requieren exactamente los checkpoints M y S"], "checkpoints": []}
    for item in checks:
        pista = item["pista"]
        record = {"pista": pista, "pesos_presentes": False, "tamano_correcto": False,
                  "sha256_correcto": False, "manifiesto_entrenamiento_valido": False}
        outputs.append(record)
        rel = item.get("archivo")
        if not isinstance(rel, str) or not rel:
            errors.append(f"{pista}: ruta de checkpoint invalida")
            continue
        path = root / rel
        # Las rutas no pueden apuntar fuera del repositorio.
        if path.is_symlink() or not path.resolve().is_relative_to(root):
            errors.append(f"{pista}: ruta insegura")
            continue
        if not path.is_file():
            errors.append(f"{pista}: pesos ausentes")
            continue
        record["pesos_presentes"] = True
        expected_size = item.get("bytes")
        record["tamano_correcto"] = type(expected_size) is int and expected_size > 0 and path.stat().st_size == expected_size
        if not record["tamano_correcto"]:
            errors.append(f"{pista}: tamano distinto del manifiesto")
        expected_sha = item.get("sha256")
        if not isinstance(expected_sha, str) or len(expected_sha) != 64:
            errors.append(f"{pista}: SHA256 de distribucion invalido")
            continue
        record["sha256_correcto"] = sha256_archivo(path) == expected_sha.lower()
        if not record["sha256_correcto"]:
            errors.append(f"{pista}: SHA256 distinto del manifiesto")
        training_path = path.parent / "manifiesto_entrenamiento.json"
        try:
            if training_path.is_symlink() or not training_path.resolve().is_relative_to(root):
                raise ValueError("ruta insegura")
            training = json.loads(training_path.read_text(encoding="utf-8-sig"))
            valid = (
                training.get("sha256_model_safetensors") == expected_sha.lower()
                and training.get("scibert_snapshot") == manifest.get("revision_modelo_base")
                and isinstance(training.get("config"), dict)
                and training["config"].get("entrada") == "AB"
                and isinstance(training["config"].get("semilla"), int)
            )
        except (OSError, ValueError, UnicodeError, json.JSONDecodeError, AttributeError, TypeError):
            valid = False
        record["manifiesto_entrenamiento_valido"] = valid
        if not valid:
            errors.append(f"{pista}: manifiesto de entrenamiento ausente o inconsistente")
    return {"listo": not errors, "errores": errors, "checkpoints": outputs,
            "nota": "Verifica integridad local; no demuestra carga SciBERT ni inferencia."}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--manifest", type=Path, default=Path("docs/manifiesto_distribucion_ms.json"))
    args = parser.parse_args()
    manifest_path = args.manifest if args.manifest.is_absolute() else args.root / args.manifest
    result = verificar(args.root, manifest_path)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["listo"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
