#!/usr/bin/env bash
# La imagen ya debe estar publicada y fijada por digest.
set -euo pipefail
: "${SCIENCE_IMAGE_URI:?Falta SCIENCE_IMAGE_URI con digest SHA256}"
[[ "$SCIENCE_IMAGE_URI" =~ @sha256:[a-f0-9]{64}$ ]] || { echo 'La imagen requiere digest'; exit 1; }
terraform_bin=${TERRAFORM_BIN:-terraform}
parameter=/citas-api/science/image_uri
previous_name=$(aws ssm describe-parameters --parameter-filters "Key=Name,Values=$parameter" --query 'Parameters[0].Name' --output text)
previous=''
previous_task=$(aws ecs describe-services --cluster citas-api --services citas-api-science --query 'services[0].taskDefinition' --output text)
plan_directory=''
if [[ "$previous_name" != None ]]; then
  previous=$(aws ssm get-parameter --name "$parameter" --query 'Parameter.Value' --output text)
fi
restore_pointer() {
  result=$?
  if [[ $result -ne 0 && -n "$previous" ]]; then
    aws ssm put-parameter --name "$parameter" --type String --value "$previous" --overwrite >/dev/null || true
    if [[ "$previous_task" != None && -n "$previous_task" ]]; then
      aws ecs update-service --cluster citas-api --service citas-api-science --task-definition "$previous_task" >/dev/null || true
    fi
    echo 'Despliegue no aceptado: puntero SSM anterior restaurado. Revisar ECS/rollback antes de reintentar.' >&2
  fi
  if [[ -n "$plan_directory" ]]; then rm -rf "$plan_directory"; fi
  exit "$result"
}
trap restore_pointer EXIT
aws ssm put-parameter --name "$parameter" --type String --value "$SCIENCE_IMAGE_URI" --overwrite >/dev/null
plan_directory=$(mktemp -d)
chmod 700 "$plan_directory"
"$terraform_bin" -chdir=terraform plan -input=false -lock-timeout=5m \
  -target=aws_ecs_service.scientific -target=aws_ecs_task_definition.scientific \
  -target=aws_lb_listener_rule.scientific -target=aws_lb_target_group.scientific \
  -target=aws_cloudwatch_log_group.scientific -out="$plan_directory/deploy.tfplan"
"$terraform_bin" -chdir=terraform show -json "$plan_directory/deploy.tfplan" > "$plan_directory/plan.json"
python - "$plan_directory/plan.json" <<'PY'
import json, sys
allowed = {'aws_ecs_service.scientific', 'aws_ecs_task_definition.scientific',
           'aws_lb_listener_rule.scientific', 'aws_lb_target_group.scientific',
           'aws_cloudwatch_log_group.scientific'}
for resource in json.load(open(sys.argv[1])).get('resource_changes', []):
    actions = resource['change']['actions']
    if resource['mode'] == 'data' or actions == ['no-op']:
        continue
    base = resource['address'].split('[')[0]
    if base not in allowed or ('delete' in actions and not (base == 'aws_ecs_task_definition.scientific' and 'create' in actions)):
        raise SystemExit('Plan rechazado: cambio fuera del servicio científico o destrucción: ' + resource['address'])
PY
"$terraform_bin" -chdir=terraform apply -input=false "$plan_directory/deploy.tfplan"
expected=$("$terraform_bin" -chdir=terraform output -raw scientific_task_definition_arn)
aws ecs wait services-stable --cluster citas-api --services citas-api-science
actual=$(aws ecs describe-services --cluster citas-api --services citas-api-science --query 'services[0].taskDefinition' --output text)
[[ "$actual" == "$expected" ]] || { echo 'ECS no conservó la revisión esperada'; exit 1; }
python - <<'PY'
import json, urllib.request
base = 'https://api.proyectocitas-grupo19.click'
with urllib.request.urlopen(base + '/api/estado', timeout=15) as response:
    assert response.status == 200
with urllib.request.urlopen(base + '/api/analisis-cita-ms/estado', timeout=15) as response:
    state = json.load(response)
    assert state['modelos_cargados'] is True
    assert state['release'] == json.load(open('config/ms_release.json'))['release_id']
print('API estándar 200 y modelos científicos cargados; se ejecuta ahora la comparación sintética.')
PY
python scripts/probar_api_cientifica.py \
  --url https://api.proyectocitas-grupo19.click \
  --estado-path /api/analisis-cita-ms/estado \
  --solicitud tests/fixtures/ms_sintetico_solicitud.json \
  --referencia tests/fixtures/ms_sintetico_referencia.json \
  --salida artifacts/ms_deploy/aceptacion_ci_sintetica.json

python scripts/probar_flujo_integrado_ms.py \
  --salida artifacts/ms_deploy/aceptacion_ci_integrada.json

rm -rf "$plan_directory"
