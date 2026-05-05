# -----------------------------------------------------------------------------
# API Gateway (HTTP API v2) — fronts the Lambda handlers.
# -----------------------------------------------------------------------------

resource "aws_apigatewayv2_api" "gateway" {
  name          = "${var.name_prefix}-gateway"
  protocol_type = "HTTP"
  description   = "AWS Agent Gateway for cross-cloud agent invocation."

  cors_configuration {
    allow_methods = ["GET", "POST", "OPTIONS"]
    allow_origins = ["*"]
    allow_headers = ["*"]
  }
}

resource "aws_cloudwatch_log_group" "apigw" {
  name              = "/aws/apigateway/${var.name_prefix}-gateway"
  retention_in_days = var.log_retention_days
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.gateway.id
  name        = "$default"
  auto_deploy = true

  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.apigw.arn
    format = jsonencode({
      requestId      = "$context.requestId"
      routeKey       = "$context.routeKey"
      status         = "$context.status"
      responseLength = "$context.responseLength"
      traceparent    = "$context.authorizer.traceparent"
      integrationErr = "$context.integrationErrorMessage"
      sourceIp       = "$context.identity.sourceIp"
    })
  }

  default_route_settings {
    throttling_burst_limit = 50
    throttling_rate_limit  = 20
  }
}

# --- Integrations -------------------------------------------------------------

resource "aws_apigatewayv2_integration" "invoke" {
  api_id                 = aws_apigatewayv2_api.gateway.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.invoke.invoke_arn
  integration_method     = "POST"
  payload_format_version = "2.0"
  timeout_milliseconds   = 15000
}

resource "aws_apigatewayv2_integration" "status" {
  api_id                 = aws_apigatewayv2_api.gateway.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.status.invoke_arn
  integration_method     = "POST"
  payload_format_version = "2.0"
  timeout_milliseconds   = 10000
}

resource "aws_apigatewayv2_integration" "health" {
  api_id                 = aws_apigatewayv2_api.gateway.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.health.invoke_arn
  integration_method     = "POST"
  payload_format_version = "2.0"
  timeout_milliseconds   = 5000
}

# --- JWT authorizer (Azure Entra ID) -----------------------------------------
# Validates bearer tokens issued by the Azure tenant. API Gateway fetches the
# JWKS automatically from the issuer's OIDC discovery document
# (.../v2.0/.well-known/openid-configuration -> jwks_uri).

resource "aws_apigatewayv2_authorizer" "entra_jwt" {
  count            = var.entra_tenant_id != "" && var.entra_application_id != "" ? 1 : 0
  api_id           = aws_apigatewayv2_api.gateway.id
  authorizer_type  = "JWT"
  identity_sources = ["$request.header.Authorization"]
  name             = "${var.name_prefix}-entra-jwt"

  jwt_configuration {
    audience = [var.entra_application_id]
    issuer   = "https://login.microsoftonline.com/${var.entra_tenant_id}/v2.0"
  }
}

locals {
  entra_jwt_enabled       = var.entra_tenant_id != "" && var.entra_application_id != ""
  entra_jwt_authorizer_id = local.entra_jwt_enabled ? aws_apigatewayv2_authorizer.entra_jwt[0].id : null
  entra_jwt_auth_type     = local.entra_jwt_enabled ? "JWT" : "NONE"
}

# --- Routes -------------------------------------------------------------------

resource "aws_apigatewayv2_route" "invoke" {
  api_id             = aws_apigatewayv2_api.gateway.id
  route_key          = "POST /agents/{agentName}/invoke"
  target             = "integrations/${aws_apigatewayv2_integration.invoke.id}"
  authorization_type = local.entra_jwt_auth_type
  authorizer_id      = local.entra_jwt_authorizer_id
}

resource "aws_apigatewayv2_route" "status" {
  api_id             = aws_apigatewayv2_api.gateway.id
  route_key          = "GET /executions/{executionId}"
  target             = "integrations/${aws_apigatewayv2_integration.status.id}"
  authorization_type = local.entra_jwt_auth_type
  authorizer_id      = local.entra_jwt_authorizer_id
}

resource "aws_apigatewayv2_route" "health" {
  api_id    = aws_apigatewayv2_api.gateway.id
  route_key = "GET /health"
  target    = "integrations/${aws_apigatewayv2_integration.health.id}"
}

# --- Lambda permissions -------------------------------------------------------

resource "aws_lambda_permission" "apigw_invoke" {
  statement_id  = "AllowAPIGWInvokeLambda"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.invoke.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.gateway.execution_arn}/*/*"
}

resource "aws_lambda_permission" "apigw_status" {
  statement_id  = "AllowAPIGWInvokeLambda"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.status.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.gateway.execution_arn}/*/*"
}

resource "aws_lambda_permission" "apigw_health" {
  statement_id  = "AllowAPIGWInvokeLambda"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.health.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.gateway.execution_arn}/*/*"
}
