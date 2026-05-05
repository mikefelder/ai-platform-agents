data "aws_caller_identity" "current" {}
data "aws_partition" "current" {}

locals {
  account_id = data.aws_caller_identity.current.account_id
  partition  = data.aws_partition.current.partition

  executions_table = "${var.name_prefix}-executions"
  executor_fn      = "${var.name_prefix}-executor"
  invoke_fn        = "${var.name_prefix}-invoke"
  status_fn        = "${var.name_prefix}-status"
  health_fn        = "${var.name_prefix}-health"
}

# ---------------------------------------------------------------------------
# DynamoDB execution store
# ---------------------------------------------------------------------------

resource "aws_dynamodb_table" "executions" {
  name         = local.executions_table
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "executionId"

  attribute {
    name = "executionId"
    type = "S"
  }

  ttl {
    attribute_name = "expiresAt"
    enabled        = true
  }

  point_in_time_recovery {
    enabled = true
  }
}

# ---------------------------------------------------------------------------
# Lambda packaging
#
# Produces a single deterministic zip containing the gateway source plus
# pinned runtime dependencies. All four handler Lambdas share the same zip
# and differ only by their `handler` attribute.
# ---------------------------------------------------------------------------

resource "null_resource" "build_lambda_package" {
  triggers = {
    src_hash     = sha1(join("", [for f in fileset("${path.module}/../services/gateway/src", "**/*.py") : filesha1("${path.module}/../services/gateway/src/${f}")]))
    requirements = filesha1("${path.module}/../services/gateway/requirements.txt")
  }

  provisioner "local-exec" {
    command     = "${path.module}/../scripts/build_lambda.sh"
    interpreter = ["bash", "-c"]
  }
}

data "archive_file" "gateway" {
  depends_on  = [null_resource.build_lambda_package]
  type        = "zip"
  source_dir  = "${path.module}/../services/gateway/build/lambda-package"
  output_path = "${path.module}/../services/gateway/build/gateway.zip"
}

locals {
  common_env = {
    LOG_LEVEL                             = "INFO"
    EXECUTIONS_TABLE                      = aws_dynamodb_table.executions.name
    EXECUTOR_FUNCTION                     = local.executor_fn
    OTEL_SERVICE_NAME                     = "aws-agent-gateway"
    APPLICATIONINSIGHTS_CONNECTION_STRING = var.application_insights_connection_string
    OTEL_EXPORTER_OTLP_ENDPOINT           = var.otel_exporter_otlp_endpoint
    OTEL_EXPORTER_OTLP_HEADERS            = var.otel_exporter_otlp_headers
    GATEWAY_STATIC_BEARER                 = var.gateway_static_bearer
  }

  executor_env = merge(local.common_env, {
    BEDROCK_AGENT_RUNTIME_ARN = var.bedrock_agent_runtime_arn
    BEDROCK_AGENT_ID          = var.bedrock_agent_id
    BEDROCK_AGENT_ALIAS_ID    = var.bedrock_agent_alias_id
    BEDROCK_FALLBACK_MODEL_ID = var.bedrock_fallback_model_id
  })
}

# ---------------------------------------------------------------------------
# Lambdas
# ---------------------------------------------------------------------------

resource "aws_cloudwatch_log_group" "invoke" {
  name              = "/aws/lambda/${local.invoke_fn}"
  retention_in_days = var.log_retention_days
}

resource "aws_cloudwatch_log_group" "status" {
  name              = "/aws/lambda/${local.status_fn}"
  retention_in_days = var.log_retention_days
}

resource "aws_cloudwatch_log_group" "executor" {
  name              = "/aws/lambda/${local.executor_fn}"
  retention_in_days = var.log_retention_days
}

resource "aws_cloudwatch_log_group" "health" {
  name              = "/aws/lambda/${local.health_fn}"
  retention_in_days = var.log_retention_days
}

resource "aws_lambda_function" "invoke" {
  function_name    = local.invoke_fn
  role             = aws_iam_role.gateway_lambda.arn
  handler          = "gateway.invoke_handler.handler"
  runtime          = "python3.12"
  timeout          = 15
  memory_size      = 512
  filename         = data.archive_file.gateway.output_path
  source_code_hash = data.archive_file.gateway.output_base64sha256

  environment {
    variables = local.common_env
  }

  depends_on = [aws_cloudwatch_log_group.invoke]
}

resource "aws_lambda_function" "status" {
  function_name    = local.status_fn
  role             = aws_iam_role.gateway_lambda.arn
  handler          = "gateway.status_handler.handler"
  runtime          = "python3.12"
  timeout          = 10
  memory_size      = 512
  filename         = data.archive_file.gateway.output_path
  source_code_hash = data.archive_file.gateway.output_base64sha256

  environment {
    variables = local.common_env
  }

  depends_on = [aws_cloudwatch_log_group.status]
}

resource "aws_lambda_function" "executor" {
  function_name    = local.executor_fn
  role             = aws_iam_role.executor_lambda.arn
  handler          = "gateway.executor_handler.handler"
  runtime          = "python3.12"
  timeout          = 300
  memory_size      = 1024
  filename         = data.archive_file.gateway.output_path
  source_code_hash = data.archive_file.gateway.output_base64sha256

  environment {
    variables = local.executor_env
  }

  depends_on = [aws_cloudwatch_log_group.executor]
}

resource "aws_lambda_function" "health" {
  function_name    = local.health_fn
  role             = aws_iam_role.gateway_lambda.arn
  handler          = "gateway.health_handler.handler"
  runtime          = "python3.12"
  timeout          = 5
  memory_size      = 256
  filename         = data.archive_file.gateway.output_path
  source_code_hash = data.archive_file.gateway.output_base64sha256

  environment {
    variables = local.common_env
  }

  depends_on = [aws_cloudwatch_log_group.health]
}
