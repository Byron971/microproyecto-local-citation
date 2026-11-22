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
    parser.add_argument("action", choices=["clone", "clone-result", "build", "build-result"])
    parser.add_argument("--work", required=True, type=Path)
    parser.add_argument("--commit")
    args = parser.parse_args()
    instance = json.loads((args.work / "outputs.json").read_text())["instance_id"]["value"]
    if args.action == "build":
        command = "sudo -u ubuntu bash /opt/citas/microproyecto-local-citation/scripts/build_publish_ec2.sh"
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
        name = "build" if args.action == "build-result" else "clone"
        saved = json.loads((args.work / f"{name}-command.json").read_text())
        result = aws("ssm", "get-command-invocation", "--instance-id", instance,
                     "--command-id", saved["command_id"])
        report = {key: result[key] for key in ("Status", "ResponseCode", "StandardOutputContent", "StandardErrorContent")}
        (args.work / f"{name}-result.json").write_text(json.dumps(report, indent=2))
        print(json.dumps(report, indent=2))
        if result["Status"] in ("Failed", "Cancelled", "TimedOut"):
            raise SystemExit(1)


if __name__ == "__main__":
    main()
