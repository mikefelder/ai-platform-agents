# Licensed under the MIT License. See LICENSE file in the project root.
"""AWS Bedrock agent tool — MCP-shaped JSON invoke + poll via API Gateway."""

import os
import time
import uuid

import httpx
from agent_framework import tool
from opentelemetry import trace
from opentelemetry.propagate import inject
from pydantic import Field
from typing_extensions import Annotated

from tools.sla import record_sla_breach, sla_breach_message, sla_for

_tracer = trace.get_tracer("uaip.tools", "1.0.0")
_POLL_INTERVAL_S = 1.0
_AGENT_NAME = "Engineering Agent (Bedrock)"
_TOOL_NAME = "invoke_bedrock_agent"


def _get_auth_headers() -> dict[str, str]:
    """Acquire an Entra bearer token for the AWS gateway using managed identity."""
    federation_client_id = os.environ.get("AWS_FEDERATION_CLIENT_ID", "")
    if not federation_client_id:
        return {}
    try:
        from azure.identity import ManagedIdentityCredential, DefaultAzureCredential
        client_id = os.environ.get("AZURE_CLIENT_ID", "")
        credential = ManagedIdentityCredential(client_id=client_id) if client_id else DefaultAzureCredential()
        # Scope must match the app registration's identifier_uris
        token = credential.get_token(f"api://{federation_client_id}/.default")
        return {"Authorization": f"Bearer {token.token}"}
    except Exception as e:
        # Log but don't fail — proceed without auth as fallback
        import logging
        logging.getLogger("uaip.bedrock").warning(f"OIDC token acquisition failed: {e}")
        return {}


@tool(approval_mode="never_require")
def invoke_bedrock_agent(
    task: Annotated[str, Field(description="The task or query to send to the AWS Bedrock agent.")],
    agent_name: Annotated[str, Field(description="Name of the Bedrock agent to invoke (e.g. 'compliance').")] = "compliance",
) -> str:
    """Invoke an AWS Bedrock agent via the cross-cloud gateway.

    Uses the MCP-shaped async contract:
      POST /agents/{agentName}/invoke → 202 + executionId
      GET  /executions/{executionId}  → poll for completion

    The AWS gateway is fronted by API Gateway and backed by Lambda + Bedrock.
    """
    gateway_url = os.environ.get("AWS_BEDROCK_GATEWAY_URL", "")
    if not gateway_url:
        return "AWS Bedrock gateway not configured (AWS_BEDROCK_GATEWAY_URL not set)."

    with _tracer.start_as_current_span("uaip.tool.invoke_bedrock_agent") as span:
        span.set_attribute("uc", "use-case-2")
        span.set_attribute("tool.name", "invoke_bedrock_agent")
        span.set_attribute("agent.name", "Engineering Agent (Bedrock)")
        span.set_attribute("agent.type", "external")
        span.set_attribute("cloud.provider", "aws")
        span.set_attribute("bedrock.agent_name", agent_name)

        # SLA budget covers invoke + all polling attempts combined
        sla_seconds = sla_for(_AGENT_NAME)
        max_poll_attempts = max(1, int(sla_seconds / _POLL_INTERVAL_S))
        span.set_attribute("sla.threshold_seconds", sla_seconds)
        span.set_attribute("sla.max_poll_attempts", max_poll_attempts)
        started = time.monotonic()

        invocation_id = f"inv-{uuid.uuid4().hex[:8]}"
        invoke_url = f"{gateway_url.rstrip('/')}/agents/{agent_name}/invoke"
        auth_headers = _get_auth_headers()
        apim_key = os.environ.get("APIM_SUBSCRIPTION_KEY", "")
        if apim_key:
            auth_headers["Ocp-Apim-Subscription-Key"] = apim_key

        # Propagate W3C traceparent to AWS for cross-cloud correlation
        carrier: dict[str, str] = {}
        inject(carrier)
        traceparent = carrier.get("traceparent", "")

        # MCP-shaped invocation payload per the AWS handoff spec
        body = {
            "mcpVersion": "1.0",
            "traceparent": traceparent,
            "invocation": {
                "invocationId": invocation_id,
                "parentAgent": "uaip-supervisor",
                "targetAgent": f"aws-bedrock-{agent_name}",
                "async": True,
            },
            "input": {
                "taskType": "knowledge_retrieval",
                "payload": {"query": task},
            },
        }

        try:
            # Phase 1: Invoke (expect 202 Accepted)
            headers = {**auth_headers, "Content-Type": "application/json"}
            if traceparent:
                headers["traceparent"] = traceparent
            with httpx.Client(timeout=30.0) as client:
                resp = client.post(invoke_url, json=body, headers=headers)
                resp.raise_for_status()

            ack = resp.json()
            execution_id = ack.get("executionId", "")
            span.set_attribute("bedrock.execution_id", execution_id)
            if not execution_id:
                span.set_attribute("error", True)
                return f"Bedrock gateway returned no executionId: {ack}"

            # Phase 2: Poll for completion (bounded by SLA budget)
            poll_url = f"{gateway_url.rstrip('/')}/executions/{execution_id}"
            for _ in range(max_poll_attempts):
                if time.monotonic() - started >= sla_seconds:
                    break
                time.sleep(_POLL_INTERVAL_S)
                with httpx.Client(timeout=10.0) as client:
                    poll_resp = client.get(poll_url, headers=auth_headers)
                    poll_resp.raise_for_status()

                result = poll_resp.json()
                status = result.get("status", "")

                if status == "completed":
                    content = result.get("result", {}).get("content", str(result.get("result", {})))
                    telemetry = result.get("telemetry", {})
                    duration = telemetry.get("durationMs", "N/A")
                    tokens_in = telemetry.get("tokens", {}).get("input", "N/A")
                    tokens_out = telemetry.get("tokens", {}).get("output", "N/A")
                    span.set_attribute("bedrock.duration_ms", int(duration) if str(duration).isdigit() else 0)
                    span.set_attribute("bedrock.tokens.input", int(tokens_in) if str(tokens_in).isdigit() else 0)
                    span.set_attribute("bedrock.tokens.output", int(tokens_out) if str(tokens_out).isdigit() else 0)
                    span.set_attribute("error", False)
                    return (
                        f"[AWS Bedrock — {agent_name}]\n"
                        f"{content}\n\n"
                        f"(execution: {execution_id}, duration: {duration}ms, "
                        f"tokens: {tokens_in} in / {tokens_out} out)"
                    )

                if status == "failed":
                    error = result.get("error", "Unknown error")
                    span.set_attribute("error", True)
                    return f"Bedrock agent '{agent_name}' failed: {error} (execution: {execution_id})"

            record_sla_breach(
                span,
                agent_name=_AGENT_NAME,
                tool_name=_TOOL_NAME,
                sla_seconds=sla_seconds,
                elapsed_seconds=time.monotonic() - started,
                cause="poll_exhausted",
                extra={"bedrock.execution_id": execution_id, "bedrock.agent_name": agent_name},
            )
            return sla_breach_message(_AGENT_NAME, sla_seconds, cause="poll_exhausted")

        except httpx.TimeoutException:
            record_sla_breach(
                span,
                agent_name=_AGENT_NAME,
                tool_name=_TOOL_NAME,
                sla_seconds=sla_seconds,
                elapsed_seconds=time.monotonic() - started,
                cause="http_timeout",
            )
            return sla_breach_message(_AGENT_NAME, sla_seconds, cause="http_timeout")
        except httpx.HTTPStatusError as e:
            span.set_attribute("error", True)
            return f"Bedrock gateway error (HTTP {e.response.status_code}): {e.response.text[:200]}"
        except Exception as e:
            span.set_attribute("error", True)
            return f"Bedrock agent invocation failed: {e}"
