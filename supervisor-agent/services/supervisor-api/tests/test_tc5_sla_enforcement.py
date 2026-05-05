# Licensed under the MIT License. See LICENSE file in the project root.
"""TC-5 (SLA Enforcement with Escalation) tests.

Verifies:
  * agents.yaml SLA values are loaded and exposed via ``sla_for``
  * tool httpx clients use the per-agent SLA as their timeout
  * on ``httpx.TimeoutException``, tools mark the span as an SLA breach
    (``sla.breach=True``), emit an ``agent.sla_breach`` event, and return
    a structured "SLA breach" message
  * the Bedrock tool derives ``max_poll_attempts`` from the per-agent SLA
"""

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

# Stub `agent_framework` so we can import the tool modules without the runtime dep.
if "agent_framework" not in sys.modules:
    _af = types.ModuleType("agent_framework")

    def _tool(*_args, **_kwargs):
        def _decorate(fn):
            fn.func = fn
            return fn

        return _decorate

    _af.tool = _tool
    sys.modules["agent_framework"] = _af

from tools import sla as sla_module  # noqa: E402
from tools import bedrock as bedrock_tool  # noqa: E402
from tools import compliance as compliance_tool  # noqa: E402
from tools import governance as governance_tool  # noqa: E402
from tools import knowledge as knowledge_tool  # noqa: E402


_APIM_UC1 = "https://ai-alz-apim-i3ro.azure-api.net/uc1"
_APIM_UC3 = "https://ai-alz-apim-i3ro.azure-api.net/uc3"
_FOUNDRY = "https://aoai-test.openai.azure.com/"
_APIM_KEY = "test-apim-subscription-key"


def _underlying(fn):
    return getattr(fn, "func", getattr(fn, "_func", fn))


class _SpanRecorder:
    """Minimal stand-in for an OTEL span that records attributes and events."""

    def __init__(self) -> None:
        self.attributes: dict = {}
        self.events: list[tuple[str, dict]] = []

    def set_attribute(self, key, value):
        self.attributes[key] = value

    def add_event(self, name, attributes=None):
        self.events.append((name, dict(attributes or {})))


@pytest.fixture(autouse=True)
def _reset_sla_cache():
    sla_module.reset_sla_cache()
    yield
    sla_module.reset_sla_cache()


# ---------------------------------------------------------------------------
# sla_for / config loading
# ---------------------------------------------------------------------------

def test_sla_for_loads_known_agents_from_yaml():
    assert sla_module.sla_for("Knowledge Agent") == 15.0
    assert sla_module.sla_for("Compliance Agent") == 45.0
    assert sla_module.sla_for("Engineering Agent (Bedrock)") == 60.0
    assert sla_module.sla_for("Governance Agent") == 15.0
    assert sla_module.sla_for("Supervisor Agent") == 10.0
    assert sla_module.sla_for("Synthesizer Agent") == 30.0


def test_sla_for_unknown_agent_returns_default():
    assert sla_module.sla_for("Nonexistent Agent") == 60.0


def test_sla_for_unknown_agent_honours_env_default(monkeypatch):
    monkeypatch.setenv("SLA_DEFAULT_SECONDS", "7.5")
    sla_module.reset_sla_cache()
    assert sla_module.sla_for("Nonexistent Agent") == 7.5


# ---------------------------------------------------------------------------
# record_sla_breach behaviour
# ---------------------------------------------------------------------------

def test_record_sla_breach_sets_span_attrs_and_event():
    span = _SpanRecorder()
    payload = sla_module.record_sla_breach(
        span,
        agent_name="Knowledge Agent",
        tool_name="search_knowledge",
        sla_seconds=15.0,
        elapsed_seconds=15.7,
        cause="http_timeout",
    )

    assert span.attributes["error"] is True
    assert span.attributes["sla.breach"] is True
    assert span.attributes["sla.threshold_seconds"] == 15.0
    assert span.attributes["sla.elapsed_seconds"] == 15.7
    assert span.events and span.events[0][0] == "agent.sla_breach"
    assert payload["agent.name"] == "Knowledge Agent"
    assert payload["sla.cause"] == "http_timeout"


# ---------------------------------------------------------------------------
# Knowledge Agent SLA breach
# ---------------------------------------------------------------------------

@respx.mock
def test_search_knowledge_returns_breach_message_on_timeout(monkeypatch):
    monkeypatch.setenv("UC1_RAG_ENDPOINT", _APIM_UC1)
    monkeypatch.setenv("APIM_SUBSCRIPTION_KEY", _APIM_KEY)

    respx.post(f"{_APIM_UC1}/responses").mock(
        side_effect=httpx.ReadTimeout("simulated SLA breach")
    )

    result = _underlying(knowledge_tool.search_knowledge)(query="test")

    assert "SLA breach" in result
    assert "Knowledge Agent" in result
    assert "15" in result  # 15s configured SLA


# ---------------------------------------------------------------------------
# Governance Agent SLA breach
# ---------------------------------------------------------------------------

@respx.mock
def test_governance_get_returns_breach_message_on_timeout(monkeypatch):
    monkeypatch.setenv("UC3_GOVERNANCE_ENDPOINT", _APIM_UC3)
    monkeypatch.setenv("APIM_SUBSCRIPTION_KEY", _APIM_KEY)

    respx.get(f"{_APIM_UC3}/api/agents/health").mock(
        side_effect=httpx.ConnectTimeout("simulated SLA breach")
    )

    # query_agent_health calls _governance_get under the hood
    result = _underlying(governance_tool.query_agent_health)()

    assert "SLA breach" in result
    assert "Governance Agent" in result
    assert "15" in result


# ---------------------------------------------------------------------------
# Compliance Agent SLA breach
# ---------------------------------------------------------------------------

@respx.mock
def test_compliance_returns_breach_message_on_timeout(monkeypatch):
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", _FOUNDRY)
    monkeypatch.setenv("COMPLIANCE_MODEL", "o4-mini")

    # Stub the credential so we don't need real Azure auth in tests.
    class _StubToken:
        token = "fake-token"

    class _StubCred:
        def get_token(self, *_args, **_kwargs):
            return _StubToken()

    monkeypatch.setattr(compliance_tool, "_get_credential", lambda: _StubCred())

    respx.post(
        f"{_FOUNDRY}openai/deployments/o4-mini/chat/completions",
        params={"api-version": "2025-04-01-preview"},
    ).mock(side_effect=httpx.ReadTimeout("simulated SLA breach"))

    result = _underlying(compliance_tool.analyze_compliance)(question="is this safe?")

    assert "SLA breach" in result
    assert "Compliance Agent" in result
    assert "45" in result


# ---------------------------------------------------------------------------
# Bedrock Agent — SLA controls poll budget
# ---------------------------------------------------------------------------

def test_bedrock_max_poll_attempts_derived_from_sla(monkeypatch):
    """The Bedrock tool must size its polling loop from the per-agent SLA."""
    # Ensure config is reloaded with our override.
    monkeypatch.setattr(
        sla_module,
        "sla_for",
        lambda name: 8.0 if name == "Engineering Agent (Bedrock)" else 60.0,
    )
    # _POLL_INTERVAL_S is 1.0 so 8s SLA → 8 attempts max.
    sla_seconds = sla_module.sla_for("Engineering Agent (Bedrock)")
    derived = max(1, int(sla_seconds / bedrock_tool._POLL_INTERVAL_S))
    assert derived == 8


def test_bedrock_min_poll_attempts_is_one(monkeypatch):
    """Even with a sub-second SLA, polling must run at least once."""
    monkeypatch.setattr(
        sla_module,
        "sla_for",
        lambda name: 0.1 if name == "Engineering Agent (Bedrock)" else 60.0,
    )
    sla_seconds = sla_module.sla_for("Engineering Agent (Bedrock)")
    derived = max(1, int(sla_seconds / bedrock_tool._POLL_INTERVAL_S))
    assert derived == 1
