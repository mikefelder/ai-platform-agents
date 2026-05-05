# Unified AI Platform — Multi-Cloud Agent Accelerator

A production-ready multi-cloud AI platform accelerator that demonstrates multi-agent orchestration, cross-cloud execution, centralized governance, and end-to-end observability on Azure and AWS.

## What This Is

An opinionated starting point for building enterprise AI agent platforms that:

- **Orchestrate multiple AI agents** with fan-out/fan-in workflows (Azure OpenAI + AWS Bedrock)
- **Retrieve and cite documents** via RAG with Azure AI Search
- **Enforce governance** — cost tracking, policy enforcement, incident resolution, SIEM integration
- **Observe everything** — OpenTelemetry traces across cloud boundaries with W3C traceparent propagation
- **Secure by default** — managed identity auth, VNet isolation, APIM AI Gateway, zero hardcoded credentials

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                      Azure AI Landing Zone                          │
│                                                                     │
│  ┌──────────┐     ┌──────────────────────────────────────────────┐  │
│  │   APIM   │────▶│  Supervisor Agent (gpt-4.1)                  │  │
│  │AI Gateway│     │  WorkflowBuilder: fan-out/fan-in             │  │
│  └──────────┘     │                                              │  │
│       │           │  ┌────────────┐ ┌────────────┐               │  │
│       │           │  │ Knowledge  │ │ Compliance │               │  │
│       │           │  │ (gpt-4.1-  │ │ (o4-mini)  │               │  │
│       │           │  │  mini)     │ │            │               │  │
│       │           │  └──────┬─────┘ └────────────┘               │  │
│       │           │         │                                    │  │
│       │           │  ┌──────┴─────┐ ┌────────────┐               │  │
│       │           │  │  External  │ │ Governance │               │  │
│       │           │  │  (Bedrock) │ │ (gpt-4.1)  │               │  │
│       │           │  └──────┬─────┘ └────────────┘               │  │
│       │           │         │                                    │  │
│       │           │  ┌──────┴─────┐                              │  │
│       │           │  │Synthesizer │ → Merged response            │  │
│       │           │  └────────────┘                              │  │
│       │           └──────────────────────────────────────────────┘  │
│       │                                                             │
│       ▼           ┌─────────────┐  ┌──────────┐  ┌──────────────┐  │
│  ┌─────────┐      │ RAG Agent   │  │ Azure AI │  │ App Insights │  │
│  │Frontend │      │ (gpt-4.1-  │  │ Search   │  │ + Sentinel   │  │
│  │(React)  │      │  mini)     │  │          │  │              │  │
│  └─────────┘      └─────────────┘  └──────────┘  └──────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
                          │ OIDC
                          ▼
              ┌───────────────────────┐
              │  AWS Bedrock Gateway  │
              │  (Lambda + Claude)    │
              └───────────────────────┘
```

## Repository Structure

```
ai-platform-agents/          ← You are here
├── rag-agent/               # RAG Knowledge Agent (document search + cited responses)
│   ├── services/rag-agent/  # Agent Framework SDK, Azure AI Search tool
│   ├── infra/               # Terraform (Container App, APIM, identity)
│   └── scripts/             # populate_index.py (sample documents)
│
├── supervisor-agent/        # Multi-Agent Supervisor (fan-out/fan-in orchestration)
│   ├── services/supervisor-api/  # WorkflowBuilder, agents.yaml, 4 specialized agents
│   └── infra/               # Terraform (Container App, APIM, Entra ID)
│
├── bedrock-gateway/         # AWS Bedrock Gateway (cross-cloud agent invocation)
│   ├── services/gateway/    # Lambda handlers (invoke + poll MCP contract)
│   └── infra/               # Terraform (API Gateway, Lambda, DynamoDB, IAM)
│
└── docs/                    # Shared documentation
    ├── uaip_solution_architecture.md
    └── ...
```

### Related Repositories

| Repo | Purpose |
|------|---------|
| [`ai-platform-governance`](https://github.com/{your-org}/ai-platform-governance) | Governance Hub — observability, cost tracking, incident resolution, SIEM |
| [`ai-platform-frontend`](https://github.com/{your-org}/ai-platform-frontend) | React Chat UI + Agent Flow DAG visualization |
| [`azure-ai-landing-zone`](https://github.com/{your-org}/azure-ai-landing-zone) | Azure AI Landing Zone — foundational infrastructure (Terraform AVM) |

## Quick Start

### Prerequisites

- Azure subscription with [AI Landing Zone](https://github.com/{your-org}/azure-ai-landing-zone) deployed
- Azure CLI authenticated
- Terraform >= 1.9
- Python 3.12+
- (Optional) AWS account for cross-cloud Bedrock agent

### 1. Deploy the RAG Agent

```bash
cd rag-agent

# Populate AI Search with sample documents
python scripts/populate_index.py

# Build and deploy
cd infra
terraform init && terraform plan -out=tfplan && terraform apply tfplan
```

### 2. Deploy the Supervisor Agent

```bash
cd supervisor-agent/infra
terraform init && terraform plan -out=tfplan && terraform apply tfplan
```

### 3. (Optional) Deploy the Bedrock Gateway

```bash
cd bedrock-gateway/infra
terraform init && terraform plan -out=tfplan && terraform apply tfplan
```

### 4. Test It

```bash
curl -X POST https://<your-apim>/supervisor/responses \
  -H "Content-Type: application/json" \
  -H "Ocp-Apim-Subscription-Key: <key>" \
  -d '{"input": "What are the product specifications for Sample Project?"}'
```

## Customization

### Bring Your Own Documents

Replace the sample documents in `rag-agent/scripts/populate_index.py` with your own. The agent instructions in `rag-agent/services/rag-agent/main.py` are domain-agnostic — they work with any document corpus.

### Add or Modify Agents

Agent definitions are declarative in `supervisor-agent/services/supervisor-api/agents.yaml`. Change instructions, models, tools, or add new agents without modifying Python code.

### Change Models

Each agent specifies its model in `agents.yaml`. The platform supports:
- **gpt-4.1** — planning and synthesis
- **gpt-4.1-mini** — fast retrieval
- **o4-mini** — reasoning (compliance analysis)
- **Claude** (via Bedrock) — cross-cloud

## Key Technologies

| Component | Technology |
|-----------|-----------|
| Agent Framework | Microsoft Agent Framework SDK |
| API Protocol | OpenAI Responses API |
| Orchestration | WorkflowBuilder (fan-out/fan-in) |
| Search | Azure AI Search (hybrid) |
| LLMs | Azure OpenAI (gpt-4.1, o4-mini) + AWS Bedrock (Claude) |
| Infrastructure | Terraform with Azure Verified Modules |
| Gateway | Azure API Management (AI Gateway) |
| Observability | OpenTelemetry → Application Insights + Grafana |
| Security | Managed Identity, OIDC federation, VNet isolation |
| Frontend | React 19 + TypeScript + React Flow |

## License

MIT
