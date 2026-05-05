output "apim_gateway_url" {
  value = "https://${data.azurerm_api_management.alz.name}.azure-api.net/uc1"
}

output "rag_fqdn" {
  value = azurerm_container_app.rag.ingress[0].fqdn
}

output "rag_identity_client_id" {
  value = azurerm_user_assigned_identity.rag.client_id
}

output "rag_identity_principal_id" {
  value = azurerm_user_assigned_identity.rag.principal_id
}

output "appinsights_connection_string" {
  value     = azurerm_application_insights.uc1.connection_string
  sensitive = true
}

output "search_endpoint" {
  value = "https://${data.azurerm_search_service.alz.name}.search.windows.net"
}

output "search_index_name" {
  value = var.search_index_name
}
