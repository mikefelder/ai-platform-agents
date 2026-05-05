# Licensed under the MIT License. See LICENSE file in the project root.
"""Escalation publisher tests."""

from __future__ import annotations

import sys
import types
from pathlib import Path

import httpx
import pytest
import respx

_SVC_ROOT = Path(__file__).resolve().parents[1]
if str(_SVC_ROOT) not in sys.path:
    sys.path.insert(0, str(_SVC_ROOT))

# Stub `agent_framework` so tools.sla can be imported without the runtime dep.
if "agent_framework" not in sys.modules:
    _af = types.ModuleType("agent_framework")

    def _tool(*_args, **_kwargs):
        def _decorate(fn):
            fn.func = fn
            return fn

        return _decorate

    _af.tool = _tool
    sys.modules["agent_framework"] = _af

from tools import escalation as escalation_mod  # noqa: E402
from tools import sla as sla_module  # noqa: E402


_UC3 = "https://ai-alz-apim-i40e.azure-api.net/uc3"
_KEY = "test-apim-key"


@pytest.fixture(autouse=True)
def _reset_ctx():
    token = escalation_mod.set_incident_context(None)
    yield
    escalation_mod._incident_id_ctx.reset(token)


def test_publish_no_op_when_no_incident_id(monkeypatch):
    monkeypatch.setenv("UC3_GOVERNANCE_ENDPOINT", _UC3)
    monkeypatch.delenv("UAIP_INCIDENT_ID", raising=False)
    assert escalation_mod.publish_sla_breach(
        agent_name="Knowledge Agent",
        sla_threshold_seconds=15.0,
        elapsed_seconds=22.0,
        cause="http_timeout",
        tool_name="search_knowledge",
    ) is False


def test_publish_no_op_when_endpoint_missing(monkeypatch):
    monkeypatch.delenv("UC3_GOVERNANCE_ENDPOINT", raising=False)
    assert escalation_mod.publish_sla_breach(
        agent_name="Knowledge Agent",
        sla_threshold_seconds=15.0,
        elapsed_seconds=22.0,
        cause="http_timeout",
        tool_name="search_knowledge",
        incident_id="inc-123",
    ) is False


@respx.mock
def test_publish_posts_when_incident_in_context(monkeypatch):
    monkeypatch.setenv("UC3_GOVERNANCE_ENDPOINT", _UC3)
    monkeypatch.setenv("APIM_SUBSCRIPTION_KEY", _KEY)
    escalation_mod.set_incident_context("inc-abc")

    route = respx.post(f"{_UC3}/api/incidents/inc-abc/escalations").mock(
        return_value=httpx.Response(202, json={"status": "escalated"})
    )

    ok = escalation_mod.publish_sla_breach(
        agent_name="Knowledge Agent",
        sla_threshold_seconds=15.0,
        elapsed_seconds=22.4,
        cause="http_timeout",
        tool_name="search_knowledge",
    )
    assert ok is True
    assert route.called
    sent = route.calls.last.request
    assert sent.headers.get("Ocp-Apim-Subscription-Key") == _KEY
    body = sent.read().decode()
    assert '"type":"sla_breach"' in body
    assert '"agent_name":"Knowledge Agent"' in body
    assert '"reason":"http_timeout"' in body


@respx.mock
def test_publish_explicit_incident_id_overrides_context(monkeypatch):
    monkeypatch.setenv("UC3_GOVERNANCE_ENDPOINT", _UC3)
    monkeypatch.delenv("APIM_SUBSCRIPTION_KEY", raising=False)
    escalation_mod.set_incident_context("inc-from-context")

    route = respx.post(f"{_UC3}/api/incidents/inc-explicit/escalations").mock(
        return_value=httpx.Response(202, json={})
    )

    ok = escalation_mod.publish_sla_breach(
        agent_name="Compliance Agent",
        sla_threshold_seconds=45.0,
        elapsed_seconds=None,
        cause="http_timeout",
        tool_name="analyze_compliance",
        incident_id="inc-explicit",
    )
    assert ok is True
    assert route.called


@respx.mock
def test_publish_returns_false_on_http_error(monkeypatch):
    monkeypatch.setenv("UC3_GOVERNANCE_ENDPOINT", _UC3)
    escalation_mod.set_incident_context("inc-xyz")

    respx.post(f"{_UC3}/api/incidents/inc-xyz/escalations").mock(
        return_value=httpx.Response(500, text="boom")
    )

    assert escalation_mod.publish_sla_breach(
        agent_name="Knowledge Agent",
        sla_threshold_seconds=15.0,
        elapsed_seconds=15.5,
        cause="http_timeout",
        tool_name="search_knowledge",
    ) is False


@respx.mock
def test_record_sla_breach_triggers_publish_when_incident_in_context(monkeypatch):
    """Integration: tools.sla.record_sla_breach should call escalation publisher."""
    monkeypatch.setenv("UC3_GOVERNANCE_ENDPOINT", _UC3)
    monkeypatch.setenv("APIM_SUBSCRIPTION_KEY", _KEY)
    escalation_mod.set_incident_context("inc-int")

    route = respx.post(f"{_UC3}/api/incidents/inc-int/escalations").mock(
        return_value=httpx.Response(202, json={})
    )

    class _Span:
        def __init__(self):
            self.attrs = {}
            self.events = []

        def set_attribute(self, k, v):
            self.attrs[k] = v

        def add_event(self, name, attributes=None):
            self.events.append((name, dict(attributes or {})))

    sla_module.record_sla_breach(
        _Span(),
        agent_name="Knowledge Agent",
        tool_name="search_knowledge",
        sla_seconds=15.0,
        elapsed_seconds=15.9,
        cause="http_timeout",
    )

    assert route.called
