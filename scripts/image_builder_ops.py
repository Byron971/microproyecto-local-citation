"""Operaciones del constructor por SSM; invocar mediante Makefile."""
import argparse
import json
from pathlib import Path
import re
import subprocess


def aws(*args):
    return json.loads(subprocess.check_output(
        ["aws", "--region", "us-east-1", *args, "--output", "json"], text=True))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["clone", "clone-result", "build", "build-result", "inspect", "inspect-result", "models", "models-result", "publish-models", "publish-models-result", "compatible", "compatible-result", "qlora-auth", "qlora-auth-result", "qlora-check", "qlora-check-result", "qlora-browser", "qlora-browser-result", "qlora-files", "qlora-files-result", "qlora-audit", "qlora-audit-result"])
    parser.add_argument("--work", required=True, type=Path)
    parser.add_argument("--commit")
    args = parser.parse_args()
    instance = json.loads((args.work / "outputs.json").read_text())["instance_id"]["value"]
    if args.action == "qlora-audit":
        code = "AUDITOR_SOURCE = " + repr(Path("scripts/auditar_adapter_qlora.py").read_text()) + "\n" + Path("scripts/recover_adapter_ec2.py").read_text()
        command = "sudo -u ubuntu python3 - <<'QLORA_AUDIT_SCRIPT'\n" + code + "\nQLORA_AUDIT_SCRIPT"
        result = aws("ssm", "send-command", "--instance-ids", instance,
                     "--document-name", "AWS-RunShellScript", "--parameters", json.dumps({"commands": [command],"executionTimeout":["600"]}))
        (args.work / "qlora-audit-command.json").write_text(json.dumps({"command_id":result["Command"]["CommandId"]}))
        print("Recuperación y auditoría del adaptador enviadas")
    elif args.action == "qlora-files":
        command = """sudo -u ubuntu python3 - <<'QLORA_FILES'
import json
from pathlib import Path
root=Path('/home/ubuntu/Downloads/qlora')
print(json.dumps({'files':[{'path':str(p.relative_to(root)), 'bytes':p.stat().st_size} for p in sorted(root.rglob('*')) if p.is_file()][:100]},indent=2))
QLORA_FILES"""
        result = aws("ssm", "send-command", "--instance-ids", instance,
                     "--document-name", "AWS-RunShellScript", "--parameters", json.dumps({"commands": [command]}))
        (args.work / "qlora-files-command.json").write_text(json.dumps({"command_id":result["Command"]["CommandId"]}))
        print("Consulta de descargas enviada")
    elif args.action == "qlora-browser":
        command = "bash <<'QLORA_BROWSER_SCRIPT'\n" + Path("scripts/qlora_browser_ec2.sh").read_text() + "\nQLORA_BROWSER_SCRIPT"
        result = aws("ssm", "send-command", "--instance-ids", instance,
                     "--document-name", "AWS-RunShellScript", "--parameters", json.dumps({"commands": [command],"executionTimeout":["1200"]}))
        (args.work / "qlora-browser-command.json").write_text(json.dumps({"command_id":result["Command"]["CommandId"]}))
        print("Preparación del navegador EC2 enviada")
    elif args.action == "qlora-check":
        command = """sudo -u ubuntu python3 - <<'QLORA_CHECK'
import configparser,json
from pathlib import Path
p=Path('/home/ubuntu/.config/rclone/uniandes.conf')
c=configparser.ConfigParser(interpolation=None)
if p.exists():c.read(p)
configured=c.has_section('uniandes')
token=json.loads(c.get('uniandes','token',fallback='{}')) if configured else {}
print(json.dumps({'authorized':bool(token.get('access_token')), 'drive_configured':bool(c.get('uniandes','drive_id',fallback='')) if configured else False, 'private_config_permissions':oct(p.stat().st_mode & 0o777) if p.exists() else None}))
QLORA_CHECK"""
        result = aws("ssm", "send-command", "--instance-ids", instance,
                     "--document-name", "AWS-RunShellScript", "--parameters", json.dumps({"commands": [command]}))
        (args.work / "qlora-check-command.json").write_text(json.dumps({"command_id":result["Command"]["CommandId"]}))
        print("Comprobación privada enviada")
    elif args.action == "qlora-auth":
        command = "bash <<'QLORA_AUTH_SCRIPT'\n" + Path("scripts/qlora_auth_ec2.sh").read_text() + "\nQLORA_AUTH_SCRIPT"
        result = aws("ssm", "send-command", "--instance-ids", instance,
                     "--document-name", "AWS-RunShellScript", "--parameters", json.dumps({"commands": [command]}))
        (args.work / "qlora-auth-command.json").write_text(json.dumps({"command_id":result["Command"]["CommandId"]}))
        print("Autorización remota preparada; consultar resultado")
    elif args.action == "compatible":
        command = "sudo -u ubuntu /opt/citas/tools/bin/python - <<'COMPAT_SCRIPT'\n" + Path("scripts/compatible_image_ec2.py").read_text() + "\nCOMPAT_SCRIPT"
        result = aws("ssm", "send-command", "--instance-ids", instance,
                     "--document-name", "AWS-RunShellScript", "--parameters", json.dumps({"commands": [command]}))
        (args.work / "compatible-command.json").write_text(json.dumps({"command_id": result["Command"]["CommandId"]}))
        print("Publicación Docker V2 enviada")
    elif args.action == "publish-models":
        command = "sudo -u ubuntu bash <<'PUBLISH_MODELS_SCRIPT'\n" + Path("scripts/publish_models_ec2.sh").read_text() + "\nPUBLISH_MODELS_SCRIPT"
        result = aws("ssm", "send-command", "--instance-ids", instance,
                     "--document-name", "AWS-RunShellScript", "--parameters",
                     json.dumps({"commands": [command], "executionTimeout": ["1800"]}))
        (args.work / "publish-models-command.json").write_text(json.dumps({"command_id":result["Command"]["CommandId"]}))
        print("Publicación del paquete enviada:",result["Command"]["CommandId"])
    elif args.action == "models":
        command = "sudo -u ubuntu env -u AWS_PROFILE -u AWS_ACCESS_KEY_ID -u AWS_SECRET_ACCESS_KEY -u AWS_SESSION_TOKEN /opt/citas/tools/bin/python - <<'MODELS_SCRIPT'\n" + Path("scripts/prepare_models_ec2.py").read_text() + "\nMODELS_SCRIPT"
        result = aws("ssm", "send-command", "--instance-ids", instance,
                     "--document-name", "AWS-RunShellScript", "--parameters",
                     json.dumps({"commands": [command], "executionTimeout": ["1800"]}))
        (args.work / "models-command.json").write_text(json.dumps({"command_id": result["Command"]["CommandId"]}))
        print("Preparación de modelos enviada:", result["Command"]["CommandId"])
    elif args.action == "inspect":
        command = """sudo -u ubuntu /opt/citas/tools/bin/python - <<'PYREMOTE'
import boto3,json,subprocess
repo='citas-ms-serverless-t04'
e=boto3.client('ecr',region_name='us-east-1')
for family,local in [('ms','citas-science'),('serverless','citas-serverless-ms')]:
 commit=subprocess.check_output(['git','-C','/opt/citas/microproyecto-local-citation','rev-parse','HEAD'],text=True).strip()
 info=json.loads(subprocess.check_output(['docker','image','inspect',local+':'+commit]))[0]
 tag='t04-'+family+'-'+commit
 remote=e.batch_get_image(repositoryName=repo,imageIds=[{'imageTag':tag}])
 print(json.dumps({'family':family,'Id':info['Id'],'RepoDigests':info.get('RepoDigests'),'remote':remote}))
PYREMOTE"""
        result = aws("ssm", "send-command", "--instance-ids", instance,
                     "--document-name", "AWS-RunShellScript", "--parameters", json.dumps({"commands": [command]}))
        (args.work / "inspect-command.json").write_text(json.dumps({"command_id":result["Command"]["CommandId"]}))
        print("Diagnóstico enviado")
    elif args.action == "build":
        command = "sudo -u ubuntu bash <<'BUILD_SCRIPT'\n" + Path("scripts/build_publish_ec2.sh").read_text() + "\nBUILD_SCRIPT"
        result = aws("ssm", "send-command", "--instance-ids", instance,
                     "--document-name", "AWS-RunShellScript", "--parameters",
                     json.dumps({"commands": [command], "executionTimeout": ["3600"]}))
        command_id = result["Command"]["CommandId"]
        (args.work / "build-command.json").write_text(json.dumps({"command_id": command_id}))
        print("Construcción y publicación enviadas:", command_id)
    elif args.action == "clone":
        if not re.fullmatch(r"[a-f0-9]{40}", args.commit or ""):
            raise ValueError("Se requiere un commit completo")
        command = """set -eu
sudo -u ubuntu bash <<'BUILDER'
set -eu
cd /opt/citas
if [ ! -e microproyecto-local-citation ]; then
  git clone --single-branch --branch feat/flujo-cientifico-ec2 https://github.com/Byron971/microproyecto-local-citation.git
fi
cd microproyecto-local-citation
test "$(git remote get-url origin)" = https://github.com/Byron971/microproyecto-local-citation.git
test -z "$(git status --porcelain)"
git fetch origin feat/flujo-cientifico-ec2
git checkout --detach EXPECTED_COMMIT
test "$(git rev-parse HEAD)" = EXPECTED_COMMIT
test -f Dockerfile.ms
test -f Dockerfile.serverless-ms
printf 'Commit: '; git rev-parse HEAD
printf 'Estado: '; test -z "$(git status --porcelain)" && echo limpio
printf 'Arquitectura: '; uname -m
printf 'Docker: '; docker --version
df -h /opt/citas
BUILDER
""".replace("EXPECTED_COMMIT", args.commit)
        result = aws("ssm", "send-command", "--instance-ids", instance,
                     "--document-name", "AWS-RunShellScript", "--parameters",
                     json.dumps({"commands": [command], "executionTimeout": ["600"]}))
        command_id = result["Command"]["CommandId"]
        (args.work / "clone-command.json").write_text(json.dumps({"command_id": command_id, "commit": args.commit}))
        print("Clonación enviada:", command_id)
    else:
        name = args.action.removesuffix("-result")
        saved = json.loads((args.work / f"{name}-command.json").read_text())
        result = aws("ssm", "get-command-invocation", "--instance-id", instance,
                     "--command-id", saved["command_id"])
        report = {key: result[key] for key in ("Status", "ResponseCode", "StandardOutputContent", "StandardErrorContent")}
        (args.work / f"{name}-result.json").write_text(json.dumps(report, indent=2))
        if name == "compatible" and result["Status"] == "Success":
            images = json.loads(result["StandardOutputContent"])
            if not images["images"]["serverless"]["unchanged_layers_and_config"]:
                raise ValueError("Conversión no verificada")
            (args.work / "published-images.json").write_text(json.dumps(images, indent=2))
        print(json.dumps(report, indent=2))
        if result["Status"] in ("Failed", "Cancelled", "TimedOut"):
            raise SystemExit(1)


if __name__ == "__main__":
    main()
