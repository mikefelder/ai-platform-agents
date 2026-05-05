# AWS Bedrock Agent Gateway

> AWS-side implementation of the [Unified AI Platform Accelerator](../docs/uaip_solution_architecture.md).
> Exposes Amazon Bedrock agents to the Azure supervisor via the async invoke + poll MCP contract.

Pairs with the Azure-hosted [`supervisor-agent`](../uaip-workload-uc2-supervisor-agent/README.md) and conforms to the contract defined in [`docs/aws_handoff_bedrock_agents_gateway.md`](../docs/aws_handoff_bedrock_agents_gateway.md).

---

## What this is

A serverless gateway that exposes Amazon Bedrock agents to the Azure supervisor via the **async invoke + poll** MCP contract:

```
Azure supervisor (APIM)
    │  POST /agents/{agentName}/invoke   (MCP envelope, traceparent)
    ▼
+----------------------------------------------------------+
|             AWS Agent Gateway (this repo)                |
|                                                          |
|   API Gateway (HTTP API)                                 |
|     POST /agents/{agentName}/invoke ─► invoke Lambda     |
|     GET  /executions/{executionId}  ─► status Lambda     |
|     GET  /health                    ─► health Lambda     |
|                                                          |
|   invoke Lambda                                          |
|     ├─ writes execution record to DynamoDB               |
|     ├─ async-invokes executor Lambda                     |
|     └─ returns 202 { executionId, status: "accepted" }   |
|                                                          |
|   executor Lambda (async)                                |
|     ├─ marks running                                     |
|     ├─ calls Bedrock (AgentCore | Bedrock Agent | Converse fallback) |
|     ├─ writes result + telemetry to DynamoDB             |
|     └─ marks completed | failed                          |
|                                                          |
|   status Lambda                                          |
|     └─ reads DynamoDB, returns ExecutionResult           |
|                                                          |
|   OpenTelemetry SDK ─► Azure Monitor (or APIM-fronted    |
|                        OTLP collector — env-configurable)|
+----------------------------------------------------------+
```

## File layout

```
uaip-bedrock-agent/
├── openapi.yaml                       Canonical AWS Agent Gateway contract
├── Makefile                           Build / Terraform / smoke targets
├── infra/
│   ├── terraform.tf                   Providers, default tags
│   ├── variables.tf                   All inputs (region, Bedrock target, OIDC, OTEL)
│   ├── main.tf                        DDB + Lambda packaging + 4 Lambdas
│   ├── api_gateway.tf                 HTTP API v2, routes, integrations
│   ├── iam.tf                         Roles + Entra OIDC federation scaffold
│   ├── outputs.tf                     gateway_base_url, role ARNs
│   └── terraform.tfvars.example       Copy to terraform.tfvars and edit
├── scripts/
│   └── build_lambda.sh                Pip-installs deps for python3.12/manylinux
└── services/
    └── gateway/
        ├── pyproject.toml
        ├── requirements.txt           Pinned runtime deps (used in Lambda zip)
        └── src/gateway/
            ├── common.py              DDB client, telemetry init, traceparent helpers
            ├── invoke_handler.py      POST /agents/{name}/invoke
            ├── status_handler.py      GET  /executions/{id}
            ├── executor_handler.py    Async Bedrock executor (3 modes)
            └── health_handler.py      GET /health
```

## Bedrock execution modes

The executor Lambda picks the most specific configured target (selection happens per-request):

| Mode               | Trigger                                               | API used                                         |
|--------------------|-------------------------------------------------------|--------------------------------------------------|
| AgentCore runtime  | `BEDROCK_AGENT_RUNTIME_ARN` set                       | `bedrock-agentcore.InvokeAgentRuntime`           |
| Bedrock Agent      | `BEDROCK_AGENT_ID` + `BEDROCK_AGENT_ALIAS_ID` set     | `bedrock-agent-runtime.InvokeAgent`              |
| **Converse fallback (default)** | none of the above                          | `bedrock-runtime.Converse` (Claude Haiku)        |

The fallback exists so a brand-new AWS account can demonstrate the full async contract end-to-end with no prior Bedrock provisioning. You only need to enable model access for `anthropic.claude-3-haiku-20240307-v1:0` in the Bedrock console.

To upgrade to a real AgentCore runtime later, build a runtime container, push it, run `aws bedrock-agentcore create-agent-runtime ...`, and set `bedrock_agent_runtime_arn` in `terraform.tfvars`. No code changes required.

## Telemetry → Azure

OpenTelemetry traces are exported using the same `APPLICATIONINSIGHTS_CONNECTION_STRING` pattern as the Azure supervisor (see [supervisor `otel.py`](../uaip-workload-uc2-supervisor-agent/services/supervisor-api/src/supervisor_api/telemetry/otel.py)). Two transport options:

1. **Direct (recommended for PoC):** Set `application_insights_connection_string` in `terraform.tfvars`. The Lambda uses `azure-monitor-opentelemetry-exporter` to ship spans directly to the App Insights ingestion endpoint over HTTPS.
2. **Via APIM-fronted OTLP collector:** Set `otel_exporter_otlp_endpoint` (and optional `otel_exporter_otlp_headers` for an APIM subscription key) — useful once you stand up an OTEL Collector behind APIM that forwards to Application Insights. APIM itself does not natively ingest OTLP, so it always sits in front of a collector.

Either way, the W3C `traceparent` from the supervisor is honoured, so the AWS spans appear under the same trace as the Azure root span (`use-case-2.workflow`).

## Identity (Entra ID → AWS)

The Terraform scaffolds an IAM OIDC provider trusting `https://login.microsoftonline.com/{tenant_id}/v2.0` plus an IAM role (`uaip-bedrock-entra-federated`) the supervisor can assume via `sts:AssumeRoleWithWebIdentity`. The role grants `execute-api:Invoke` against the gateway only.

`entra_tenant_id` and `entra_application_id` default to empty so the first `terraform apply` succeeds in a brand-new account without Azure-side coordination. Populate them once the supervisor's app registration exists, then re-apply. For initial bring-up you can use `gateway_static_bearer` instead — set both Azure and AWS to the same token.

## Quick start (brand-new AWS account)

```bash
# 1. AWS credentials (any of: aws sso login, env vars, ~/.aws/credentials)
aws sts get-caller-identity --region ap-southeast-2

# 2. Enable Bedrock model access for the fallback model
#    Console → Bedrock → Model access → enable
#      "Anthropic Claude 3 Haiku" in ap-southeast-2

# 3. Configure
cp infra/terraform.tfvars.example infra/terraform.tfvars
#    Edit application_insights_connection_string to point at the UC2 App Insights

# 4. Deploy
make tf-init
make tf-apply

# 5. Smoke-test
make smoke-health
make smoke-invoke
```

The `smoke-invoke` target POSTs an MCP envelope identical to what the Azure supervisor sends, then polls `/executions/{id}` until completion. The returned shape matches section 4.3.3 of the handoff spec.

## Wiring the Azure supervisor

Set the following in the supervisor's environment (or per-request body):

```env
DEFAULT_BEDROCK_PROXY_URL=https://<api-id>.execute-api.ap-southeast-2.amazonaws.com
DEFAULT_BEDROCK_AGENTS=compliance,safety
DEFAULT_BEDROCK_GATEWAY_MODE=async
```

Get the URL from `make tf-output`. The supervisor's existing async path (`bedrock_proxy_agent.py::_run_async`) works unmodified.

## Notes / limitations

- Static bearer auth is intentionally weak; replace with the OIDC-federated role before any non-PoC use.
- DynamoDB records expire after 7 days via TTL on `expiresAt`.
- The Lambda zip pins `python3.12` / `manylinux2014_x86_64` wheels; build host needs `python3` + `pip` reachable from the shell.
- Bedrock agent quotas in a new account default to low values; request a service-limit increase before load testing.
- Secrets (`gateway_static_bearer`, `application_insights_connection_string`, `otel_exporter_otlp_headers`) flow into Lambda env vars in plaintext. Move them to Secrets Manager or SSM Parameter Store for production.
