# Unified AI Platform — Solution Architecture

> A multi-cloud, multi-agent AI platform built on Microsoft Azure with AWS cross-cloud integration.
> Demonstrates centralized governance, observability, and intelligent orchestration across cloud boundaries.

---

## Platform Overview

The Unified AI Platform is an enterprise AI orchestration platform that centralizes model access, agent coordination, governance, and monitoring across Azure and AWS. It enables users to query engineering knowledge bases, receive compliance analysis, and leverage cross-cloud AI capabilities through a single conversational interface.

### Design Principles

- **Centralized governance** — Single control plane for AI access, policy enforcement, and cost tracking
- **Multi-cloud interoperability** — Azure as orchestration hub, AWS as distributed agent execution environment
- **Identity-based access** — Managed identity and OIDC federation, no shared credentials
- **OpenTelemetry-native** — Unified observability across all agents and clouds
- **Agent Framework SDK** — Microsoft's standard for building, hosting, and orchestrating AI agents

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                            Azure AI Landing Zone                                │
│                                                                                 │
│  ┌───────────────────────────────────────────────────────────────────────────┐  │
│  │                    Azure API Management (AI Gateway)                      │  │
│  │  /uc1/*  → UC1 RAG Agent       Rate limiting, content safety,            │   │
│  │  /uc2/*  → UC2 Supervisor       prompt injection detection,              │   │
│  │  /uc3/*  → UC3 Governance       W3C traceparent injection,               │   │
│  │  /otel/* → OTEL Collector       request logging for FinOps               │   │
│  └─────────────────────────────┬─────────────────────────────────────────────┘  │
│                                │                                                │
│  ┌─────────────────────────────┼─────────────────────────────────────────────┐  │
│  │         Azure Container Apps Environment (Internal ILB)                   │  │
│  │                                                                           │  │
│  │  ┌─────────────────┐  ┌─────────────────────────────────────────────┐    │   │
│  │  │  UC1 RAG Agent  │  │  UC2 Supervisor Agent                      │    │    │
  │  │  gpt-4.1-mini   │  │  (Agent Framework SDK, port 8088)          │    │     │
  │  │  AI Search tool │  │  ┌───────────┐     Fan-out (concurrent)    │    │     │
  │  │  internal-only  │  │  │ Supervisor │──┬──┬──┬──┐                │    │     │
  │  │  Port 8088      │  │  │  gpt-4.1   │  │  │  │  │                │    │     │
  │  └─────────────────┘  │  └───────────┘  │  │  │  │                │    │      │
  │                        │   ┌──────┐ ┌────┴┐┌┴───┐┌┴────────┐      │    │      │
  │  ┌─────────────────┐  │   │Know- │ │Comp-││Bed- ││Governan-│      │    │      │
  │  │  UC3 Governance │  │   │ledge │ │lianc││rock ││ce       │      │    │      │
  │  │  FastAPI :8000  │  │   │4.1m  │ │o4-m ││AWS  ││gpt-4.1  │      │    │      │
│  │  │  9 API routers  │  │   └──┬───┘ └──┬──┘└──┬──┘└──┬──────┘      │    │     │
│  │  └─────────────────┘  │      └────────┴───┬──┴──────┘              │    │    │
│  │                        │           ┌──────┴──────┐                  │    │   │
│  │  ┌─────────────────┐  │           │ Aggregator  │                  │    │    │
│  │  │  OTEL Collector │  │           └──────┬──────┘                  │    │    │
│  │  │  Port 4318      │  │           ┌──────┴──────┐                  │    │    │
│  │  │  OTLP/HTTP      │  │           │ Synthesizer │                  │    │    │
│  │  └─────────────────┘  │           │  gpt-4.1    │                  │    │    │
│  │                        │           └─────────────┘                  │    │   │
│  │  ┌─────────────────┐  │            Port 8088                       │    │    │
│  │  │  Frontend       │  └─────────────────────────────────────────────┘    │   │
│  │  │  React/nginx    │                                                     │   │
│  │  │  Port 8080      │                                                     │   │
│  │  └─────────────────┘                                                     │   │
│  └───────────────────────────────────────────────────────────────────────────┘  │
│                                                                                 │
│  ┌──────────────┐ ┌──────────────┐ ┌───────────┐ ┌────────────────────────┐     │
│  │Azure OpenAI  │ │Azure AI      │ │ Cosmos DB │ │ Log Analytics          │     │
│  │gpt-4.1      │ │Search        │ │ Incidents │ │ ┌────────────────────┐ │      │
│  │gpt-4.1-mini │ │knowledge-   │ │ Workflows │ │ │Microsoft Sentinel │ │       │
│  │o4-mini      │ │docs (6 docs) │ │           │ │ │5 analytics rules  │ │       │
│  └──────────────┘ └──────────────┘ └───────────┘ │ └────────────────────┘ │     │
│                                                    │ App Insights (×3 UCs) │    │
│  ┌──────────────┐ ┌──────────────┐ ┌───────────┐ │ FinOps Workbook       │      │
│  │ ACR          │ │ Service Bus  │ │Event Grid │ └────────────────────────┘     │
│  │ genaicri40e  │ │ Incidents    │ │ Triggers  │                                │
│  └──────────────┘ └──────────────┘ └───────────┘                                │
└─────────────────────────┬───────────────────────────────────────────────────────┘
                          │ OIDC Federation (Entra ID ↔ AWS IAM)
                          ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                          AWS (ap-southeast-2)                                   │
│                                                                                 │
│  ┌──────────────────────────────────────────────────────────────┐               │
│  │  AWS Agent Gateway (Serverless)                              │               │
│  │  API Gateway → Lambda Functions → DynamoDB                   │               │
│  │                                                              │               │
│  │  POST /agents/{name}/invoke  → 202 Accepted + executionId   │                │
│  │  GET  /executions/{id}       → Poll for completion           │               │
│  │  GET  /health                → Health check                  │               │
│  │                                                              │               │
│  │  Bedrock: Claude Haiku 4.5 (fallback model)                 │                │
│  │  OTEL → Azure Monitor (same trace as Azure spans)           │                │
│  └──────────────────────────────────────────────────────────────┘               │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## Repositories

| Repository | Description | Stack |
|-----------|-------------|-------|
| [`uaip-workload-uc1-rag-agent`](https://github.com/{your-org}/ai-platform-agents) | RAG Knowledge Assistant — searches engineering docs, generates cited responses | Agent Framework SDK, Azure AI Search, gpt-4.1-mini |
| [`uaip-workload-uc2-supervisor-agent`](https://github.com/{your-org}/ai-platform-agents) | Multi-Agent Supervisor — fan-out/fan-in orchestration across 4 agents | Agent Framework SDK WorkflowBuilder, agents.yaml |
| [`uaip-workload-uc3-governance-hub`](https://github.com/{your-org}/ai-platform-governance) | Governance & Monitoring Hub — observability, costs, policies, incidents | FastAPI, OTEL Collector, Sentinel, Cosmos DB |
| [`uaip-frontend`](https://github.com/{your-org}/ai-platform-frontend) | Unified AI Platform Frontend — Chat + Agent Flow visualization | React 19, TypeScript, React Flow, nginx |
| [`uaip-bedrock-agent`](https://github.com/{your-org}/ai-platform-agents) | AWS Bedrock Agent Gateway — async invoke+poll MCP contract | AWS Lambda, API Gateway, DynamoDB, Bedrock |
| [`azure-ai-landing-zone-terraform`](https://github.com/{your-org}/azure-ai-landing-zone) | Azure AI Landing Zone — foundational infrastructure | Terraform AVM, VNet, APIM, ACR, CAE, AI Services |

---

## Use Cases

### UC1 — RAG Knowledge Assistant

**Purpose:** Answer natural language questions using the organization's internal engineering document corpus.

**How it works:**
1. User query arrives via Chat UI or Responses API
2. Agent Framework invokes gpt-4.1-mini
3. LLM calls `search_engineering_docs` tool → Azure AI Search (hybrid semantic)
4. AI Search returns ranked document chunks from `knowledge-base-docs` index (6 documents)
5. LLM generates cited response with standards references
6. Response returned via OpenAI Responses API format

**Key artifacts:**
- `services/rag-agent/main.py` — Agent Framework entrypoint
- `services/rag-agent/tools/search.py` — AI Search hybrid query tool
- `agents.yaml` via Foundry descriptor pattern
- 6 mock engineering documents (valve specs, safety reports, contracts, instrument data sheets)

---

### UC2 — Multi-Agent Supervisor

**Purpose:** Orchestrate multiple specialized agents across Azure and AWS to fulfill complex requests.

**How it works:**
1. User request arrives at `POST /uc2/responses`
2. **Supervisor** (gpt-4.1) plans which agents to consult
3. **Fan-out:** 4 agents execute concurrently:
   - **Knowledge** (gpt-4.1-mini) — searches UC1 RAG via APIM
   - **Compliance** (o4-mini) — safety & regulatory analysis
   - **Bedrock** (Claude Haiku 4.5) — AWS cross-cloud retrieval via async MCP
   - **Governance** (gpt-4.1) — platform health, costs, traces via UC3
4. **Fan-in:** `FanInAggregator` (custom Executor) collects all responses
5. **Synthesizer** (gpt-4.1) merges into unified response with citations

**Stack consolidation (April 2026):** UC2 was previously a dual-stack repo (FastAPI "v1" + Agent Framework "v2" coexisting). The legacy FastAPI service, mock proxies, and `Dockerfile.v2` / `requirements.v2.txt` files have been deleted. The repo now ships a **single** Agent Framework SDK supervisor on `python:3.12-slim`, port 8088, with deps `agent-framework`, `agent-framework-foundry-hosting`, `azure-identity`, etc.

**Key artifacts:**
- `services/supervisor-api/main.py` — WorkflowBuilder with FanInAggregator
- `services/supervisor-api/agents.yaml` — Declarative agent definitions (6 agents)
- `services/supervisor-api/tools/` — 4 tool modules (knowledge, compliance, bedrock, governance)

**Agent configuration is declarative** — change agent behavior, models, or instructions by editing `agents.yaml` without modifying Python code.

---

### UC3 — Governance & Monitoring Hub

**Purpose:** Centralized governance, observability, cost tracking, SIEM, and incident management.

**Components:**
- **Governance API** (FastAPI, 9 routers) — costs, traces, health, policies, compliance, incidents, approvals, workflows, events
- **OTEL Collector** — receives OTLP/HTTP from all agents, normalizes, exports to Azure Monitor
- **Microsoft Sentinel** — 5 analytics rules for anomaly detection, security monitoring
- **FinOps Workbook** — 6-panel Azure Monitor dashboard (token consumption, agent performance, API traffic, cross-cloud metrics, content safety)
- **Incident Resolution** (UC4) — AI-driven triage via Azure OpenAI with rule-based fallback, human-in-the-loop approvals

**Key artifacts:**
- `services/governance-api/src/governance_api/` — FastAPI app with 9 routers
- `services/otel-collector/otel-collector-config.yaml` — OTEL Collector pipeline
- `infra/main.sentinel.tf` — 5 Sentinel analytics rules
- `infra/main.workbook.tf` — FinOps governance workbook
- `infra/main.monitor.tf` — APIM + Container App diagnostic settings

---

### UC4 — Incident Resolution (integrated into UC3)

**Purpose:** AI-driven incident management with human-in-the-loop approvals.

**How it works:**
1. Event triggers incident (`POST /api/incidents`)
2. AI triage agent (Azure OpenAI gpt-4.1-mini) classifies: severity, category, recommended action
3. Falls back to rule-based triage if AI unavailable
4. Human approvals via `POST /api/approvals/{id}/respond`
5. Resolution via `POST /api/incidents/{id}/resolve`
6. State persisted in Cosmos DB, events via Service Bus

**Triage categories:** `model_failure`, `latency_degradation`, `cost_anomaly`, `security_event`, `compliance_violation`, `infrastructure`

---

## Technology Stack

| Layer | Technology | Details |
|-------|-----------|---------|
| **Agent Framework** | Microsoft Agent Framework SDK 1.1.x | `WorkflowBuilder`, `Agent`, `FunctionTools`, `ResponsesHostServer` |
| **LLM Models** | Azure OpenAI | gpt-4.1 (orchestration), gpt-4.1-mini (retrieval), o4-mini (reasoning) |
| **Cross-Cloud LLM** | AWS Bedrock | Claude Haiku 4.5 (ap-southeast-2) |
| **API Protocol** | OpenAI Responses API | Standard protocol for all agents |
| **AI Gateway** | Azure API Management | Routing, rate limiting, content safety, trace injection, FinOps logging |
| **Search** | Azure AI Search | Hybrid semantic search, `knowledge-base-docs` index |
| **Compute (Azure)** | Azure Container Apps | Internal ILB, auto-scaling, managed identity |
| **Compute (AWS)** | AWS Lambda + API Gateway v2 | Serverless, DynamoDB state, async execution |
| **State** | Cosmos DB | Incident workflows, events, approvals |
| **Messaging** | Service Bus + Event Grid | Event-driven incident orchestration |
| **SIEM** | Microsoft Sentinel | 5 analytics rules, Log Analytics integration |
| **Observability** | OpenTelemetry | OTEL Collector → Azure Monitor, W3C traceparent |
| **Frontend** | React 19 + TypeScript + Vite | Chat UI, Agent Flow visualization (React Flow) |
| **IaC** | Terraform (AVM) | Azure AI Landing Zone module + per-UC infrastructure |
| **Cross-Cloud Auth** | Entra ID OIDC ↔ AWS IAM | Workload identity federation, no static credentials |
| **Container Registry** | Azure Container Registry | Private, firewall-controlled access |

---

## Security Controls

| Control | Implementation |
|---------|---------------|
| **Identity** | User-Assigned Managed Identity for all Azure services |
| **Caller identity** | Entra JWT validation on UC3 governance API (PyJWT/JWKS); `AUTH_MODE=required\|optional\|disabled`; caller `oid`/`upn`/roles captured on incidents and approvals (TC-1 / TC-9) |
| **Cross-cloud auth** | OIDC federation (Entra ID ↔ AWS IAM), no static credentials |
| **Network isolation** | VNet-integrated CAE (**internal** ILB 192.168.1.111), private endpoints, Bastion for jumpbox |
| **Zero-bypass gateway (TC-3)** | UC1 RAG `external_enabled=false` — only internal CAE FQDN exposed. APIM is the **only** ingress path. NSG `ai-alz-cae-nsg` on `ContainerAppEnvironmentSubnet` enforces `DenyJumpboxDirect` (priority 150, src `192.168.6.0/24`) so VNet-resident hosts cannot bypass APIM. Codified in `uaip-workload-uc1-rag-agent/infra/main.network.tf`. Verified by `uaip-workload-uc3-governance-hub/scripts/tc3.ps1` (3a/3b/3c PASS). **Note (Apr 30, 2026):** the two NSG `Deny*` rules are temporarily removed from the live `ai-alz-cae-nsg` for demo purposes; defense-in-depth design and Terraform code remain unchanged — reapply with `cd uaip-workload-uc1-rag-agent/infra && terraform apply` to restore. UC1 internal-only ingress alone keeps TC-3 3c green in the meantime. |
| **API access** | APIM subscription keys required for all endpoints |
| **Content safety** | APIM policies detect and block prompt injection patterns |
| **Rate limiting** | Per-subscription request quotas (UC1: 30/min, UC2: 20/min) |
| **AI Search** | Public network access disabled — private endpoints only |
| **ACR** | Default firewall deny — opened temporarily for builds only |
| **Audit trail** | APIM GatewayLogs → Log Analytics → Sentinel |
| **RBAC** | Least privilege: OpenAI User, AcrPull, Search Reader only |
| **Entra app roles** | `uaip-governance` app (`06bf98a1-d997-4a60-a616-3c384828f408`) defines `workflow-orchestrator`, `incident-commanders`, `senior-engineers`, `on-call` (codified in `uaip-workload-uc3-governance-hub/infra/main.entra.tf`) |
| **Secrets** | Zero hardcoded credentials — all auth via managed identity |

---

## Observability & Governance

### Telemetry Flow

```
Agents (Agent Framework SDK)
  │  ObservabilitySettings + Azure Monitor exporters
  ▼
Application Insights (×3 UCs)  ──→  Log Analytics Workspace
  │                                       │
  │  AWS Bedrock (OTEL SDK)               ▼
  │    └──→ App Insights (direct)    Microsoft Sentinel
  │         or APIM → OTEL Collector   • 5 analytics rules
  │                                    • Anomaly detection
  ▼                                    • Alerting
FinOps Workbook (Azure Monitor)
  • Agent performance
  • Token consumption by model
  • Daily usage trends
  • API gateway traffic
  • Cross-cloud metrics
  • Content safety summary
```

### Sentinel Analytics Rules

| Rule | Severity | Description |
|------|----------|-------------|
| Anomalous Token Consumption | Medium | Token spike > 3× rolling average |
| High Agent Failure Rate | High | Any agent > 20% failure rate in 15min |
| Content Safety Violations | High | Requests blocked by content safety policy |
| Repeated Rate Limit Breaches | Medium | > 10 429s per subscription in 5min |
| Cross-Cloud Latency Degradation | Medium | P95 on Bedrock/OCI calls > 5s |
| Agent SLA Breach (TC-5) | Medium | OTEL `agent.sla_breach` events surfaced from per-agent `sla_timeout_seconds` in `agents.yaml` |

---

## API Surface

### UC1 — RAG Agent (`/uc1/*`)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/uc1/responses` | Query knowledge base (Responses API) |
| `GET` | `/uc1/readiness` | Health check |

### UC2 — Supervisor (`/uc2/*`)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/uc2/responses` | Multi-agent orchestration (Responses API) |
| `GET` | `/uc2/readiness` | Health check |

### UC3 — Governance (`/uc3/*`)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/uc3/api/costs/summary` | Token & cost summary |
| `GET` | `/uc3/api/costs/by-agent` | Costs broken down by agent |
| `GET` | `/uc3/api/agents/health` | Agent health status |
| `GET` | `/uc3/api/agents/traces` | Agent trace queries |
| `GET/POST` | `/uc3/api/policies` | Governance policy CRUD |
| `GET` | `/uc3/api/policies/registry` | List enterprise policies |
| `GET` | `/uc3/api/policies/registry/{id}/active` | Active policy version |
| `GET` | `/uc3/api/policies/registry/{id}/versions` | Version history |
| `POST` | `/uc3/api/policies/registry/{id}/versions` | Publish new version (TC-2 — Entra caller identity required) |
| `GET` | `/uc3/api/policies/gateway/digest` | SHA-256 digest of shipped APIM policy sources (TC-2f) |
| `GET` | `/uc3/api/compliance/report` | Compliance report |
| `POST` | `/uc3/api/incidents` | Create incident (AI triage; embeds versioned `policy_applied` snapshot) |
| `POST` | `/uc3/api/incidents/{id}/approvals` | Per-incident approval (TC-2 Option A — binds approval to versioned snapshot) |
| `POST` | `/uc3/api/incidents/{id}/resolve` | Resolve incident |
| `POST` | `/uc3/api/approvals/{id}/respond` | Human-in-the-loop approval (enforces `approver_role` from snapshot) |

### OTEL Collector (`/otel/*`)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/otel/v1/traces` | OTLP/HTTP trace ingestion |
| `POST` | `/otel/v1/metrics` | OTLP/HTTP metric ingestion |
| `POST` | `/otel/v1/logs` | OTLP/HTTP log ingestion |

### AWS Bedrock Gateway

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/agents/{name}/invoke` | Async agent invocation (→ 202) |
| `GET` | `/executions/{id}` | Poll execution status/result |
| `GET` | `/health` | Gateway health check |

---

## Deployment

### Prerequisites

- Azure subscription with [AI Landing Zone](https://github.com/{your-org}/azure-ai-landing-zone) deployed
- AWS account with Bedrock model access enabled (Claude Haiku, ap-southeast-2)
- Terraform >= 1.9, Azure CLI, Node.js 20+, Python 3.12+

### Deployment Order

```
1. Azure AI Landing Zone (foundation)
   └── VNet, APIM, ACR, CAE, AI Services, AI Search, Log Analytics

2. UC1 RAG Agent
   ├── Populate AI Search index: python3 scripts/populate_index.py
   ├── Build: az acr build --image uc1-rag-agent:latest ...
   └── Terraform: cd infra && terraform apply -var-file=terraform.tfvars.msdn

3. UC3 Governance Hub
   ├── Build: az acr build --image uc3-governance-api:latest ...
   └── Terraform: cd infra && terraform apply (creates Cosmos, Service Bus, Sentinel, workbook)

4. AWS Bedrock Gateway
   ├── Configure: cp infra/terraform.tfvars.example infra/terraform.tfvars
   └── Deploy: make tf-apply

5. UC2 Supervisor Agent
   ├── Build: az acr build --image uc2-supervisor-api:v2 ...
   └── Terraform: cd infra && terraform apply (creates container app + OIDC federation)

6. Frontend
   ├── Build: az acr build --image uaip-frontend:latest ...
   └── Deploy: az containerapp update --set-env-vars IMAGE_PULL_TIMESTAMP=$(date +%s)
```

### Quick Reference — Build & Deploy

UC2 and UC3 use a `Makefile` `acr-build` target that derives image tags from the repo-root `VERSION` file (currently `0.2.0`) and bakes a secondary `sha-<git7>` tag for audit:

```bash
# UC2 / UC3 (recommended)
make acr-build           # builds genaicri40e.azurecr.io/<image>:v0.2.0 + :sha-<git7>
make acr-build-deploy    # build + containerapp update in one step
```

Manual fallback (any repo) — opens ACR firewall, builds, locks back down:

```bash
az acr update -n genaicri40e --default-action Allow

az acr build --registry genaicri40e --image uc1-rag-agent:cr30 \
  --file services/rag-agent/Dockerfile services/rag-agent --platform linux/amd64

az acr build --registry genaicri40e --image uc2-supervisor-api:v0.2.0 \
  --file services/supervisor-api/Dockerfile services/supervisor-api --platform linux/amd64

az acr build --registry genaicri40e --image uc3-governance-api:v0.2.0 \
  --file services/governance-api/Dockerfile services/governance-api --platform linux/amd64

az acr build --registry genaicri40e --image uaip-frontend:cr27 \
  --file Dockerfile . --platform linux/amd64

az acr update -n genaicri40e --default-action Deny
```

> **Image tag convention (Apr 2026)**: Test-named tags (`tc2-live`, `tc3-live`) have been retired. UC2 + UC3 default to `v$(VERSION)` from the repo-root `VERSION` file plus `sha-<git7>` baked at build time. Test scripts (`tc2.ps1`, `tc3.ps1`, `loadtest_uc1.ps1`) are acceptance probes only and do not drive image names.

---

## Infrastructure Summary

### Azure Resources (AI Landing Zone)

| Resource | Name | Purpose |
|----------|------|---------|
| Resource Group | `ai-lz-rg-msdn-mb44x` (region `australiaeast`) | All UAIP resources |
| VNet | `ai-lz-vnet-msdn` (`192.168.0.0/20`) | Private networking |
| Subnet — CAE | `ContainerAppEnvironmentSubnet` `192.168.1.0/24` (delegation `Microsoft.App/environments`, NSG `ai-alz-cae-nsg`) | Container Apps Environment |
| Subnet — APIM | `APIMSubnet` `192.168.4.0/24` | APIM Internal VNet |
| Subnet — Jumpbox | `JumpboxSubnet` `192.168.6.0/24` | Management hop |
| Subnets — Other | `PrivateEndpointSubnet`, `AIFoundrySubnet`, `AppGatewaySubnet`, `DevOpsBuildSubnet`, `AzureBastionSubnet` | Per-purpose isolation |
| APIM | `ai-alz-apim-i40e` (Developer SKU, Internal VNet, private IP `192.168.4.4`) | AI Gateway |
| ACR | `genaicri40e` (Standard, default-action `Deny`) | Container images |
| CAE | `ai-alz-container-app-env-i40e` (internal ILB `192.168.1.111`, infra RG `rg-managed-ai-lz-rg-msdn-mb44x`, LB `capp-svc-lb`) | Container Apps environment |
| AI Services | `ai-foundry-i40e` | Azure OpenAI (gpt-4.1 cap 15, gpt-4.1-mini cap 11, o4-mini cap 7) |
| AI Search | `ai-alz-ks-ai-search-i40e` (publicAccess `Enabled`, AAD+API key) | Document search |
| Log Analytics | Shared workspace | Centralized logging for all UCs |
| Grafana | `uaip-grafana` (Standard) | 15-panel UAIP dashboard (`uaip-agent-finops-v3`) + 40+ pre-built |
| Bastion | `ai-alz-bastion` (Standard) | Secure jumpbox access |
| Jump VM | `ai-alz-jumpvm` (NIC `ai-alz-jumpvm-nic1`, IP `192.168.6.4`, PowerShell 5.1) | Management VM, no public IP |

### Container Apps

| App | Image | Port | Ingress | Health |
|-----|-------|------|---------|--------|
| `ca-uc1-rag-agent` | `uc1-rag-agent:cr30` | 8088 | **Internal only** (`external_enabled=false`) — FQDN `ca-uc1-rag-agent.internal.ambitiouscliff-ec38b96b.australiaeast.azurecontainerapps.io` | `/readiness` |
| `ca-uc2-supervisor` | `uc2-supervisor-api:v0.2.0` (+ `sha-<git7>`) | 8088 | Internal | `/readiness` |
| `ca-uc3-governance` | `uc3-governance-api:v0.2.0` (+ `sha-<git7>`) | 8000 | Internal | `/readiness` |
| `ca-uc3-otel-collector` | OTEL Collector contrib | 4318 | Internal | — |
| `ca-uaip-frontend` | `uaip-frontend:cr27` | 8080 | Internal | `/` |

All five apps run on the **internal** CAE; external reach is exclusively via APIM (and, for the frontend, via APIM-fronted nginx proxy).

### AWS Resources

| Resource | Purpose |
|----------|---------|
| API Gateway (HTTP v2) | Agent gateway entry point |
| Lambda × 4 | invoke, executor, status, health handlers |
| DynamoDB | Execution state (PAY_PER_REQUEST, TTL 7d) |
| IAM OIDC Provider | Entra ID federation |

---

## Test & Verification Scripts

Acceptance probes live in `uaip-workload-uc3-governance-hub/scripts/` and are PowerShell 5.1 / ASCII-only so they run on the jumpbox VM (`ai-alz-jumpvm`):

| Script | Purpose |
|--------|---------|
| `tc2.ps1` | TC-2 enforcement \u2014 versioned policy registry round-trip, snapshot binding on incidents, approver-role enforcement (mismatch \u2192 403), distinct-approver tally, single-veto, idempotent `policy_decision`, gateway digest endpoint. |
| `tc3.ps1` | TC-3 zero-bypass \u2014 3a (APIM unauth \u2192 401), 3b (APIM authed \u2192 200), 3c (jumpbox direct to internal CAE FQDN must be **denied** \u2014 by NSG `DenyJumpboxDirect` rule when codified, or by unresolvable internal-only ingress when the NSG drift is in effect). |
| `loadtest_uc1.ps1` | Concurrency probe over UC1 RAG via APIM; background-job fan-out, p50/p95/p99 latency, success rate. Image tag is independent of the script name. |

Test scripts are **acceptance probes only** \u2014 they neither mutate live data beyond their incident sandboxes nor drive image tag names.\n\n---\n\n## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| **Agent Framework SDK** over Semantic Kernel | Microsoft's latest agent platform \u2014 WorkflowBuilder, ResponsesHostServer, Foundry hosting |
| **WorkflowBuilder fan-out/fan-in** over sequential tools | 4× faster concurrent execution (~60s vs ~180s) |
| **Declarative `agents.yaml`** | Change agent behavior without code changes — Microsoft recommended pattern |
| **Custom `FanInAggregator` executor** | SDK's fan-in requires list[AgentExecutorResponse] → str bridge for synthesizer |
| **APIM as AI Gateway** (not direct calls) | Centralized rate limiting, content safety, trace injection, FinOps logging |
| **Async MCP for AWS** (not synchronous) | Resilient cross-cloud execution — 202 + poll pattern handles variable latency |
| **OTEL Collector via APIM** | Cross-cloud agents push telemetry over HTTPS through the same gateway |
| **Sentinel on shared workspace** | Analytics rules query the same Log Analytics that receives APIM + OTEL data |

---

## Documents

| Document | Location | Purpose |
|----------|----------|---------|
| PoC Proposal | [`docs/uaip_poc_proposal_30_march_2026.md`](docs/uaip_poc_proposal_30_march_2026.md) | Requirements and success criteria for 4 use cases |
| Platform Strategy | [`docs/uaip_solution_architecture.md`](docs/uaip_solution_architecture.md) | Multi-cloud AI platform design principles |
| AWS Handoff Spec | [`docs/aws_handoff_bedrock_agents_gateway.md`](docs/aws_handoff_bedrock_agents_gateway.md) | AWS technical handoff for Bedrock gateway |
| Gap Analysis | [`docs/gap_analysis_report.md`](docs/gap_analysis_report.md) | Requirements vs. implementation assessment |

---

## Status

**PoC Phase — April 2026**

| Component | Status |
|-----------|--------|
| Azure AI Landing Zone | ✅ Deployed |
| UC1 RAG Knowledge Agent | ✅ Deployed (`uc1-rag-agent:cr30`, internal-only ingress) |
| UC2 Multi-Agent Supervisor | ✅ Deployed (`uc2-supervisor-api:v0.2.0` + `sha-<git7>`, single-stack on Agent Framework SDK) |
| UC3 Governance Hub | ✅ Deployed (`uc3-governance-api:v0.2.0` + `sha-<git7>`, TC-2 versioned policies + TC-1/9 caller identity) |
| UC4 Incident Resolution | ✅ Integrated into UC3 with AI triage + voting engine + per-incident approval binding |
| AWS Bedrock Gateway | ✅ Deployed (4 Lambda functions, OTEL→Azure Monitor) |
| Frontend | ✅ Deployed (cr27, Chat + Agent Flow) |
| Grafana Dashboards | ✅ Deployed (Standard tier, 15-panel custom dashboard `uaip-agent-finops-v3`) |
| APIM Content Safety | ✅ 11 prompt injection/jailbreak patterns blocked |
| Sentinel SIEM | ✅ 6 analytics rules (incl. Agent SLA Breach), diagnostic settings wired |
| Zero-bypass gateway (TC-3) | ✅ UC1 internal-only, NSG `ai-alz-cae-nsg` codified in `uaip-workload-uc1-rag-agent/infra/main.network.tf` |
| Versioned policy enforcement (TC-2) | ✅ Append-only registry + per-incident snapshot + approver-role enforcement |
| Per-agent SLA (TC-5) | ✅ `agents.yaml` `sla_timeout_seconds`, OTEL `agent.sla_breach` events, Sentinel rule |
| Caller identity (TC-1 / TC-9) | ✅ Entra JWT validation; 4 app roles on `uaip-governance` |
| FinOps Dashboard | ✅ Azure Monitor Workbook (6 panels) + Grafana |
| LLM-as-Judge Evaluation | ✅ Pipeline implemented (3-dimension scoring) |
| Cross-Cloud OTEL | ✅ AWS Lambda spans → Azure App Insights via force_flush() |
| OCI / ServiceNow | ⬜ Out of scope for PoC |

---

## Use Case Requirements Traceability

### UC1 — RAG Knowledge Assistant

> **Repo:** [`uaip-workload-uc1-rag-agent`](https://github.com/{your-org}/ai-platform-agents)
> **Container:** `ca-uc1-rag-agent` (cr30) | **Model:** gpt-4.1-mini | **Port:** 8088

| # | Requirement | Priority | Status | Implementation |
|---|-------------|----------|--------|----------------|
| 1.1 | OpenTelemetry instrumentation — spans for query, retrieval, LLM inference | P1 | ✅ Done | `configure_azure_monitor()` + `create_resource()` from Agent Framework SDK. Spans auto-emitted for chat completions and tool calls. App Insights `ai-uc1-rag-agent`. |
| 1.2 | Azure API Management AI Gateway — rate limiting, failover, token tracking | P1 | ✅ Done | APIM `/uc1/*` routes with 30 req/min rate limit, W3C traceparent injection, GatewayLogs diagnostic export to Log Analytics. |
| 1.3 | Azure Content Safety guardrails — prompt injection detection, content filtering | P2 | ✅ Done | APIM policy blocks 11 prompt injection/jailbreak patterns (shared with UC2). APIM-level enforcement. |
| 1.4 | LLM-as-Judge evaluation pipeline — correctness/relevance/groundedness scoring | P3 | ✅ Done | `evaluation/judge.py` — scores on Groundedness, Relevance, Completeness (1-5) using gpt-4.1 as judge. 5 default test questions covering valve specs, safety, piping, instruments, governance policy. CLI: `python -m evaluation.judge --endpoint <url>` |
| 1.5 | Governance / access control — Entra ID auth + per-department search filters | P4 | ⬜ Deferred | APIM subscription keys provide API-level access control. Per-department AI Search security filters not implemented — would require Entra ID user context propagation + search index security trimming. |
| 1.6 | Cost management dashboards — token usage, estimated spend, budget alerts | P3 | ✅ Done | Grafana dashboard: Token Usage by Model, Token Usage Over Time, LLM Latency panels. Azure Monitor FinOps Workbook. Budget alerts not configured (stretch goal). |
| 1.7 | Hybrid semantic search over engineering documents | P1 | ⚠️ Partial | Using `queryType: simple` (keyword search). Standard-tier AI Search doesn't support semantic ranking — would need S2+ tier upgrade or vector embeddings. Keyword search works well for structured document retrieval in the PoC. |
| 1.8 | Cited responses with document references | P1 | ✅ Done | Agent instructions require citations. Responses include document names (SP-MECH-VAL-001, WS-PIP-MAT-002, etc.) and standards references (ASME B16.34, API 6D). |
| 1.9 | Follow-up QA on specific documents | P2 | ✅ Done | `answer_from_document` tool — filters AI Search by document title for focused Q&A. |
| 1.10 | Managed identity (no API keys) | P1 | ✅ Done | User-Assigned Managed Identity `id-uc1-rag-agent` with RBAC: AcrPull, Cognitive Services OpenAI User, Search Index Data Reader, Search Index Data Contributor. |
| 1.11 | Infrastructure as Code | P1 | ✅ Done | Full Terraform `infra/` — container app, RBAC, APIM APIs, App Insights. `terraform.tfvars.msdn` for MSDN PoC environment. |

---

### UC2 — Multi-Agent Supervisor & Monitoring

> **Repo:** [`uaip-workload-uc2-supervisor-agent`](https://github.com/{your-org}/ai-platform-agents)
> **Container:** `ca-uc2-supervisor` (cr35) | **Model:** gpt-4.1 (planning) | **Port:** 8088

| # | Requirement | Priority | Status | Implementation |
|---|-------------|----------|--------|----------------|
| 2.1 | Central supervisor orchestrating multiple agents | P1 | ✅ Done | `WorkflowBuilder` with `add_multi_selection_edge_group` for dynamic routing. Supervisor plans which agents to invoke, selection function parses plan and routes concurrently. |
| 2.2 | Azure native agent | P1 | ✅ Done | Knowledge Agent (gpt-4.1-mini via UC1 RAG) + Compliance Agent (o4-mini direct OpenAI call) + Governance Agent (gpt-4.1 via UC3 API). |
| 2.3 | AWS Bedrock agent (via proxy) | P1 | ✅ Done | External Agent (Cross-Cloud) — async invoke+poll via API Gateway → Lambda → Claude Haiku 4.5. MCP-shaped JSON contract. OIDC federation (Entra ↔ AWS IAM). |
| 2.4 | ServiceNow agent (via proxy) | P3 | ⬜ Deferred | `services/mock-proxies/servicenow_proxy.py` exists but not wired into workflow. No ServiceNow instance available for PoC. Governance Agent demonstrates the third external agent pattern. |
| 2.5 | End-to-end OTEL tracing — Supervisor → agent → tool/API | P1 | ✅ Done | `configure_azure_monitor()` + httpx instrumentation. Custom spans: `uaip.supervisor.route`, `uaip.aggregator.fan_in`, `uaip.tool.*` for each tool. |
| 2.6 | Request-level and step-level spans | P1 | ✅ Done | Custom `_tracer` spans at routing, aggregation, and tool levels. Agent Framework SDK emits `chat`, `invoke_agent` spans automatically. |
| 2.7 | Required span attributes (agent.name, agent.type, tool.name, uc, error) | P1 | ✅ Done | All tools set: `uc=use-case-2`, `agent.name`, `agent.type` (native/external/orchestrator), `tool.name`, `error`. Bedrock adds `cloud.provider=aws`, `bedrock.execution_id`, token counts. |
| 2.8 | Telemetry export to Azure Monitor / App Insights | P1 | ✅ Done | `APPLICATIONINSIGHTS_CONNECTION_STRING` env var → `configure_azure_monitor()`. OTEL spans, dependencies, and GenAI metrics all flow to App Insights. |
| 2.9 | Declarative agent configuration | P2 | ✅ Done | `agents.yaml` — 6 agents with name, model, role, tools, instructions. Agent behavior changeable without code changes. |
| 2.10 | Cross-cloud W3C traceparent propagation | P1 | ✅ Done | Bedrock tool injects traceparent via `opentelemetry.propagate.inject()` into both HTTP header and MCP payload body. AWS Lambda attaches context and continues the trace. |
| 2.11 | OIDC federation (no static credentials) | P1 | ✅ Done | Entra app registration + federated credential. Supervisor acquires JWT for `api://{client_id}/.default`, AWS API Gateway validates via OIDC authorizer. |
| 2.12 | Content safety guardrails | P2 | ✅ Done | APIM policy with 11 pattern checks: prompt injection, jailbreak, DAN, developer mode bypass. Returns 400 with `content_policy_violation`. |
| 2.13 | Infrastructure as Code | P1 | ✅ Done | Terraform `infra/` — container app, RBAC, APIM, Entra app registrations, App Insights. |
| 2.14 | Per-agent SLA enforcement (TC-5) | P1 | ✅ Done | `sla_timeout_seconds` per agent in `agents.yaml`; `services/supervisor-api/tools/sla.py` wraps tool invocations with `asyncio.wait_for`, records `agent.sla_breach` OTEL events on timeout, and surfaces a deterministic timeout response. 9 new tests in `tests/test_tc5_sla.py`. Sentinel rule **Agent SLA Breach** alerts on the OTEL events. |
| 2.15 | Stack consolidation (April 2026) | — | ✅ Done | Legacy FastAPI v1 stack + mock-proxies removed. Single Agent Framework SDK supervisor on `python:3.12-slim`, port 8088. Image now `uc2-supervisor-api:v0.2.0` (+ `sha-<git7>`). |

---

### UC3 — Governance & Monitoring Hub

> **Repo:** [`uaip-workload-uc3-governance-hub`](https://github.com/{your-org}/ai-platform-governance)
> **Container:** `ca-uc3-governance` (latest) | **Framework:** FastAPI | **Port:** 8000

| # | Requirement | Priority | Status | Implementation |
|---|-------------|----------|--------|----------------|
| 3.1 | Unified telemetry — OTEL Collector ingests from all agents | P1 | ✅ Done | `ca-uc3-otel-collector` — OTLP/HTTP receivers, batch processor, Azure Monitor exporter. Routes: `/otel/v1/traces`, `/otel/v1/metrics`, `/otel/v1/logs`. |
| 3.2 | Cross-cloud observability — Azure + AWS spans | P1 | ✅ Done | Azure agents emit via `configure_azure_monitor()`. AWS Lambda emits via `AzureMonitorTraceExporter` with `force_flush()`. Both share W3C traceparent for correlation. |
| 3.3 | Cost & token tracking API | P1 | ✅ Done | `/api/costs/summary`, `/api/costs/by-agent`, `/api/costs/trends` — queries Log Analytics for token consumption data. |
| 3.4 | Policy enforcement API | P2 | ✅ Done | `/api/policies` — CRUD for governance policies (in-memory store, extensible to Cosmos DB). |
| 3.5 | Compliance reporting | P2 | ✅ Done | `/api/compliance/report` — generates compliance reports from telemetry and policy data. |
| 3.6 | SIEM — Microsoft Sentinel integration | P1 | ✅ Done | Sentinel workspace with 5 analytics rules: Anomalous Token Consumption, High Agent Failure Rate, Content Safety Violations, Rate Limit Breaches, Cross-Cloud Latency Degradation. |
| 3.7 | OTEL Collector via APIM | P2 | ✅ Done | APIM `/otel/*` routes forward to OTEL Collector container app. Cross-cloud agents can push telemetry via HTTPS. |
| 3.8 | Grafana dashboards | P2 | ✅ Done | Azure Managed Grafana (Standard) with custom 15-panel UAIP dashboard `uaip-agent-finops-v3`: Prompts, Tool Invocations, Cross-Cloud Calls, Avg Agents/Prompt, Foundry Success, Bedrock Success, Agents Selected by Supervisor, Tool Performance & SLA Compliance (TC-5), LLM Calls/min — Foundry vs Bedrock, Foundry Latency by Deployment, Bedrock Cross-Cloud Hops, Validator Verdicts by Agent (TC-4/TC-6), Agent Selection Over Time, Recent Failures (drill-in to App Insights). Plus 40+ pre-built Azure dashboards. |
| 3.9 | FinOps Workbook | P2 | ✅ Done | Azure Monitor Workbook with 6 KQL panels: agent performance, token consumption, daily trends, API traffic, cross-cloud metrics, content safety. Deployed via Terraform. |
| 3.10 | Infrastructure as Code | P1 | ✅ Done | Terraform `infra/` — container apps, OTEL collector, APIM, Cosmos DB, Service Bus, Event Grid, Sentinel, App Insights, FinOps Workbook. |
| 3.11 | Versioned policy registry + enforcement (TC-2) | P1 | ✅ Done | Append-only `EnterprisePolicy` registry with SHA-256 canonical hashing. `Incident.create` embeds a `policy_applied` snapshot (policy_id, version, hash, threshold rule, approver_role). `approval_service.respond()` reads the snapshot and enforces approver role via Entra app role membership — mismatched roles raise `ApprovalRoleError` → HTTP 403. Distinct-approver tally + single-veto short-circuit. Idempotent `policy_decision` writes. `WorkflowEvent` emissions: `policy.threshold_met`, `policy.rejected`. 6 new tests in `tests/test_tc2_enforcement.py` (50/50 passing). |
| 3.12 | APIM gateway digest (TC-2f) | P1 | ✅ Done | `GET /api/policies/gateway/digest` returns SHA-256 over `infra/main.apim*.tf` + APIM policy XML files. Current digest `a6c45e9f…`. Lets governance plane prove which policy bundle is live in APIM at any moment. |
| 3.13 | Caller identity (TC-1 / TC-9) | P1 | ✅ Done | `CallerIdentity` model + Entra JWT validation (PyJWT + JWKS cache). `AUTH_MODE` env: `required` / `optional` / `disabled`. `Incident.reported_by` and `ApprovalRequest.approver_oid` / `_tenant_id` / `_auth_mode` populated from validated tokens. 4 Entra app roles defined on `uaip-governance` app (`workflow-orchestrator`, `incident-commanders`, `senior-engineers`, `on-call`) and codified in `infra/main.entra.tf` (azuread `~> 3.0`). |
| 3.14 | Sentinel rule — Agent SLA Breach | P1 | ✅ Done | Scheduled rule added to `infra/main.sentinel.tf` watching for OTEL `agent.sla_breach` events emitted by UC2 (TC-5).

---

### UC4 — Incident Resolution (integrated into UC3)

> **Repo:** [`uaip-workload-uc3-governance-hub`](https://github.com/{your-org}/ai-platform-governance) (merged)
> **Reference:** [`uaip-workload-uc4-incident-resolution`](https://github.com/{your-org}/ai-platform-governance)

| # | Requirement | Priority | Status | Implementation |
|---|-------------|----------|--------|----------------|
| 4.1 | AI-driven incident triage (classify severity, category, action) | P1 | ✅ Done | Azure OpenAI gpt-4.1-mini triage agent. Classifies: severity (p1-p4), category (6 types), recommended action, reasoning. Rule-based fallback when AI unavailable. |
| 4.2 | Human-in-the-loop approval gates | P1 | ✅ Done | `/api/approvals/{id}/respond` — approve/reject with notes. Incidents transition to `awaiting_approval` when decision confidence is low or severity is P1/P2. |
| 4.3 | Event-driven workflow engine | P1 | ✅ Done | Service Bus + Event Grid infrastructure. `/api/events` router for event routing. Incident state machine: received → triaging → investigating → deciding → awaiting_approval → remediating → resolved. |
| 4.4 | Multi-agent voting / quorum | P1 | ✅ Done | `DecisionEngine` with 3 strategies: weighted_majority, unanimous, quorum. `/api/incidents/{id}/votes` to submit agent votes, `/api/incidents/{id}/decide` to run voting. Auto-approve for P3/P4 with >95% confidence. |
| 4.5 | Long-running workflow checkpoint / resume | P2 | ✅ Done | Cosmos DB persistence for incidents (lazy-init, in-memory fallback). `WorkflowState` tracks current status, agent results, decision confidence, approval ID. Read-through cache. |
| 4.6 | Integration with UC1 (knowledge context) | P3 | ✅ Done | `_get_knowledge_context()` queries UC1 RAG endpoint for engineering context related to the incident. Knowledge is injected into the AI triage prompt for richer severity/category classification. Activated when `UC1_RAG_ENDPOINT` is set. |
| 4.7 | Integration with UC2 (multi-agent orchestration) | P3 | ✅ Done | `_run_supervisor_triage()` routes incident through UC2 multi-agent supervisor. Supervisor orchestrates Knowledge, Compliance, and Governance agents for comprehensive analysis. Activated when `UC2_SUPERVISOR_ENDPOINT` is set. Cascade: UC2 → AI+UC1 → rules. |
| 4.8 | Decision transparency — voting, confidence, escalation audit | P1 | ✅ Done | `Decision` model captures outcome, confidence, strategy, all votes with reasoning, requires_approval flag. Full vote history at `/api/incidents/{id}/votes`. |

---

### Frontend

> **Repo:** [`uaip-frontend`](https://github.com/{your-org}/ai-platform-frontend) (private)
> **Container:** `ca-uaip-frontend` (cr27) | **Stack:** React 19, TypeScript, Vite, nginx | **Port:** 8080

| # | Requirement | Priority | Status | Implementation |
|---|-------------|----------|--------|----------------|
| F.1 | Conversational chat interface | P1 | ✅ Done | Chat page with message history, "+ New Chat" button, session persistence via sessionStorage. |
| F.2 | Multi-agent visualization | P1 | ✅ Done | Agent Flow page with React Flow DAG: Supervisor → 4 agents → Synthesizer. Cloud badges (Azure/AWS/Governance), model labels, active/idle status. |
| F.3 | Tool call detection | P1 | ✅ Done | V2 (tool_call parsing) + V3 (text-based detection) for Knowledge Agent, Compliance Agent, External Agent (AWS), Governance Agent. |
| F.4 | Agent naming consistency | P2 | ✅ Done | "{Name} Agent" format across all pages. Engineering → "External Agent (AWS)", model shown as "Claude Sonnet 4". |
| F.5 | Custom branding | P2 | ✅ Done | Dark navy nav, green accent, configurable logo. |
| F.6 | Infrastructure as Code | P2 | ✅ Done | Terraform `infra/` — container app, user-assigned identity, ACR pull RBAC. |

---

### Cross-Cloud (AWS Bedrock)

> **Repo:** [`uaip-bedrock-agent`](https://github.com/{your-org}/ai-platform-agents)
> **Stack:** AWS Lambda, API Gateway v2, DynamoDB, Bedrock Claude Haiku 4.5

| # | Requirement | Priority | Status | Implementation |
|---|-------------|----------|--------|----------------|
| X.1 | Async invoke + poll MCP contract | P1 | ✅ Done | `POST /agents/{name}/invoke` → 202 + executionId. `GET /executions/{id}` → poll. DynamoDB state with 7-day TTL. |
| X.2 | Bedrock model integration (Claude) | P1 | ✅ Done | 3-tier fallback: AgentCore Runtime → Bedrock Agent → Converse API (Claude Haiku 4.5). |
| X.3 | OIDC federation (Entra ↔ AWS IAM) | P1 | ✅ Done | Terraform `iam.tf` — OIDC provider, federated IAM role. API Gateway JWT authorizer validates Entra tokens. |
| X.4 | OTEL telemetry → Azure App Insights | P1 | ✅ Done | `AzureMonitorTraceExporter` + `ConsoleSpanExporter`. `force_flush()` in handler finally blocks ensures spans export before Lambda freezes. Custom attributes: `uc`, `cloud.provider`, `agent.name`, `execution.id`. |
| X.5 | W3C traceparent propagation | P1 | ✅ Done | Incoming traceparent extracted via `opentelemetry.propagate.extract()`. Spans created as children of Azure parent trace. Full cross-cloud E2E correlation. |
| X.6 | Infrastructure as Code | P1 | ✅ Done | Terraform `infra/` — DynamoDB, 4 Lambda functions, API Gateway, IAM, CloudWatch log groups. |

---

### Platform / Landing Zone

> **Repo:** [`azure-ai-landing-zone-terraform`](https://github.com/{your-org}/azure-ai-landing-zone)

| # | Requirement | Priority | Status | Implementation |
|---|-------------|----------|--------|----------------|
| P.1 | VNet with private subnets | P1 | ✅ Done | Hub VNet with subnets for CAE, APIM, Private Endpoints, Bastion. Internal ILB for CAE. |
| P.2 | Azure API Management (AI Gateway) | P1 | ✅ Done | Private VNet-integrated APIM. Rate limiting, content safety, trace injection, FinOps logging. |
| P.3 | Azure Container Apps Environment | P1 | ✅ Done | Internal load balancer, VNet-integrated. 5 container apps deployed. |
| P.4 | Azure OpenAI (AI Foundry) | P1 | ✅ Done | 3 model deployments: gpt-4.1 (cap 15), gpt-4.1-mini (cap 11), o4-mini (cap 7). |
| P.5 | Azure AI Search | P1 | ✅ Done | Standard tier, `knowledge-base-docs` index (6 documents). AAD+API Key auth. |
| P.6 | Azure Container Registry | P1 | ✅ Done | Standard SKU, default firewall deny. Opened temporarily for ACR Tasks builds. |
| P.7 | Azure Managed Grafana | P2 | ✅ Done | Standard tier, system-assigned identity with Monitoring Reader RBAC. Azure Monitor data source auto-provisioned. |
| P.8 | Log Analytics + App Insights | P1 | ✅ Done | Shared Log Analytics workspace. 3 App Insights instances (one per UC). Public ingestion enabled for OTEL. |
| P.9 | Bastion + Jump VM | P2 | ✅ Done | Standard SKU Bastion for secure management access. No public IPs on workloads. |
| P.10 | Terraform IaC (AVM) | P1 | ✅ Done | Azure Verified Modules pattern. Full landing zone reproducible via `terraform apply`. |

---

## Requirements Summary

| Use Case | Total Requirements | ✅ Done | ⚠️ Partial | ⬜ Deferred |
|----------|--------------------|---------|-----------|-------------|
| **UC1** — RAG Knowledge Assistant | 11 | 9 | 1 | 1 |
| **UC2** — Multi-Agent Supervisor | 15 | 14 | 0 | 1 |
| **UC3** — Governance Hub | 14 | 14 | 0 | 0 |
| **UC4** — Incident Resolution | 8 | 8 | 0 | 0 |
| **Frontend** | 6 | 6 | 0 | 0 |
| **Cross-Cloud (AWS)** | 6 | 6 | 0 | 0 |
| **Platform / Landing Zone** | 10 | 10 | 0 | 0 |
| **Total** | **70** | **67 (96%)** | **1 (1%)** | **2 (3%)** |

### Deferred Items (out of PoC scope)

| ID | Item | Reason |
|----|------|--------|
| 1.5 | Per-department AI Search security filters | Requires Entra user context propagation — enterprise auth pattern |
| 2.4 | ServiceNow agent | No ServiceNow instance available for PoC |

### Partial Items

| ID | Item | Gap | Path to Complete |
|----|------|-----|-----------------|
| 1.7 | Hybrid semantic search | Standard tier AI Search (keyword only) | Upgrade to S2+ or add vector embeddings |
