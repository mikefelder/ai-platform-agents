output "gateway_base_url" {
  description = "Base URL for the AWS Agent Gateway. Configure the Azure supervisor's bedrock_gateway_url to this value (async mode)."
  value       = aws_apigatewayv2_api.gateway.api_endpoint
}

output "invoke_route" {
  value = "POST ${aws_apigatewayv2_api.gateway.api_endpoint}/agents/{agentName}/invoke"
}

output "status_route" {
  value = "GET ${aws_apigatewayv2_api.gateway.api_endpoint}/executions/{executionId}"
}

output "executions_table_name" {
  value = aws_dynamodb_table.executions.name
}

output "executor_function_arn" {
  value = aws_lambda_function.executor.arn
}

output "entra_federated_role_arn" {
  description = "IAM role the Azure supervisor assumes via Entra OIDC federation. Empty until entra_* vars are populated."
  value       = try(aws_iam_role.entra_federated[0].arn, "")
}
