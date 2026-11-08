#!/usr/bin/env bash
# CI publica la imagen antes de ejecutar este script.
set -euo pipefail
: "${IMAGE_TAG:?Falta IMAGE_TAG}"
parameter="/citas-api/api/image_tag"
# Consultar existencia sin confundir un error de permisos con un parámetro ausente.
previous=$(aws ssm describe-parameters --parameter-filters "Key=Name,Values=$parameter" --query 'Parameters[0].Name' --output text)
if [[ "$previous" != None ]]; then
  previous=$(aws ssm get-parameter --name "$parameter" --query 'Parameter.Value' --output text)
else
  previous=''
fi
restore_tag() {
  status=$?
  if [[ $status -ne 0 && -n "$previous" ]]; then
    echo '::warning::Despliegue fallido; se restaura el tag SSM anterior. Revisa ECS y el estado de Terraform.'
    aws ssm put-parameter --name "$parameter" --type String --value "$previous" --overwrite >/dev/null || true
  fi
  exit "$status"
}
trap restore_tag EXIT
aws ssm put-parameter --name "$parameter" --type String --value "$IMAGE_TAG" --overwrite >/dev/null
terraform -chdir=terraform plan -lock-timeout=5m -out=deploy.tfplan
terraform -chdir=terraform apply -input=false deploy.tfplan
bash scripts/ci/verify-deployment.sh
