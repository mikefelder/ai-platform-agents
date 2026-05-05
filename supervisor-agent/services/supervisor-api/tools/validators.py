"""TC-4 / TC-6 — response validators for the supervisor fan-in.

These validators run after the agent fan-in and before synthesis. They are
intentionally heuristic (demo-grade) and never raise — they decorate the
aggregated response with a structured ``Validation Report`` block that the
synthesizer can incorporate or surface verbatim.

- ``MonitoringValidator`` (TC-4): Confirms platform-health signals are present
  whenever the user's intent appears to require operational visibility. Surfaces
  staleness or missing-metric hints for Sentinel / on-call follow-up.
- ``DiagnosticValidator`` (TC-6): Heuristic similarity check against a small
  in-memory corpus of historical incident snippets. The Cosmos-backed lookup
  is the production target; for the PoC we ship a deterministic seed so the
  demo path is reproducible.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable


_MONITORING_KEYWORDS = (
    "health",
    "latency",
    "error rate",
    "uptime",
    "availability",
    "p95",
    "p99",
    "throughput",
    "cost",
    "spend",
    "usage",
    "sla",
)

_MONITORING_TRIGGERS = (
    "platform health",
    "agent health",
    "dashboard",
    "monitor",
    "monitoring",
    "metrics",
    "status",
    "incident",
    "outage",
    "degraded",
)


_HISTORICAL_INCIDENTS: tuple[dict, ...] = (
    {
        "incident_id": "HIST-2024-0142",
        "summary": "Knowledge agent latency degradation due to AI Search throttling",
        "tags": ("knowledge", "latency", "search", "throttle"),
    },
    {
        "incident_id": "HIST-2024-0207",
        "summary": "Compliance agent standards lookup failure after corpus update",
        "tags": ("compliance", "standards", "spec", "corpus"),
    },
    {
        "incident_id": "HIST-2024-0318",
        "summary": "Cross-cloud agent timeout during network maintenance",
        "tags": ("external", "bedrock", "timeout", "aws"),
    },
    {
        "incident_id": "HIST-2025-0011",
        "summary": "Governance dashboard cost spike from rogue evaluation harness",
        "tags": ("governance", "cost", "spike", "evaluation"),
    },
)


@dataclass
class ValidatorFinding:
    severity: str  # info | warning
    code: str
    message: str
    detail: dict | None = None


@dataclass
class ValidationReport:
    validator: str
    passed: bool
    findings: list[ValidatorFinding] = field(default_factory=list)

    def to_markdown(self) -> str:
        head = f"- **{self.validator}**: {'PASS' if self.passed else 'WARN'}"
        if not self.findings:
            return head
        lines = [head]
        for f in self.findings:
            lines.append(f"  - `{f.severity}` [{f.code}] {f.message}")
        return "\n".join(lines)


def _tokens(text: str) -> set[str]:
    return {t for t in re.split(r"[^a-z0-9]+", text.lower()) if len(t) >= 3}


class MonitoringValidator:
    """TC-4 — verifies platform-health signals when the question warrants them."""

    name = "MonitoringValidator"

    def evaluate(self, *, user_text: str, combined_response: str) -> ValidationReport:
        report = ValidationReport(validator=self.name, passed=True)
        intent = (user_text or "").lower()
        body = (combined_response or "").lower()
        needs_monitoring = any(t in intent for t in _MONITORING_TRIGGERS)
        if not needs_monitoring:
            report.findings.append(
                ValidatorFinding(
                    severity="info",
                    code="MON_NOT_REQUIRED",
                    message="Intent did not require platform-health context.",
                )
            )
            return report

        present = sorted(k for k in _MONITORING_KEYWORDS if k in body)
        if not present:
            report.passed = False
            report.findings.append(
                ValidatorFinding(
                    severity="warning",
                    code="MON_MISSING_METRICS",
                    message=(
                        "Response references monitoring intent but contains no "
                        "platform metrics (health/latency/cost/SLA)."
                    ),
                )
            )
            return report

        report.findings.append(
            ValidatorFinding(
                severity="info",
                code="MON_METRICS_PRESENT",
                message=f"Detected platform-health signals: {', '.join(present)}.",
                detail={"signals": present},
            )
        )
        return report


class DiagnosticValidator:
    """TC-6 — surfaces similar historical incidents for diagnostic context."""

    name = "DiagnosticValidator"

    def __init__(self, corpus: Iterable[dict] | None = None, threshold: int = 2):
        self._corpus = tuple(corpus) if corpus is not None else _HISTORICAL_INCIDENTS
        self._threshold = threshold

    def _score(self, query_tokens: set[str], item: dict) -> tuple[int, list[str]]:
        item_tokens = _tokens(item["summary"]) | set(item.get("tags", ()))
        overlap = sorted(query_tokens & item_tokens)
        return len(overlap), overlap

    def evaluate(self, *, user_text: str, combined_response: str) -> ValidationReport:
        report = ValidationReport(validator=self.name, passed=True)
        haystack = f"{user_text or ''}\n{combined_response or ''}"
        tokens = _tokens(haystack)
        if not tokens:
            report.passed = False
            report.findings.append(
                ValidatorFinding(
                    severity="warning",
                    code="DIAG_EMPTY_INPUT",
                    message="No content available for similarity scoring.",
                )
            )
            return report

        scored = []
        for item in self._corpus:
            score, overlap = self._score(tokens, item)
            if score >= self._threshold:
                scored.append((score, overlap, item))
        scored.sort(key=lambda t: t[0], reverse=True)
        top = scored[:3]
        if not top:
            report.findings.append(
                ValidatorFinding(
                    severity="info",
                    code="DIAG_NO_MATCH",
                    message="No similar historical incidents above threshold.",
                )
            )
            return report

        for score, overlap, item in top:
            report.findings.append(
                ValidatorFinding(
                    severity="info",
                    code="DIAG_MATCH",
                    message=(
                        f"Similar to {item['incident_id']} (score={score}): "
                        f"{item['summary']}"
                    ),
                    detail={
                        "incident_id": item["incident_id"],
                        "score": score,
                        "overlap": overlap,
                    },
                )
            )
        return report


def run_validators(
    *,
    user_text: str,
    combined_response: str,
    validators: Iterable | None = None,
) -> tuple[list[ValidationReport], str]:
    """Run all validators and return (reports, markdown_block)."""
    chain = list(validators) if validators is not None else [
        MonitoringValidator(),
        DiagnosticValidator(),
    ]
    reports = [v.evaluate(user_text=user_text, combined_response=combined_response) for v in chain]
    body = "\n".join(r.to_markdown() for r in reports)
    block = f"## Validation Report\n{body}"
    return reports, block
