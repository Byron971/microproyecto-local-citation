#!/usr/bin/env python3
"""Elimina únicamente los recursos base de make init, tras revisar el estado remoto."""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


def aws(*args):
    command = ["aws", "--region", os.environ.get("AWS_REGION", "us-east-1")]
    if os.environ.get("AWS_PROFILE"):
        command += ["--profile", os.environ["AWS_PROFILE"]]
    result = subprocess.run(command + list(args) + ["--output", "json"],
                            check=True, capture_output=True, text=True)
    return json.loads(result.stdout) if result.stdout.strip() else {}


def destroy(bucket, repository, state_key):
    account = aws("sts", "get-caller-identity")["Account"]
    owner = ["--expected-bucket-owner", account]
    # Revisar todo antes de la primera eliminación, incluidas claves antiguas.
    versions = aws("s3api", "list-object-versions", "--bucket", bucket, *owner)
    objects = versions.get("Versions", []) + versions.get("DeleteMarkers", [])
    allowed = {state_key}
    if any(item["Key"] not in allowed for item in objects):
        raise ValueError("El bucket contiene otros archivos o bloqueos. No se elimina: usa un bucket exclusivo y espera a que termine Terraform.")
    if any(item.get("IsLatest") for item in versions.get("DeleteMarkers", [])):
        raise ValueError("Un estado remoto fue borrado. Recupéralo y valida sus recursos antes de eliminar el bucket.")
    current = aws("s3api", "list-objects-v2", "--bucket", bucket, *owner)
    for item in current.get("Contents", []):
        if item["Key"] not in allowed:
            raise ValueError("El bucket contiene otros archivos o bloqueos. No se elimina.")
        with tempfile.TemporaryDirectory() as temporary:
            target = str(Path(temporary) / "state.json")
            aws("s3api", "get-object", "--bucket", bucket, "--key", item["Key"], *owner, target)
            state = json.loads(Path(target).read_text())
        if not isinstance(state, dict) or not isinstance(state.get("resources"), list) or "version" not in state:
            raise ValueError("No se pudo validar el estado remoto. No se elimina.")
        if any(resource.get("mode") != "data" and resource.get("instances")
               for resource in state["resources"]):
            raise ValueError("Quedan recursos en Terraform. Ejecuta primero terraform destroy en el stack del proyecto.")
    print(f"Cuenta: {account}. Eliminando ECR {repository} y bucket {bucket}.", flush=True)
    try:
        aws("ecr", "delete-repository", "--repository-name", repository, "--force")
    except subprocess.CalledProcessError as error:
        if "RepositoryNotFoundException" not in (error.stderr or ""):
            raise
    for offset in range(0, len(objects), 1000):
        batch = [{"Key": item["Key"], "VersionId": item["VersionId"]}
                 for item in objects[offset:offset + 1000]]
        result = aws("s3api", "delete-objects", "--bucket", bucket, *owner,
                     "--delete", json.dumps({"Objects": batch, "Quiet": True}))
        if result.get("Errors"):
            raise ValueError("S3 no pudo borrar algunas versiones. Revisa los permisos antes de continuar.")
    aws("s3api", "delete-bucket", "--bucket", bucket, *owner)
    print("Recursos base eliminados. El tag SSM de make push se elimina por separado.")


if __name__ == "__main__":
    try:
        destroy(*sys.argv[1:])
    except (ValueError, KeyError, OSError, subprocess.CalledProcessError) as error:
        detail = error.stderr if isinstance(error, subprocess.CalledProcessError) else str(error)
        print(f"No se completó la eliminación: {detail}", file=sys.stderr)
        sys.exit(1)
