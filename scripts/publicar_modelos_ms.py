"""Publicar o verificar la release privada sin subir Gold ni credenciales.

Requiere AWS CLI y permisos del perfil seleccionado. La verificación descarga
cada objeto a un directorio temporal y compara sus bytes con el SHA-256 esperado.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import tempfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("upload", "verify"))
    parser.add_argument("--manifest", type=Path, default=ROOT / "config/ms_release.json")
    parser.add_argument("--profile", required=True)
    parser.add_argument("--region", default="us-east-1")
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    bucket, prefix = manifest["bucket"], manifest["prefix"]
    if not re.fullmatch(r"[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]", bucket):
        raise ValueError("Bucket inválido")
    if not re.fullmatch(r"ms-scibert-[a-f0-9]{16}", manifest["release_id"]):
        raise ValueError("Identificador de release inválido")
    if prefix != f"releases/{manifest['release_id']}/":
        raise ValueError("Prefijo de release inválido")
    files = manifest["files"]
    if not isinstance(files, list) or not files:
        raise ValueError("Inventario vacío")
    seen = set()
    for item in files:
        path = PurePosixPath(item["path"])
        if (path.is_absolute() or ".." in path.parts or path.as_posix() != item["path"]
                or item["path"] in seen or path.name == "pred_gold.jsonl"):
            raise ValueError("Ruta no permitida o duplicada en inventario")
        seen.add(item["path"])
        if not (ROOT / item["path"]).resolve().is_relative_to(ROOT):
            raise ValueError("El archivo local sale del repositorio")
        if not re.fullmatch(r"[a-f0-9]{64}", item["sha256"]):
            raise ValueError("SHA-256 inválido")
        if type(item["bytes"]) is not int or item["bytes"] <= 0:
            raise ValueError("Tamaño inválido")
    payload = {k: v for k, v in manifest.items() if k not in ("bucket", "prefix")}
    identity = {k: v for k, v in payload.items() if k != "release_id"}
    digest = hashlib.sha256(json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    if manifest["release_id"] != f"ms-scibert-{digest[:16]}":
        raise ValueError("El identificador no coincide con el inventario")
    release_bytes = (json.dumps(payload, indent=2) + "\n").encode()
    base = ["aws", "--profile", args.profile, "--region", args.region,
            "--endpoint-url", f"https://s3.{args.region}.amazonaws.com"]

    def aws(*command: str) -> subprocess.CompletedProcess:
        return subprocess.run(base + list(command), check=True, capture_output=True)

    def existing(key: str) -> dict | None:
        result = subprocess.run(base + ["s3api", "head-object", "--bucket", bucket, "--key", key], capture_output=True)
        if result.returncode == 0:
            return json.loads(result.stdout)
        error = result.stderr.decode(errors="replace")
        if "404" in error or "Not Found" in error:
            return None
        raise RuntimeError("No se pudo consultar S3; comprobar red y permisos antes de reintentar")

    with tempfile.TemporaryDirectory(prefix="citas-modelos-") as temporary:
        target = Path(temporary) / "object"
        for item in files:
            key, source = prefix + item["path"], ROOT / item["path"]
            uri = f"s3://{bucket}/{key}"
            if args.mode == "upload":
                if source.stat().st_size != item["bytes"] or sha256(source) != item["sha256"]:
                    raise ValueError("El archivo local no coincide con el inventario")
                remote = existing(key)
                if remote is not None:
                    if remote["ContentLength"] != item["bytes"] or remote.get("Metadata", {}).get("sha256") != item["sha256"]:
                        raise ValueError("Objeto remoto diferente; no se reemplaza una release existente")
                else:
                    aws("s3", "cp", str(source), uri, "--sse", "AES256", "--metadata", "sha256=" + item["sha256"], "--only-show-errors")
            else:
                aws("s3", "cp", uri, str(target), "--only-show-errors")
                if target.stat().st_size != item["bytes"] or sha256(target) != item["sha256"]:
                    raise ValueError("Objeto descargado distinto del inventario")
            print(f"{args.mode} OK {item['path']}", flush=True)
        uri = f"s3://{bucket}/{prefix}release.json"
        if args.mode == "upload" and existing(prefix + "release.json") is None:
            target.write_bytes(release_bytes)
            aws("s3", "cp", str(target), uri, "--sse", "AES256", "--only-show-errors")
        if aws("s3", "cp", uri, "-", "--only-show-errors").stdout != release_bytes:
            raise ValueError("Manifiesto remoto diferente")
    print(f"RELEASE OK {uri}")


if __name__ == "__main__":
    main()
