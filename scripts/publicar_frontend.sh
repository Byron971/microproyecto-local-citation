#!/usr/bin/env bash
# Requiere infraestructura aplicada en terraform/frontend. No crea recursos.
set -euo pipefail
cd "$(dirname "$0")/.."
export AWS_REGION="${AWS_REGION:-us-east-1}"
TERRAFORM_BIN="${TERRAFORM:-terraform}"
bucket=$("$TERRAFORM_BIN" -chdir=terraform/frontend output -raw frontend_bucket)
distribution=$("$TERRAFORM_BIN" -chdir=terraform/frontend output -raw distribution_id)
VITE_API_BASE_URL=$("$TERRAFORM_BIN" -chdir=terraform/frontend output -raw api_base_url)
export VITE_API_BASE_URL
aws sts get-caller-identity >/dev/null
npm --prefix frontend ci
npm --prefix frontend run build
# No usar --delete: conservar assets con hash de versiones abiertas.
aws s3 sync frontend/dist/assets/ "s3://$bucket/assets/" --cache-control 'public,max-age=31536000,immutable'
aws s3 sync frontend/dist/ "s3://$bucket/" --exclude 'assets/*' --exclude index.html --cache-control 'no-cache,max-age=0,must-revalidate'
aws s3 cp frontend/dist/index.html "s3://$bucket/index.html" --content-type 'text/html; charset=utf-8' --cache-control 'no-cache,max-age=0,must-revalidate'
aws cloudfront create-invalidation --distribution-id "$distribution" --paths '/index.html' >/dev/null
printf 'Frontend publicado: %s\n' "$("$TERRAFORM_BIN" -chdir=terraform/frontend output -raw frontend_url)"
