"""Entrada privada por terminal; Terraform escribe SecureString sin guardar el valor."""
import getpass
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

if not sys.stdin.isatty():
    raise SystemExit('Ejecuta este comando en una terminal interactiva para ocultar la clave.')
key = getpass.getpass('Clave de OpenAI (oculta; no se guardará en archivos): ')
if not key.strip():
    raise SystemExit('Clave vacía; no se hizo ningún cambio.')
env = dict(os.environ, TF_VAR_openai_api_key=key)
for name in ['TF_LOG', 'TF_LOG_PATH', 'TF_LOG_PROVIDER', 'TF_LOG_CORE']:
    env.pop(name, None)
tf = os.environ.get('TERRAFORM', 'terraform')
base = [tf, '-chdir=terraform/commercial_secret']
subprocess.run(base + ['init', '-input=false', '-plugin-dir=../.terraform/providers'], env=env, check=True)
previous = subprocess.run(base + ['output', '-json'], env=env, capture_output=True, text=True)
outputs = json.loads(previous.stdout) if previous.returncode == 0 else {}
env['TF_VAR_key_version'] = str(outputs.get('key_version', {}).get('value', 0) + 1)
with tempfile.TemporaryDirectory(prefix='citas-commercial-') as directory:
    plan = str(Path(directory) / 'secret.tfplan')
    subprocess.run(base + ['plan', '-input=false', '-out=' + plan], env=env, check=True)
    result = subprocess.check_output(base + ['show', '-json', plan], env=env)
    for change in json.loads(result).get('resource_changes', []):
        if change['mode'] == 'data' or change['change']['actions'] == ['no-op']:
            continue
        if change['address'] != 'aws_ssm_parameter.openai' or change['change']['actions'] not in [['create'], ['update']]:
            raise SystemExit('Plan fuera de alcance; no se aplicó.')
    subprocess.run(base + ['apply', '-input=false', plan], env=env, check=True)
print('Secreto configurado. La aplicación continúa deshabilitada hasta su despliegue.')
