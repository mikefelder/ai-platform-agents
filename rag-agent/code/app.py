"""
This module contains the entry point for the application.
"""

import os
import logging
from azure.monitor.opentelemetry import configure_azure_monitor
from opentelemetry import trace
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.sdk.trace.export import BatchSpanProcessor

logging.captureWarnings(True)

# Logging configuration from environment variables
AZURE_BASIC_LOGGING_LEVEL = os.environ.get("LOGLEVEL", "INFO")
PACKAGE_LOGGING_LEVEL = os.environ.get("PACKAGE_LOGGING_LEVEL", "WARNING")
AZURE_LOGGING_PACKAGES = os.environ.get("AZURE_LOGGING_PACKAGES", "")
AZURE_LOGGING_PACKAGES = [pkg.strip() for pkg in AZURE_LOGGING_PACKAGES if pkg.strip()]

# Configure logging levels from environment variables
logging.basicConfig(
    level=getattr(logging, AZURE_BASIC_LOGGING_LEVEL.upper(), logging.INFO)
)

# Configure Azure package logging levels
azure_package_log_level = getattr(
    logging, PACKAGE_LOGGING_LEVEL.upper(), logging.WARNING
)
for logger_name in AZURE_LOGGING_PACKAGES:
    logging.getLogger(logger_name).setLevel(azure_package_log_level)

# We cannot use EnvHelper here as Application Insights should be configured first
# for instrumentation to work correctly
if os.getenv("APPLICATIONINSIGHTS_ENABLED", "false").lower() == "true":
    configure_azure_monitor()
    HTTPXClientInstrumentor().instrument()  # httpx is used by openai

# OTLP exporter — sends spans to the UC3 governance OTEL collector (or any
# OTLP-compatible backend) in addition to Azure Monitor.
otlp_endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
if otlp_endpoint:
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
        OTLPSpanExporter,
    )

    provider = trace.get_tracer_provider()
    if hasattr(provider, "add_span_processor"):
        provider.add_span_processor(
            BatchSpanProcessor(OTLPSpanExporter(endpoint=otlp_endpoint))
        )

# pylint: disable=wrong-import-position
from create_app import create_app  # noqa: E402

app = create_app()

if __name__ == "__main__":
    app.run()
