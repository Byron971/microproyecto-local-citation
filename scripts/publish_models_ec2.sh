#!/bin/bash
set -euo pipefail
unset AWS_PROFILE AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN
export AWS_DEFAULT_REGION=us-east-1 TF_IN_AUTOMATION=1 TF_INPUT=0
cd /opt/citas/microproyecto-local-citation
LOG=/opt/citas/publish-models.log
exec 3>&1
exec >"$LOG" 2>&1
trap 'result=$?; if [ "$result" -ne 0 ]; then tail -n 60 "$LOG" >&3; fi' EXIT
/opt/citas/tools/bin/python - <<'PY'
import boto3,json
from pathlib import Path
s=boto3.Session(region_name='us-east-1')
assert s.client('sts').get_caller_identity()['Account']=='646941583111'
r=json.loads(Path('/opt/citas/models/prepared-models.json').read_text())
assert r['files_verified'] and r['matches_local_bundle']
s3=s.client('s3'); bucket='citas-api-models-646941583111-us-east-1'
key='experiments/t04-ms-serverless/'+r['sha256']+'/model.tar.gz'
try:
 s3.head_object(Bucket=bucket,Key='terraform/t04-ms-artifact/terraform.tfstate')
except s3.exceptions.ClientError as e:
 if e.response['Error']['Code'] not in ('404','NoSuchKey'):raise
 versions=s3.list_object_versions(Bucket=bucket,Prefix=key)
 assert not any(x['Key']==key for x in versions.get('Versions',[])+versions.get('DeleteMarkers',[])), 'Objeto previo sin estado propio; no se reemplaza'
PY
mkdir -p /opt/citas/bin
if [ ! -x /opt/citas/bin/terraform ]; then
  TEMP=$(mktemp -d)
  (cd "$TEMP"
   curl -fsSLO https://releases.hashicorp.com/terraform/1.14.8/terraform_1.14.8_linux_amd64.zip
   curl -fsSLO https://releases.hashicorp.com/terraform/1.14.8/terraform_1.14.8_SHA256SUMS
   sha256sum --check --ignore-missing terraform_1.14.8_SHA256SUMS
   unzip -q terraform_1.14.8_linux_amd64.zip terraform
   install -m 0755 terraform /opt/citas/bin/terraform)
  rm -rf "$TEMP"
fi
TF=/opt/citas/bin/terraform
MODULE=terraform/model_artifact
"$TF" -chdir="$MODULE" init -input=false
"$TF" -chdir="$MODULE" plan -input=false -out=/opt/citas/models/publish.tfplan
"$TF" -chdir="$MODULE" show -json /opt/citas/models/publish.tfplan > /opt/citas/models/publish-plan.json
/opt/citas/tools/bin/python - <<'PY'
import json
p=json.load(open('/opt/citas/models/publish-plan.json'))
r=[x for x in p.get('resource_changes',[]) if x['mode']=='managed']
assert len(r)==1 and r[0]['address']=='aws_s3_object.bundle'
assert r[0]['change']['actions'] in (['create'],['no-op']), 'No se permiten reemplazos ni modificaciones'
a=r[0]['change']['after']
assert a['bucket']=='citas-api-models-646941583111-us-east-1'
assert a['key']=='experiments/t04-ms-serverless/b75e3075c4bf630d1b5aaf9c0ce7a2e43265446231ed550869e6df38b35def7f/model.tar.gz'
PY
"$TF" -chdir="$MODULE" apply -input=false /opt/citas/models/publish.tfplan
/opt/citas/tools/bin/python - <<'PY'
import boto3,hashlib,json
from pathlib import Path
r=json.loads(Path('/opt/citas/models/prepared-models.json').read_text())
bucket='citas-api-models-646941583111-us-east-1';key='experiments/t04-ms-serverless/'+r['sha256']+'/model.tar.gz'
s3=boto3.client('s3',region_name='us-east-1');head=s3.head_object(Bucket=bucket,Key=key)
assert head['ContentLength']==r['tar_bytes']
assert head['Metadata']['sha256']==r['sha256']
assert head['ServerSideEncryption']=='AES256'
request={'Bucket':bucket,'Key':key}
if head.get('VersionId'):request['VersionId']=head['VersionId']
body=s3.get_object(**request)['Body'];digest=hashlib.sha256()
try:
 for chunk in body.iter_chunks(8*1024*1024):digest.update(chunk)
finally:body.close()
assert digest.hexdigest()==r['sha256'], 'SHA256 remoto incorrecto'
report={'s3_uri':'s3://'+bucket+'/'+key,'bytes':head['ContentLength'],'sha256':digest.hexdigest(),'version_id':head.get('VersionId'),'encrypted':True,'remote_bytes_verified':True,'terraform_state':'s3://'+bucket+'/terraform/t04-ms-artifact/terraform.tfstate','endpoint_created':False}
Path('/opt/citas/models/published-models.json').write_text(json.dumps(report,indent=2))
PY
cat /opt/citas/models/published-models.json >&3
