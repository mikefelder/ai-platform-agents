# AWS Bedrock Agent Gateway
#
# Conventions match the Azure-side supervisor repo.

SHELL := /bin/bash
.DEFAULT_GOAL := help

INFRA_DIR := infra
GATEWAY_DIR := services/gateway

AWS_REGION ?= ap-southeast-2

# ---------------------------------------------------------------------------
# Help
# ---------------------------------------------------------------------------

.PHONY: help
help:
	@echo "AWS Bedrock Agent Gateway"
	@echo ""
	@echo "Setup:"
	@echo "  make install               Install local dev deps for the gateway"
	@echo "  make build                 Build Lambda deployment zip"
	@echo ""
	@echo "Terraform:"
	@echo "  make tf-init               terraform init"
	@echo "  make tf-plan               terraform plan"
	@echo "  make tf-apply              terraform apply"
	@echo "  make tf-destroy            terraform destroy"
	@echo "  make tf-output             show outputs (gateway URL, etc.)"
	@echo ""
	@echo "Smoke tests:"
	@echo "  make smoke-health          curl GET /health"
	@echo "  make smoke-invoke          POST /agents/compliance/invoke + poll"
	@echo ""

# ---------------------------------------------------------------------------
# Local dev / build
# ---------------------------------------------------------------------------

.PHONY: install
install:
	cd $(GATEWAY_DIR) && python3 -m venv .venv && \
	  .venv/bin/pip install --upgrade pip && \
	  .venv/bin/pip install -e ".[dev]"

.PHONY: build
build:
	./scripts/build_lambda.sh

.PHONY: clean
clean:
	rm -rf $(GATEWAY_DIR)/build

# ---------------------------------------------------------------------------
# Terraform
# ---------------------------------------------------------------------------

.PHONY: tf-init tf-plan tf-apply tf-destroy tf-output

tf-init:
	cd $(INFRA_DIR) && terraform init

tf-plan:
	cd $(INFRA_DIR) && terraform plan

tf-apply:
	cd $(INFRA_DIR) && terraform apply

tf-destroy:
	cd $(INFRA_DIR) && terraform destroy

tf-output:
	cd $(INFRA_DIR) && terraform output

# ---------------------------------------------------------------------------
# Smoke tests (require `make tf-output` to have a gateway URL)
# ---------------------------------------------------------------------------

GATEWAY_URL ?= $(shell cd $(INFRA_DIR) && terraform output -raw gateway_base_url 2>/dev/null)
TRACEPARENT ?= 00-$(shell python3 -c 'import secrets;print(secrets.token_hex(16))')-$(shell python3 -c 'import secrets;print(secrets.token_hex(8))')-01

.PHONY: smoke-health
smoke-health:
	@test -n "$(GATEWAY_URL)" || (echo "GATEWAY_URL not set; run 'make tf-apply' first" && exit 1)
	curl -sS "$(GATEWAY_URL)/health" | jq .

.PHONY: smoke-invoke
smoke-invoke:
	@test -n "$(GATEWAY_URL)" || (echo "GATEWAY_URL not set" && exit 1)
	@echo "==> POST /agents/compliance/invoke"
	@RESP=$$(curl -sS -X POST "$(GATEWAY_URL)/agents/compliance/invoke" \
	    -H "Content-Type: application/json" \
	    -H "traceparent: $(TRACEPARENT)" \
	    -d '{"mcpVersion":"1.0","traceparent":"$(TRACEPARENT)","invocation":{"invocationId":"inv-smoke","parentAgent":"makefile","targetAgent":"compliance","async":true},"input":{"taskType":"general","payload":{"query":"Summarise the safety compliance status."}}}'); \
	echo "$$RESP" | jq .; \
	EXEC_ID=$$(echo "$$RESP" | jq -r .executionId); \
	echo "==> Polling /executions/$$EXEC_ID"; \
	for i in 1 2 3 4 5 6 7 8 9 10 15 20 25 30; do \
	  STATUS=$$(curl -sS "$(GATEWAY_URL)/executions/$$EXEC_ID" | tee /tmp/exec.json | jq -r .status); \
	  echo "  attempt $$i: status=$$STATUS"; \
	  if [ "$$STATUS" = "completed" ] || [ "$$STATUS" = "failed" ]; then break; fi; \
	  sleep 2; \
	done; \
	cat /tmp/exec.json | jq .
