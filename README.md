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

## Dependency Security Updates

Dependabot checks dependencies weekly. Python and npm security fixes are grouped
separately from routine version updates to reduce the number of remediation PRs.
Enable **Dependabot security updates** in the repository's security settings;
the configuration file alone does not enable this repository setting.

Dependency PRs require manual review. The former conflict-only auto-merge workflow
has been removed: a mergeable PR is not necessarily compatible. This also removes
its post-merge notification comments. Before restoring automatic merging, establish
passing build/test baselines and require those checks through branch protection or
a ruleset. Treat major upgrades as separate migrations.

For an initial npm cleanup, run `npm audit` and
`npm audit fix --package-lock-only --ignore-scripts` in each of:

- `rag-agent`
- `rag-agent/code/frontend`
- `rag-agent/extensions/teams`
- `rag-agent/tests/integration/ui`

Review the lockfile diff, install with `npm ci`, and run the project's build/tests
before merging. Do not use blanket `npm audit fix --force`: its proposed fixes may
include breaking upgrades or downgrades. Repeat the audit after updates; transitive
dependencies may require a targeted parent-package update.

For the Poetry-managed Python project in `rag-agent`, use `poetry check --lock`
and targeted `poetry update <package>` commands. Exact dependency pins may need
manifest changes first; update related framework packages together and commit
`pyproject.toml` and `poetry.lock` consistently. For pip-managed projects, audit
resolved dependencies in an isolated environment and keep deployment requirements
aligned with their `pyproject.toml` definitions.

After merging to the default branch, recheck Dependabot for remaining alerts.
Local npm/Python audit totals are not equivalent to GitHub's alert count. Do not
dismiss alerts merely to reduce the total; document genuinely inapplicable alerts
or upstream blockers individually.

## License

MIT
