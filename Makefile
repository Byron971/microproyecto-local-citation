# Construcción y publicación de la imagen del API en Amazon ECR.
#
# Uso típico:
#   make init    # prepara bucket/ECR e inicializa Terraform
#   make login   # verifica las credenciales de AWS y autentica Docker contra ECR
#   make build   # construye la imagen para linux/amd64 (Fargate x86)
#   make push    # sube la imagen a ECR con el SHA corto del commit como tag
#
# Las variables se pueden sobrescribir al invocar, por ejemplo:
#   make push AWS_PROFILE=personal IMAGE_TAG=prueba

AWS_REGION     ?= us-east-1
ECR_REPOSITORY ?= citas-api
PLATFORM       ?= linux/amd64
TF_STATE_BUCKET ?= maia2026-grupo19
ECR_KEEP_IMAGES ?= 5
PROJECT_NAME   ?= citas-api
TF_STATE_KEY   ?= $(PROJECT_NAME)/terraform.tfstate
PYTHON         ?= python3
TERRAFORM      ?= terraform
TF_ARGS        ?=
IMAGE_TAG      ?= $(shell git rev-parse --short HEAD)

# AWS_PROFILE es opcional: si se define, se pasa a todos los comandos de aws.
ifdef AWS_PROFILE
AWS := aws --profile $(AWS_PROFILE) --region $(AWS_REGION)
else
AWS := aws --region $(AWS_REGION)
endif

export AWS_REGION
export TF_VAR_aws_region = $(AWS_REGION)
export TF_VAR_project_name = $(PROJECT_NAME)
export TF_VAR_ecr_repository = $(ECR_REPOSITORY)
ifdef AWS_PROFILE
export AWS_PROFILE
endif

# El account ID se consulta solo cuando una receta lo usa (asignación diferida).
AWS_ACCOUNT_ID = $(shell $(AWS) sts get-caller-identity --query Account --output text)
ECR_REGISTRY   = $(AWS_ACCOUNT_ID).dkr.ecr.$(AWS_REGION).amazonaws.com
LOCAL_IMAGE    = $(ECR_REPOSITORY):$(IMAGE_TAG)
REMOTE_IMAGE   = $(ECR_REGISTRY)/$(ECR_REPOSITORY):$(IMAGE_TAG)

.DEFAULT_GOAL := help
.PHONY: help check-aws destroy init init-bucket init-ecr login build push tf-plan tf-apply deploy publish-frontend

help: ## Muestra los comandos disponibles
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  make %-10s %s\n", $$1, $$2}'

check-aws:
	@$(AWS) sts get-caller-identity >/dev/null 2>&1 || { \
		echo "No hay credenciales de AWS válidas. Configúralas con 'aws configure' o define AWS_PROFILE."; \
		exit 1; }

init: init-bucket init-ecr ## Prepara bucket/ECR e inicializa Terraform con el estado en S3
	$(TERRAFORM) -chdir=terraform init -backend-config="bucket=$(TF_STATE_BUCKET)" -backend-config="region=$(AWS_REGION)" -backend-config="key=$(TF_STATE_KEY)"

init-bucket: check-aws
	@if $(AWS) s3api head-bucket --bucket $(TF_STATE_BUCKET) >/dev/null 2>&1; then \
		echo "Bucket $(TF_STATE_BUCKET) ya existe, no se modifica."; \
	else \
		echo "Creando bucket $(TF_STATE_BUCKET)..."; \
		if [ "$(AWS_REGION)" = "us-east-1" ]; then \
			$(AWS) s3api create-bucket --bucket $(TF_STATE_BUCKET) >/dev/null || exit 1; \
		else \
			$(AWS) s3api create-bucket --bucket $(TF_STATE_BUCKET) \
				--create-bucket-configuration LocationConstraint=$(AWS_REGION) >/dev/null || exit 1; \
		fi; \
		$(AWS) s3api put-bucket-versioning --bucket $(TF_STATE_BUCKET) \
			--versioning-configuration Status=Enabled && \
		$(AWS) s3api put-bucket-encryption --bucket $(TF_STATE_BUCKET) \
			--server-side-encryption-configuration \
			'{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}' && \
		$(AWS) s3api put-public-access-block --bucket $(TF_STATE_BUCKET) \
			--public-access-block-configuration \
			BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true && \
		echo "Bucket $(TF_STATE_BUCKET) creado con versionado, cifrado y acceso público bloqueado."; \
	fi

init-ecr: check-aws
	@if $(AWS) ecr describe-repositories --repository-names $(ECR_REPOSITORY) >/dev/null 2>&1; then \
		echo "Repositorio ECR $(ECR_REPOSITORY) ya existe, no se modifica."; \
	else \
		echo "Creando repositorio ECR $(ECR_REPOSITORY)..."; \
		$(AWS) ecr create-repository --repository-name $(ECR_REPOSITORY) \
			--image-scanning-configuration scanOnPush=true \
			--image-tag-mutability MUTABLE \
			--encryption-configuration encryptionType=AES256 >/dev/null && \
		$(AWS) ecr put-lifecycle-policy --repository-name $(ECR_REPOSITORY) \
			--lifecycle-policy-text '{"rules":[{"rulePriority":1,"description":"Conservar las ultimas $(ECR_KEEP_IMAGES) imagenes","selection":{"tagStatus":"any","countType":"imageCountMoreThan","countNumber":$(ECR_KEEP_IMAGES)},"action":{"type":"expire"}}]}' >/dev/null && \
		echo "Repositorio ECR $(ECR_REPOSITORY) creado (scan on push, conserva $(ECR_KEEP_IMAGES) imágenes)."; \
	fi
	@echo "URI: $(ECR_REGISTRY)/$(ECR_REPOSITORY)"

login: check-aws ## Verifica las credenciales y autentica Docker contra ECR
	@echo "Cuenta: $(AWS_ACCOUNT_ID)  Región: $(AWS_REGION)"
	@$(AWS) ecr get-login-password | docker login --username AWS --password-stdin $(ECR_REGISTRY)

build: ## Construye la imagen del API para linux/amd64
	docker build --platform $(PLATFORM) -t $(LOCAL_IMAGE) .

push: check-aws ## Sube la imagen a ECR etiquetada con el SHA corto del commit
	@$(AWS) ecr describe-repositories --repository-names $(ECR_REPOSITORY) >/dev/null 2>&1 || { \
		echo "El repositorio ECR '$(ECR_REPOSITORY)' no existe. Ejecuta primero make init."; \
		exit 1; }
	@docker image inspect $(LOCAL_IMAGE) >/dev/null 2>&1 || { \
		echo "No existe la imagen local $(LOCAL_IMAGE). Ejecuta 'make build' primero."; \
		exit 1; }
	docker tag $(LOCAL_IMAGE) $(REMOTE_IMAGE)
	docker push $(REMOTE_IMAGE)
	@echo "Imagen publicada: $(REMOTE_IMAGE)"

	$(AWS) ssm put-parameter --name /$(PROJECT_NAME)/api/image_tag --type String --value $(IMAGE_TAG) --overwrite >/dev/null

tf-plan: ## Muestra los cambios de infraestructura
	$(TERRAFORM) -chdir=terraform plan $(TF_ARGS)

tf-apply: ## Aplica los cambios de infraestructura sin reconstruir la imagen
	$(TERRAFORM) -chdir=terraform apply $(TF_ARGS)

# Publicar assets antes que index.html; conservar hashes de versiones abiertas.
publish-frontend: check-aws ## Compila React, publica en S3 y actualiza CloudFront
	@set -eu; \
	bucket=$$($(TERRAFORM) -chdir=terraform output -raw frontend_bucket); \
	distribution=$$($(TERRAFORM) -chdir=terraform output -raw distribution_id); \
	api_url=$$($(TERRAFORM) -chdir=terraform output -raw api_base_url); \
	frontend_url=$$($(TERRAFORM) -chdir=terraform output -raw frontend_url); \
	npm --prefix frontend ci; \
	VITE_API_BASE_URL="$$api_url" npm --prefix frontend run build; \
	$(AWS) s3 sync frontend/dist/assets/ "s3://$$bucket/assets/" --cache-control 'public,max-age=31536000,immutable'; \
	$(AWS) s3 sync frontend/dist/ "s3://$$bucket/" --exclude 'assets/*' --exclude index.html --cache-control 'no-cache,max-age=0,must-revalidate'; \
	$(AWS) s3 cp frontend/dist/index.html "s3://$$bucket/index.html" --content-type 'text/html; charset=utf-8' --cache-control 'no-cache,max-age=0,must-revalidate'; \
	$(AWS) cloudfront create-invalidation --distribution-id "$$distribution" --paths '/index.html' >/dev/null; \
	printf 'Frontend publicado: %s\n' "$$frontend_url"

deploy: ## Publica API y React con un único stack (requiere make init previo)
	$(MAKE) login
	$(MAKE) build
	$(MAKE) push
	$(TERRAFORM) -chdir=terraform apply $(TF_ARGS)
	$(MAKE) publish-frontend

# Ejecutar después de terraform destroy y sin despliegues concurrentes.
destroy: check-aws ## Elimina ECR y bucket de estado de make init (incluye todas las versiones)
	@AWS_REGION="$(AWS_REGION)" $(PYTHON) scripts/destruir_init.py "$(TF_STATE_BUCKET)" "$(ECR_REPOSITORY)" "$(TF_STATE_KEY)"
