# Multi-Agent Supervisor

> A multi-agent orchestrator that coordinates specialized agents across Azure and AWS using dynamic multi-selection routing with concurrent execution.
> Part of the [Unified AI Platform Accelerator](../docs/uaip_solution_architecture.md).

---

## Overview

The Supervisor Agent orchestrates complex queries by dispatching them to specialized agents running in parallel, then synthesizing a unified response. It demonstrates **cross-cloud multi-agent orchestration**, **centralized governance**, and **end-to-end observability**.

Built on the **Microsoft Agent Framework SDK** using `WorkflowBuilder` for fan-out/fan-in orchestration, with declarative agent configuration via `agents.yaml`.

> **April 2026 stack consolidation:** The legacy FastAPI "v1" service, mock proxies, and `Dockerfile.v2` / `requirements.v2.txt` files have been deleted. The repo now ships a single Agent Framework SDK supervisor on `python:3.12-slim`, port 8088. Image tag is `uc2-supervisor-api:v$(VERSION)` (currently `v0.2.0`) plus a `sha-<git7>` audit tag, both produced by `make acr-build`.

### Key Capabilities

- **Dynamic multi-selection routing** — Supervisor plans which agents to invoke; only relevant agents execute concurrently
- **Declarative agent configuration** — agent definitions, instructions, tools, and models in `agents.yaml`
- **Cross-cloud execution** — Azure OpenAI + AWS Bedrock agents in the same workflow
- **Multi-model orchestration** — gpt-4.1 (planning), gpt-4.1-mini (retrieval), o4-mini (compliance reasoning)
- **OpenAI Responses API** — standard protocol via `ResponsesHostServer`
- **OIDC federation** — Entra ID ↔ AWS IAM for cross-cloud auth (no static credentials)

---

## Architecture

```
┌────────────────────────────────────────────────────────────────────────────┐
│                          Azure AI Landing Zone                             │
│                                                                            │
│  ┌──────────┐     ┌─────────────────────────────────────────────────────┐  │
│  │   APIM   │     │  Container App: ca-uc2-supervisor (port 8088)       │  │
│  │ /uc2/*   │────▶│                                                     │  │
│  └──────────┘     │  ┌──────────────────────────────────────────────┐   │  │
│                   │  │     WorkflowBuilder (Agent Framework SDK)    │   │  │
│                   │  │                                              │   │  │
│                   │  │  ┌─────────────┐                             │   │  │
│                   │  │  │ Supervisor  │  gpt-4.1 — Plans which      │   │  │
│                   │  │  │ (Planner)   │  agents to invoke           │   │  │
│                   │  │  └──────┬──────┘                             │   │  │
│                   │  │         │ multi-selection (concurrent)       │   │  │
│                   │  │    ┌────┼────────┬────────────┐              │   │  │
│                   │  │    ▼    ▼        ▼            ▼              │   │  │
│                   │  │ ┌─────┐┌────────┐┌─────────┐┌──────────┐     │   │  │
│                   │  │ │Know-││Compli- ││Engineer-││Governance│     │   │  │
│                   │  │ │ledge││ance    ││ing (AWS)││(     │     │   │  │
│                   │  │ │4.1m ││o4-mini ││gpt-4.1  ││gpt-4.1   │     │   │  │
│                   │  │ └──┬──┘└───┬────┘└────┬────┘└────┬─────┘     │   │  │
│                   │  │    │       │          │          │           │   │  │
│                   │  │    └───────┴────┬─────┴──────────┘           │   │  │
│                   │  │                │ fan-in                      │   │  │
│                   │  │         ┌──────┴──────┐                      │   │  │
│                   │  │         │ Aggregator  │  Merges responses    │   │  │
│                   │  │         └──────┬──────┘                      │   │  │
│                   │  │                ▼                             │   │  │
│                   │  │         ┌─────────────┐                      │   │  │
│                   │  │         │ Synthesizer │  gpt-4.1 — Unified   │   │  │
│                   │  │         │             │  response            │   │  │
│                   │  │         └─────────────┘                      │   │  │
│                   │  └──────────────────────────────────────────────┘   │  │
│                   └─────────────────────────────────────────────────────┘  │
│                                                                            │
│  Tool Backends:                                                            │
│  ├── Knowledge → RAG Agent (container-to-container, direct FQDN)              │
│  ├── Compliance → Azure OpenAI (o4-mini reasoning model, direct)           │
│  ├── External → AWS Agent Gateway (async invoke+poll, MCP contract)        │
│  └── Governance → Governance Hub (via APIM /governance/*)                   │
└────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ OIDC federation
                                    ▼
                    ┌───────────────────────────────────┐
                    │  AWS Agent Gateway (Lambda)       │
                    │  POST /agents/{name}/invoke → 202 │
                    │  GET  /executions/{id} → result   │
                    │  Claude Haiku 4.5 (Bedrock)       │
                    └───────────────────────────────────┘
```

### Agents (from `agents.yaml`)

| Agent | Model | Type | Role | Tools |
|-------|-------|------|------|-------|
| **Supervisor Agent** | gpt-4.1 | orchestrator | Plans which agents to invoke | — |
| **Knowledge Agent** | gpt-4.1-mini | native | Document retrieval (RAG) | `search_knowledge` |
| **Compliance Agent** | o4-mini | native | Safety & regulatory analysis (reasoning model) | `analyze_compliance` |
| **External Agent (Cross-Cloud)** | gpt-4.1 | external | Cross-cloud knowledge via AWS Bedrock (Claude Haiku 4.5) | `invoke_bedrock_agent` |
| **Governance Agent** | gpt-4.1 | native | Platform health, costs, traces | `query_governance_costs`, `query_governance_traces`, `query_agent_health` |
| **Synthesizer Agent** | gpt-4.1 | native | Merges all agent outputs into a coherent response | — |

### OpenTelemetry Span Attributes

All tools emit custom spans with these attributes for observability:

| Attribute | Example | Description |
|-----------|---------|-------------|
| `agent.name` | `Knowledge Agent` | Agent that owns this span |
| `agent.type` | `native` / `external` / `orchestrator` | Classification for cross-cloud visibility |
| `tool.name` | `search_knowledge` | Tool function name |
| `error` | `true` / `false` | Whether the operation failed |
| `cloud.provider` | `aws` | (Bedrock only) Cloud provider |
| `bedrock.execution_id` | `aws-exec-abc123` | (Bedrock only) Execution tracking ID |

### Azure Services

| Service | Resource | Purpose |
|---------|----------|---------|
| Azure Container Apps | `ca-uc2-supervisor` (min=2, max=4 replicas, `http-concurrency=50`) | Hosts the supervisor workflow; warm pool of 2 replicas eliminates cold-start during demos and parallel TC scripts |
| Azure OpenAI | gpt-4.1, gpt-4.1-mini, o4-mini | LLMs for orchestration, retrieval, reasoning |
| Azure API Management | `ai-alz-apim-i40e` | AI Gateway — routing, rate limiting, content safety |
| Application Insights | Supervisor workspace | Observability and OTEL telemetry |
| Azure Entra ID | App registrations | OIDC federation for AWS cross-cloud auth |

---

## API

```
POST /supervisor/responses    — Process query through multi-agent workflow (OpenAI Responses API)
GET  /supervisor/readiness    — Health check
```

### Example Request

```json
{
  "input": "What are the compliance requirements for our product specifications? Also check what the cross-cloud agent knows about this."
}
```

### Example Response Flow

1. **Supervisor** plans: "I will consult Knowledge, Compliance, and External agents"
2. **Knowledge** (concurrent): Searches AI Search for relevant specs
3. **Compliance** (concurrent): Analyzes applicable standards and requirements
4. **External** (concurrent): Invokes AWS agent for cross-cloud knowledge
5. **Synthesizer**: Merges all results with citations and standards references

---

## How It Works

### Workflow Execution

```
1. Request arrives at POST /supervisor/responses
2. WorkflowBuilder routes to Supervisor agent (gpt-4.1)
3. Supervisor generates a routing plan naming which agents to invoke
4. Selection function parses the plan and selects matching agents
5. Multi-selection: Only selected agents execute concurrently
   - Each agent calls its tools (AI Search, OpenAI, Bedrock, Governance API)
6. FanInAggregator collects responses from invoked agents
7. Aggregator formats responses as markdown sections with agent headers
8. Synthesizer merges into a single coherent response
9. Response returned via OpenAI Responses API format
```

### Declarative Configuration

Agent definitions live in `agents.yaml` — change agent behavior, instructions, or model assignments without modifying Python code:

```yaml
- name: Knowledge
  model: gpt-4.1-mini
  role: retrieval
  tools:
    - search_knowledge
  instructions: |
    You are the Knowledge Retrieval Agent...
```

---

## Project Structure

```
services/supervisor-api/
  main.py                  # WorkflowBuilder entrypoint + FanInAggregator
  agents.yaml              # Declarative agent definitions (incl. per-agent sla_timeout_seconds for TC-5)
  Dockerfile               # Container image (python:3.12-slim, port 8088)
  requirements.txt         # Python deps: agent-framework, agent-framework-foundry-hosting, azure-identity, ...
  tools/
    knowledge.py           # RAG search via APIM
    compliance.py          # Azure OpenAI compliance analysis (o4-mini)
    bedrock.py             # AWS Bedrock async invoke+poll (MCP contract)
    governance.py          # Governance queries via APIM
    sla.py                 # Per-agent SLA timeout wrapper (TC-5) — emits agent.sla_breach OTEL events
    validators.py          # Monitoring (TC-4) + Diagnostic (TC-6) post-aggregation validators
  tests/
    test_tc5_sla.py        # 9 tests covering timeout, breach event emission, deterministic timeout response
    test_tc4_tc6_validators.py  # 8 tests for Monitoring + Diagnostic validators (TC-4, TC-6)

infra/                     # Terraform deployment
  main.container_app.tf    # Container App (port 8088, /readiness probes)
  main.apim.tf             # APIM routes (/supervisor/responses, /supervisor/readiness)
  main.identity.tf         # UAMI + RBAC (OpenAI User, AcrPull)
  main.entra.tf            # Entra ID app registrations for OIDC federation
  data.tf                  # Data sources for ALZ resources
  terraform.tfvars.msdn    # MSDN PoC configuration
```

---

## Getting Started

### Prerequisites

- Azure subscription with AI Landing Zone deployed
- RAG RAG Agent deployed and healthy
- Governance Governance Hub deployed and healthy
- AWS Bedrock Gateway deployed (optional for non-cross-cloud testing)
- Azure CLI, Terraform >= 1.9, Python 3.12+

### 1. Build and Push Container Image

Use the `Makefile` target (recommended) — it stamps `v$(VERSION)` from `VERSION` plus a `sha-<git7>` audit tag and toggles the ACR firewall:

```bash
make acr-build           # builds genaicri40e.azurecr.io/uc2-supervisor-api:v0.2.0 + :sha-<git7>
make acr-build-deploy    # build + containerapp update in one step
```

Manual fallback:

```bash
az acr update -n genaicri40e --default-action Allow

az acr build --registry genaicri40e \
  --image uc2-supervisor-api:v0.2.0 \
  --file services/supervisor-api/Dockerfile ./services/supervisor-api

az acr update -n genaicri40e --default-action Deny
```

### 2. Deploy Infrastructure

```bash
cd infra
terraform init
terraform workspace select msdn
terraform plan -var-file=terraform.tfvars.msdn -out=tfplan
terraform apply tfplan
```

### 3. Deploy New Image

```bash
az containerapp update -n ca-uc2-supervisor -g ai-lz-rg-msdn-mb44x \
  --image genaicri40e.azurecr.io/uc2-supervisor-api:v0.2.0
```

### 4. Lock ACR and Verify Deployment

```bash
az acr update -n genaicri40e --default-action Deny
```

```bash
az containerapp revision list -n ca-uc2-supervisor \
  -g ai-lz-rg-msdn-mb44x \
  --query "[?properties.active].{name:name,health:properties.healthState}" -o table
```

---

## AWS Bedrock Integration

The supervisor invokes AWS Bedrock agents via MCP-shaped JSON over HTTPS:

```
POST /agents/{agentName}/invoke  → 202 + executionId
GET  /executions/{executionId}   → poll for completion
```

Authentication uses Entra ID OIDC federation — the supervisor's managed identity acquires a bearer token scoped to the federation app registration. See the [AWS Handoff Specification](../docs/aws_handoff_bedrock_agents_gateway.md) for the full API contract.

---

## Observability

- **OpenTelemetry** traces via Agent Framework SDK `ObservabilitySettings`
- **W3C traceparent** propagated to AWS for cross-cloud trace correlation
- **Azure Monitor** exporters ship traces, logs, and metrics
- **Tool-call transparency** — every tool invocation visible in Responses API output

---

## Security & Guardrails

| Control | Implementation |
|---------|---------------|
| Azure OpenAI auth | User-Assigned Managed Identity |
| AWS Bedrock auth | OIDC federation (Entra ID → AWS IAM) |
| API access control | APIM subscription key required |
| Network isolation | VNet-integrated CAE (internal load balancer) |
| Cross-cloud identity | No static credentials — OIDC tokens only |
| Content safety | APIM policy blocks prompt injection patterns at the gateway |
| Rate limiting | APIM enforces 20 requests/minute per subscription |
| Per-agent SLA (TC-5) | `sla_timeout_seconds` per agent in `agents.yaml`; tools wrapped via `tools/sla.py` with `asyncio.wait_for`. On timeout the workflow records an OTEL `agent.sla_breach` event (consumed by Sentinel rule **Agent SLA Breach**) and returns a deterministic timeout response. |
| Monitoring validator (TC-4) | `tools/validators.py::MonitoringValidator` runs in `FanInAggregator`. When the user prompt contains monitoring keywords/triggers (latency, p95, throughput, SLA, dashboard, ...), the combined response is scanned for telemetry signals — emits `MON_MISSING_METRICS` (warning) when no metrics surface, `MON_METRICS_PRESENT` (info) when they do, `MON_NOT_REQUIRED` otherwise. Findings appended as a `## Validation Report` block; OTEL span attrs `validators.count` / `validators.passed`. |
| Diagnostic validator (TC-6) | `tools/validators.py::DiagnosticValidator` token-overlaps the user prompt against a curated `_HISTORICAL_INCIDENTS` corpus (HIST-2024-0142, HIST-2024-0207, HIST-2024-0318, HIST-2025-0011). Top-3 matches above threshold emit `DIAG_MATCH` findings (info) referencing prior incident IDs and root causes; otherwise `DIAG_NO_MATCH`. Validators are wrapped in try/except so failures never break the workflow. |
| Observability logging | APIM outbound policy logs request metadata, latency, and trace IDs for FinOps governance |

---

## Reference Architecture

This implementation follows the [Microsoft Multi-Agent Reference Architecture](https://microsoft.github.io/multi-agent-reference-architecture/):

| Pattern | Implementation |
|---------|---------------|
| Dynamic multi-selection orchestration | `WorkflowBuilder.add_multi_selection_edge_group()` with keyword-based routing |
| Declarative agent definitions | `agents.yaml` with roles, models, tools, boundaries |
| Specialized agents | Each agent has domain-specific tools and instructions |
| Cross-cloud execution | AWS Bedrock via MCP async contract |
| Unified observability | OTEL + W3C traceparent across Azure and AWS |
| AI Gateway | APIM for centralized routing and governance |
