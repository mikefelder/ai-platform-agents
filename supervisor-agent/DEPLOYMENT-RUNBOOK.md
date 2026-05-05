# UAIP PoC — Deployment Runbook

> **Purpose**: Reproduce the full UAIP multi-agent PoC in a new Azure environment.  
> **Last verified**: 27 April 2026 against `ai-lz-rg-msdn-mb44x` (australiaeast).

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Landing Zone (Terraform)](#2-landing-zone-terraform)
3. [UC2 Supervisor Agent (Terraform + CLI)](#3-uc2-supervisor-agent)
4. [UC1 RAG Knowledge Agent (CLI)](#4-uc1-rag-knowledge-agent)
5. [UC3 Governance Hub (Terraform + CLI)](#5-uc3-governance-hub)
6. [Frontend (CLI)](#6-frontend)
7. [AWS Bedrock Cross-Cloud Agent](#7-aws-bedrock-cross-cloud-agent)
8. [Grafana Observability](#8-grafana-observability)
9. [CLI-Only Changes Not in Terraform](#9-cli-only-changes-not-in-terraform)
10. [Post-Deployment Verification](#10-post-deployment-verification)

---

## 1. Prerequisites

### Azure Resources (provisioned by ALZ Terraform)

These are created by the `azure-ai-landing-zone-terraform` repo and must exist before workload deployment:

| Resource | Name Pattern | Notes |
|----------|-------------|-------|
| Resource Group | `ai-lz-rg-*` | All workloads deploy here |
| Container App Environment | `ai-alz-container-app-env-*` | Internal VNet, ILB |
| Container Registry | `genaicri*` | Standard SKU, `defaultAction=Deny` |
| API Management | `ai-alz-apim-*` | Private VNet (IP 192.168.4.4) |
| Azure OpenAI (AI Foundry) | `ai-foundry-*` | Cognitive Services account |
| AI Search | `ai-alz-ks-ai-search-*` | Standard tier |
| Key Vault | `ai-alz-kv-*` | |
| Log Analytics Workspace | `ai-alz-law` | |
| Bastion | `ai-alz-bastion` | Standard SKU |
| VNet | `ai-alz-vnet-*` | With subnets for CAE, APIM, Bastion |

### Azure OpenAI Model Deployments

Deploy these models in AI Foundry before agent deployment:

```bash
# Current deployments (adjust capacity as needed)
az cognitiveservices account deployment create \
  --name ai-foundry-i40e \
  --resource-group $RG \
  --deployment-name gpt-4.1 \
  --model-name gpt-4.1 --model-version 2025-04-14 \
  --model-format OpenAI \
  --sku-name GlobalStandard --sku-capacity 15

az cognitiveservices account deployment create \
  --name ai-foundry-i40e \
  --resource-group $RG \
  --deployment-name gpt-4.1-mini \
  --model-name gpt-4.1-mini --model-version 2025-04-14 \
  --model-format OpenAI \
  --sku-name GlobalStandard --sku-capacity 11

az cognitiveservices account deployment create \
  --name ai-foundry-i40e \
  --resource-group $RG \
  --deployment-name o4-mini \
  --model-name o4-mini --model-version 2025-04-16 \
  --model-format OpenAI \
  --sku-name GlobalStandard --sku-capacity 7
```

### AI Search Configuration

**⚠️ CLI-only — not in any Terraform:**

```bash
# 1. Enable RBAC + API Key auth (required for managed identity access)
az search service update \
  --name $SEARCH_NAME \
  --resource-group $RG \
  --auth-options aadOrApiKey

# 2. Enable public access (needed for data upload; can restrict later)
az search service update \
  --name $SEARCH_NAME \
  --resource-group $RG \
  --public-access enabled

# 3. Create the search index "knowledge-base-docs"
#    (Upload documents via portal or REST API — index schema is defined
#     by the document upload process in the UC1 repo)
```

### Log Analytics — Public Access

**⚠️ CLI-only — required for OTEL telemetry ingestion:**

```bash
az monitor log-analytics workspace update \
  --workspace-name ai-alz-law \
  --resource-group $RG \
  --ingestion-access Enabled \
  --query-access Enabled
```

---

## 2. Landing Zone (Terraform)

```bash
cd azure-ai-landing-zone-terraform
terraform init
terraform apply
```

This creates the shared infrastructure (VNet, CAE, ACR, APIM, AI Foundry, AI Search, Key Vault, Bastion).

---

## 3. UC2 Supervisor Agent

### 3a. Terraform (infra + RBAC + APIM)

```bash
cd uaip-workload-uc2-supervisor-agent/infra
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with your environment values
terraform init
terraform workspace new msdn  # or select existing
terraform apply -var-file=terraform.tfvars
```

**Terraform manages**: Container App, Managed Identity, RBAC (ACR Pull, Key Vault, OpenAI User), App Insights, APIM APIs, Entra app registrations.

### 3b. Build & Deploy Image

```bash
# Open ACR firewall temporarily
az acr update --name $ACR --resource-group $RG --default-action Allow -o none

# Build
az acr build --registry $ACR --resource-group $RG \
  --image uc2-supervisor:cr34 \
  --file services/supervisor-api/Dockerfile.v2 \
  ./services/supervisor-api

# Deploy (update image tag)
az containerapp update \
  --name ca-uc2-supervisor \
  --resource-group $RG \
  --image $ACR.azurecr.io/uc2-supervisor:cr34 \
  -o none

# Lock ACR
az acr update --name $ACR --resource-group $RG --default-action Deny -o none
```

### 3c. CLI-only env vars not in Terraform

**⚠️ These were set via `az containerapp update --set-env-vars` and may not match Terraform state:**

```bash
az containerapp update --name ca-uc2-supervisor --resource-group $RG \
  --set-env-vars \
    "ENABLE_SENSITIVE_DATA=true"
```

> **Note**: The `IMAGE_PULL_TIMESTAMP` env var is used as a workaround to force Container App revision updates when the image tag doesn't change.

---

## 4. UC1 RAG Knowledge Agent

**⚠️ No Terraform — entirely CLI-deployed.**

### 4a. Create Managed Identity

```bash
az identity create \
  --name id-uc1-rag-agent \
  --resource-group $RG \
  --location australiaeast
```

### 4b. RBAC Assignments

```bash
UC1_PRINCIPAL_ID=$(az identity show --name id-uc1-rag-agent --resource-group $RG --query principalId -o tsv)
UC1_CLIENT_ID=$(az identity show --name id-uc1-rag-agent --resource-group $RG --query clientId -o tsv)

# ACR Pull
az role assignment create \
  --assignee-object-id $UC1_PRINCIPAL_ID \
  --assignee-principal-type ServicePrincipal \
  --role "AcrPull" \
  --scope $(az acr show --name $ACR --resource-group $RG --query id -o tsv)

# Azure OpenAI User
az role assignment create \
  --assignee-object-id $UC1_PRINCIPAL_ID \
  --assignee-principal-type ServicePrincipal \
  --role "Cognitive Services OpenAI User" \
  --scope $(az cognitiveservices account show --name $AI_FOUNDRY --resource-group $RG --query id -o tsv)

# AI Search — Index Data Reader + Contributor
SEARCH_ID=$(az search service show --name $SEARCH_NAME --resource-group $RG --query id -o tsv)
az role assignment create \
  --assignee-object-id $UC1_PRINCIPAL_ID \
  --assignee-principal-type ServicePrincipal \
  --role "Search Index Data Reader" \
  --scope $SEARCH_ID

az role assignment create \
  --assignee-object-id $UC1_PRINCIPAL_ID \
  --assignee-principal-type ServicePrincipal \
  --role "Search Index Data Contributor" \
  --scope $SEARCH_ID
```

### 4c. Create App Insights

```bash
az monitor app-insights component create \
  --app ai-uc1-rag-agent \
  --resource-group $RG \
  --location australiaeast \
  --workspace $(az monitor log-analytics workspace show --workspace-name ai-alz-law --resource-group $RG --query id -o tsv)
```

### 4d. Build & Deploy

```bash
az acr update --name $ACR --resource-group $RG --default-action Allow -o none

az acr build --registry $ACR --resource-group $RG \
  --image uc1-rag-agent:cr30 \
  --file services/rag-agent/Dockerfile \
  services/rag-agent

az containerapp create \
  --name ca-uc1-rag-agent \
  --resource-group $RG \
  --environment ai-alz-container-app-env-i40e \
  --image $ACR.azurecr.io/uc1-rag-agent:cr30 \
  --target-port 8080 \
  --ingress external \
  --transport http \
  --cpu 0.5 --memory 1Gi \
  --min-replicas 1 --max-replicas 3 \
  --user-assigned $(az identity show --name id-uc1-rag-agent --resource-group $RG --query id -o tsv) \
  --registry-server $ACR.azurecr.io \
  --registry-identity $(az identity show --name id-uc1-rag-agent --resource-group $RG --query id -o tsv) \
  --env-vars \
    "AZURE_OPENAI_ENDPOINT=https://$AI_FOUNDRY.openai.azure.com/" \
    "AZURE_AI_MODEL_DEPLOYMENT_NAME=gpt-4.1-mini" \
    "AZURE_CLIENT_ID=$UC1_CLIENT_ID" \
    "AZURE_AI_SEARCH_ENDPOINT=https://$SEARCH_NAME.search.windows.net" \
    "AZURE_AI_SEARCH_INDEX=knowledge-base-docs" \
    "APPLICATIONINSIGHTS_CONNECTION_STRING=$(az monitor app-insights component show --app ai-uc1-rag-agent --resource-group $RG --query connectionString -o tsv)" \
    "OTEL_SERVICE_NAME=uc1-rag-agent" \
    "OTEL_RESOURCE_ATTRIBUTES=service.namespace=uaip,deployment.environment=poc" \
    "ENABLE_SENSITIVE_DATA=true"

az acr update --name $ACR --resource-group $RG --default-action Deny -o none
```

---

## 5. UC3 Governance Hub

### 5a. Terraform

```bash
cd uaip-workload-uc3-governance-hub/infra
cp terraform.tfvars.example terraform.tfvars
terraform init
terraform workspace new msdn
terraform apply -var-file=terraform.tfvars
```

**Terraform manages**: Container App, OTEL Collector, Managed Identity, RBAC, APIM APIs, App Insights, Cosmos DB, Service Bus, Event Grid, Sentinel workspace, FinOps Workbook.

### 5b. Build & Deploy

```bash
az acr update --name $ACR --resource-group $RG --default-action Allow -o none

az acr build --registry $ACR --resource-group $RG \
  --image uc3-governance-api:latest \
  --file services/governance-api/Dockerfile \
  services/governance-api

az containerapp update \
  --name ca-uc3-governance \
  --resource-group $RG \
  --image $ACR.azurecr.io/uc3-governance-api:latest \
  -o none

az acr update --name $ACR --resource-group $RG --default-action Deny -o none
```

---

## 6. Frontend

**⚠️ No Terraform — entirely CLI-deployed.**

### 6a. Build & Deploy

```bash
cd uaip-frontend

az acr update --name $ACR --resource-group $RG --default-action Allow -o none

az acr build --registry $ACR --resource-group $RG \
  --image uaip-frontend:cr27 .

az containerapp create \
  --name ca-uaip-frontend \
  --resource-group $RG \
  --environment ai-alz-container-app-env-i40e \
  --image $ACR.azurecr.io/uaip-frontend:cr27 \
  --target-port 8000 \
  --ingress external \
  --transport http \
  --cpu 0.25 --memory 0.5Gi \
  --min-replicas 1 --max-replicas 1 \
  --registry-server $ACR.azurecr.io \
  --system-assigned

az acr update --name $ACR --resource-group $RG --default-action Deny -o none
```

> The frontend is a static React app served by a Python HTTP server. It calls the UC2 supervisor API endpoint directly from the browser.

---

## 7. AWS Bedrock Cross-Cloud Agent

### 7a. AWS Side (Lambda + API Gateway)

Deployed from `uaip-bedrock-agent` repo. See its README for:
- Lambda function with Claude Sonnet 4 via Bedrock
- API Gateway with JWT authorizer (validates Azure Entra tokens)
- Gateway URL: `https://dkzipl1xle.execute-api.ap-southeast-2.amazonaws.com`

### 7b. Azure Entra Registration

The UC2 Terraform (`main.entra.tf`) creates:
- App registration for AWS federation (`AWS_FEDERATION_CLIENT_ID`)
- Used by the supervisor to get JWT tokens for cross-cloud calls

---

## 8. Grafana Observability

**⚠️ Grafana was created via CLI, not Terraform:**

### 8a. Create Grafana Instance

```bash
az grafana create \
  --name uaip-grafana \
  --resource-group $RG \
  --location australiaeast \
  --sku-tier Standard \
  --public-network-access Enabled
```

### 8b. Grant Access

```bash
GRAFANA_ID=$(az grafana show --name uaip-grafana --resource-group $RG --query id -o tsv)
MY_UPN=$(az account show --query user.name -o tsv)
az role assignment create --assignee "$MY_UPN" --role "Grafana Admin" --scope "$GRAFANA_ID"
```

### 8c. Data Source

Azure Monitor data source is auto-provisioned (`azure-monitor-oob`) using managed identity.

### 8d. Custom Dashboard

The custom "UAIP — Agent Observability & FinOps" dashboard (uid: `uaip-agent-finops-v3`) was created via the Grafana API using a Python script. The dashboard JSON includes 11 panels covering:
- Agent Invocations, Token Usage by Model, LLM Latency
- Token Usage Over Time, Tool Executions, Workflow Execution
- Cross-Cloud section (Bedrock calls, Lambda telemetry)
- All External Dependencies

> The dashboard was pushed via `az grafana dashboard create` / API. To re-create, use the export feature from the current Grafana instance or run the deployment script.

### 8e. Pre-built Azure Dashboards

Grafana Standard tier includes ~40 pre-built Azure dashboards. Notable ones for this PoC:
- `Azure / Insights / Applications` (uid: `Yo38mcvnz`)
- `Azure / Insights / Applications / OTel / HTTP`

---

## 9. CLI-Only Changes Not in Terraform

This is the critical section — changes made via Azure CLI that would be **lost** if you only ran Terraform:

### 9a. UC1 RAG Agent (entire deployment)

The UC1 container app, managed identity, RBAC, and App Insights were **all created via CLI**. There is no Terraform for UC1. See [Section 4](#4-uc1-rag-knowledge-agent).

### 9b. Frontend (entire deployment)

The frontend container app was **entirely created via CLI**. There is no Terraform. See [Section 6](#6-frontend).

### 9c. AI Search Configuration

```bash
# Auth mode change (was apiKeyOnly → aadOrApiKey)
az search service update --name $SEARCH_NAME --resource-group $RG --auth-options aadOrApiKey

# Public access enable
az search service update --name $SEARCH_NAME --resource-group $RG --public-access enabled

# Index "knowledge-base-docs" — created via document upload, schema not captured as code
```

### 9d. Log Analytics Public Access

```bash
az monitor log-analytics workspace update \
  --workspace-name ai-alz-law --resource-group $RG \
  --ingestion-access Enabled --query-access Enabled
```

### 9e. ENABLE_SENSITIVE_DATA env var

Set on both UC1 and UC2 container apps via `--set-env-vars`:
```bash
az containerapp update --name ca-uc2-supervisor --resource-group $RG --set-env-vars "ENABLE_SENSITIVE_DATA=true"
az containerapp update --name ca-uc1-rag-agent --resource-group $RG --set-env-vars "ENABLE_SENSITIVE_DATA=true"
```

### 9f. Grafana (entire deployment)

Created via CLI. See [Section 8](#8-grafana-observability).

### 9g. Azure OpenAI Model Deployments

Created via CLI or portal. See [Section 1](#azure-openai-model-deployments).

### 9h. Bastion Recreation

Bastion was recreated after MSDN credit deallocation. This is handled by ALZ Terraform but the recreation was done via CLI.

### 9i. UC3 Governance Endpoint Typo

The UC2 supervisor has a double-`https://` in `UC3_GOVERNANCE_ENDPOINT`:
```
https://https://ai-alz-apim-i40e.azure-api.net/uc3
```
This is in the Terraform `main.container_app.tf` as a computed value — check the template generates the correct URL.

---

## 10. Post-Deployment Verification

```bash
# 1. Test UC1 RAG agent
curl -X POST https://ca-uc1-rag-agent.<CAE-FQDN>/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What is an instrument data sheet?"}'

# 2. Test UC2 Supervisor (via APIM or direct)
curl -X POST https://ca-uc2-supervisor.<CAE-FQDN>/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What are the safety requirements for valve selection?"}'

# 3. Check telemetry in App Insights (wait 5 min)
az monitor app-insights query \
  --app ai-uc2-supervisor-appinsights \
  --resource-group $RG \
  --analytics-query "dependencies | where timestamp > ago(15m) | summarize count() by name"

# 4. Verify Grafana dashboard
# Open: https://<grafana-endpoint>/d/uaip-agent-finops-v3
```

---

## Environment Variables Reference

### UC2 Supervisor (`ca-uc2-supervisor`)

| Variable | Value | Source |
|----------|-------|--------|
| `AZURE_OPENAI_ENDPOINT` | `https://ai-foundry-*.openai.azure.com/` | Terraform |
| `AZURE_AI_MODEL_DEPLOYMENT_NAME` | `gpt-4.1` | Terraform |
| `AZURE_CLIENT_ID` | managed identity client ID | Terraform |
| `AZURE_AI_ENDPOINT` | `{AOAI}/openai/deployments/gpt-4.1` | Terraform |
| `AZURE_AI_DEPLOYMENT` | `gpt-4.1` | Terraform |
| `COMPLIANCE_MODEL` | `o4-mini` | Terraform |
| `AWS_BEDROCK_GATEWAY_URL` | `https://dkzipl1xle.execute-api...` | Terraform |
| `AWS_FEDERATION_CLIENT_ID` | Entra app client ID | Terraform |
| `UC1_RAG_ENDPOINT` | `https://ca-uc1-rag-agent.<CAE>` | Terraform |
| `UC3_GOVERNANCE_ENDPOINT` | `https://<APIM>/uc3` | Terraform |
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | App Insights conn string | Terraform |
| `OTEL_SERVICE_NAME` | `uc2-supervisor-api` | Terraform |
| `OTEL_RESOURCE_ATTRIBUTES` | `service.namespace=uaip,...` | Terraform |
| `ENABLE_SENSITIVE_DATA` | `true` | **CLI-only** |

### UC1 RAG Agent (`ca-uc1-rag-agent`)

| Variable | Value | Source |
|----------|-------|--------|
| `AZURE_OPENAI_ENDPOINT` | `https://ai-foundry-*.openai.azure.com/` | **CLI-only** |
| `AZURE_AI_MODEL_DEPLOYMENT_NAME` | `gpt-4.1-mini` | **CLI-only** |
| `AZURE_CLIENT_ID` | managed identity client ID | **CLI-only** |
| `AZURE_AI_SEARCH_ENDPOINT` | `https://ai-alz-ks-ai-search-*.search.windows.net` | **CLI-only** |
| `AZURE_AI_SEARCH_INDEX` | `knowledge-base-docs` | **CLI-only** |
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | App Insights conn string | **CLI-only** |
| `OTEL_SERVICE_NAME` | `uc1-rag-agent` | **CLI-only** |
| `OTEL_RESOURCE_ATTRIBUTES` | `service.namespace=uaip,...` | **CLI-only** |
| `ENABLE_SENSITIVE_DATA` | `true` | **CLI-only** |

---

## Git Repositories

| Repo | Purpose | Has Terraform? |
|------|---------|---------------|
| `uaip-workload-uc1-rag-agent` | Knowledge RAG agent | ❌ No |
| `uaip-workload-uc2-supervisor-agent` | Multi-agent supervisor | ✅ Yes |
| `uaip-workload-uc3-governance-hub` | Governance + FinOps | ✅ Yes |
| `uaip-frontend` (private) | React frontend | ❌ No |
| `uaip-bedrock-agent` | AWS Lambda + API GW | ❌ (AWS CDK/manual) |
| `azure-ai-landing-zone-terraform` | Shared landing zone | ✅ Yes |
| `alz-customizations` | AI Gateway snippets | ❌ Not a git repo |
