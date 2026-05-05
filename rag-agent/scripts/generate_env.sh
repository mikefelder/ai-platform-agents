#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# generate_env.sh
#
# Reads resource details from the deployed AVM AI/ML Landing Zone (via az CLI)
# and writes a populated .env file for use-case-1.
#
# Prerequisites:
#   - az CLI logged in (`az login`)
#   - The AVM AI/ML Landing Zone already deployed to the target subscription
#
# Usage:
#   ./use-case-1/scripts/generate_env.sh -g <RESOURCE_GROUP> [-s <SUBSCRIPTION_ID>]
#
# Example:
#   ./use-case-1/scripts/generate_env.sh -g rg-contoso-ai-poc-abc12
# ---------------------------------------------------------------------------
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE="${SCRIPT_DIR}/../.env"
SUBSCRIPTION=""
RESOURCE_GROUP=""

# ── Parse args ───────────────────────────────────────────────────────────────
usage() {
  echo "Usage: $0 -g <resource-group> [-s <subscription-id>] [-o <output-file>]"
  exit 1
}

while getopts "g:s:o:h" opt; do
  case $opt in
    g) RESOURCE_GROUP="$OPTARG" ;;
    s) SUBSCRIPTION="$OPTARG" ;;
    o) ENV_FILE="$OPTARG" ;;
    h) usage ;;
    *) usage ;;
  esac
done

[[ -z "$RESOURCE_GROUP" ]] && { echo "Error: -g <resource-group> is required"; usage; }

SUB_FLAG=""
[[ -n "$SUBSCRIPTION" ]] && SUB_FLAG="--subscription $SUBSCRIPTION"

# ── Helpers ──────────────────────────────────────────────────────────────────
info()  { printf '\033[1;34m▶ %s\033[0m\n' "$*"; }
ok()    { printf '\033[1;32m✔ %s\033[0m\n' "$*"; }
warn()  { printf '\033[1;33m⚠ %s\033[0m\n' "$*"; }

# Find a resource by type, return the first match's name
find_resource() {
  local type="$1"
  # shellcheck disable=SC2086
  az resource list -g "$RESOURCE_GROUP" $SUB_FLAG \
    --resource-type "$type" --query "[0].name" -o tsv 2>/dev/null || echo ""
}

# ── Discover resources ───────────────────────────────────────────────────────
info "Discovering resources in resource group: ${RESOURCE_GROUP}"

# AI Services (multi-service account providing OpenAI endpoint)
AI_SERVICES_NAME=$(find_resource "Microsoft.CognitiveServices/accounts")
if [[ -z "$AI_SERVICES_NAME" ]]; then
  echo "Error: No Cognitive Services account found in ${RESOURCE_GROUP}"
  exit 1
fi

# There may be multiple cognitive accounts — find the AIServices kind specifically
AI_SERVICES_NAME=$(
  # shellcheck disable=SC2086
  az cognitiveservices account list -g "$RESOURCE_GROUP" $SUB_FLAG \
    --query "[?kind=='AIServices'].name | [0]" -o tsv 2>/dev/null || echo "$AI_SERVICES_NAME"
)
info "AI Services: ${AI_SERVICES_NAME}"

# shellcheck disable=SC2086
AI_SERVICES_ENDPOINT=$(az cognitiveservices account show \
  -n "$AI_SERVICES_NAME" -g "$RESOURCE_GROUP" $SUB_FLAG \
  --query "properties.endpoint" -o tsv)

# shellcheck disable=SC2086
AI_SERVICES_KEY=$(az cognitiveservices account keys list \
  -n "$AI_SERVICES_NAME" -g "$RESOURCE_GROUP" $SUB_FLAG \
  --query "key1" -o tsv)

# Extract subdomain (AZURE_OPENAI_RESOURCE expects just the name, not full URL)
AI_SERVICES_RESOURCE=$(echo "$AI_SERVICES_ENDPOINT" | sed 's|https://||;s|\.cognitiveservices.*||;s|\.openai.*||')

# Model deployments
# shellcheck disable=SC2086
CHAT_DEPLOYMENT=$(az cognitiveservices account deployment list \
  -n "$AI_SERVICES_NAME" -g "$RESOURCE_GROUP" $SUB_FLAG \
  --query "[?properties.model.name=='gpt-4o' || properties.model.name=='gpt-4.1' || contains(properties.model.name,'gpt-4')].name | [0]" -o tsv 2>/dev/null || echo "")
[[ -z "$CHAT_DEPLOYMENT" ]] && warn "No GPT-4 chat deployment found — set AZURE_OPENAI_MODEL manually"

# shellcheck disable=SC2086
CHAT_MODEL=$(az cognitiveservices account deployment list \
  -n "$AI_SERVICES_NAME" -g "$RESOURCE_GROUP" $SUB_FLAG \
  --query "[?name=='${CHAT_DEPLOYMENT}'].properties.model.name | [0]" -o tsv 2>/dev/null || echo "$CHAT_DEPLOYMENT")

# shellcheck disable=SC2086
EMBEDDING_DEPLOYMENT=$(az cognitiveservices account deployment list \
  -n "$AI_SERVICES_NAME" -g "$RESOURCE_GROUP" $SUB_FLAG \
  --query "[?contains(properties.model.name,'embedding')].name | [0]" -o tsv 2>/dev/null || echo "")
[[ -z "$EMBEDDING_DEPLOYMENT" ]] && warn "No embedding deployment found — set AZURE_OPENAI_EMBEDDING_MODEL manually"

# AI Search
SEARCH_NAME=$(find_resource "Microsoft.Search/searchServices")
if [[ -n "$SEARCH_NAME" ]]; then
  SEARCH_ENDPOINT="https://${SEARCH_NAME}.search.windows.net"
  # shellcheck disable=SC2086
  SEARCH_KEY=$(az search admin-key show \
    --service-name "$SEARCH_NAME" -g "$RESOURCE_GROUP" $SUB_FLAG \
    --query "primaryKey" -o tsv 2>/dev/null || echo "")
  info "AI Search: ${SEARCH_NAME}"
else
  warn "No AI Search found — set AZURE_SEARCH_* manually"
  SEARCH_ENDPOINT=""
  SEARCH_KEY=""
fi

# Storage Account
STORAGE_NAME=$(find_resource "Microsoft.Storage/storageAccounts")
if [[ -n "$STORAGE_NAME" ]]; then
  # shellcheck disable=SC2086
  STORAGE_KEY=$(az storage account keys list \
    -n "$STORAGE_NAME" -g "$RESOURCE_GROUP" $SUB_FLAG \
    --query "[0].value" -o tsv 2>/dev/null || echo "")
  # shellcheck disable=SC2086
  STORAGE_CONN=$(az storage account show-connection-string \
    -n "$STORAGE_NAME" -g "$RESOURCE_GROUP" $SUB_FLAG \
    --query "connectionString" -o tsv 2>/dev/null || echo "")
  info "Storage: ${STORAGE_NAME}"
else
  warn "No Storage Account found — set AZURE_BLOB_* manually"
  STORAGE_KEY=""
  STORAGE_CONN=""
fi

# Document Intelligence (FormRecognizer)
# shellcheck disable=SC2086
DOCINT_NAME=$(az cognitiveservices account list -g "$RESOURCE_GROUP" $SUB_FLAG \
  --query "[?kind=='FormRecognizer'].name | [0]" -o tsv 2>/dev/null || echo "")
if [[ -n "$DOCINT_NAME" ]]; then
  # shellcheck disable=SC2086
  DOCINT_ENDPOINT=$(az cognitiveservices account show \
    -n "$DOCINT_NAME" -g "$RESOURCE_GROUP" $SUB_FLAG \
    --query "properties.endpoint" -o tsv)
  # shellcheck disable=SC2086
  DOCINT_KEY=$(az cognitiveservices account keys list \
    -n "$DOCINT_NAME" -g "$RESOURCE_GROUP" $SUB_FLAG \
    --query "key1" -o tsv)
  info "Document Intelligence: ${DOCINT_NAME}"
else
  warn "No Document Intelligence found — set AZURE_FORM_RECOGNIZER_* manually"
  DOCINT_ENDPOINT=""
  DOCINT_KEY=""
fi

# Content Safety
# shellcheck disable=SC2086
CSAFETY_NAME=$(az cognitiveservices account list -g "$RESOURCE_GROUP" $SUB_FLAG \
  --query "[?kind=='ContentSafety'].name | [0]" -o tsv 2>/dev/null || echo "")
if [[ -n "$CSAFETY_NAME" ]]; then
  # shellcheck disable=SC2086
  CSAFETY_ENDPOINT=$(az cognitiveservices account show \
    -n "$CSAFETY_NAME" -g "$RESOURCE_GROUP" $SUB_FLAG \
    --query "properties.endpoint" -o tsv)
  # shellcheck disable=SC2086
  CSAFETY_KEY=$(az cognitiveservices account keys list \
    -n "$CSAFETY_NAME" -g "$RESOURCE_GROUP" $SUB_FLAG \
    --query "key1" -o tsv)
  info "Content Safety: ${CSAFETY_NAME}"
else
  warn "No Content Safety found — set AZURE_CONTENT_SAFETY_* manually"
  CSAFETY_ENDPOINT=""
  CSAFETY_KEY=""
fi

# Key Vault
KV_NAME=$(find_resource "Microsoft.KeyVault/vaults")
if [[ -n "$KV_NAME" ]]; then
  KV_ENDPOINT="https://${KV_NAME}.vault.azure.net/"
  info "Key Vault: ${KV_NAME}"
else
  warn "No Key Vault found"
  KV_ENDPOINT=""
fi

# PostgreSQL
PG_NAME=$(find_resource "Microsoft.DBforPostgreSQL/flexibleServers")
if [[ -n "$PG_NAME" ]]; then
  # shellcheck disable=SC2086
  PG_HOST=$(az postgres flexible-server show \
    -n "$PG_NAME" -g "$RESOURCE_GROUP" $SUB_FLAG \
    --query "fullyQualifiedDomainName" -o tsv)
  info "PostgreSQL: ${PG_NAME}"
else
  warn "No PostgreSQL found — set AZURE_POSTGRESQL_* manually"
  PG_HOST=""
fi

# Application Insights
APPI_NAME=$(find_resource "Microsoft.Insights/components")
if [[ -n "$APPI_NAME" ]]; then
  # shellcheck disable=SC2086
  APPI_CONN=$(az monitor app-insights component show \
    -a "$APPI_NAME" -g "$RESOURCE_GROUP" $SUB_FLAG \
    --query "connectionString" -o tsv 2>/dev/null || echo "")
  info "App Insights: ${APPI_NAME}"
else
  warn "No Application Insights found"
  APPI_CONN=""
fi

# ── Write .env ───────────────────────────────────────────────────────────────
info "Writing ${ENV_FILE}…"

cat > "${ENV_FILE}" <<EOF
# =============================================================================
# Auto-generated by use-case-1/scripts/generate_env.sh
# Source resource group: ${RESOURCE_GROUP}
# Generated: $(date -u +"%Y-%m-%dT%H:%M:%SZ")
# =============================================================================

# Azure AI Search
AZURE_SEARCH_SERVICE=${SEARCH_ENDPOINT}
AZURE_SEARCH_INDEX=cwyd-index
AZURE_SEARCH_KEY=${SEARCH_KEY}
AZURE_SEARCH_USE_SEMANTIC_SEARCH=True
AZURE_SEARCH_SEMANTIC_SEARCH_CONFIG=default
AZURE_SEARCH_TOP_K=5
AZURE_SEARCH_ENABLE_IN_DOMAIN=True
AZURE_SEARCH_FIELDS_ID=id
AZURE_SEARCH_CONTENT_COLUMN=content
AZURE_SEARCH_CONTENT_VECTOR_COLUMN=content_vector
AZURE_SEARCH_DIMENSIONS=1536
AZURE_SEARCH_FIELDS_TAG=tag
AZURE_SEARCH_FIELDS_METADATA=metadata
AZURE_SEARCH_FILENAME_COLUMN=filepath
AZURE_SEARCH_TITLE_COLUMN=title
AZURE_SEARCH_SOURCE_COLUMN=source
AZURE_SEARCH_TEXT_COLUMN=text
AZURE_SEARCH_LAYOUT_TEXT_COLUMN=layoutText
AZURE_SEARCH_URL_COLUMN=url
AZURE_SEARCH_CONVERSATIONS_LOG_INDEX=conversations-log
AZURE_SEARCH_USE_INTEGRATED_VECTORIZATION=false
AZURE_SEARCH_INDEXER_NAME=
AZURE_SEARCH_DATASOURCE_NAME=

# Azure OpenAI (via AI Services)
AZURE_OPENAI_RESOURCE=${AI_SERVICES_RESOURCE}
AZURE_OPENAI_API_KEY=${AI_SERVICES_KEY}
AZURE_OPENAI_MODEL=${CHAT_DEPLOYMENT}
AZURE_OPENAI_MODEL_NAME=${CHAT_MODEL}
AZURE_OPENAI_EMBEDDING_MODEL=${EMBEDDING_DEPLOYMENT}
AZURE_OPENAI_TEMPERATURE=0
AZURE_OPENAI_TOP_P=1.0
AZURE_OPENAI_MAX_TOKENS=1000
AZURE_OPENAI_STOP_SEQUENCE=
AZURE_OPENAI_SYSTEM_MESSAGE=You are an AI assistant that helps Litware Energy employees find information from internal knowledge sources.
AZURE_OPENAI_API_VERSION=2024-02-01
AZURE_OPENAI_STREAM=True

# Backend / Functions
AzureWebJobsStorage=${STORAGE_CONN}
BACKEND_URL=http://localhost:7071

# Logging
LOGLEVEL=INFO
PACKAGE_LOGGING_LEVEL=WARNING

# Storage
DOCUMENT_PROCESSING_QUEUE_NAME=doc-processing
AZURE_BLOB_ACCOUNT_NAME=${STORAGE_NAME}
AZURE_BLOB_ACCOUNT_KEY=${STORAGE_KEY}
AZURE_BLOB_CONTAINER_NAME=documents

# Document Intelligence
AZURE_FORM_RECOGNIZER_ENDPOINT=${DOCINT_ENDPOINT}
AZURE_FORM_RECOGNIZER_KEY=${DOCINT_KEY}

# Content Safety
AZURE_CONTENT_SAFETY_ENDPOINT=${CSAFETY_ENDPOINT}
AZURE_CONTENT_SAFETY_KEY=${CSAFETY_KEY}

# Orchestration
ORCHESTRATION_STRATEGY=openai_function

# Prompt Flow (not used)
AZURE_ML_WORKSPACE_NAME=
PROMPT_FLOW_DEPLOYMENT_NAME=
PROMPT_FLOW_ENDPOINT_NAME=

# Speech (optional)
AZURE_SPEECH_SERVICE_KEY=
AZURE_SPEECH_SERVICE_REGION=

# Auth
AZURE_AUTH_TYPE=keys
USE_KEY_VAULT=false
AZURE_KEY_VAULT_ENDPOINT=${KV_ENDPOINT}

# App
APP_ENV=dev
CONVERSATION_FLOW=custom

# Cosmos DB (not used — PostgreSQL selected)
AZURE_COSMOSDB_ACCOUNT_NAME=
AZURE_COSMOSDB_ACCOUNT_KEY=
AZURE_COSMOSDB_DATABASE_NAME=
AZURE_COSMOSDB_CONVERSATIONS_CONTAINER_NAME=
AZURE_COSMOSDB_ENABLE_FEEDBACK=

# PostgreSQL
AZURE_POSTGRESQL_HOST_NAME=${PG_HOST}
AZURE_POSTGRESQL_DATABASE_NAME=cwyd
AZURE_POSTGRESQL_USER=cwydsqladmin
DATABASE_TYPE=PostgreSQL

# Application Insights
APPLICATIONINSIGHTS_ENABLED=true
APPLICATIONINSIGHTS_CONNECTION_STRING=${APPI_CONN}
EOF

ok ".env written to ${ENV_FILE}"
echo ""
echo "  OpenAI resource:  ${AI_SERVICES_RESOURCE}"
echo "  Chat deployment:  ${CHAT_DEPLOYMENT:-<not found>}"
echo "  Embedding:        ${EMBEDDING_DEPLOYMENT:-<not found>}"
echo "  AI Search:        ${SEARCH_NAME:-<not found>}"
echo "  Storage:          ${STORAGE_NAME:-<not found>}"
echo "  PostgreSQL:       ${PG_HOST:-<not found>}"
echo ""
echo "  Review the .env and fill in any missing values (marked with warnings above)."
echo "  PostgreSQL password must be set manually: AZURE_POSTGRESQL_PASSWORD"
EOF_WARN=""
[[ -z "$CHAT_DEPLOYMENT" ]] && EOF_WARN="${EOF_WARN}\n  ⚠ AZURE_OPENAI_MODEL needs to be set"
[[ -z "$EMBEDDING_DEPLOYMENT" ]] && EOF_WARN="${EOF_WARN}\n  ⚠ AZURE_OPENAI_EMBEDDING_MODEL needs to be set"
[[ -z "$DOCINT_ENDPOINT" ]] && EOF_WARN="${EOF_WARN}\n  ⚠ AZURE_FORM_RECOGNIZER_* needs to be set"
[[ -z "$CSAFETY_ENDPOINT" ]] && EOF_WARN="${EOF_WARN}\n  ⚠ AZURE_CONTENT_SAFETY_* needs to be set"
[[ -n "$EOF_WARN" ]] && printf "\n%b\n" "$EOF_WARN"
