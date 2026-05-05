# RAG Knowledge Agent

> An AI-powered knowledge assistant that searches your organization's document corpus and generates cited, contextual responses.
> Part of the [Unified AI Platform Accelerator](../docs/uaip_solution_architecture.md).

---

## Overview

The RAG Knowledge Agent answers natural language questions using your indexed document corpus — specifications, compliance reports, standards, data sheets, and contracts. It retrieves relevant documents via Azure AI Search and generates accurate, cited responses using Azure OpenAI.

Built on the **Microsoft Agent Framework SDK**, the agent serves the **OpenAI Responses API** protocol and deploys as an Azure Container App with **internal-only ingress** behind Azure API Management.

### Key Capabilities

- **Keyword search** across structured and unstructured documents
- **Cited responses** with document references
- **Follow-up QA** on specific retrieved documents
- **LLM-as-Judge evaluation** pipeline (groundedness, relevance, completeness scoring)
- **OpenTelemetry observability** with traces to Azure Application Insights
- **Managed identity** — no API keys in code
- **Terraform IaC** — fully reproducible infrastructure

---

## Architecture

```
┌────────────────────────────────────────────────────────────────────────┐
│                         Azure AI Landing Zone                          │
│                                                                        │
│  ┌──────────┐     ┌──────────────────────────────────────────────────┐ │
│  │   APIM   │     │  Container App: rag-agent                        │ │
│  │ /rag/*   │────▶│                                                  │ │
│  └──────────┘     │  ┌────────────────────────────────────────────┐  │ │
│                   │  │  Agent Framework SDK (ResponsesHostServer) │  │ │
│                   │  │  Port 8088                                 │  │ │
│                   │  │                                            │  │ │
│                   │  │  OpenAIChatClient ──▶ Azure OpenAI         │  │ │
│                   │  │    Model: gpt-4.1-mini                     │  │ │
│                   │  │                                            │  │ │
│                   │  │  FunctionTools:                            │  │ │
│                   │  │    ├── search_documents                   │  │ │
│                   │  │    │     └──▶ Azure AI Search              │  │ │
│                   │  │    │          (hybrid search, index:       │  │ │
│                   │  │    │           knowledge-base-docs)        │  │ │
│                   │  │    └── answer_from_document                │  │ │
│                   │  │          └──▶ Follow-up QA on specific doc │  │ │
│                   │  └────────────────────────────────────────────┘  │ │
│                   └──────────────────────────────────────────────────┘ │
│                                                                        │
│  ┌──────────────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │ Azure AI Search      │  │ Azure OpenAI │  │ Application Insights │  │
│  │ knowledge-base-docs  │  │ gpt-4.1-mini │  │ OTEL telemetry       │  │
│  │ (your documents)     │  │              │  │                      │  │
│  └──────────────────────┘  └──────────────┘  └──────────────────────┘  │
└────────────────────────────────────────────────────────────────────────┘
```

### Azure Services

| Service | Resource | Purpose |
|---------|----------|---------|
| Azure Container Apps | `rag-agent` | Hosts the RAG agent |
| Azure OpenAI | `gpt-4.1-mini` deployment | LLM for response generation |
| Azure AI Search | AI Search instance | Document indexing and search |
| Azure API Management | APIM instance | AI Gateway — routing, rate limiting, trace injection |
| Application Insights | Workspace | Observability and OTEL telemetry |
| User-Assigned Managed Identity | UAMI | Auth for OpenAI, AI Search, ACR |

---

## Knowledge Base

The AI Search index (configurable via `AZURE_AI_SEARCH_INDEX` env var, default: `knowledge-base-docs`) contains your indexed documents. Sample documents are provided in `scripts/populate_index.py` to demonstrate the RAG pipeline.

Documents are populated via `scripts/populate_index.py`. **Replace these with your own documents** to customize the agent for your domain.

---

## API

```
POST /rag/responses    — Query the knowledge base (OpenAI Responses API)
GET  /rag/readiness    — Health check
```

### Example Request

```json
{
  "input": "What are the product specifications for Sample Project?"
}
```

### Example Response

The agent searches the knowledge base, retrieves the relevant specification document, and generates a response citing specific standards, requirements, and reference numbers from the indexed documents.

---

## How It Works

1. **User sends a query** via the Chat UI or directly via the Responses API
2. **Agent Framework receives the request** and invokes the LLM (gpt-4.1-mini)
3. **LLM decides to call `search_documents`** — the tool sends a search query to Azure AI Search
4. **AI Search returns** ranked document chunks with relevance scores
5. **LLM generates a cited response** using the retrieved documents as context
6. **Response is returned** via the OpenAI Responses API format, including tool call details for full traceability

### Tool Descriptions

| Tool | Function | Backend |
|------|----------|---------|
| `search_documents` | Searches the knowledge base for relevant documents | Azure AI Search (hybrid: keyword + vector) |
| `answer_from_document` | Follow-up QA on a specific previously-retrieved document | Azure OpenAI with document context |

---

## Project Structure

```
services/rag-agent/
  main.py              # Agent Framework entrypoint (ResponsesHostServer)
  agent.yaml           # Foundry hosted agent descriptor
  Dockerfile           # Container image (python:3.12-slim, port 8088)
  requirements.txt     # Python dependencies
  tools/
    search.py          # AI Search keyword search tool
    document_qa.py     # Document-specific follow-up QA tool
  evaluation/
    __init__.py
    judge.py           # LLM-as-Judge evaluation pipeline (3-dimension scoring)

infra/                 # Terraform deployment
  main.container_app.tf   # Container App (port 8088, internal-only ingress, /readiness probes)
  main.network.tf         # NSG `ai-alz-cae-nsg` on CAE subnet (TC-3 zero-bypass: DenyJumpboxDirect + DenyVnetIngress)
  main.apim.tf            # APIM routes (/uc1/responses, /uc1/readiness)
  main.identity.tf        # UAMI + RBAC (OpenAI User, AcrPull, Search Reader)
  main.monitor.tf         # Application Insights
  data.tf                 # Data sources for ALZ resources
  variables.tf            # Input variables (incl. alz_vnet_name)
  outputs.tf              # Output values
  terraform.tfvars.msdn   # MSDN PoC configuration

scripts/
  populate_index.py    # Create AI Search index and upload documents
```

---

## Getting Started

### Prerequisites

- Azure subscription with AI Landing Zone deployed ([azure-ai-landing-zone-terraform](../azure-ai-landing-zone-terraform))
- Azure CLI (`az`) authenticated
- Terraform >= 1.9
- Python 3.12+
- Access to Azure Container Registry (`genaicri40e`)

### 1. Populate the Knowledge Base

```bash
python3 scripts/populate_index.py
```

### 2. Build and Push Container Image

```bash
az acr update -n genaicri40e --default-action Allow

az acr build --registry genaicri40e \
  --image uc1-rag-agent:cr30 \
  --file services/rag-agent/Dockerfile services/rag-agent

az acr update -n genaicri40e --default-action Deny
```

### 3. Deploy Infrastructure

```bash
cd infra
terraform init
terraform workspace select msdn
terraform plan -var-file=terraform.tfvars.msdn -out=tfplan
terraform apply tfplan
```

### 4. Deploy New Image

```bash
az containerapp update -n ca-uc1-rag-agent -g ai-lz-rg-msdn-mb44x \
  --image genaicri40e.azurecr.io/uc1-rag-agent:cr30
```

### 5. Verify Deployment

```bash
az containerapp revision list -n ca-uc1-rag-agent \
  -g ai-lz-rg-msdn-mb44x \
  --query "[?properties.active].{name:name,health:properties.healthState}" -o table
```

---

## Integration with Supervisor Agent

The Supervisor Agent invokes the RAG agent as the `search_knowledge` tool:

```
Supervisor → tools/knowledge.py → POST /rag/responses (via APIM)
```

This enables the supervisor to incorporate knowledge retrieval into multi-agent fan-out/fan-in workflows. The RAG agent runs as one of several concurrent agents in the supervisor's orchestration DAG.

---

## Observability

- **OpenTelemetry** traces emitted via Agent Framework SDK `ObservabilitySettings`
- **Azure Monitor** exporters ship traces, logs, and metrics to Application Insights
- **Traceability** — Full request → search → response lineage visible in Responses API output
- **W3C traceparent** propagated when called from supervisor agent

---

## Security & Guardrails

| Control | Implementation |
|---------|---------------|
| Authentication to OpenAI | User-Assigned Managed Identity (`ManagedIdentityCredential`) |
| Authentication to AI Search | Managed Identity with Search Index Data Reader role |
| Container registry access | AcrPull role on UAMI |
| API access control | APIM subscription key required |
| Network isolation | VNet-integrated Container App Environment, **internal-only ingress** (`external_enabled = false`); only internal CAE FQDN exposed |
| Zero-bypass gateway | NSG on `ContainerAppEnvironmentSubnet` enforces ingress deny rules. Codified in [`infra/main.network.tf`](infra/main.network.tf). |
| AI Search access | Public network access **disabled** — private endpoints only |
| No hardcoded credentials | All auth via managed identity — zero secrets in code |
| Content safety | APIM policy blocks prompt injection patterns ("ignore previous instructions", etc.) |
| Rate limiting | APIM enforces 30 requests/minute per subscription |
