# -----------------------------------------------------------------------------
# Outputs — values needed for wiring up the cross-cloud integration
# -----------------------------------------------------------------------------

# --- Telemetry (share with AWS engineer) ---

output "appinsights_connection_string" {
  description = "Application Insights connection string — set as APPLICATIONINSIGHTS_CONNECTION_STRING."
  value       = azurerm_application_insights.uc2.connection_string
  sensitive   = true
}

output "appinsights_instrumentation_key" {
  description = "Application Insights instrumentation key."
  value       = azurerm_application_insights.uc2.instrumentation_key
  sensitive   = true
}

# --- OIDC federation (share with AWS engineer) ---

output "oidc_issuer" {
  description = "OIDC issuer URL for Entra ID token validation."
  value       = "https://login.microsoftonline.com/${data.azurerm_client_config.current.tenant_id}/v2.0"
}

output "oidc_audience" {
  description = "OIDC audience — the Application (client) ID of the federation app registration."
  value       = azuread_application.uc2_federation.client_id
}

output "oidc_jwks_uri" {
  description = "JWKS URI for Entra ID token signature verification."
  value       = "https://login.microsoftonline.com/${data.azurerm_client_config.current.tenant_id}/discovery/v2.0/keys"
}

# --- Container App ---

output "supervisor_fqdn" {
  description = "Internal FQDN of the supervisor Container App."
  value       = azurerm_container_app.supervisor.ingress[0].fqdn
}

output "supervisor_identity_principal_id" {
  description = "Principal ID of the supervisor managed identity."
  value       = azurerm_user_assigned_identity.supervisor.principal_id
}

output "supervisor_identity_client_id" {
  description = "Client ID of the supervisor managed identity."
  value       = azurerm_user_assigned_identity.supervisor.client_id
}

# --- APIM ---

output "apim_gateway_url" {
  description = "APIM gateway URL for the UC2 supervisor API."
  value       = "${data.azurerm_api_management.alz.gateway_url}/uc2"
}

# --- AWS Bedrock agent app registration (share with AWS engineer) ---

output "aws_bedrock_agent_client_id" {
  description = "Client ID (audience) for the AWS Bedrock agent Entra app registration."
  value       = azuread_application.aws_bedrock_agent.client_id
}

output "aws_bedrock_agent_oidc_issuer" {
  description = "Entra OIDC issuer URL that AWS should validate tokens against."
  value       = "https://login.microsoftonline.com/${data.azurerm_client_config.current.tenant_id}/v2.0"
}

output "aws_bedrock_agent_jwks_uri" {
  description = "JWKS URI for Entra token signature verification (share with AWS engineer)."
  value       = "https://login.microsoftonline.com/${data.azurerm_client_config.current.tenant_id}/discovery/v2.0/keys"
}
