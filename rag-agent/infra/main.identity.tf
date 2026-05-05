# -----------------------------------------------------------------------------
# UC1 RAG Agent — Managed Identity + RBAC
# -----------------------------------------------------------------------------

resource "azurerm_user_assigned_identity" "rag" {
  name                = "id-uc1-rag-agent"
  location            = data.azurerm_resource_group.alz.location
  resource_group_name = data.azurerm_resource_group.alz.name
  tags                = var.tags
}

# Pull images from ACR
resource "azurerm_role_assignment" "rag_acr_pull" {
  scope                = data.azurerm_container_registry.alz.id
  role_definition_name = "AcrPull"
  principal_id         = azurerm_user_assigned_identity.rag.principal_id
}

# Cognitive Services OpenAI User — for chat completions
resource "azurerm_role_assignment" "rag_openai_user" {
  scope                = data.azurerm_cognitive_account.ai_services.id
  role_definition_name = "Cognitive Services OpenAI User"
  principal_id         = azurerm_user_assigned_identity.rag.principal_id
}

# Search Index Data Reader — for querying the search index
resource "azurerm_role_assignment" "rag_search_reader" {
  scope                = data.azurerm_search_service.alz.id
  role_definition_name = "Search Index Data Reader"
  principal_id         = azurerm_user_assigned_identity.rag.principal_id
}

# Search Index Data Contributor — for creating/populating the index
resource "azurerm_role_assignment" "rag_search_contributor" {
  scope                = data.azurerm_search_service.alz.id
  role_definition_name = "Search Index Data Contributor"
  principal_id         = azurerm_user_assigned_identity.rag.principal_id
}
