"""TC-4 / TC-6 — supervisor response validators."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Ensure the supervisor-api root is importable when pytest is launched from elsewhere.
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from tools.validators import (  # noqa: E402
    DiagnosticValidator,
    MonitoringValidator,
    ValidationReport,
    run_validators,
)


# --- TC-4 MonitoringValidator -----------------------------------------------


def test_monitoring_validator_skips_when_intent_unrelated():
    v = MonitoringValidator()
    rep = v.evaluate(
        user_text="Show me the ASME B31.3 spec for piping",
        combined_response="The spec defines pressure ratings…",
    )
    assert rep.passed is True
    assert any(f.code == "MON_NOT_REQUIRED" for f in rep.findings)


def test_monitoring_validator_warns_when_metrics_missing():
    v = MonitoringValidator()
    rep = v.evaluate(
        user_text="What is the platform health right now?",
        combined_response="All agents are doing fine.",
    )
    assert rep.passed is False
    assert any(f.code == "MON_MISSING_METRICS" for f in rep.findings)


def test_monitoring_validator_passes_when_metrics_present():
    v = MonitoringValidator()
    rep = v.evaluate(
        user_text="Give me a monitoring dashboard summary.",
        combined_response="Latency p95=420ms, error rate=0.4%, cost spend nominal.",
    )
    assert rep.passed is True
    detail = next(f for f in rep.findings if f.code == "MON_METRICS_PRESENT")
    assert "latency" in detail.detail["signals"]
    assert "error rate" in detail.detail["signals"]


# --- TC-6 DiagnosticValidator -----------------------------------------------


def test_diagnostic_validator_returns_top_matches():
    v = DiagnosticValidator(threshold=2)
    rep = v.evaluate(
        user_text="knowledge agent latency search throttling investigation",
        combined_response="See historical pattern.",
    )
    assert rep.passed is True
    matches = [f for f in rep.findings if f.code == "DIAG_MATCH"]
    assert matches, "Expected at least one similarity match"
    assert any("HIST-2024-0142" in f.message for f in matches)


def test_diagnostic_validator_no_match_below_threshold():
    v = DiagnosticValidator(corpus=({"incident_id": "X", "summary": "abc", "tags": ()},), threshold=5)
    rep = v.evaluate(user_text="lorem ipsum", combined_response="dolor sit amet")
    assert rep.passed is True
    assert any(f.code == "DIAG_NO_MATCH" for f in rep.findings)


def test_diagnostic_validator_empty_input_warns():
    v = DiagnosticValidator()
    rep = v.evaluate(user_text="", combined_response="")
    assert rep.passed is False
    assert any(f.code == "DIAG_EMPTY_INPUT" for f in rep.findings)


# --- run_validators chain ---------------------------------------------------


def test_run_validators_returns_reports_and_markdown_block():
    reports, block = run_validators(
        user_text="platform health monitoring report",
        combined_response="latency p99 fine; cost normal; bedrock timeout aws lessons learned",
    )
    assert len(reports) == 2
    assert all(isinstance(r, ValidationReport) for r in reports)
    assert block.startswith("## Validation Report")
    assert "MonitoringValidator" in block
    assert "DiagnosticValidator" in block


def test_run_validators_isolates_failures_per_validator():
    # Force MonitoringValidator to WARN and DiagnosticValidator to PASS
    reports, _block = run_validators(
        user_text="show me the monitoring dashboard",
        combined_response="bedrock timeout aws cross-cloud peering",
    )
    by_name = {r.validator: r for r in reports}
    assert by_name["MonitoringValidator"].passed is False
    assert by_name["DiagnosticValidator"].passed is True
