# Licensed under the MIT License. See LICENSE file in the project root.
"""RAG Knowledge Retrieval tool — searches the organization's document corpus via APIM."""

import os
import time

import httpx
from agent_framework import tool
from opentelemetry import trace
from pydantic import Field
from typing_extensions import Annotated

from tools.sla import record_sla_breach, sla_breach_message, sla_for

_tracer = trace.get_tracer("tools", "1.0.0")
_AGENT_NAME = "Knowledge Agent"
_TOOL_NAME = "search_knowledge"


@tool(approval_mode="never_require")
def search_knowledge(
    query: Annotated[str, Field(description="Search query for the knowledge base (documents, contracts, reports).")],
) -> str:
    """Search the knowledge base for documents, contracts, reports, and specifications.

    Uses the RAG (Retrieval-Augmented Generation) agent which indexes
    the organization's document corpus.
    """
    with _tracer.start_as_current_span("tool.search_knowledge") as span:
        span.set_attribute("tool.name", "search_knowledge")
        span.set_attribute("agent.name", "Knowledge Agent")
        span.set_attribute("agent.type", "native")

        uc1_endpoint = os.environ.get("UC1_RAG_ENDPOINT", "")
        apim_key = os.environ.get("APIM_SUBSCRIPTION_KEY", "")

        if not uc1_endpoint:
            span.set_attribute("error", True)
            return "Knowledge retrieval is not configured (UC1_RAG_ENDPOINT not set). The UC1 RAG agent has not been deployed yet."

        headers = {"Content-Type": "application/json"}
        if apim_key:
            headers["Ocp-Apim-Subscription-Key"] = apim_key

        sla_seconds = sla_for(_AGENT_NAME)
        span.set_attribute("sla.threshold_seconds", sla_seconds)
        started = time.monotonic()

        try:
            with httpx.Client(timeout=sla_seconds) as client:
                response = client.post(
                    f"{uc1_endpoint}/responses",
                    json={"input": query},
                    headers=headers,
                )
                response.raise_for_status()
                data = response.json()
                outputs = data.get("output", [])
                messages = [o for o in outputs if o.get("type") == "message" and o.get("role") == "assistant"]
                if messages:
                    content = messages[-1].get("content", [{}])
                    text = content[0].get("text", "") if content else ""
                    span.set_attribute("error", False)
                    return text or str(data)
                span.set_attribute("error", False)
                return str(data)
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
            return f"Knowledge search failed (HTTP {e.response.status_code}): {e.response.text[:200]}"
        except Exception as e:
            span.set_attribute("error", True)
            return f"Knowledge search unavailable: {e}"
