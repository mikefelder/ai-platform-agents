"""Shared utilities: DynamoDB client, telemetry, trace propagation."""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

import boto3
from opentelemetry import trace
from opentelemetry.context import attach, detach
from opentelemetry.propagate import extract
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------

AWS_REGION = os.environ.get("AWS_REGION", "ap-southeast-2")
EXECUTIONS_TABLE = os.environ.get("EXECUTIONS_TABLE", "uaip-bedrock-executions")
EXECUTOR_FUNCTION = os.environ.get("EXECUTOR_FUNCTION", "uaip-bedrock-executor")
SERVICE_NAME = os.environ.get("OTEL_SERVICE_NAME", "aws-agent-gateway")

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

log = logging.getLogger(SERVICE_NAME)
log.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

# ---------------------------------------------------------------------------
# AWS clients (module-scoped for Lambda reuse)
# ---------------------------------------------------------------------------

_ddb = boto3.resource("dynamodb", region_name=AWS_REGION)
executions_table = _ddb.Table(EXECUTIONS_TABLE)

_lambda = boto3.client("lambda", region_name=AWS_REGION)


def invoke_executor_async(payload: dict[str, Any]) -> None:
    """Fire-and-forget async invocation of the executor Lambda."""
    _lambda.invoke(
        FunctionName=EXECUTOR_FUNCTION,
        InvocationType="Event",  # async
        Payload=json.dumps(payload).encode("utf-8"),
    )


# ---------------------------------------------------------------------------
# Telemetry
# ---------------------------------------------------------------------------

_TELEMETRY_INITIALISED = False


def init_telemetry() -> None:
    """Configure the OpenTelemetry TracerProvider.

    Exporters are selected by env vars:
      - APPLICATIONINSIGHTS_CONNECTION_STRING -> Azure Monitor exporter
      - OTEL_EXPORTER_OTLP_ENDPOINT           -> generic OTLP/HTTP exporter
      - fallback                              -> ConsoleSpanExporter (CloudWatch)
    """
    global _TELEMETRY_INITIALISED
    if _TELEMETRY_INITIALISED:
        return

    resource = Resource.create(
        {
            "service.name": SERVICE_NAME,
            "cloud.provider": "aws",
            "cloud.region": AWS_REGION,
        }
    )
    provider = TracerProvider(resource=resource)

    # Always emit to stdout (CloudWatch captures it).
    provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))

    conn_str = os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING")
    if conn_str:
        try:
            from azure.monitor.opentelemetry.exporter import AzureMonitorTraceExporter

            provider.add_span_processor(
                BatchSpanProcessor(AzureMonitorTraceExporter(connection_string=conn_str))
            )
            log.info("Azure Monitor OTEL exporter enabled")
        except Exception as exc:  # noqa: BLE001
            log.warning("Failed to init Azure Monitor exporter: %s", exc)

    otlp_endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
    if otlp_endpoint:
        try:
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
                OTLPSpanExporter,
            )

            headers_raw = os.environ.get("OTEL_EXPORTER_OTLP_HEADERS", "")
            headers = {}
            for kv in headers_raw.split(","):
                if "=" in kv:
                    k, v = kv.split("=", 1)
                    headers[k.strip()] = v.strip()

            provider.add_span_processor(
                BatchSpanProcessor(
                    OTLPSpanExporter(endpoint=otlp_endpoint, headers=headers or None)
                )
            )
            log.info("OTLP/HTTP exporter enabled: %s", otlp_endpoint)
        except Exception as exc:  # noqa: BLE001
            log.warning("Failed to init OTLP exporter: %s", exc)

    trace.set_tracer_provider(provider)
    _TELEMETRY_INITIALISED = True


def get_tracer(name: str | None = None) -> trace.Tracer:
    init_telemetry()
    return trace.get_tracer(name or SERVICE_NAME)


def flush_telemetry(timeout_ms: int = 5000) -> None:
    """Force-flush the TracerProvider.

    MUST be called at the end of every Lambda handler invocation.
    BatchSpanProcessor buffers spans and Lambda freezes the process
    before the batch interval fires — without this, spans are lost.
    """
    provider = trace.get_tracer_provider()
    if hasattr(provider, "force_flush"):
        provider.force_flush(timeout_millis=timeout_ms)


# ---------------------------------------------------------------------------
# W3C traceparent propagation
# ---------------------------------------------------------------------------

_TRACEPARENT_RE = re.compile(
    r"^00-[0-9a-f]{32}-[0-9a-f]{16}-[0-9a-f]{2}$", re.IGNORECASE
)


def attach_incoming_trace(traceparent: str | None):
    """Attach an incoming W3C traceparent to the current OTEL context.

    Returns a token that callers MUST pass to `detach()` after the span closes.
    Returns None when no valid header was supplied.
    """
    if not traceparent or not _TRACEPARENT_RE.match(traceparent):
        return None
    ctx = extract({"traceparent": traceparent})
    return attach(ctx)


def detach_trace(token) -> None:
    if token is not None:
        detach(token)


# ---------------------------------------------------------------------------
# Lambda response helpers (API Gateway HTTP API v2 format)
# ---------------------------------------------------------------------------

def http_response(status: int, body: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body or {}),
    }


def header(event: dict[str, Any], name: str) -> str | None:
    headers = event.get("headers") or {}
    # API Gateway HTTP API lowercases header names.
    return headers.get(name) or headers.get(name.lower())
