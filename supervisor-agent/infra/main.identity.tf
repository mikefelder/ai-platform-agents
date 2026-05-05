# -----------------------------------------------------------------------------
# Application Insights — linked to the ALZ Log Analytics Workspace
# Provides the OTEL endpoint for cross-cloud telemetry correlation (UC2).
# -----------------------------------------------------------------------------

resource "azurerm_application_insights" "uc2" {
  name                = "ai-uc2-supervisor-appinsights"
  location            = data.azurerm_resource_group.alz.location
  resource_group_name = data.azurerm_resource_group.alz.name
  workspace_id        = data.azurerm_log_analytics_workspace.alz.id
  application_type    = "web"
  tags                = var.tags
}

# -----------------------------------------------------------------------------
# User-Assigned Managed Identity for the Supervisor Container App.
# Used for ACR pull, Key Vault access, and APIM authentication.
# -----------------------------------------------------------------------------

resource "azurerm_user_assigned_identity" "supervisor" {
  name                = "id-uc2-supervisor"
  location            = data.azurerm_resource_group.alz.location
  resource_group_name = data.azurerm_resource_group.alz.name
  tags                = var.tags
}

# ACR pull role — lets the Container App pull images
resource "azurerm_role_assignment" "supervisor_acr_pull" {
  scope                = data.azurerm_container_registry.alz.id
  role_definition_name = "AcrPull"
  principal_id         = azurerm_user_assigned_identity.supervisor.principal_id
}

# Key Vault Secrets User — lets the app read secrets at runtime
resource "azurerm_role_assignment" "supervisor_kv_reader" {
  scope                = data.azurerm_key_vault.alz.id
  role_definition_name = "Key Vault Secrets User"
  principal_id         = azurerm_user_assigned_identity.supervisor.principal_id
}

# Cognitive Services OpenAI User — lets the app call AI Foundry models via managed identity
resource "azurerm_role_assignment" "supervisor_openai_user" {
  scope                = data.azurerm_cognitive_account.ai_services.id
  role_definition_name = "Cognitive Services OpenAI User"
  principal_id         = azurerm_user_assigned_identity.supervisor.principal_id
}
