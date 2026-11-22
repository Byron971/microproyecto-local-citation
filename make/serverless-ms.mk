MS_PROBE_WORK ?= artifacts/serverless_t04
MS_BUNDLE ?= $(MS_PROBE_WORK)/model.tar.gz
MS_PROBE_TF := terraform/serverless_ms_probe
MS_PROBE_NAME := citas-ms-serverless-t04
MS_PROBE_IMAGE := citas-serverless-ms:t04-local
MS_PROFILE := $(if $(AWS_PROFILE),$(AWS_PROFILE),josezambrana)
MS_PROBE_DATA := $(abspath $(MS_PROBE_WORK)/tfdata)
MS_TF := TF_DATA_DIR="$(MS_PROBE_DATA)" $(TERRAFORM) -chdir=$(MS_PROBE_TF)
MS_OPS := AWS_PROFILE="$(MS_PROFILE)" AWS_REGION="$(AWS_REGION)" python3 scripts/serverless_ms_ops.py --work "$(MS_PROBE_WORK)"

.PHONY: ms-serverless-preflight ms-serverless-init ms-serverless-plan ms-serverless-apply ms-serverless-push ms-serverless-enable ms-serverless-test ms-serverless-observe ms-serverless-destroy-plan ms-serverless-destroy ms-serverless-check-current
ms-serverless-preflight: ## Verifica identidad, bundle y servicio actual; genera variables locales
	$(MS_OPS) preflight --bundle "$(MS_BUNDLE)"
ms-serverless-init: ## Inicializa SOLO el Terraform aislado de T04
	$(MS_TF) init -backend=false -input=false -plugin-dir=../.terraform/providers
ms-serverless-plan: ## Genera un plan T04 sin aplicarlo
	$(MS_TF) plan -input=false -var-file="$(abspath $(MS_PROBE_WORK)/probe.tfvars.json)" -out="$(abspath $(MS_PROBE_WORK)/probe.tfplan)"
	$(MS_TF) show -json "$(abspath $(MS_PROBE_WORK)/probe.tfplan)" > "$(MS_PROBE_WORK)/plan.json"
	$(MS_OPS) check-plan
ms-serverless-apply: ## Aplica SOLO el plan T04 previamente validado
	$(MS_OPS) check-plan
	$(MS_TF) apply -input=false "$(abspath $(MS_PROBE_WORK)/probe.tfplan)"
ms-serverless-push: ## Publica la imagen AMD64 en el ECR temporal creado por Terraform
	$(MS_OPS) push --image "$(MS_PROBE_IMAGE)"
ms-serverless-enable: ## Fija el digest publicado y habilita el endpoint en las variables locales
	$(MS_OPS) enable
ms-serverless-test: ## Ejecuta como máximo seis inferencias; sin reintentos automáticos
	AWS_PROFILE="$(MS_PROFILE)" python3 scripts/probar_serverless_ms.py --endpoint "$(MS_PROBE_NAME)" --profile "$(MS_PROFILE)" --region "$(AWS_REGION)" --include-long --output "$(MS_PROBE_WORK)/aws_inference.json"
ms-serverless-observe: ## Guarda estado, logs y métricas de la prueba sin modificar AWS
	$(MS_OPS) observe
ms-serverless-destroy-plan: ## Genera y valida el retiro de los recursos temporales de T04
	$(MS_TF) plan -destroy -input=false -var-file="$(abspath $(MS_PROBE_WORK)/probe.tfvars.json)" -out="$(abspath $(MS_PROBE_WORK)/cleanup.tfplan)"
	$(MS_TF) show -json "$(abspath $(MS_PROBE_WORK)/cleanup.tfplan)" > "$(MS_PROBE_WORK)/cleanup.json"
	$(MS_OPS) check-destroy
ms-serverless-destroy: ## Retira SOLO los recursos del plan temporal validado
	$(MS_OPS) check-destroy
	$(MS_TF) apply -input=false "$(abspath $(MS_PROBE_WORK)/cleanup.tfplan)"
ms-serverless-check-current: ## Comprueba que ECS conserva la tarea y capacidad anteriores
	$(MS_OPS) check-current

.PHONY: ms-serverless-cancel-upload
ms-serverless-cancel-upload: ## Interrumpe gradualmente SOLO el apply local de esta prueba
	$(MS_OPS) cancel-upload --pid "$(MS_UPLOAD_PID)"
