# -----------------------------------------------------------------------------
# Application Insights for UC1
# -----------------------------------------------------------------------------

resource "azurerm_application_insights" "uc1" {
  name                = "ai-uc1-rag-agent"
  location            = data.azurerm_resource_group.alz.location
  resource_group_name = data.azurerm_resource_group.alz.name
  workspace_id        = data.azurerm_log_analytics_workspace.alz.id
  application_type    = "web"
  tags                = var.tags
}
