BUILDER_DIR := terraform/image_builder
BUILDER_WORK := $(abspath artifacts/image_builder)
BUILDER_TF := AWS_PROFILE=josezambrana $(TERRAFORM) -chdir=$(BUILDER_DIR)
.PHONY: builder-key builder-init builder-plan builder-apply builder-status builder-session builder-ready
builder-key:
	mkdir -p private artifacts/image_builder
	@test -e private/maiag19.pem || ssh-keygen -t rsa -b 4096 -m PEM -N '' -C maiag19-builder -f private/maiag19.pem
	chmod 600 private/maiag19.pem
	python3 -c 'import json,pathlib; pathlib.Path("artifacts/image_builder/vars.json").write_text(json.dumps({"public_key":pathlib.Path("private/maiag19.pem.pub").read_text().strip()}))'
builder-init:
	$(BUILDER_TF) init -input=false -plugin-dir=../.terraform/providers
builder-plan:
	$(BUILDER_TF) plan -input=false -var-file="$(BUILDER_WORK)/vars.json" -out="$(BUILDER_WORK)/builder.tfplan"
	$(BUILDER_TF) show -json "$(BUILDER_WORK)/builder.tfplan" > "$(BUILDER_WORK)/plan.json"
builder-apply:
	python3 -c 'import json; p=json.load(open("$(BUILDER_WORK)/plan.json")); r=[x for x in p["resource_changes"] if x["mode"]=="managed"]; assert len(r)==7 and all(x["change"]["actions"]==["create"] for x in r), "Plan inesperado"'
	$(BUILDER_TF) apply -input=false "$(BUILDER_WORK)/builder.tfplan"
	$(BUILDER_TF) output -json > "$(BUILDER_WORK)/outputs.json"
builder-status:
	AWS_PROFILE=josezambrana aws ssm describe-instance-information --region us-east-1 --filters Key=tag:Project,Values=citas-image-builder --query 'InstanceInformationList[].{Id:InstanceId,Status:PingStatus,OS:PlatformName}'
builder-session:
	AWS_PROFILE=josezambrana aws ssm start-session --region us-east-1 --target $$($(BUILDER_TF) output -raw instance_id)
builder-ready:
	AWS_PROFILE=josezambrana aws ssm send-command --region us-east-1 --instance-ids $$($(BUILDER_TF) output -raw instance_id) --document-name AWS-RunShellScript --parameters 'commands=["cloud-init status --wait >/dev/null 2>&1; test -f /opt/citas/READY && docker --version && git --version && rclone version | head -1"]' --query 'Command.CommandId' --output text > "$(BUILDER_WORK)/ready-command.txt"

.PHONY: builder-ready-result builder-destroy-plan builder-destroy
builder-ready-result:
	AWS_PROFILE=josezambrana aws ssm get-command-invocation --region us-east-1 --instance-id $$($(BUILDER_TF) output -raw instance_id) --command-id "$$(cat "$(BUILDER_WORK)/ready-command.txt")" --query '{Status:Status,Output:StandardOutputContent,Error:StandardErrorContent}'
builder-destroy-plan:
	$(BUILDER_TF) plan -destroy -input=false -var-file="$(BUILDER_WORK)/vars.json" -out="$(BUILDER_WORK)/destroy.tfplan"
builder-destroy:
	$(BUILDER_TF) apply -input=false "$(BUILDER_WORK)/destroy.tfplan"

BUILDER_COMMIT ?= $(shell git rev-parse HEAD)
.PHONY: builder-clone builder-clone-result
builder-clone:
	AWS_PROFILE=josezambrana python3 scripts/image_builder_ops.py clone --work "$(BUILDER_WORK)" --commit "$(BUILDER_COMMIT)"
builder-clone-result:
	AWS_PROFILE=josezambrana python3 scripts/image_builder_ops.py clone-result --work "$(BUILDER_WORK)"

.PHONY: builder-build builder-build-result
builder-build:
	AWS_PROFILE=josezambrana python3 scripts/image_builder_ops.py build --work "$(BUILDER_WORK)"
builder-build-result:
	AWS_PROFILE=josezambrana python3 scripts/image_builder_ops.py build-result --work "$(BUILDER_WORK)"

.PHONY: builder-build-log builder-build-log-result
builder-build-log:
	AWS_PROFILE=josezambrana aws ssm send-command --region us-east-1 --instance-ids $$($(BUILDER_TF) output -raw instance_id) --document-name AWS-RunShellScript --parameters 'commands=["tail -n 12 /opt/citas/build-images.log"]' --query 'Command.CommandId' --output text > "$(BUILDER_WORK)/log-command.txt"
builder-build-log-result:
	AWS_PROFILE=josezambrana aws ssm get-command-invocation --region us-east-1 --instance-id $$($(BUILDER_TF) output -raw instance_id) --command-id "$$(cat "$(BUILDER_WORK)/log-command.txt")" --query '{Status:Status,Output:StandardOutputContent}'

.PHONY: builder-inspect builder-inspect-result
builder-inspect:
	AWS_PROFILE=josezambrana python3 scripts/image_builder_ops.py inspect --work "$(BUILDER_WORK)"
builder-inspect-result:
	AWS_PROFILE=josezambrana python3 scripts/image_builder_ops.py inspect-result --work "$(BUILDER_WORK)"

.PHONY: builder-models builder-models-result
builder-models:
	AWS_PROFILE=josezambrana python3 scripts/image_builder_ops.py models --work "$(BUILDER_WORK)"
builder-models-result:
	AWS_PROFILE=josezambrana python3 scripts/image_builder_ops.py models-result --work "$(BUILDER_WORK)"

.PHONY: builder-permissions-apply
builder-permissions-apply:
	python3 -c 'import json; p=json.load(open("$(BUILDER_WORK)/plan.json")); r=[x for x in p["resource_changes"] if x["mode"]=="managed" and x["change"]["actions"]!=["no-op"]]; assert len(r)==1 and r[0]["address"]=="aws_iam_role_policy.artifacts" and r[0]["change"]["actions"]==["update"], "Plan inesperado"'
	$(BUILDER_TF) apply -input=false "$(BUILDER_WORK)/builder.tfplan"

.PHONY: builder-publish-models builder-publish-models-result
builder-publish-models:
	AWS_PROFILE=josezambrana python3 scripts/image_builder_ops.py publish-models --work "$(BUILDER_WORK)"
builder-publish-models-result:
	AWS_PROFILE=josezambrana python3 scripts/image_builder_ops.py publish-models-result --work "$(BUILDER_WORK)"

.PHONY: builder-artifact-lock
builder-artifact-lock:
	$(TERRAFORM) -chdir=terraform/model_artifact providers lock -platform=linux_amd64 -platform=darwin_arm64
