"""Recuperación SEGURA de checkpoints A4 originales desde medio LOCAL.

No reentrena, fabrica ni descarga pesos. Requiere SHA-256 igual al registrado
en la evidencia histórica, y --apply explícito para realizar una copia.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import tempfile
from pathlib import Path

from src.app.checkpoint_gate import REPO, REGISTRY, verificar_registro, _relative
from src.app.classifier_runtime import sha256_file


def recuperar(source: Path, destination: Path, *, registry: Path = REGISTRY,
              repo: Path = REPO, apply: bool = False) -> dict:
    if not source.is_dir() or source.is_symlink():
        raise ValueError("La fuente debe ser una carpeta local auténtica, no un symlink.")
    entries = json.loads(registry.read_text(encoding="utf-8"))
    # Gate central: coteja SHA histórico vs archivo y vs manifiesto original.
    report = verificar_registro(registry, base=source, repo=repo)
    if not report["ready"]:
        raise ValueError(
            "No se localizaron los cuatro checkpoints históricos íntegros: "
            + ", ".join(f"{x['id']}={x['status']}" for x in report["models"])
        )
    if destination.is_symlink():
        raise ValueError("Directorio de destino no puede ser enlace simbólico.")
    out = []
    for item in entries["models"]:
        rel = _relative(item["checkpoint"])
        origin = source / rel
        target = destination / rel
        if not origin.is_file() or origin.is_symlink():
            raise ValueError("Archivo fuente no regular.")
        if target.is_symlink():
            raise ValueError("Archivo destino no puede ser symlink.")
        if target.exists():
            if not target.is_file() or sha256_file(target) != item["expected_sha256"]:
                raise ValueError(f"El destino {item['id']} existe con bytes distintos; no sobrescribir.")
            status = "ya_verificado"
        else:
            status = "copiado" if apply else "listo_para_copiar"
            if apply:
                target.parent.mkdir(parents=True, exist_ok=True)
                if target.parent.is_symlink():
                    raise ValueError("Carpeta destino es symlink.")
                fd, tmp = tempfile.mkstemp(prefix=".a4-", dir=target.parent)
                try:
                    with os.fdopen(fd, "wb") as dst, origin.open("rb") as src:
                        shutil.copyfileobj(src, dst, 1024 * 1024)
                        dst.flush()
                        os.fsync(dst.fileno())
                    if sha256_file(Path(tmp)) != item["expected_sha256"]:
                        raise ValueError("Los bytes cambiaron durante la copia.")
                    os.link(tmp, target)  # atómico y falla si destino apareció
                finally:
                    Path(tmp).unlink(missing_ok=True)
        out.append({"id": item["id"], "estado": status,
                    "sha256": item["expected_sha256"]})
    return {"origen": "checkpoint_original_verificado_localmente",
            "modo": "aplicado" if apply else "simulacion_sin_escritura",
            "gold_humano": False, "checkpoints": out}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", type=Path, required=True,
                   help="Directorio corridas original del equipo de entrenamiento")
    p.add_argument("--destination", type=Path,
                   default=REPO / "proyecto_de_grado/artifacts/clasificacion_a4/corridas")
    p.add_argument("--apply", action="store_true", help="Copia los archivos SHA-verificados")
    args = p.parse_args(argv)
    try:
        result = recuperar(args.source, args.destination, apply=args.apply)
    except (ValueError, OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
        p.exit(2, f"Recuperación bloqueada: {exc}\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
