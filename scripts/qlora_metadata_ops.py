"""Consulta acotada de metadatos del adaptador recuperado, mediante Makefile."""
import argparse
import json
from pathlib import Path
from image_builder_ops import aws

p=argparse.ArgumentParser()
p.add_argument('action',choices=['send','result'])
p.add_argument('--work',type=Path,required=True)
a=p.parse_args()
instance=json.loads((a.work/'outputs.json').read_text())['instance_id']['value']
if a.action=='send':
    command="""sudo -u ubuntu python3 - <<'METADATA'
import json,re
from pathlib import Path
r=json.loads(Path('/opt/citas/qlora/recovered-adapter.json').read_text())
root=Path(r['adapter_root'])
s=(root/'README.md').read_text()
versions=[line.strip() for line in s.splitlines() if any(word in line.lower() for word in ['transformers ', 'peft ', 'pytorch ', 'accelerate ', 'bitsandbytes ', 'base_model:', 'library_name:'])]
print(json.dumps({'readme_metadata':versions[:25]},indent=2))
METADATA"""
    result=aws('ssm','send-command','--instance-ids',instance,'--document-name','AWS-RunShellScript','--parameters',json.dumps({'commands':[command]}))
    (a.work/'qlora-metadata-command.json').write_text(json.dumps({'command_id':result['Command']['CommandId']}))
    print('Consulta de metadatos enviada')
else:
    command_id=json.loads((a.work/'qlora-metadata-command.json').read_text())['command_id']
    r=aws('ssm','get-command-invocation','--instance-id',instance,'--command-id',command_id)
    print(json.dumps({key:r[key] for key in ['Status','StandardOutputContent','StandardErrorContent']},indent=2))
