#!/usr/bin/env bash
set -euo pipefail
: "${RELEASE_COMMIT:?Falta revisión}"
[[ "$RELEASE_COMMIT" =~ ^[0-9a-f]{40}$ ]]
cd /opt/citas/microproyecto-local-citation
git diff --exit-code HEAD -- Dockerfile Dockerfile.ms src packages requirements config scripts/iniciar_ciencia.py >/dev/null
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
case "${RELEASE_KIND:-all}" in
  api) export RELEASE_KINDS=api ;;
  all) export RELEASE_KINDS='api ms' ;;
  *) exit 1 ;;
esac
for kind in $RELEASE_KINDS; do
  file=Dockerfile
  [[ "$kind" == ms ]] && file=Dockerfile.ms
  tag="$registry/citas-api:release-$kind-$RELEASE_COMMIT"
  if ! docker build --platform linux/amd64 -f "$file" --build-arg MS_CODE_SHA="$RELEASE_COMMIT" -t "$tag" . > /opt/citas/release-build.log 2>&1; then
    tail -n 35 /opt/citas/release-build.log
    exit 1
  fi
  docker push "$tag" >> /opt/citas/release-build.log 2>&1
done
/opt/citas/tools/bin/python - <<'PY'
import boto3,json,os
revision=os.environ['RELEASE_COMMIT']
e=boto3.client('ecr',region_name='us-east-1')
images={}
for kind in os.environ['RELEASE_KINDS'].split():
 tag=f'release-{kind}-{revision}'
 digest=e.describe_images(repositoryName='citas-api',imageIds=[{'imageTag':tag}])['imageDetails'][0]['imageDigest']
 images[kind]={'commit':revision,'tag':tag,'uri':'646941583111.dkr.ecr.us-east-1.amazonaws.com/citas-api@'+digest}
print('RELEASE_IMAGES='+json.dumps({'commit':revision,'images':images}))
PY
