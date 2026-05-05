# -----------------------------------------------------------------------------
# APIM — UC1 RAG Knowledge Agent API
# -----------------------------------------------------------------------------

resource "azurerm_api_management_api" "rag" {
  name                = "uc1-rag-agent-api"
  api_management_name = data.azurerm_api_management.alz.name
  resource_group_name = data.azurerm_resource_group.alz.name
  revision            = "1"
  display_name        = "UC1 RAG Knowledge Agent API"
  path                = "uc1"
  protocols           = ["https"]

  subscription_required = true
  subscription_key_parameter_names {
    header = "Ocp-Apim-Subscription-Key"
    query  = "subscription-key"
  }
}

# POST /uc1/responses → OpenAI Responses API
resource "azurerm_api_management_api_operation" "rag_responses" {
  operation_id        = "responses"
  api_name            = azurerm_api_management_api.rag.name
  api_management_name = data.azurerm_api_management.alz.name
  resource_group_name = data.azurerm_resource_group.alz.name
  display_name        = "Agent Responses (OpenAI Responses API)"
  method              = "POST"
  url_template        = "/responses"
}

# GET /uc1/readiness
resource "azurerm_api_management_api_operation" "rag_readiness" {
  operation_id        = "readiness"
  api_name            = azurerm_api_management_api.rag.name
  api_management_name = data.azurerm_api_management.alz.name
  resource_group_name = data.azurerm_resource_group.alz.name
  display_name        = "Readiness Check"
  method              = "GET"
  url_template        = "/readiness"
}

# Backend
resource "azurerm_api_management_backend" "rag" {
  name                = "uc1-rag-agent-backend"
  api_management_name = data.azurerm_api_management.alz.name
  resource_group_name = data.azurerm_resource_group.alz.name
  protocol            = "http"
  url                 = "https://${azurerm_container_app.rag.ingress[0].fqdn}"
}

# Policy
resource "azurerm_api_management_api_policy" "rag" {
  api_name            = azurerm_api_management_api.rag.name
  api_management_name = data.azurerm_api_management.alz.name
  resource_group_name = data.azurerm_resource_group.alz.name

  xml_content = <<-XML
    <policies>
      <inbound>
        <base />
        <set-backend-service backend-id="${azurerm_api_management_backend.rag.name}" />
        <!-- Rate limiting: 30 requests per minute per subscription -->
        <rate-limit calls="30" renewal-period="60" />
        <!-- Content safety: block prompt injection patterns (only on methods with a body) -->
        <choose>
          <when condition="@{
            if (context.Request.Method == &quot;GET&quot; || context.Request.Method == &quot;HEAD&quot; || context.Request.Method == &quot;OPTIONS&quot;) { return false; }
            var body = context.Request.Body?.As&lt;string&gt;(preserveContent: true);
            if (string.IsNullOrEmpty(body)) { return false; }
            var b = body.ToLower();
            return b.Contains(&quot;ignore previous instructions&quot;) || b.Contains(&quot;ignore all instructions&quot;) || b.Contains(&quot;disregard your instructions&quot;);
          }">
            <return-response>
              <set-status code="400" reason="Content Policy Violation" />
              <set-header name="Content-Type" exists-action="override">
                <value>application/json</value>
              </set-header>
              <set-body>{"error": {"code": "content_policy_violation", "message": "Request blocked by content safety policy."}}</set-body>
            </return-response>
          </when>
        </choose>
        <!-- W3C traceparent injection -->
        <set-header name="traceparent" exists-action="skip">
          <value>@{
            var traceId = Guid.NewGuid().ToString("N");
            var spanId  = Guid.NewGuid().ToString("N").Substring(0, 16);
            return $"00-{traceId}-{spanId}-01";
          }</value>
        </set-header>
        <!-- APIM does NOT auto-rewrite Host when using set-backend-service.
             Without this override, CAE Envoy receives Host=apim-fqdn and
             returns "Application not found" (404). -->
        <set-header name="Host" exists-action="override">
          <value>${azurerm_container_app.rag.ingress[0].fqdn}</value>
        </set-header>
      </inbound>
      <backend>
        <base />
      </backend>
      <outbound>
        <base />
      </outbound>
      <on-error>
        <base />
      </on-error>
    </policies>
  XML
}
