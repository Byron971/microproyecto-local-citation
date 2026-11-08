#!/usr/bin/env bash
set -euo pipefail
cluster=$(terraform -chdir=terraform output -raw cluster_name)
service=$(terraform -chdir=terraform output -raw service_name)
expected=$(terraform -chdir=terraform output -raw task_definition_arn)
# El waiter por defecto puede terminar antes de que actúe el circuit breaker.
for attempt in 1 2 3; do
  if aws ecs wait services-stable --cluster "$cluster" --services "$service"; then
    break
  fi
  if [[ $attempt == 3 ]]; then
    echo '::error::ECS no alcanzó estabilidad; revisa eventos del servicio y CloudWatch.'
    exit 1
  fi
done
actual=$(aws ecs describe-services --cluster "$cluster" --services "$service" --query 'services[0].taskDefinition' --output text)
if [[ "$actual" != "$expected" ]]; then
  echo '::error::ECS volvió a una revisión anterior: el despliegue falló.'
  exit 1
fi
count=$(aws ecs describe-services --cluster "$cluster" --services "$service" --query 'services[0].desiredCount' --output text)
if [[ "$count" == 0 ]]; then
  echo 'Servicio apagado (desired_count=0); se omite la verificación HTTP.'
  exit 0
fi
url=$(terraform -chdir=terraform output -raw api_url)
python3 scripts/ci/smoke-api.py "$url"
if [[ -n "${GITHUB_STEP_SUMMARY:-}" ]]; then
  printf 'API desplegada: %s\n' "$url" >> "$GITHUB_STEP_SUMMARY"
fi
