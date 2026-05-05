# -----------------------------------------------------------------------------
# Entra ID App Registration — OIDC identity for cross-cloud federation
# AWS Bedrock AgentCore validates tokens issued by this app registration.
# -----------------------------------------------------------------------------

resource "azuread_application" "uc2_federation" {
  display_name = "uaip-uc2-supervisor-aws-federation"

  sign_in_audience = "AzureADMyOrg"

  api {
    # Expose an Application ID URI that AWS uses as the OIDC audience
    requested_access_token_version = 2
  }

  tags = ["uaip", "uc2", "aws-federation"]
}

resource "azuread_service_principal" "uc2_federation" {
  client_id = azuread_application.uc2_federation.client_id
}

# Allow the supervisor managed identity to acquire tokens for this app
resource "azuread_application_federated_identity_credential" "supervisor_mi" {
  application_id = azuread_application.uc2_federation.id
  display_name   = "uc2-supervisor-managed-identity"
  description    = "Allows the UC2 supervisor Container App managed identity to request tokens"
  audiences      = ["api://AzureADTokenExchange"]
  issuer         = "https://login.microsoftonline.com/${data.azurerm_client_config.current.tenant_id}/v2.0"
  subject        = azurerm_user_assigned_identity.supervisor.principal_id
}

# -----------------------------------------------------------------------------
# Entra ID App Registration — identity for the AWS Bedrock agent
# AWS uses this app's client_id as the audience when requesting OIDC tokens
# to authenticate inbound calls from Bedrock AgentCore to Azure (e.g. APIM).
# -----------------------------------------------------------------------------

resource "azuread_application" "aws_bedrock_agent" {
  display_name = "uaip-uc2-aws-bedrock-agent"

  sign_in_audience = "AzureADMyOrg"

  api {
    requested_access_token_version = 2
  }

  tags = ["uaip", "uc2", "aws-bedrock-agent"]
}

resource "azuread_service_principal" "aws_bedrock_agent" {
  client_id = azuread_application.aws_bedrock_agent.client_id
}

# Federated credential — allows AWS to exchange its OIDC token for an Entra token.
# Only created when the AWS engineer provides the actual issuer + subject values.
resource "azuread_application_federated_identity_credential" "aws_bedrock_oidc" {
  count = var.aws_oidc_issuer != "" && var.aws_oidc_subject != "" ? 1 : 0

  application_id = azuread_application.aws_bedrock_agent.id
  display_name   = "aws-bedrock-agentcore-federation"
  description    = "Allows AWS Bedrock AgentCore to authenticate to Azure via OIDC"
  audiences      = [azuread_application.aws_bedrock_agent.client_id]
  issuer         = var.aws_oidc_issuer
  subject        = var.aws_oidc_subject
}
