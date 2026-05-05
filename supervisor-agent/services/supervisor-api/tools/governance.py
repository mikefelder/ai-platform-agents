# Licensed under the MIT License. See LICENSE file in the project root.
"""Governance Hub tools — query costs, traces, compliance, and agent health via APIM."""

import os
import time

import httpx
from agent_framework import tool
from opentelemetry import trace
from pydantic import Field
from typing_extensions import Annotated

from tools.sla import record_sla_breach, sla_breach_message, sla_for

_tracer = trace.get_tracer("uaip.tools", "1.0.0")
_AGENT_NAME = "Governance Agent"


def _governance_get(path: str, tool_name: str = "governance") -> str:
    """Make a GET request to the UC3 governance API via APIM."""
    with _tracer.start_as_current_span(f"uaip.tool.{tool_name}") as span:
        span.set_attribute("uc", "use-case-2")
        span.set_attribute("tool.name", tool_name)
        span.set_attribute("agent.name", _AGENT_NAME)
        span.set_attribute("agent.type", "native")

        uc3_endpoint = os.environ.get("UC3_GOVERNANCE_ENDPOINT", "")
        apim_key = os.environ.get("APIM_SUBSCRIPTION_KEY", "")

        if not uc3_endpoint:
            span.set_attribute("error", True)
            return "Governance hub not configured (UC3_GOVERNANCE_ENDPOINT not set)."

        sla_seconds = sla_for(_AGENT_NAME)
        span.set_attribute("sla.threshold_seconds", sla_seconds)
        started = time.monotonic()

        try:
            with httpx.Client(timeout=sla_seconds) as client:
                response = client.get(
                    f"{uc3_endpoint}{path}",
                    headers={"Ocp-Apim-Subscription-Key": apim_key},
                )
                response.raise_for_status()
                span.set_attribute("error", False)
                return response.text
        except httpx.TimeoutException:
            record_sla_breach(
                span,
                agent_name=_AGENT_NAME,
                tool_name=tool_name,
                sla_seconds=sla_seconds,
                elapsed_seconds=time.monotonic() - started,
                cause="http_timeout",
            )
            return sla_breach_message(_AGENT_NAME, sla_seconds, cause="http_timeout")
        except httpx.HTTPStatusError as e:
            span.set_attribute("error", True)
            return f"Governance query failed (HTTP {e.response.status_code}): {e.response.text[:200]}"
        except Exception as e:
            span.set_attribute("error", True)
            return f"Governance query unavailable: {e}"


@tool(approval_mode="never_require")
def query_governance_costs(
    scope: Annotated[str, Field(description="Cost query scope: 'summary', 'by-agent', or 'trends'.")] = "summary",
) -> str:
    """Query AI platform cost data from the governance hub.

    Returns token usage, inference costs, and spend breakdowns across
    agents and cloud providers.
    """
    path_map = {
        "summary": "/api/costs/summary",
        "by-agent": "/api/costs/by-agent",
        "trends": "/api/costs/trends",
    }
    path = path_map.get(scope, "/api/costs/summary")
    return _governance_get(path, tool_name="query_governance_costs")


@tool(approval_mode="never_require")
def query_governance_traces(
    trace_id: Annotated[str, Field(description="Optional trace ID to get details for a specific trace. Leave empty for recent traces.")] = "",
) -> str:
    """Query agent execution traces from the governance hub.

    Returns OpenTelemetry trace data showing agent invocations,
    tool calls, latency, and cross-cloud execution flows.
    """
    if trace_id:
        return _governance_get(f"/api/agents/{trace_id}", tool_name="query_governance_traces")
    return _governance_get("/api/agents/traces", tool_name="query_governance_traces")


@tool(approval_mode="never_require")
def query_agent_health() -> str:
    """Check health status of all agents in the Unified AI Platform.

    Returns availability, response times, and error rates for each
    registered agent across Azure and AWS.
    """
    return _governance_get("/api/agents/health", tool_name="query_agent_health")
