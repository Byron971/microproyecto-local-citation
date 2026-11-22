QLORA_TOOLS ?= /private/tmp/maiag19-tools-$(shell id -u)
QLORA_PLUGIN := $(QLORA_TOOLS)/bin
.PHONY: qlora-session-plugin qlora-auth-tunnel
qlora-session-plugin:
	@test ! -L "$(QLORA_TOOLS)"
	mkdir -p "$(QLORA_TOOLS)/bin"
	chmod 700 "$(QLORA_TOOLS)"
	curl -fL --connect-timeout 10 --max-time 180 https://s3.amazonaws.com/session-manager-downloads/plugin/latest/mac_arm64/sessionmanager-bundle.zip -o "$(QLORA_TOOLS)/bundle.zip"
	unzip -oq "$(QLORA_TOOLS)/bundle.zip" -d "$(QLORA_TOOLS)"
	python3 "$(QLORA_TOOLS)/sessionmanager-bundle/install" -i "$(QLORA_TOOLS)/plugin" -b "$(QLORA_PLUGIN)/session-manager-plugin"
	"$(QLORA_PLUGIN)/session-manager-plugin" --version
qlora-auth-tunnel:
	PATH="$(QLORA_PLUGIN):$$PATH" AWS_PROFILE=josezambrana aws ssm start-session --region us-east-1 --target $$($(BUILDER_TF) output -raw instance_id) --document-name AWS-StartPortForwardingSession --parameters '{"portNumber":["53682"],"localPortNumber":["53682"]}'

.PHONY: qlora-auth-start qlora-auth-status
qlora-auth-start:
	AWS_PROFILE=josezambrana python3 scripts/image_builder_ops.py qlora-auth --work "$(BUILDER_WORK)"
qlora-auth-status:
	AWS_PROFILE=josezambrana python3 scripts/image_builder_ops.py qlora-auth-result --work "$(BUILDER_WORK)"

.PHONY: qlora-auth-check qlora-auth-check-result
qlora-auth-check:
	AWS_PROFILE=josezambrana python3 scripts/image_builder_ops.py qlora-check --work "$(BUILDER_WORK)"
qlora-auth-check-result:
	AWS_PROFILE=josezambrana python3 scripts/image_builder_ops.py qlora-check-result --work "$(BUILDER_WORK)"

.PHONY: qlora-browser-start qlora-browser-status qlora-browser-tunnel
qlora-browser-start:
	AWS_PROFILE=josezambrana python3 scripts/image_builder_ops.py qlora-browser --work "$(BUILDER_WORK)"
qlora-browser-status:
	AWS_PROFILE=josezambrana python3 scripts/image_builder_ops.py qlora-browser-result --work "$(BUILDER_WORK)"
qlora-browser-tunnel:
	PATH="$(QLORA_PLUGIN):$$PATH" AWS_PROFILE=josezambrana aws ssm start-session --region us-east-1 --target $$($(BUILDER_TF) output -raw instance_id) --document-name AWS-StartPortForwardingSession --parameters '{"portNumber":["6080"],"localPortNumber":["6080"]}'

.PHONY: qlora-browser-verify qlora-browser-verify-result
qlora-browser-verify:
	AWS_PROFILE=josezambrana aws ssm send-command --region us-east-1 --instance-ids $$($(BUILDER_TF) output -raw instance_id) --document-name AWS-RunShellScript --parameters 'commands=["pgrep -u ubuntu -f firefox >/dev/null && echo FIREFOX_RUNNING; ss -lnt | awk '\''NR==1 || /127.0.0.1:6080|127.0.0.1:5900/'\''"]' --query 'Command.CommandId' --output text > "$(BUILDER_WORK)/browser-verify-command.txt"
qlora-browser-verify-result:
	AWS_PROFILE=josezambrana aws ssm get-command-invocation --region us-east-1 --instance-id $$($(BUILDER_TF) output -raw instance_id) --command-id "$$(cat "$(BUILDER_WORK)/browser-verify-command.txt")" --query '{Status:Status,Output:StandardOutputContent}'

.PHONY: qlora-files qlora-files-result
qlora-files:
	AWS_PROFILE=josezambrana python3 scripts/image_builder_ops.py qlora-files --work "$(BUILDER_WORK)"
qlora-files-result:
	AWS_PROFILE=josezambrana python3 scripts/image_builder_ops.py qlora-files-result --work "$(BUILDER_WORK)"

.PHONY: qlora-audit qlora-audit-result
qlora-audit:
	AWS_PROFILE=josezambrana python3 scripts/image_builder_ops.py qlora-audit --work "$(BUILDER_WORK)"
qlora-audit-result:
	AWS_PROFILE=josezambrana python3 scripts/image_builder_ops.py qlora-audit-result --work "$(BUILDER_WORK)"

.PHONY: qlora-metadata qlora-metadata-result
qlora-metadata:
	AWS_PROFILE=josezambrana python3 scripts/qlora_metadata_ops.py send --work "$(BUILDER_WORK)"
qlora-metadata-result:
	AWS_PROFILE=josezambrana python3 scripts/qlora_metadata_ops.py result --work "$(BUILDER_WORK)"

.PHONY: qlora-base qlora-base-result
qlora-base:
	AWS_PROFILE=josezambrana python3 scripts/qlora_base_ops.py send --work "$(BUILDER_WORK)"
qlora-base-result:
	AWS_PROFILE=josezambrana python3 scripts/qlora_base_ops.py result --work "$(BUILDER_WORK)"
