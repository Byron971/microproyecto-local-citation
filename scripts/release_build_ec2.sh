#!/usr/bin/env bash
set -euo pipefail
: "${RELEASE_COMMIT:?Falta revisión}"
[[ "$RELEASE_COMMIT" =~ ^[0-9a-f]{40}$ ]]
cd /opt/citas/microproyecto-local-citation
git diff --quiet && git diff --cached --quiet
git fetch origin feat/flujo-cientifico-ec2
git checkout --detach "$RELEASE_COMMIT"
registry=646941583111.dkr.ecr.us-east-1.amazonaws.com
export DOCKER_CONFIG=$(mktemp -d)
trap 'rm -rf "$DOCKER_CONFIG"' EXIT
/opt/citas/tools/bin/python - <<'PY' | docker login --username AWS --password-stdin 646941583111.dkr.ecr.us-east-1.amazonaws.com
import base64,boto3
value=boto3.client('ecr',region_name='us-east-1').get_authorization_token()['authorizationData'][0]['authorizationToken']
print(base64.b64decode(value).decode().split(':',1)[1])
PY
for kind in api ms; do
  file=Dockerfile
  [[ "$kind" == ms ]] && file=Dockerfile.ms
  tag="$registry/citas-api:release-$kind-$RELEASE_COMMIT"
  docker build --platform linux/amd64 -f "$file" --build-arg MS_CODE_SHA="$RELEASE_COMMIT" -t "$tag" .
  docker push "$tag"
done
/opt/citas/tools/bin/python - <<'PY'
import boto3,json,os
revision=os.environ['RELEASE_COMMIT']
e=boto3.client('ecr',region_name='us-east-1')
images={}
for kind in ['api','ms']:
 tag=f'release-{kind}-{revision}'
 digest=e.describe_images(repositoryName='citas-api',imageIds=[{'imageTag':tag}])['imageDetails'][0]['imageDigest']
 images[kind]={'tag':tag,'uri':'646941583111.dkr.ecr.us-east-1.amazonaws.com/citas-api@'+digest}
print('RELEASE_IMAGES='+json.dumps({'commit':revision,'images':images}))
PY
