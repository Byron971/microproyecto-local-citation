"""Confirma revisiones activas, salud HTTP y el bundle publicado."""
import hashlib,json,urllib.request
from pathlib import Path
from image_builder_ops import aws
root=Path('artifacts')
outputs=json.loads((root/'release-outputs.json').read_text())
images=json.loads((root/'image_builder/release-images.json').read_text())
services=aws('ecs','describe-services','--cluster','citas-api','--services','citas-api','citas-api-science')
assert not services['failures']
report={'services':{},'web':'https://proyectocitas-grupo19.click','qlora':'suspendido y oculto'}
for service in services['services']:
 science=service['serviceName'].endswith('-science')
 kind='ms' if science else 'api'
 expected=outputs['scientific_task_definition_arn' if science else 'task_definition_arn']['value']
 assert service['taskDefinition']==expected, 'ECS volvió a otra revisión'
 assert service['runningCount']==service['desiredCount']==1
 assert service['pendingCount']==0
 assert len(service['deployments'])==1 and service['deployments'][0]['rolloutState']=='COMPLETED'
 definition=aws('ecs','describe-task-definition','--task-definition',expected)['taskDefinition']
 image=definition['containerDefinitions'][0]['image']
 wanted=images['images'][kind]['uri'] if science else images['images'][kind]['uri'].split('@')[0]+':'+images['images'][kind]['tag']
 assert image==wanted
 report['services'][kind]={'task':expected,'image':image,'stable':True}
def read(url):
 with urllib.request.urlopen(url,timeout=30) as response:
  assert response.status==200
  return response.read()
api='https://api.proyectocitas-grupo19.click'
assert json.loads(read(api+'/api/estado'))['listo'] is True
state=json.loads(read(api+'/api/analisis-cita-ms/estado'))
assert state['modelos_cargados'] is True and state['revision_codigo']==images['images']['ms'].get('commit',images['commit'])
corpus_release=Path('config/corpus_release.json')
if corpus_release.exists():
 corpus_manifest=json.loads(corpus_release.read_text())
 assert state['total_articulos_preparados']==corpus_manifest['total_articulos']
 assert state['version_corpus']==hashlib.sha256(corpus_release.read_bytes()).hexdigest()
 report['articulos_preparados']=state['total_articulos_preparados']
 report['version_corpus']=state['version_corpus']
assert state['release']==json.loads(Path('config/ms_release.json').read_text())['release_id']
index=Path('frontend/dist/index.html').read_bytes()
assert read(report['web']+'/')==index, 'CloudFront aún sirve otro index'
report['index_sha256']=hashlib.sha256(index).hexdigest()
report['api_health']=True
(root/'release-confirmation.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2))
