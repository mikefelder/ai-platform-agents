# -----------------------------------------------------------------------------
# Platform / ALZ references — these point to resources already deployed by the
# uaip-platform-alz Terraform.
# -----------------------------------------------------------------------------

variable "subscription_id" {
  description = "Azure subscription ID where the ALZ was deployed."
  type        = string
}

variable "resource_group_name" {
  description = "Name of the ALZ resource group (e.g. ai-lz-rg-standalone-yc9gj)."
  type        = string
}

variable "location" {
  description = "Azure region (must match ALZ deployment)."
  type        = string
  default     = "australiaeast"
}

variable "container_app_environment_name" {
  description = "Name of the Container App Environment deployed by the ALZ."
  type        = string
}

variable "container_registry_name" {
  description = "Name of the Azure Container Registry deployed by the ALZ."
  type        = string
}

variable "log_analytics_workspace_name" {
  description = "Name of the Log Analytics Workspace deployed by the ALZ."
  type        = string
}

variable "apim_name" {
  description = "Name of the API Management instance deployed by the ALZ."
  type        = string
}

variable "key_vault_name" {
  description = "Name of the GenAI Key Vault deployed by the ALZ."
  type        = string
}

variable "ai_services_name" {
  description = "Name of the AI Services (Cognitive Services) account deployed by the ALZ."
  type        = string
}

variable "azure_ai_deployment" {
  description = "Name of the AI Foundry model deployment to use."
  type        = string
  default     = "gpt-4.1"
}

# -----------------------------------------------------------------------------
# UC2 workload configuration
# -----------------------------------------------------------------------------

variable "supervisor_image_tag" {
  description = "Container image tag for the supervisor-api (e.g. latest, v1.0.0)."
  type        = string
  default     = "latest"
}

variable "aws_bedrock_endpoint" {
  description = "Full URL of the AWS Bedrock AgentCore invocations endpoint."
  type        = string
}

variable "uc1_rag_endpoint" {
  description = "FQDN URL of the UC1 RAG Knowledge Agent container app (direct container-to-container)."
  type        = string
}

variable "enable_sensitive_data" {
  description = "Enable prompt/response capture in OTEL telemetry. Set to false in production."
  type        = bool
  default     = true
}

variable "aws_bedrock_gateway_mode" {
  description = "Gateway mode: 'sync' for AgentCore direct, 'async' for MCP gateway."
  type        = string
  default     = "sync"

  validation {
    condition     = contains(["sync", "async"], var.aws_bedrock_gateway_mode)
    error_message = "Must be 'sync' or 'async'."
  }
}

variable "aws_bedrock_agents" {
  description = "List of Bedrock agent names to invoke."
  type        = list(string)
  default     = ["compliance"]
}

variable "supervisor_min_replicas" {
  description = "Minimum number of Container App replicas."
  type        = number
  default     = 1
}

variable "supervisor_max_replicas" {
  description = "Maximum number of Container App replicas."
  type        = number
  default     = 3
}

variable "tags" {
  description = "Tags to apply to all workload resources."
  type        = map(string)
  default = {
    workload = "uc2-supervisor-agent"
    program  = "uaip"
  }
}

# -----------------------------------------------------------------------------
# AWS OIDC federation — values provided by the AWS engineer
# -----------------------------------------------------------------------------

variable "aws_oidc_issuer" {
  description = "OIDC issuer URL for AWS Bedrock AgentCore. Leave empty to skip federated credential creation."
  type        = string
  default     = ""
}

variable "aws_oidc_subject" {
  description = "OIDC subject claim from the AWS Bedrock agent identity. Leave empty to skip federated credential creation."
  type        = string
  default     = ""
}
