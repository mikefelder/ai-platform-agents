"""GET /executions/{executionId}

Returns the current execution state from DynamoDB in the contract shape
defined in the AWS handoff spec section 4.3.3.
"""

from __future__ import annotations

from opentelemetry.trace import StatusCode

from gateway.common import (
    attach_incoming_trace,
    detach_trace,
    executions_table,
    get_tracer,
    header,
    http_response,
)

_tracer = get_tracer(__name__)


def handler(event: dict, _context) -> dict:
    traceparent = header(event, "traceparent")
    token = attach_incoming_trace(traceparent)

    try:
        with _tracer.start_as_current_span("aws.agent_gateway.status") as span:
            span.set_attribute("cloud.provider", "aws")

            path_params = event.get("pathParameters") or {}
            execution_id = path_params.get("executionId")
            if not execution_id:
                return http_response(400, {"error": "executionId path parameter required"})
            span.set_attribute("execution.id", execution_id)

            item = executions_table.get_item(Key={"executionId": execution_id}).get("Item")
            if not item:
                span.set_status(StatusCode.ERROR, "not found")
                return http_response(404, {"error": f"Execution {execution_id} not found"})

            response: dict = {
                "executionId": item["executionId"],
                "status": item["status"],
            }
            if item.get("result") is not None:
                response["result"] = item["result"]
            if item.get("telemetry") is not None:
                response["telemetry"] = _coerce_numbers(item["telemetry"])
            if item.get("error"):
                response["error"] = item["error"]

            span.set_attribute("agent.status", item["status"])
            return http_response(200, response)
    finally:
        detach_trace(token)


def _coerce_numbers(value):
    """DynamoDB returns `Decimal` for numeric values; coerce for JSON output."""
    from decimal import Decimal

    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, dict):
        return {k: _coerce_numbers(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_coerce_numbers(v) for v in value]
    return value
