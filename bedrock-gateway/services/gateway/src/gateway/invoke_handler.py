"""POST /agents/{agentName}/invoke

Persists an execution record in DynamoDB, fires the executor Lambda
asynchronously, and returns 202 Accepted with an executionId.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from datetime import datetime, timezone

from opentelemetry import trace
from opentelemetry.trace import StatusCode

from gateway.common import (
    attach_incoming_trace,
    detach_trace,
    executions_table,
    flush_telemetry,
    get_tracer,
    header,
    http_response,
    invoke_executor_async,
    log,
)

_tracer = get_tracer(__name__)

# Optional static bearer token for brand-new-account bring-up.
# In production this is replaced by a JWT validated by API Gateway Lambda
# authorizer using Entra ID OIDC (see infra/iam.tf).
EXPECTED_BEARER = os.environ.get("GATEWAY_STATIC_BEARER")


def handler(event: dict, _context) -> dict:
    traceparent = header(event, "traceparent")
    token = attach_incoming_trace(traceparent)

    try:
        with _tracer.start_as_current_span("aws.agent_gateway.invoke") as span:
            span.set_attribute("cloud.provider", "aws")

            # --- Auth (optional; production uses OIDC authorizer) ---
            if EXPECTED_BEARER:
                auth = header(event, "authorization") or ""
                if not auth.startswith("Bearer ") or auth[7:].strip() != EXPECTED_BEARER:
                    span.set_status(StatusCode.ERROR, "unauthorized")
                    return http_response(401, {"error": "Unauthorized"})

            # --- Parse path param ---
            path_params = event.get("pathParameters") or {}
            agent_name = path_params.get("agentName")
            if not agent_name:
                return http_response(400, {"error": "agentName path parameter required"})
            span.set_attribute("agent.name", agent_name)

            # --- Parse body ---
            try:
                body = json.loads(event.get("body") or "{}")
            except json.JSONDecodeError:
                return http_response(400, {"error": "Invalid JSON body"})

            if body.get("mcpVersion") != "1.0":
                return http_response(
                    400,
                    {"error": "Unsupported or missing mcpVersion; expected '1.0'"},
                )

            invocation = body.get("invocation") or {}
            input_block = body.get("input") or {}

            invocation_id = invocation.get("invocationId") or f"inv-{uuid.uuid4().hex[:8]}"
            execution_id = f"aws-exec-{uuid.uuid4().hex[:12]}"
            span.set_attribute("invocation.id", invocation_id)
            span.set_attribute("execution.id", execution_id)

            # --- Persist execution record ---
            now = datetime.now(timezone.utc).isoformat()
            executions_table.put_item(
                Item={
                    "executionId": execution_id,
                    "agentName": agent_name,
                    "status": "accepted",
                    "invocationId": invocation_id,
                    "parentAgent": invocation.get("parentAgent"),
                    "targetAgent": invocation.get("targetAgent") or agent_name,
                    "taskType": input_block.get("taskType") or "general",
                    "payload": input_block.get("payload") or {},
                    "traceparent": traceparent,
                    "createdAt": now,
                    "updatedAt": now,
                    # Expire records 7 days after creation.
                    "expiresAt": int(time.time()) + 7 * 24 * 3600,
                }
            )

            # --- Fire executor asynchronously ---
            try:
                invoke_executor_async(
                    {
                        "executionId": execution_id,
                        "agentName": agent_name,
                        "traceparent": traceparent,
                    }
                )
            except Exception as exc:  # noqa: BLE001
                log.exception("Failed to dispatch executor Lambda: %s", exc)
                span.set_status(StatusCode.ERROR, "executor dispatch failed")
                # Mark record as failed so /executions/{id} reflects reality.
                executions_table.update_item(
                    Key={"executionId": execution_id},
                    UpdateExpression="SET #s = :s, #e = :e, updatedAt = :u",
                    ExpressionAttributeNames={"#s": "status", "#e": "error"},
                    ExpressionAttributeValues={
                        ":s": "failed",
                        ":e": f"Executor dispatch failed: {exc!s}",
                        ":u": datetime.now(timezone.utc).isoformat(),
                    },
                )
                return http_response(
                    500, {"error": "Failed to dispatch executor"}
                )

            span.set_attribute("http.status_code", 202)
            return http_response(
                202,
                {"executionId": execution_id, "status": "accepted"},
            )

    finally:
        flush_telemetry()
        detach_trace(token)
