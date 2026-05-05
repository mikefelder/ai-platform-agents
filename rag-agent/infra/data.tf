# -----------------------------------------------------------------------------
# Data sources — reference existing ALZ resources
# -----------------------------------------------------------------------------

data "azurerm_client_config" "current" {}

data "azurerm_resource_group" "alz" {
  name = var.resource_group_name
}

data "azurerm_container_app_environment" "alz" {
  name                = var.container_app_environment_name
  resource_group_name = data.azurerm_resource_group.alz.name
}

data "azurerm_container_registry" "alz" {
  name                = var.container_registry_name
  resource_group_name = data.azurerm_resource_group.alz.name
}

data "azurerm_log_analytics_workspace" "alz" {
  name                = var.log_analytics_workspace_name
  resource_group_name = data.azurerm_resource_group.alz.name
}

data "azurerm_api_management" "alz" {
  name                = var.apim_name
  resource_group_name = data.azurerm_resource_group.alz.name
}

data "azurerm_cognitive_account" "ai_services" {
  name                = var.ai_services_name
  resource_group_name = data.azurerm_resource_group.alz.name
}

data "azurerm_search_service" "alz" {
  name                = var.ai_search_name
  resource_group_name = data.azurerm_resource_group.alz.name
}
