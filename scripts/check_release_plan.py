"""Rechaza cambios ajenos a las imágenes, sus servicios y las rutas científicas."""
import json
from pathlib import Path
plan=json.loads(Path('artifacts/release-plan.json').read_text())
allowed={'aws_ssm_parameter.release_api','aws_ssm_parameter.release_science[0]',
 'aws_ecs_task_definition.api','aws_ecs_task_definition.scientific[0]',
 'aws_ecs_service.api','aws_ecs_service.scientific[0]','aws_lb_listener_rule.scientific[0]'}
changes=[]
for r in plan.get('resource_changes',[]):
 actions=r['change']['actions']
 if r['mode']=='data' or actions==['no-op']:continue
 assert r['address'] in allowed, 'Cambio ajeno: '+r['address']
 assert 'delete' not in actions or (r['address'].startswith('aws_ecs_task_definition.') and 'create' in actions), 'Destrucción inesperada'
 changes.append({'resource':r['address'],'actions':actions})
print(json.dumps(changes,indent=2))
