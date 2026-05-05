# Licensed under the MIT License. See LICENSE file in the project root.
"""Compliance analysis tool — calls Azure AI Foundry for compliance/safety questions."""

import os
import time

import httpx
from agent_framework import tool
from azure.identity import ManagedIdentityCredential, DefaultAzureCredential
from opentelemetry import trace
from pydantic import Field
from typing_extensions import Annotated

from tools.sla import record_sla_breach, sla_breach_message, sla_for

_tracer = trace.get_tracer("uaip.tools", "1.0.0")
_AGENT_NAME = "Compliance Agent"
_TOOL_NAME = "analyze_compliance"

# Cached credential — avoids IMDS round-trip on every tool invocation
_credential = None

def _get_credential():
    global _credential
    if _credential is None:
        client_id = os.environ.get("AZURE_CLIENT_ID", "")
        _credential = ManagedIdentityCredential(client_id=client_id) if client_id else DefaultAzureCredential()
    return _credential


@tool(approval_mode="never_require")
def analyze_compliance(
    question: Annotated[str, Field(description="The compliance, safety, or regulatory question to analyze.")],
) -> str:
    """Analyze compliance, safety, or regulatory questions using Azure AI Foundry.

    Provides concise, actionable analysis for compliance,
    safety standards, and regulatory requirements.
    """
    endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT", "")
    deployment = os.environ.get("COMPLIANCE_MODEL", "o4-mini")
    is_reasoning = deployment.startswith("o")

    if not endpoint:
        return "Compliance analysis unavailable (AZURE_AI_ENDPOINT not set)."

    with _tracer.start_as_current_span("uaip.tool.analyze_compliance") as span:
        span.set_attribute("uc", "use-case-2")
        span.set_attribute("tool.name", "analyze_compliance")
        span.set_attribute("agent.name", "Compliance Agent")
        span.set_attribute("agent.type", "native")
        span.set_attribute("gen_ai.request.model", deployment)

        sla_seconds = sla_for(_AGENT_NAME)
        span.set_attribute("sla.threshold_seconds", sla_seconds)
        started = time.monotonic()

        try:
            # Use the OpenAI-compatible chat completions API on Foundry
            url = f"{endpoint}openai/deployments/{deployment}/chat/completions?api-version=2025-04-01-preview"

            token = _get_credential().get_token("https://cognitiveservices.azure.com/.default")

            # Reasoning models (o-series) use 'developer' role instead of 'system'
            system_role = "developer" if is_reasoning else "system"
            body: dict = {
                "messages": [
                    {
                        "role": system_role,
                        "content": (
                            "You are a compliance and safety advisor. "
                            "Provide concise, actionable analysis grounded in "
                            "standards and regulatory frameworks."
                        ),
                    },
                    {"role": "user", "content": question},
                ],
            }
            if is_reasoning:
                body["max_completion_tokens"] = 2048
            else:
                body["max_tokens"] = 1024

            with httpx.Client(timeout=sla_seconds) as client:
                response = client.post(
                    url,
                    json=body,
                    headers={
                        "Authorization": f"Bearer {token.token}",
                        "Content-Type": "application/json",
                    },
                )
                response.raise_for_status()
                data = response.json()
                span.set_attribute("error", False)
                return data["choices"][0]["message"]["content"]
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
        except Exception as e:
            span.set_attribute("error", True)
            return f"Compliance analysis failed: {e}"
