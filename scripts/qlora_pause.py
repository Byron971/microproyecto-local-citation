"""Suspende solo la descarga QLoRA lanzada por este repositorio."""
import json
from pathlib import Path
from image_builder_ops import aws
work = Path('artifacts/image_builder')
record = work / 'qlora-base-command.json'
if record.exists():
    command_id = json.loads(record.read_text())['command_id']
    instance = json.loads((work / 'outputs.json').read_text())['instance_id']['value']
    result = aws('ssm', 'get-command-invocation', '--instance-id', instance, '--command-id', command_id)
    print('Descarga QLoRA: ' + result['Status'])
    if result['Status'] in ['Pending', 'InProgress', 'Delayed']:
        aws('ssm', 'cancel-command', '--command-id', command_id, '--instance-ids', instance)
        print('Cancelación solicitada; archivos descargados conservados.')
