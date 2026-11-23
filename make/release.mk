# Publicación del recorrido disponible; QLoRA permanece suspendido.
.PHONY: release-status release-check
release-status:
	$(AWS) ecs describe-services --cluster citas-api --services citas-api citas-api-science --query 'services[].{service:serviceName,task:taskDefinition,desired:desiredCount,running:runningCount,deployments:deployments[].{status:status,rollout:rolloutState}}'
	AWS_PROFILE=$(AWS_PROFILE) $(TERRAFORM) -chdir=terraform output -json > artifacts/release-outputs.json
	$(AWS) ssm get-parameter --name /citas-api/science/image_uri --query Parameter.Value --output text
release-check:
	python3 scripts/probar_flujo_integrado_ms.py --salida artifacts/release-integrated.json
.PHONY: release-images release-plan release-qlora-pause
release-images:
	$(AWS) ecr describe-images --repository-name citas-api --query 'imageDetails[].{tags:imageTags,digest:imageDigest,pushed:imagePushedAt}'
release-plan:
	$(TERRAFORM) -chdir=terraform plan -input=false -lock-timeout=2m $(if $(RELEASE_VARS),-var-file="$(abspath $(RELEASE_VARS))") -out="$(abspath artifacts/release.tfplan)"
	$(TERRAFORM) -chdir=terraform show -json "$(abspath artifacts/release.tfplan)" > artifacts/release-plan.json
release-qlora-pause:
	AWS_PROFILE=$(AWS_PROFILE) python3 scripts/qlora_pause.py
.PHONY: release-public-state
release-public-state:
	python3 -c 'import json,urllib.request; u="https://api.proyectocitas-grupo19.click/api/analisis-cita-ms/estado"; print(json.dumps(json.load(urllib.request.urlopen(u,timeout=30)),indent=2))'
.PHONY: release-build release-build-result
release-build:
	AWS_PROFILE=$(AWS_PROFILE) python3 scripts/release_build_ops.py send --commit "$(shell git rev-parse HEAD)"
release-build-result:
	AWS_PROFILE=$(AWS_PROFILE) python3 scripts/release_build_ops.py result

.PHONY: release-prepare release-apply release-wait
release-prepare:
	AWS_PROFILE=$(AWS_PROFILE) python3 scripts/prepare_release.py
release-apply:
	python3 scripts/check_release_plan.py
	$(TERRAFORM) -chdir=terraform apply -input=false "$(abspath artifacts/release.tfplan)"
release-wait:
	$(AWS) ecs wait services-stable --cluster citas-api --services citas-api citas-api-science

.PHONY: release-web-check
release-web-check:
	mkdir -p artifacts/release-web
	E2E_BASE_URL=https://proyectocitas-grupo19.click LIVE_SCIENCE_E2E=1 T03_OUTPUT_DIR="$(abspath artifacts/release-web)" npm --prefix frontend run test:e2e -- scientific-real.spec.ts --workers=1
.PHONY: release-events
release-events:
	$(AWS) ecs describe-services --cluster citas-api --services citas-api citas-api-science --query 'services[].{service:serviceName,events:events[:4].message}'
	$(AWS) logs tail /ecs/citas-api-science --since 8m --format short
.PHONY: release-web-storage
release-web-storage:
	$(AWS) s3api head-bucket --bucket citas-api-web-646941583111-us-east-1
	$(AWS) s3api get-bucket-location --bucket citas-api-web-646941583111-us-east-1
	$(AWS) s3api list-objects-v2 --bucket citas-api-web-646941583111-us-east-1 --max-keys 1 --query '{Count:KeyCount,Names:Contents[].Key}'
.PHONY: release-confirm
release-confirm: release-status
	AWS_PROFILE=$(AWS_PROFILE) python3 scripts/confirm_release.py

.PHONY: release-build-api
release-build-api:
	AWS_PROFILE=$(AWS_PROFILE) python3 scripts/release_build_ops.py send --kind api --commit "$(shell git rev-parse HEAD)"

.PHONY: release-build-ms
release-build-ms:
	AWS_PROFILE=$(AWS_PROFILE) python3 scripts/release_build_ops.py send --kind ms --commit "$(shell git rev-parse HEAD)"

.PHONY: article-search-check article-search-web-check
article-search-check:
	python3 scripts/check_prepared_search.py
article-search-web-check:
	E2E_BASE_URL=https://proyectocitas-grupo19.click LIVE_ARTICLE_SEARCH=1 npm --prefix frontend run test:e2e -- article-search-live.spec.ts --workers=1 --output=../artifacts/article-search-live
