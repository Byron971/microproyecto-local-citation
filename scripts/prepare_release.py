"""Fija imágenes publicadas y conserva punteros para reversión Terraform."""
import json
from pathlib import Path
from image_builder_ops import aws
root=Path('artifacts')
images=json.loads((root/'image_builder/release-images.json').read_text())
for image in images['images'].values():
 actual=aws('ecr','describe-images','--repository-name','citas-api','--image-ids','imageTag='+image['tag'])['imageDetails'][0]['imageDigest']
 assert image['uri'].endswith('@'+actual), 'Digest publicado diferente'
values={
 'release_api_image_tag':images['images']['api']['tag'],
 'release_science_image_uri':images['images']['ms']['uri'],
}
rollback={
 'release_api_image_tag':aws('ssm','get-parameter','--name','/citas-api/api/image_tag')['Parameter']['Value'],
 'release_science_image_uri':aws('ssm','get-parameter','--name','/citas-api/science/image_uri')['Parameter']['Value'],
}
(root/'release.tfvars.json').write_text(json.dumps(values,indent=2))
backup=root/'release-rollback.tfvars.json'
context=root/'release-context.json'
previous=json.loads(context.read_text()) if context.exists() else {}
if not backup.exists() or (previous and previous.get('commit')!=images['commit']):
 backup.write_text(json.dumps(rollback,indent=2))
context.write_text(json.dumps({'commit':images['commit']},indent=2))
print(json.dumps(values,indent=2))
