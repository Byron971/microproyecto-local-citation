"""Publicación remota de imágenes; sin cambios ECS ni modelos."""
import argparse,json,re
from pathlib import Path
from image_builder_ops import aws
p=argparse.ArgumentParser()
p.add_argument('action',choices=['send','result'])
p.add_argument('--commit')
a=p.parse_args()
w=Path('artifacts/image_builder')
i=json.loads((w/'outputs.json').read_text())['instance_id']['value']
r=w/'release-command.json'
if a.action=='send':
 assert a.commit and re.fullmatch('[0-9a-f]{40}',a.commit)
 command='sudo -u ubuntu env RELEASE_COMMIT='+a.commit+" bash <<'RELEASE_BUILD'\n"+Path('scripts/release_build_ec2.sh').read_text()+'\nRELEASE_BUILD'
 response=aws('ssm','send-command','--instance-ids',i,'--document-name','AWS-RunShellScript','--parameters',json.dumps({'commands':[command],'executionTimeout':['3600']}))
 r.write_text(json.dumps({'command_id':response['Command']['CommandId']}))
 print('Construcción y publicación enviadas a EC2')
else:
 response=aws('ssm','get-command-invocation','--instance-id',i,'--command-id',json.loads(r.read_text())['command_id'])
 (w/'release-result.json').write_text(json.dumps(response,indent=2))
 print(json.dumps({k:response[k] for k in ['Status','StandardOutputContent','StandardErrorContent']},indent=2))
 for line in response['StandardOutputContent'].splitlines():
  if line.startswith('RELEASE_IMAGES='):
   (w/'release-images.json').write_text(json.dumps(json.loads(line.removeprefix('RELEASE_IMAGES=')),indent=2))
 if response['Status'] in ['Failed','Cancelled','TimedOut']:raise SystemExit(1)
