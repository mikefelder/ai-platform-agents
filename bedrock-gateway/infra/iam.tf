# -----------------------------------------------------------------------------
# IAM — Gateway Lambdas + Bedrock Executor + Entra OIDC federation (scaffold)
# -----------------------------------------------------------------------------

# ---- Assume-role trust policy for Lambda ------------------------------------

data "aws_iam_policy_document" "lambda_trust" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

# ---- Gateway Lambdas (invoke / status / health) -----------------------------

resource "aws_iam_role" "gateway_lambda" {
  name               = "${var.name_prefix}-gateway-lambda"
  assume_role_policy = data.aws_iam_policy_document.lambda_trust.json
}

resource "aws_iam_role_policy_attachment" "gateway_basic" {
  role       = aws_iam_role.gateway_lambda.name
  policy_arn = "arn:${local.partition}:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

data "aws_iam_policy_document" "gateway_inline" {
  statement {
    sid    = "DynamoExecutionRW"
    effect = "Allow"
    actions = [
      "dynamodb:GetItem",
      "dynamodb:PutItem",
      "dynamodb:UpdateItem",
      "dynamodb:Query",
    ]
    resources = [aws_dynamodb_table.executions.arn]
  }

  statement {
    sid       = "InvokeExecutor"
    effect    = "Allow"
    actions   = ["lambda:InvokeFunction"]
    resources = [aws_lambda_function.executor.arn]
  }
}

resource "aws_iam_role_policy" "gateway_inline" {
  name   = "${var.name_prefix}-gateway-inline"
  role   = aws_iam_role.gateway_lambda.id
  policy = data.aws_iam_policy_document.gateway_inline.json
}

# ---- Executor Lambda --------------------------------------------------------

resource "aws_iam_role" "executor_lambda" {
  name               = "${var.name_prefix}-executor-lambda"
  assume_role_policy = data.aws_iam_policy_document.lambda_trust.json
}

resource "aws_iam_role_policy_attachment" "executor_basic" {
  role       = aws_iam_role.executor_lambda.name
  policy_arn = "arn:${local.partition}:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

data "aws_iam_policy_document" "executor_inline" {
  statement {
    sid    = "DynamoExecutionRW"
    effect = "Allow"
    actions = [
      "dynamodb:GetItem",
      "dynamodb:UpdateItem",
    ]
    resources = [aws_dynamodb_table.executions.arn]
  }

  statement {
    sid    = "BedrockInvoke"
    effect = "Allow"
    actions = [
      "bedrock:InvokeModel",
      "bedrock:InvokeModelWithResponseStream",
      "bedrock:Converse",
      "bedrock:ConverseStream",
    ]
    # Allow:
    #   - Foundation models in the deployment region (direct invoke).
    #   - Foundation models in any region (cross-region inference profiles
    #     fan out to other regions; Bedrock checks perms on the underlying FM).
    #   - Inference profiles (au.*, apac.*, global.*) in the deployment region.
    resources = [
      "arn:${local.partition}:bedrock:${var.aws_region}::foundation-model/*",
      "arn:${local.partition}:bedrock:*::foundation-model/*",
      "arn:${local.partition}:bedrock:${var.aws_region}:${local.account_id}:inference-profile/*",
    ]
  }

  dynamic "statement" {
    for_each = var.bedrock_agent_id != "" ? [1] : []
    content {
      sid     = "BedrockAgentInvoke"
      effect  = "Allow"
      actions = ["bedrock:InvokeAgent"]
      resources = [
        "arn:${local.partition}:bedrock:${var.aws_region}:${local.account_id}:agent-alias/${var.bedrock_agent_id}/${var.bedrock_agent_alias_id}",
      ]
    }
  }

  dynamic "statement" {
    for_each = var.bedrock_agent_runtime_arn != "" ? [1] : []
    content {
      sid    = "BedrockAgentCoreInvoke"
      effect = "Allow"
      actions = [
        "bedrock-agentcore:InvokeAgentRuntime",
      ]
      resources = [var.bedrock_agent_runtime_arn]
    }
  }
}

resource "aws_iam_role_policy" "executor_inline" {
  name   = "${var.name_prefix}-executor-inline"
  role   = aws_iam_role.executor_lambda.id
  policy = data.aws_iam_policy_document.executor_inline.json
}

# -----------------------------------------------------------------------------
# Entra ID -> AWS workload identity federation (scaffold)
#
# Creates an IAM OIDC provider trusting the Azure Entra ID tenant and a
# role the Azure supervisor can assume to call API Gateway via sigv4 /
# InvokeAgent calls. The Entra application id MUST be populated before the
# trust policy evaluates non-trivially.
# -----------------------------------------------------------------------------

resource "aws_iam_openid_connect_provider" "entra" {
  count = var.entra_tenant_id != "" ? 1 : 0

  url = "https://login.microsoftonline.com/${var.entra_tenant_id}/v2.0"

  client_id_list = compact([
    var.entra_application_id,
  ])

  # Microsoft rotates these; update the thumbprint via
  # `openssl s_client -connect login.microsoftonline.com:443 -showcerts`.
  # AWS accepts a well-known placeholder when the RP proves the JWT
  # via standard OIDC discovery, but we keep an explicit value here so
  # the provider is created deterministically.
  thumbprint_list = [
    "990f4193972f2becf12ddeda5237f9c952f20d9e",
  ]
}

data "aws_iam_policy_document" "entra_federated_trust" {
  count = var.entra_tenant_id != "" && var.entra_application_id != "" ? 1 : 0

  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.entra[0].arn]
    }

    condition {
      test     = "StringEquals"
      variable = "login.microsoftonline.com/${var.entra_tenant_id}/v2.0:aud"
      values   = [var.entra_application_id]
    }
  }
}

resource "aws_iam_role" "entra_federated" {
  count = var.entra_tenant_id != "" && var.entra_application_id != "" ? 1 : 0

  name               = "${var.name_prefix}-entra-federated"
  assume_role_policy = data.aws_iam_policy_document.entra_federated_trust[0].json
  description        = "Assumed by the Azure UAIP supervisor via Entra ID workload identity federation."
}

data "aws_iam_policy_document" "entra_federated_inline" {
  count = var.entra_tenant_id != "" && var.entra_application_id != "" ? 1 : 0

  statement {
    sid       = "InvokeGateway"
    effect    = "Allow"
    actions   = ["execute-api:Invoke"]
    resources = ["${aws_apigatewayv2_api.gateway.execution_arn}/*/*"]
  }
}

resource "aws_iam_role_policy" "entra_federated_inline" {
  count = var.entra_tenant_id != "" && var.entra_application_id != "" ? 1 : 0

  name   = "${var.name_prefix}-entra-federated-inline"
  role   = aws_iam_role.entra_federated[0].id
  policy = data.aws_iam_policy_document.entra_federated_inline[0].json
}
