# -----------------------------------------------------------------------------
# Platform / ALZ references
# -----------------------------------------------------------------------------

variable "subscription_id" {
  description = "Azure subscription ID."
  type        = string
}

variable "resource_group_name" {
  description = "Name of the ALZ resource group."
  type        = string
}

variable "location" {
  description = "Azure region."
  type        = string
  default     = "australiaeast"
}

variable "container_app_environment_name" {
  description = "Name of the Container App Environment."
  type        = string
}

variable "alz_vnet_name" {
  description = "Name of the ALZ virtual network hosting CAE/APIM/Jumpbox subnets."
  type        = string
}

variable "container_registry_name" {
  description = "Name of the Azure Container Registry."
  type        = string
}

variable "log_analytics_workspace_name" {
  description = "Name of the Log Analytics Workspace."
  type        = string
}

variable "apim_name" {
  description = "Name of the API Management instance."
  type        = string
}

variable "key_vault_name" {
  description = "Name of the Key Vault."
  type        = string
}

variable "ai_services_name" {
  description = "Name of the AI Services account."
  type        = string
}

variable "ai_search_name" {
  description = "Name of the AI Search service."
  type        = string
}

variable "azure_ai_deployment" {
  description = "Name of the AI model deployment."
  type        = string
  default     = "gpt-4.1"
}

# -----------------------------------------------------------------------------
# UC1 workload configuration
# -----------------------------------------------------------------------------

variable "rag_image_tag" {
  description = "Container image tag for the RAG agent."
  type        = string
  default     = "latest"
}

variable "rag_min_replicas" {
  description = "Minimum replicas."
  type        = number
  default     = 1
}

variable "rag_max_replicas" {
  description = "Maximum replicas."
  type        = number
  default     = 3
}

variable "search_index_name" {
  description = "Name of the AI Search index for documents."
  type        = string
  default     = "knowledge-base-docs"
}

variable "tags" {
  description = "Tags to apply to all resources."
  type        = map(string)
  default = {
    workload = "uc1-rag-agent"
    program  = "uaip"
  }
}

variable "enable_sensitive_data" {
  description = "Enable prompt/response capture in OTEL telemetry. Set to false in production."
  type        = bool
  default     = true
}
