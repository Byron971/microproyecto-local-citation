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
