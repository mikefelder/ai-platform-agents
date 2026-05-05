# Licensed under the MIT License. See LICENSE file in the project root.
"""TC-5 — SLA enforcement helpers for agent tools.

Each agent in agents.yaml carries an `sla_timeout_seconds` field. Tools call
`sla_for(agent_name)` to size their httpx timeouts, and on `httpx.TimeoutException`
they call `record_sla_breach(...)` which:

  * sets span attributes (`error=True`, `sla.breach=True`, thresholds)
  * adds an OTEL span event named `agent.sla_breach` with structured payload
  * emits a WARNING-level log record

The OTEL event flowing into App Insights is the trigger source for the Sentinel
analytics rule "Agent SLA breach detected" and for any downstream Service Bus /
Logic App escalation. The supervisor itself does not directly mutate incident
state — that boundary stays inside UC3 governance-api.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger("uaip.sla")

_AGENTS_YAML = Path(__file__).resolve().parents[1] / "agents.yaml"
_DEFAULT_SLA_SECONDS = 60.0

_sla_cache: dict[str, float] | None = None


def _load_sla_config() -> dict[str, float]:
    """Read agents.yaml once and return {agent_name: sla_seconds}."""
    try:
        with open(_AGENTS_YAML) as f:
            agents = yaml.safe_load(f) or []
    except FileNotFoundError:
        logger.warning("agents.yaml not found at %s — SLA defaults will apply", _AGENTS_YAML)
        return {}

    out: dict[str, float] = {}
    for a in agents:
        name = a.get("name")
        sla = a.get("sla_timeout_seconds")
        if name and sla is not None:
            try:
                out[name] = float(sla)
            except (TypeError, ValueError):
                logger.warning("Invalid sla_timeout_seconds=%r for agent %r — ignored", sla, name)
    return out


def sla_for(agent_name: str) -> float:
    """Return the SLA timeout (seconds) configured for the named agent.

    Falls back to ``SLA_DEFAULT_SECONDS`` env var, then to 60s.
    Cached on first read; call :func:`reset_sla_cache` in tests.
    """
    global _sla_cache
    if _sla_cache is None:
        _sla_cache = _load_sla_config()

    if agent_name in _sla_cache:
        return _sla_cache[agent_name]

    env_default = os.environ.get("SLA_DEFAULT_SECONDS")
    if env_default:
        try:
            return float(env_default)
        except ValueError:
            pass
    return _DEFAULT_SLA_SECONDS


def reset_sla_cache() -> None:
    """Clear the cached SLA config (used by tests)."""
    global _sla_cache
    _sla_cache = None


def record_sla_breach(
    span: Any,
    *,
    agent_name: str,
    tool_name: str,
    sla_seconds: float,
    elapsed_seconds: float | None = None,
    cause: str = "timeout",
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Mark ``span`` as an SLA breach and emit the structured ``agent.sla_breach`` event.

    Returns the event payload so callers can include it in their tool response
    or in any escalation message.
    """
    payload: dict[str, Any] = {
        "agent.name": agent_name,
        "tool.name": tool_name,
        "sla.threshold_seconds": float(sla_seconds),
        "sla.cause": cause,
    }
    if elapsed_seconds is not None:
        payload["sla.elapsed_seconds"] = float(elapsed_seconds)
    if extra:
        payload.update(extra)

    if span is not None:
        try:
            span.set_attribute("error", True)
            span.set_attribute("sla.breach", True)
            span.set_attribute("sla.threshold_seconds", float(sla_seconds))
            if elapsed_seconds is not None:
                span.set_attribute("sla.elapsed_seconds", float(elapsed_seconds))
            span.add_event("agent.sla_breach", attributes=payload)
        except Exception as exc:  # pragma: no cover — defensive only
            logger.debug("Failed to annotate span for SLA breach: %s", exc)

    logger.warning(
        "SLA breach: agent=%s tool=%s threshold=%.1fs elapsed=%s cause=%s",
        agent_name,
        tool_name,
        sla_seconds,
        f"{elapsed_seconds:.1f}s" if elapsed_seconds is not None else "n/a",
        cause,
    )

    # Fire-and-forget UC3 escalation. No-op when no incident_id is bound to
    # the current context (preserves prior local-test behaviour).
    try:
        from tools.escalation import publish_sla_breach

        publish_sla_breach(
            agent_name=agent_name,
            sla_threshold_seconds=sla_seconds,
            elapsed_seconds=elapsed_seconds,
            cause=cause,
            tool_name=tool_name,
        )
    except Exception as exc:  # pragma: no cover — defensive only
        logger.debug("Failed to publish UC3 SLA escalation: %s", exc)

    return payload


def sla_breach_message(agent_name: str, sla_seconds: float, cause: str = "timeout") -> str:
    """Formatted user-facing string returned by tools when an SLA is breached."""
    return (
        f"[{agent_name}] SLA breach ({cause}): exceeded {sla_seconds:.0f}s budget. "
        f"Escalation event emitted (agent.sla_breach)."
    )
