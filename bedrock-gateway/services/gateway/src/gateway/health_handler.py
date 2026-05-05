"""GET /health — minimal liveness probe (no DDB or Bedrock dependency)."""

from __future__ import annotations

from gateway.common import http_response


def handler(_event, _context):
    return http_response(200, {"status": "ok", "service": "aws-agent-gateway"})
