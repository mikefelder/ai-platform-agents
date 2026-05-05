"""Executor Lambda — invoked asynchronously by the invoke_handler.

Runs the actual Bedrock call (AgentCore runtime, Bedrock Agent, or a
Converse stub) and writes the result back to DynamoDB.

Selection order:
  1. BEDROCK_AGENT_RUNTIME_ARN set  -> bedrock-agentcore-runtime.InvokeAgentRuntime
  2. BEDROCK_AGENT_ID + ALIAS_ID set -> bedrock-agent-runtime.InvokeAgent
  3. fallback                        -> bedrock-runtime.Converse (Claude Haiku)

The fallback lets a brand-new account demonstrate the full async contract
with no prior Bedrock provisioning — enable Claude Haiku in Bedrock model
access and you are done.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError
from opentelemetry.trace import StatusCode

from gateway.common import (
    AWS_REGION,
    attach_incoming_trace,
    detach_trace,
    executions_table,
    flush_telemetry,
    get_tracer,
    log,
)

_tracer = get_tracer(__name__)

AGENT_RUNTIME_ARN = os.environ.get("BEDROCK_AGENT_RUNTIME_ARN")
AGENT_ID = os.environ.get("BEDROCK_AGENT_ID")
AGENT_ALIAS_ID = os.environ.get("BEDROCK_AGENT_ALIAS_ID")
FALLBACK_MODEL_ID = os.environ.get(
    "BEDROCK_FALLBACK_MODEL_ID",
    "au.anthropic.claude-haiku-4-5-20251001-v1:0",
)

_bedrock_runtime = boto3.client("bedrock-runtime", region_name=AWS_REGION)
try:
    _bedrock_agent_runtime = boto3.client("bedrock-agent-runtime", region_name=AWS_REGION)
except Exception:  # noqa: BLE001
    _bedrock_agent_runtime = None

try:
    _bedrock_agentcore = boto3.client("bedrock-agentcore", region_name=AWS_REGION)
except Exception:  # noqa: BLE001
    # Service name varies by botocore version; fall back to None.
    _bedrock_agentcore = None


def handler(event: dict, _context) -> dict:
    execution_id = event["executionId"]
    agent_name = event.get("agentName", "unknown")
    traceparent = event.get("traceparent")

    token = attach_incoming_trace(traceparent)
    start = time.monotonic()

    try:
        with _tracer.start_as_current_span("aws.agent_gateway.execute") as span:
            span.set_attribute("cloud.provider", "aws")
            span.set_attribute("execution.id", execution_id)
            span.set_attribute("agent.name", agent_name)

            _mark_running(execution_id)

            record = executions_table.get_item(Key={"executionId": execution_id}).get(
                "Item"
            )
            if not record:
                log.error("Execution %s not found in DDB", execution_id)
                return {"ok": False}

            payload = record.get("payload") or {}
            query = payload.get("query") or payload.get("input") or ""

            try:
                if AGENT_RUNTIME_ARN and _bedrock_agentcore is not None:
                    span.set_attribute("bedrock.mode", "agentcore_runtime")
                    content, citations, tokens_in, tokens_out = _invoke_agentcore(
                        query, agent_name
                    )
                elif AGENT_ID and AGENT_ALIAS_ID and _bedrock_agent_runtime is not None:
                    span.set_attribute("bedrock.mode", "bedrock_agent")
                    content, citations, tokens_in, tokens_out = _invoke_bedrock_agent(
                        query
                    )
                else:
                    span.set_attribute("bedrock.mode", "converse_fallback")
                    content, citations, tokens_in, tokens_out = _invoke_converse(
                        query, agent_name
                    )
            except ClientError as exc:
                log.exception("Bedrock call failed: %s", exc)
                span.set_status(StatusCode.ERROR, str(exc))
                _mark_failed(execution_id, f"Bedrock error: {exc!s}")
                return {"ok": False}
            except Exception as exc:  # noqa: BLE001
                log.exception("Unexpected executor failure: %s", exc)
                span.set_status(StatusCode.ERROR, str(exc))
                _mark_failed(execution_id, str(exc))
                return {"ok": False}

            duration_ms = int((time.monotonic() - start) * 1000)
            span.set_attribute("bedrock.telemetry.durationMs", duration_ms)
            span.set_attribute("bedrock.telemetry.tokens.input", tokens_in)
            span.set_attribute("bedrock.telemetry.tokens.output", tokens_out)

            _mark_completed(
                execution_id,
                content=content,
                citations=citations,
                duration_ms=duration_ms,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
            )
            return {"ok": True}
    finally:
        flush_telemetry()
        detach_trace(token)


# ---------------------------------------------------------------------------
# Bedrock call paths
# ---------------------------------------------------------------------------

def _invoke_agentcore(query: str, agent_name: str) -> tuple[str, list[str], int, int]:
    """Invoke a Bedrock AgentCore runtime via InvokeAgentRuntime."""
    resp = _bedrock_agentcore.invoke_agent_runtime(
        agentRuntimeArn=AGENT_RUNTIME_ARN,
        qualifier=os.environ.get("BEDROCK_AGENT_RUNTIME_QUALIFIER", "DEFAULT"),
        payload=json.dumps(
            {"inputText": query, "agentName": agent_name}
        ).encode("utf-8"),
        contentType="application/json",
        accept="application/json",
    )
    body_bytes = b""
    if "response" in resp:
        for chunk in resp["response"]:
            body_bytes += chunk if isinstance(chunk, bytes) else chunk.get("bytes", b"")
    elif "payload" in resp:
        body_bytes = resp["payload"].read() if hasattr(resp["payload"], "read") else resp["payload"]

    try:
        parsed = json.loads(body_bytes.decode("utf-8") or "{}")
    except Exception:  # noqa: BLE001
        parsed = {"output": {"text": body_bytes.decode("utf-8", errors="replace")}}

    content = (
        parsed.get("output", {}).get("text")
        or parsed.get("content")
        or parsed.get("completion")
        or ""
    )
    usage = parsed.get("usage") or {}
    return (
        content,
        parsed.get("citations") or [],
        int(usage.get("inputTokens") or 0),
        int(usage.get("outputTokens") or 0),
    )


def _invoke_bedrock_agent(query: str) -> tuple[str, list[str], int, int]:
    """Invoke a classic Bedrock Agent (bedrock-agent-runtime.InvokeAgent)."""
    session_id = f"uaip-{uuid.uuid4().hex[:12]}"
    resp = _bedrock_agent_runtime.invoke_agent(
        agentId=AGENT_ID,
        agentAliasId=AGENT_ALIAS_ID,
        sessionId=session_id,
        inputText=query,
    )
    content_parts: list[str] = []
    citations: list[str] = []
    tokens_in = tokens_out = 0

    for event in resp.get("completion", []):
        if "chunk" in event:
            chunk = event["chunk"]
            if "bytes" in chunk:
                content_parts.append(chunk["bytes"].decode("utf-8", errors="replace"))
            attribution = chunk.get("attribution") or {}
            for cit in attribution.get("citations", []):
                for ref in cit.get("retrievedReferences", []):
                    loc = ref.get("location") or {}
                    ident = (
                        loc.get("s3Location", {}).get("uri")
                        or loc.get("webLocation", {}).get("url")
                        or json.dumps(loc)
                    )
                    citations.append(ident)
        if "trace" in event:
            usage = (
                event.get("trace", {})
                .get("trace", {})
                .get("orchestrationTrace", {})
                .get("modelInvocationOutput", {})
                .get("metadata", {})
                .get("usage", {})
            )
            tokens_in += int(usage.get("inputTokens") or 0)
            tokens_out += int(usage.get("outputTokens") or 0)

    return "".join(content_parts), citations, tokens_in, tokens_out


def _invoke_converse(query: str, agent_name: str) -> tuple[str, list[str], int, int]:
    """Fallback: Bedrock Converse with a fixed system prompt per agent_name."""
    system_prompt = (
        f"You are the {agent_name} agent in the Unified AI Platform. "
        "Answer concisely; cite document ids when appropriate."
    )
    resp = _bedrock_runtime.converse(
        modelId=FALLBACK_MODEL_ID,
        messages=[{"role": "user", "content": [{"text": query or "Hello"}]}],
        system=[{"text": system_prompt}],
        inferenceConfig={"maxTokens": 512, "temperature": 0.2},
    )
    output = resp.get("output", {}).get("message", {}).get("content", [])
    text = "".join(c.get("text", "") for c in output)
    usage = resp.get("usage") or {}
    return (
        text,
        [],
        int(usage.get("inputTokens") or 0),
        int(usage.get("outputTokens") or 0),
    )


# ---------------------------------------------------------------------------
# DynamoDB state transitions
# ---------------------------------------------------------------------------

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _mark_running(execution_id: str) -> None:
    executions_table.update_item(
        Key={"executionId": execution_id},
        UpdateExpression="SET #s = :s, updatedAt = :u",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={":s": "running", ":u": _now()},
    )


def _mark_failed(execution_id: str, error: str) -> None:
    executions_table.update_item(
        Key={"executionId": execution_id},
        UpdateExpression="SET #s = :s, #e = :e, updatedAt = :u",
        ExpressionAttributeNames={"#s": "status", "#e": "error"},
        ExpressionAttributeValues={":s": "failed", ":e": error, ":u": _now()},
    )


def _mark_completed(
    execution_id: str,
    *,
    content: str,
    citations: list[str],
    duration_ms: int,
    tokens_in: int,
    tokens_out: int,
) -> None:
    executions_table.update_item(
        Key={"executionId": execution_id},
        UpdateExpression=(
            "SET #s = :s, #r = :r, telemetry = :t, updatedAt = :u"
        ),
        ExpressionAttributeNames={"#s": "status", "#r": "result"},
        ExpressionAttributeValues={
            ":s": "completed",
            ":r": {"content": content, "citations": citations},
            ":t": {
                "durationMs": duration_ms,
                "tokens": {"input": tokens_in, "output": tokens_out},
            },
            ":u": _now(),
        },
    )
