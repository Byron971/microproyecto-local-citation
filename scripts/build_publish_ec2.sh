#!/bin/bash
# Ejecutar en EC2 mediante make builder-build; sin claves AWS locales.
set -euo pipefail
cd /opt/citas/microproyecto-local-citation
unset AWS_PROFILE AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN
export AWS_DEFAULT_REGION=us-east-1
COMMIT=$(git rev-parse HEAD)
test -z "$(git status --porcelain)"
test "$(uname -m)" = x86_64
LOG=/opt/citas/build-images.log
exec 3>&1
exec >"$LOG" 2>&1
trap 'result=$?; if [ "$result" -ne 0 ]; then tail -n 60 "$LOG" >&3; fi' EXIT
python3 -m venv /opt/citas/tools
/opt/citas/tools/bin/pip install --disable-pip-version-check boto3
BASE="citas-science:${COMMIT}"
SERVERLESS="citas-serverless-ms:${COMMIT}"
docker build --platform linux/amd64 --build-arg "MS_CODE_SHA=$COMMIT" -f Dockerfile.ms -t "$BASE" .
docker build --platform linux/amd64 --build-arg "MS_BASE_IMAGE=$BASE" -f Dockerfile.serverless-ms -t "$SERVERLESS" .
docker run --rm --entrypoint python "$SERVERLESS" -c 'import torch; import src.app.serverless_main; assert not torch.cuda.is_available(); print("Importaciones CPU correctas")'
/opt/citas/tools/bin/python - "$COMMIT" <<'PY'
import base64,json,os,subprocess,sys,tempfile
from pathlib import Path
import boto3
commit=sys.argv[1]
session=boto3.Session(region_name='us-east-1')
assert session.client('sts').get_caller_identity()['Account']=='646941583111'
ecr=session.client('ecr')
repo='citas-ms-serverless-t04'
registry='646941583111.dkr.ecr.us-east-1.amazonaws.com'
result={'commit':commit,'images':{}}
with tempfile.TemporaryDirectory(prefix='citas-docker-') as config:
 env=dict(os.environ,DOCKER_CONFIG=config)
 token=ecr.get_authorization_token()['authorizationData'][0]['authorizationToken']
 username,password=base64.b64decode(token).decode().split(':',1)
 subprocess.run(['docker','login','--username',username,'--password-stdin',registry],input=password,text=True,env=env,stdout=subprocess.DEVNULL,check=True)
 for family,local in [('ms','citas-science'),('serverless','citas-serverless-ms')]:
  source=f'{local}:{commit}'
  info=json.loads(subprocess.check_output(['docker','image','inspect',source]))[0]
  assert info['Architecture']=='amd64'
  tag=f't04-{family}-{commit}'
  uri=f'{registry}/{repo}:{tag}'
  try:
   published=ecr.describe_images(repositoryName=repo,imageIds=[{'imageTag':tag}])['imageDetails'][0]
  except ecr.exceptions.ImageNotFoundException:
   subprocess.run(['docker','tag',source,uri],check=True)
   subprocess.run(['docker','push',uri],env=env,check=True)
   published=ecr.describe_images(repositoryName=repo,imageIds=[{'imageTag':tag}])['imageDetails'][0]
  digest=published['imageDigest']
  remote=ecr.batch_get_image(repositoryName=repo,imageIds=[{'imageDigest':digest}])
  manifest=json.loads(remote['images'][0]['imageManifest'])
  assert manifest['config']['digest']==info['Id'], 'Imagen publicada distinta del build local'
  result['images'][family]={'uri':f'{registry}/{repo}@{digest}','tag':tag,'architecture':info['Architecture'],'local_bytes':info['Size'],'registry_bytes':published['imageSizeInBytes']}
Path('/opt/citas/published-images.json').write_text(json.dumps(result,indent=2))
PY
cat /opt/citas/published-images.json >&3
