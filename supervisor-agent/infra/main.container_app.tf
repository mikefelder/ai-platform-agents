# -----------------------------------------------------------------------------
# Supervisor API — Container App (Microsoft Agent Framework SDK)
# Hosted agent using the Responses API protocol on port 8088.
# -----------------------------------------------------------------------------

resource "azurerm_container_app" "supervisor" {
  name                         = "ca-uc2-supervisor"
  container_app_environment_id = data.azurerm_container_app_environment.alz.id
  resource_group_name          = data.azurerm_resource_group.alz.name
  revision_mode                = "Single"
  tags                         = var.tags

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.supervisor.id]
  }

  registry {
    server   = data.azurerm_container_registry.alz.login_server
    identity = azurerm_user_assigned_identity.supervisor.id
  }

  template {
    min_replicas = var.supervisor_min_replicas
    max_replicas = var.supervisor_max_replicas

    container {
      name   = "supervisor-api"
      image  = "${data.azurerm_container_registry.alz.login_server}/uc2-supervisor-api:${var.supervisor_image_tag}"
      cpu    = 0.5
      memory = "1Gi"

      # --- Azure OpenAI (Agent Framework SDK) ---
      env {
        name  = "AZURE_OPENAI_ENDPOINT"
        value = replace(data.azurerm_cognitive_account.ai_services.endpoint, ".cognitiveservices.azure.com", ".openai.azure.com")
      }
      env {
        name  = "AZURE_AI_MODEL_DEPLOYMENT_NAME"
        value = var.azure_ai_deployment
      }
      env {
        name  = "AZURE_CLIENT_ID"
        value = azurerm_user_assigned_identity.supervisor.client_id
      }

      # --- Compliance tool (direct Foundry chat) ---
      env {
        name  = "AZURE_AI_ENDPOINT"
        value = "${replace(data.azurerm_cognitive_account.ai_services.endpoint, ".cognitiveservices.azure.com/", ".openai.azure.com/")}openai/deployments/${var.azure_ai_deployment}"
      }
      env {
        name  = "AZURE_AI_DEPLOYMENT"
        value = var.azure_ai_deployment
      }
      env {
        name  = "COMPLIANCE_MODEL"
        value = "o4-mini"
      }

      # --- AWS Bedrock Gateway ---
      env {
        name  = "AWS_BEDROCK_GATEWAY_URL"
        value = var.aws_bedrock_endpoint
      }
      env {
        name  = "AWS_FEDERATION_CLIENT_ID"
        value = azuread_application.aws_bedrock_agent.client_id
      }

      # --- UC1 RAG endpoint (direct container-to-container in same CAE) ---
      env {
        name  = "UC1_RAG_ENDPOINT"
        value = var.uc1_rag_endpoint
      }

      # --- UC3 Governance endpoint (via APIM) ---
      env {
        name  = "UC3_GOVERNANCE_ENDPOINT"
        value = "${data.azurerm_api_management.alz.gateway_url}/uc3"
      }

      # --- APIM subscription key ---
      env {
        name  = "APIM_SUBSCRIPTION_KEY"
        value = "" # Injected at runtime or via Key Vault
      }

      # --- Telemetry ---
      env {
        name  = "APPLICATIONINSIGHTS_CONNECTION_STRING"
        value = azurerm_application_insights.uc2.connection_string
      }
      env {
        name  = "OTEL_SERVICE_NAME"
        value = "uc2-supervisor-api"
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

      # --- Health probes (Agent Framework serves /readiness on 8088) ---
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

    # Scale on HTTP concurrency
    http_scale_rule {
      name                = "http-concurrency"
      concurrent_requests = "50"
    }
  }

  ingress {
    external_enabled = true
    target_port      = 8088
    transport        = "http"

    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }

  depends_on = [
    azurerm_role_assignment.supervisor_acr_pull
  ]
}
