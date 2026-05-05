# -----------------------------------------------------------------------------
# UC1 RAG Agent — Container App (Microsoft Agent Framework SDK)
# -----------------------------------------------------------------------------

resource "azurerm_container_app" "rag" {
  name                         = "ca-uc1-rag-agent"
  container_app_environment_id = data.azurerm_container_app_environment.alz.id
  resource_group_name          = data.azurerm_resource_group.alz.name
  revision_mode                = "Single"
  tags                         = var.tags

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.rag.id]
  }

  registry {
    server   = data.azurerm_container_registry.alz.login_server
    identity = azurerm_user_assigned_identity.rag.id
  }

  template {
    min_replicas = var.rag_min_replicas
    max_replicas = var.rag_max_replicas

    container {
      name   = "rag-agent"
      image  = "${data.azurerm_container_registry.alz.login_server}/uc1-rag-agent:${var.rag_image_tag}"
      cpu    = 0.5
      memory = "1Gi"

      # --- Azure OpenAI ---
      env {
        name  = "AZURE_OPENAI_ENDPOINT"
        value = replace(data.azurerm_cognitive_account.ai_services.endpoint, ".cognitiveservices.azure.com", ".openai.azure.com")
      }
      env {
        name  = "AZURE_AI_MODEL_DEPLOYMENT_NAME"
        value = "gpt-4.1-mini"
      }
      env {
        name  = "AZURE_CLIENT_ID"
        value = azurerm_user_assigned_identity.rag.client_id
      }

      # --- AI Search ---
      env {
        name  = "AZURE_AI_SEARCH_ENDPOINT"
        value = "https://${data.azurerm_search_service.alz.name}.search.windows.net"
      }
      env {
        name  = "AZURE_AI_SEARCH_INDEX"
        value = var.search_index_name
      }

      # --- Telemetry ---
      env {
        name  = "APPLICATIONINSIGHTS_CONNECTION_STRING"
        value = azurerm_application_insights.uc1.connection_string
      }
      env {
        name  = "OTEL_SERVICE_NAME"
        value = "uc1-rag-agent"
      }
      env {
        name  = "OTEL_RESOURCE_ATTRIBUTES"
        value = "service.namespace=uaip,deployment.environment=poc"
      }

      # --- Sensitive data tracing (prompt/response capture for debugging) ---
      env {
        name  = "ENABLE_SENSITIVE_DATA"
        value = tostring(var.enable_sensitive_data)
      }

      # --- Health probes (Agent Framework /readiness on 8088) ---
      liveness_probe {
        transport        = "HTTP"
        path             = "/readiness"
        port             = 8088
        timeout          = 5
        interval_seconds = 10
      }

      readiness_probe {
        transport        = "HTTP"
        path             = "/readiness"
        port             = 8088
        timeout          = 5
        interval_seconds = 10
      }

      startup_probe {
        transport               = "HTTP"
        path                    = "/readiness"
        port                    = 8088
        timeout                 = 5
        interval_seconds        = 3
        failure_count_threshold = 10
      }
    }

    http_scale_rule {
      name                = "http-concurrency"
      concurrent_requests = "20"
    }
  }

  ingress {
    # The CAE environment is internal (ILB on 192.168.1.111) so external=true
    # here means "exposed on the env's internal load balancer to the VNet" -
    # NOT publicly reachable. external=false would scope the app to env-internal
    # FQDN only (cluster-local), which APIM (different subnet) cannot reach.
    # Bypass protection is enforced by APIM subscription-key requirement plus
    # NSG rules restricting direct CAE-ILB access to the APIMSubnet.
    external_enabled = true
    target_port      = 8088
    transport        = "http"

    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }

  depends_on = [
    azurerm_role_assignment.rag_acr_pull
  ]
}
