"""Ejecuta la descarga verificable en EC2 mediante los objetivos Make."""
import argparse
import json
from pathlib import Path
from image_builder_ops import aws

parser = argparse.ArgumentParser()
parser.add_argument('action', choices=['send', 'result'])
parser.add_argument('--work', type=Path, required=True)
args = parser.parse_args()
instance = json.loads((args.work / 'outputs.json').read_text())['instance_id']['value']
record = args.work / 'qlora-base-command.json'
if args.action == 'send':
    source = Path(__file__).with_name('qlora_base_ec2.py').read_text()
    command = "sudo -u ubuntu /opt/citas/tools/bin/python - <<'QLORA_BASE'\n" + source + '\nQLORA_BASE'
    result = aws('ssm', 'send-command', '--instance-ids', instance, '--document-name', 'AWS-RunShellScript', '--parameters', json.dumps({'commands': [command], 'executionTimeout': ['3600']}))
    record.write_text(json.dumps({'command_id': result['Command']['CommandId']}))
    print('Descarga enviada a EC2')
else:
    result = aws('ssm', 'get-command-invocation', '--instance-id', instance, '--command-id', json.loads(record.read_text())['command_id'])
    (args.work / 'qlora-base-result.json').write_text(json.dumps(result, indent=2))
    print(json.dumps({key: result[key] for key in ['Status', 'StandardOutputContent', 'StandardErrorContent']}, indent=2))
    if result['Status'] in ['Failed', 'Cancelled', 'TimedOut']:
        raise SystemExit(1)
