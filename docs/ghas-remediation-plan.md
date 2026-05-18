# GHAS Remediation Plan

## Current status (this PR)

- GHAS alert APIs for this repository currently return `403 Resource not accessible by integration`, so full alert metadata could not be pulled directly in this environment.
- Local dependency audits were run to begin remediation immediately.

### Local audit baseline and progress

| Area | Baseline | After this PR | Notes |
|---|---:|---:|---|
| `rag-agent/code/frontend` (`npm audit`) | 11 (1 critical, 6 high, 4 moderate) | 0 | Remediated with non-breaking `npm audit fix` |
| `rag-agent/tests/integration/ui` (`npm audit`) | 13 (1 critical, 7 high, 3 moderate, 2 low) | 0 | Remediated with lockfile-only audit fix |
| `rag-agent/extensions/teams` (`npm audit`) | 3 (2 high, 1 low) | 3 | Remaining issues require `restify` major downgrade/upgrade decision (`npm audit fix --force`) |

## Remediation strategy for all GHAS findings

1. **Export and classify GHAS alerts**
   - Pull all open GHAS alerts (code scanning, dependency, secret, and IaC where applicable).
   - Group by: severity, exploitability, fix availability, and owning path (`rag-agent`, `supervisor-agent`, `bedrock-gateway`).

2. **Prioritized remediation waves**
   - **Wave 1 (Immediate):** Critical + High with non-breaking fixes.
   - **Wave 2 (Planned):** High requiring major version changes (e.g., framework/runtime upgrades).
   - **Wave 3 (Hardening):** Moderate/Low and defense-in-depth findings.

3. **Safe delivery controls**
   - Apply fixes in small batches per component.
   - Run component-local build/tests after each batch.
   - Use staged PRs for major-version dependency changes.

4. **Repository hygiene**
   - Keep lockfiles current via Dependabot.
   - Triage GHAS alerts weekly and enforce SLA targets:
     - Critical: 24h
     - High: 7d
     - Moderate: 30d

## Next implementation batch

1. Resolve remaining `rag-agent/extensions/teams` vulnerabilities via supported `restify` path (major change), with compatibility validation.
2. Run Python-focused vulnerability scan/remediation (`pip`/Poetry stacks) for `rag-agent`, `supervisor-agent`, and `bedrock-gateway`.
3. Triage and remediate GHAS code-scanning findings once API/token permissions are available.
