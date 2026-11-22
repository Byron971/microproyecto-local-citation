"""Descarga una release fijada usando el rol AWS y valida cada byte antes de servir."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath


def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def preparar(client, manifest, root):
    root = root.resolve()
    expected = {k: v for k, v in manifest.items() if k not in ("bucket", "prefix")}
    remote = json.loads(client.get_object(Bucket=manifest["bucket"], Key=manifest["prefix"] + "release.json")["Body"].read())
    if remote != expected:
        raise RuntimeError("La release remota no coincide con el inventario fijado en la imagen")
    for item in manifest["files"]:
        relative = PurePosixPath(item["path"])
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("Ruta insegura en inventario")
        target = (root / str(relative)).resolve()
        if not target.is_relative_to(root):
            raise ValueError("Ruta fuera del volumen")
        if target.is_file() and target.stat().st_size == item["bytes"] and sha256(target) == item["sha256"]:
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        partial = target.with_name(target.name + ".partial")
        print("Descargando:", item["path"], flush=True)
        try:
            client.download_file(manifest["bucket"], manifest["prefix"] + item["path"], str(partial))
            if partial.stat().st_size != item["bytes"] or sha256(partial) != item["sha256"]:
                raise RuntimeError("Archivo descargado no coincide con SHA256/tamaño: " + item["path"])
            partial.replace(target)
        finally:
            partial.unlink(missing_ok=True)
        print("Verificado:", item["path"], flush=True)


def main():
    import boto3
    from botocore.config import Config
    manifest = json.loads(Path("/app/config/ms_release.json").read_text())
    root = Path(os.environ.get("MS_MODEL_ROOT", "/models"))
    client = boto3.client("s3", region_name=os.environ.get("AWS_REGION", "us-east-1"),
                          config=Config(retries={"mode": "standard", "max_attempts": 10}))
    preparar(client, manifest, root)
    if os.environ.get('MS_ENABLE_GLOBAL_SEARCH') == '1':
        search_manifest = json.loads(Path(os.environ.get(
            'MS_SEARCH_MANIFEST', '/app/config/search_release.json')).read_text())
        preparar(client, search_manifest, root)
    os.environ["HF_HOME"] = str(root / "artifacts/huggingface")
    os.environ["MS_ARTIFACTS_DIR"] = str(root / "proyecto_de_grado/artifacts/experimentos_10")
    os.environ["MS_RELEASE_ID"] = manifest["release_id"]
    os.environ['MS_SEARCH_DIR'] = str(root / 'artifacts/scientific_search')
    os.execvp("python", ["python", "-m", "uvicorn", "src.app.science_main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"])


if __name__ == "__main__":
    main()
