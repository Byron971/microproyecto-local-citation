.PHONY: commercial-secret commercial-test
commercial-secret:
	AWS_PROFILE=josezambrana TERRAFORM="$(TERRAFORM)" python3 scripts/configure_commercial_secret.py
commercial-test:
	.venv/bin/python -m pytest -q tests/test_commercial_api.py tests/test_providers_openai.py
.PHONY: commercial-secret-validate
commercial-secret-validate:
	$(TERRAFORM) -chdir=terraform/commercial_secret init -input=false -plugin-dir=../.terraform/providers
	$(TERRAFORM) -chdir=terraform/commercial_secret validate
.PHONY: commercial-plan
commercial-plan:
	$(TERRAFORM) -chdir=terraform plan -input=false -lock-timeout=2m -var-file="$(abspath artifacts/t09-prepare.tfvars.json)" -out="$(abspath artifacts/t09-prepare.tfplan)"
	$(TERRAFORM) -chdir=terraform show -json "$(abspath artifacts/t09-prepare.tfplan)" > artifacts/t09-prepare-plan.json
