"""Publica la traducción Docker V2 de ECR sin cambiar las capas ni configuración."""
import base64
import hashlib
import json
from pathlib import Path
import urllib.request

import boto3

session = boto3.Session(region_name='us-east-1')
assert session.client('sts').get_caller_identity()['Account'] == '646941583111'
ecr = session.client('ecr')
repo = 'citas-ms-serverless-t04'
registry = '646941583111.dkr.ecr.us-east-1.amazonaws.com'
report = json.loads(Path('/opt/citas/published-images.json').read_text())
kind = 'application/vnd.docker.distribution.manifest.v2+json'
image = report['images']['serverless']
original = ecr.batch_get_image(repositoryName=repo, imageIds=[{'imageTag': image['tag']}])['images'][0]
source = json.loads(original['imageManifest'])
auth = ecr.get_authorization_token()['authorizationData'][0]['authorizationToken']
request = urllib.request.Request('https://' + registry + '/v2/' + repo + '/manifests/' + image['tag'],
                                 headers={'Authorization': 'Basic ' + auth, 'Accept': kind})
with urllib.request.urlopen(request, timeout=60) as response:
    payload = response.read()
converted = json.loads(payload)
assert converted['mediaType'] == kind
assert converted['config']['digest'] == source['config']['digest']
assert [(x['digest'], x['size']) for x in converted['layers']] == [(x['digest'], x['size']) for x in source['layers']]
digest = 'sha256:' + hashlib.sha256(payload).hexdigest()
tag = image['tag'] + '-docker-v2'
try:
    existing = ecr.describe_images(repositoryName=repo, imageIds=[{'imageTag': tag}])['imageDetails'][0]
    assert existing['imageDigest'] == digest
except ecr.exceptions.ImageNotFoundException:
    stored = ecr.put_image(repositoryName=repo, imageTag=tag, imageManifest=payload.decode(), imageManifestMediaType=kind)
    assert stored['image']['imageId']['imageDigest'] == digest
check = ecr.batch_get_image(repositoryName=repo, imageIds=[{'imageDigest': digest}])['images'][0]
assert json.loads(check['imageManifest'])['mediaType'] == kind
image.update(source_oci_uri=image['uri'], uri=registry + '/' + repo + '@' + digest,
             tag=tag, manifest_type=kind, unchanged_layers_and_config=True)
Path('/opt/citas/published-images-compatible.json').write_text(json.dumps(report, indent=2))
print(json.dumps(report, indent=2))
