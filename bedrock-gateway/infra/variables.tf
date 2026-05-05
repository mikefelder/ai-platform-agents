variable "aws_region" {
  description = "AWS region for gateway deployment."
  type        = string
  default     = "ap-southeast-2"
}

variable "environment" {
  description = "Deployment environment label (dev, poc, prod)."
  type        = string
  default     = "poc"
}

variable "name_prefix" {
  description = "Resource name prefix."
  type        = string
  default     = "uaip-bedrock"
}

# ---------------------------------------------------------------------------
# Bedrock target selection (pick one; fallback Converse model is used if none)
# ---------------------------------------------------------------------------

variable "bedrock_agent_runtime_arn" {
  description = "Optional Bedrock AgentCore runtime ARN. When set, the executor uses bedrock-agentcore.InvokeAgentRuntime."
  type        = string
  default     = ""
}

variable "bedrock_agent_id" {
  description = "Optional classic Bedrock Agent id (bedrock-agent-runtime.InvokeAgent)."
  type        = string
  default     = ""
}

variable "bedrock_agent_alias_id" {
  description = "Optional Bedrock Agent alias id. Required alongside bedrock_agent_id."
  type        = string
  default     = ""
}

variable "bedrock_fallback_model_id" {
  description = "Bedrock model id (or inference profile id) for the fallback Converse path. Default is the APAC-region inference profile for Claude Haiku 4.5."
  type        = string
  default     = "au.anthropic.claude-haiku-4-5-20251001-v1:0"
}

# ---------------------------------------------------------------------------
# Telemetry export to Azure Monitor
# ---------------------------------------------------------------------------

variable "application_insights_connection_string" {
  description = "Azure Application Insights connection string. When set, the Lambdas export traces to Azure Monitor."
  type        = string
  sensitive   = true
  default     = ""
}

variable "otel_exporter_otlp_endpoint" {
  description = "Optional generic OTLP/HTTP endpoint (e.g. APIM-fronted collector). Leave blank to skip."
  type        = string
  default     = ""
}

variable "otel_exporter_otlp_headers" {
  description = "Comma-separated key=value headers for the OTLP exporter (e.g. Ocp-Apim-Subscription-Key=...)."
  type        = string
  sensitive   = true
  default     = ""
}

# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

variable "gateway_static_bearer" {
  description = "Static bearer token to require on /agents/*/invoke. Leave blank to disable (PoC only; production uses Entra OIDC)."
  type        = string
  sensitive   = true
  default     = ""
}

# ---- Entra ID workload identity federation (scaffold only) ------------------

variable "entra_tenant_id" {
  description = "Azure Entra ID tenant id. Leave blank to skip OIDC provider creation."
  type        = string
  default     = ""
}

variable "entra_application_id" {
  description = "Azure Entra application (client) id that the Azure supervisor uses to federate into AWS. TODO: populate once Azure-side app registration exists."
  type        = string
  default     = ""
}

# ---------------------------------------------------------------------------
# Observability
# ---------------------------------------------------------------------------

variable "log_retention_days" {
  description = "CloudWatch log retention in days."
  type        = number
  default     = 14
}
