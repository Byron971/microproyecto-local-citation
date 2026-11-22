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
