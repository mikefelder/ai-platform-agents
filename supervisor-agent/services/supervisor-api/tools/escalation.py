# Licensed under the MIT License. See LICENSE file in the project root.
"""Escalation publisher.

When an SLA breach is detected by ``tools.sla.record_sla_breach`` the supervisor
optionally posts an escalation event to the governance-api so the incident's
state machine flips to ESCALATED and a forensic ``escalation.sla_breach``
``WorkflowEvent`` is appended.

The supervisor's request pipeline does not (yet) thread an ``incident_id`` into
each agent invocation, so the publisher reads the id from a ``ContextVar`` that
upstream callers set via :func:`set_incident_context`. When the context var is
unset the publisher is a no-op — the OTEL ``agent.sla_breach`` event recorded
on the span remains the sole signal.

Wiring is intentionally fire-and-forget: a failure to escalate must not mask
the original SLA breach, so all errors are caught and logged at WARNING.
"""

from __future__ import annotations

import contextvars
import logging
import os

import httpx

logger = logging.getLogger("uaip.escalation")

# Per-request context for incident id. Callers (FastAPI middleware, executor
# pre-step, manual test harnesses) call set_incident_context(id) at the start
# of a request and reset() when done.
_incident_id_ctx: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "uaip_incident_id", default=None
)


def set_incident_context(incident_id: str | None) -> contextvars.Token:
    """Bind ``incident_id`` to the current execution context.

    Returns the reset token; call ``_incident_id_ctx.reset(token)`` (or use
    ``contextvars.copy_context()``) to restore the previous value.
    """
    return _incident_id_ctx.set(incident_id)


def current_incident_id() -> str | None:
    """Return the incident id bound to the current context, or env override."""
    ctx_value = _incident_id_ctx.get()
    if ctx_value:
        return ctx_value
    env_value = os.environ.get("UAIP_INCIDENT_ID")
    return env_value or None


def publish_sla_breach(
    *,
    agent_name: str,
    sla_threshold_seconds: float,
    elapsed_seconds: float | None,
    cause: str,
    tool_name: str,
    incident_id: str | None = None,
    timeout_seconds: float = 5.0,
) -> bool:
    """POST an SLA breach escalation to UC3 governance-api via APIM.

    Returns True when the call succeeded (HTTP 2xx), False otherwise. Designed
    to be called from inside ``record_sla_breach`` after the OTEL event is
    emitted, so it is safe to swallow all exceptions.
    """
    iid = incident_id or current_incident_id()
    if not iid:
        return False

    endpoint = os.environ.get("UC3_GOVERNANCE_ENDPOINT", "").rstrip("/")
    if not endpoint:
        logger.debug("UC3_GOVERNANCE_ENDPOINT not set — skipping SLA escalation publish")
        return False

    apim_key = os.environ.get("APIM_SUBSCRIPTION_KEY", "")
    body: dict = {
        "type": "sla_breach",
        "source": "supervisor",
        "agent_name": agent_name,
        "sla_threshold_seconds": float(sla_threshold_seconds),
        "reason": cause,
        "details": {"tool_name": tool_name},
    }
    if elapsed_seconds is not None:
        body["elapsed_seconds"] = float(elapsed_seconds)

    headers = {"Content-Type": "application/json"}
    if apim_key:
        headers["Ocp-Apim-Subscription-Key"] = apim_key

    try:
        with httpx.Client(timeout=timeout_seconds) as client:
            resp = client.post(
                f"{endpoint}/api/incidents/{iid}/escalations",
                json=body,
                headers=headers,
            )
            if resp.status_code // 100 == 2:
                logger.info(
                    "Published SLA escalation to UC3 incident=%s agent=%s status=%s",
                    iid, agent_name, resp.status_code,
                )
                return True
            logger.warning(
                "UC3 escalation publish failed: status=%s body=%s",
                resp.status_code, resp.text[:200],
            )
            return False
    except Exception as exc:
        logger.warning("UC3 escalation publish error for incident=%s: %s", iid, exc)
        return False
