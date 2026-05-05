# UAIP Genericization & Consolidation — Status Tracker

> **Last updated:** May 5, 2026
> **Goal:** Transform the Worley-specific UAIP codebase into a public-facing, domain-agnostic Multi-Cloud AI Platform Accelerator.
> **Branch:** `sanitize/genericize-for-public` (all repos — committed & pushed)

---

## Phase 1 — Sanitization in Place (DONE ✅, committed & pushed)

All changes exist on `sanitize/genericize-for-public` branches, committed and pushed to origin.

### UC1 — `uaip-workload-uc1-rag-agent` (12 files changed)

| File | Change | Status |
|------|--------|--------|
| `services/rag-agent/main.py` | Removed copyright header, genericized agent instructions, renamed `search_engineering_docs` → `search_documents` | ✅ |
| `services/rag-agent/tools/search.py` | Removed copyright, renamed function, changed default index `worley-engineering-docs` → `knowledge-base-docs` | ✅ |
| `services/rag-agent/tools/document_qa.py` | Removed copyright, changed default index name | ✅ |
| `services/rag-agent/tools/__init__.py` | Removed "UC1" from module comment | ✅ |
| `services/rag-agent/agent.yaml` | Renamed from `uaip-uc1-rag-knowledge-agent` → `rag-knowledge-agent`, removed "Worley" | ✅ |
| `services/rag-agent/evaluation/judge.py` | Replaced engineering-specific test questions with generic ones | ✅ |
| `scripts/populate_index.py` | **Full rewrite** — 6 EPC/engineering docs → 6 domain-neutral samples (product specs, compliance audits, SLAs, data sheets, governance policy) | ✅ |
| `infra/variables.tf` | Changed default `search_index_name` to `knowledge-base-docs` | ✅ |
| `infra/terraform.tfvars.msdn` | Changed index name | ✅ |
| `README.md` | Full rewrite — removed all Worley/engineering references | ✅ |
| `DEMO-SCRIPT.md` | Replaced 3 Worley references with generic wording | ✅ |
| `uaip_solution_architecture.md` | **Deleted** (stale duplicate of `docs/` canonical copy) | ✅ |

### UC2 — `uaip-workload-uc2-supervisor-agent` (19 files changed)

| File | Change | Status |
|------|--------|--------|
| `services/supervisor-api/main.py` | Removed copyright, removed "Engineering Agent (Bedrock)" → "External Agent (Cross-Cloud)", removed `uc` OTEL span attr, genericized routing keywords | ✅ |
| `services/supervisor-api/agents.yaml` | Genericized all 6 agent definitions — removed Worley references, renamed Engineering → External | ✅ |
| `services/supervisor-api/agent.yaml` | Renamed to `supervisor-agent`, removed "Worley UAIP UC2" | ✅ |
| `services/supervisor-api/tools/knowledge.py` | Removed copyright, genericized docstrings, removed `uc` span attr | ✅ |
| `services/supervisor-api/tools/compliance.py` | Removed copyright, genericized system prompt | ✅ |
| `services/supervisor-api/tools/bedrock.py` | Removed copyright | ✅ |
| `services/supervisor-api/tools/governance.py` | Removed copyright, removed "UC3" from docstring | ✅ |
| `services/supervisor-api/tools/sla.py` | Removed copyright | ✅ |
| `services/supervisor-api/tools/escalation.py` | Removed copyright, removed "UC3" from docstring | ✅ |
| `services/supervisor-api/tools/validators.py` | Genericized incident history descriptions | ✅ |
| `services/supervisor-api/tests/test_tc5_escalation_publish.py` | Removed copyright | ✅ |
| `services/supervisor-api/tests/test_tc5_sla_enforcement.py` | Removed copyright | ✅ |
| `services/supervisor-api/tests/test_tc3_gateway_enforcement.py` | Removed copyright | ✅ |
| `DEPLOYMENT-RUNBOOK.md` | Replaced `worley-engineering-docs` → `knowledge-base-docs`, `Worley-AI-Sandbox` → `ai-platform-sandbox` | ✅ |
| `Makefile` | Removed "Worley-AI-Sandbox" comment | ✅ |
| `infra/terraform.tfvars.example` | Removed "Worley-AI-Sandbox" comment | ✅ |
| `README.md` | Major rewrite — removed Worley/UC/engineering references | ✅ |
| `uaip_solution_architecture.md` | **Deleted** (stale duplicate) | ✅ |
| `docs/uaip_solution_architecture.md` | **Deleted** (stale duplicate) | ✅ |

### UC3 — `uaip-workload-uc3-governance-hub` (10 files changed)

| File | Change | Status |
|------|--------|--------|
| `README.md` | Removed Worley/UC references, genericized incident resolution section | ✅ |
| `Makefile` | Removed "Worley-AI-Sandbox" comment | ✅ |
| `infra/main.workbook.tf` | Changed workbook title from "Worley UAIP" to generic | ✅ |
| `scripts/tc2.ps1` | Removed "Worley jumpbox" reference | ✅ |
| `services/governance-api/src/governance_api/__init__.py` | Removed "Worley UAIP UC3" | ✅ |
| `services/governance-api/src/governance_api/main.py` | Removed "Worley UAIP UC3" from FastAPI title | ✅ |
| `services/governance-api/src/governance_api/services/orchestration_service.py` | Removed "Worley" from triage prompt | ✅ |
| `services/governance-api/src/governance_api/services/schema_normalizer.py` | Replaced UC-numbered service names with descriptive names | ✅ |
| `services/mock-telemetry/main.py` | Replaced UC-numbered agent names | ✅ |
| `docs/uaip_solution_architecture.md` | **Deleted** (stale duplicate) | ✅ |

### Frontend — `uaip-frontend` (6 files changed)

| File | Change | Status |
|------|--------|--------|
| `src/App.tsx` | Removed `worley-logo.png` reference | ✅ |
| `src/pages/ChatPage.tsx` | Genericized UI text, renamed "Engineering Agent" → "External Agent" | ✅ |
| `src/api.ts` | Renamed agent detection from "Engineering" → "External" | ✅ |
| `mock-server.mjs` | Rewrote mock responses with domain-neutral content | ✅ |
| `README.md` | Removed Worley branding references | ✅ |
| `public/worley-logo.png` | **Deleted** | ✅ |

### Bedrock — `uaip-bedrock-agent` (8 files changed)

| File | Change | Status |
|------|--------|--------|
| `README.md` | Removed "Worley UAIP" | ✅ |
| `openapi.yaml` | Changed title from "Worley AWS Agent Gateway" | ✅ |
| `Makefile` | Removed "Worley UAIP" references | ✅ |
| `infra/api_gateway.tf` | Genericized description | ✅ |
| `services/gateway/src/gateway/__init__.py` | Removed "Worley UAIP" | ✅ |
| `services/gateway/src/gateway/executor_handler.py` | Removed `uc` span attr, genericized system prompt | ✅ |
| `services/gateway/src/gateway/invoke_handler.py` | Removed `uc` span attr | ✅ |
| `services/gateway/src/gateway/status_handler.py` | Removed `uc` span attr | ✅ |
| `services/gateway/build/lambda-package/gateway/__init__.py` | Removed "Worley UAIP" | ✅ |
| `services/gateway/build/lambda-package/gateway/executor_handler.py` | Genericized system prompt | ✅ |

### UC4 — `uaip-workload-uc4-incident-resolution` (1 file)

| File | Change | Status |
|------|--------|--------|
| `infra/terraform.tfvars.example` | Removed "Worley-AI-Sandbox" | ✅ |

### Shared Docs — `docs/`

| File | Change | Status |
|------|--------|--------|
| `uaip_poc_proposal_30_march_2026.md` | **Deleted** — proprietary Worley proposal | ✅ |
| `worley_unified_ai_platform_Draft.md` | **Deleted** — proprietary Worley strategy doc | ✅ |
| `SANITIZATION-PLAN.md` | **Created** — full sanitization roadmap | ✅ |

---

## Phase 2 — Remaining Work

### 2A. Remaining File Sanitization (DONE ✅)

All P1/P2/P3 items completed:
- `docs/uaip_solution_architecture.md` — all Worley/mikefelder/engineering references replaced ✅
- `docs/aws_handoff_bedrock_agents_gateway.md` — all Worley references replaced ✅
- `docs/gap_analysis_report.md` — all Worley references replaced ✅
- `docs/test-case-findings.md`, `test-case-action-plan.md`, `DEMO-SCRIPT.md`, `TELEMETRY-WALKTHROUGH.md` — cleaned ✅
- UC3/UC4 test files — `@worley.com` → `@example.com` ✅
- UC1 `DEMO-SCRIPT.md` — engineering-specific prompts genericized ✅
- UC2 `README.md` — remaining UC/Engineering references cleaned ✅
- `mikefelder/` GitHub URLs → `{your-org}/` placeholders ✅

### 2B. Commit & Push Phase 1+2A Changes (DONE ✅)

| Repo | Commit | Pushed |
|------|--------|--------|
| UC1 `uaip-workload-uc1-rag-agent` | `21cc48d` | ✅ |
| UC2 `uaip-workload-uc2-supervisor-agent` | `e5f1044` | ✅ |
| UC3 `uaip-workload-uc3-governance-hub` | `1c487bd` | ✅ |
| UC4 `uaip-workload-uc4-incident-resolution` | `e25e8e0` | ✅ |
| Bedrock `uaip-bedrock-agent` | `378842d` | ✅ |
| Frontend `uaip-frontend` | `cfa4cea` | ✅ |

### 2C. Cleanup (PARTIALLY DONE)

| # | Action | Status |
|---|--------|--------|
| 1 | Clean up UC2 stale `tfplan*` files + add to `.gitignore` | ✅ Done |
| 2 | **Archive UC4 repo** | ❌ Not done (requires GitHub settings) |
| 3 | **Merge UC1 + UC2** into single agents repo | ❌ Not done |
| 4 | **Merge `alz-customizations/`** into landing zone repo | ❌ Not done |
| 5 | **Extract shared Terraform module** | ❌ Not done |

### 2D. New Documentation for Public Accelerator (NOT DONE)

| # | Document | Purpose | Status |
|---|----------|---------|--------|
| 1 | `QUICKSTART.md` | 5-minute setup: deploy landing zone → deploy agents → chat | ❌ |
| 2 | `CUSTOMIZATION.md` | How to bring your own documents, change agent instructions, add new agents | ❌ |
| 3 | `ARCHITECTURE.md` | Clean architecture diagram (Mermaid) replacing the ASCII art | ❌ |
| 4 | Root `README.md` | Accelerator overview linking to all components | ❌ |
| 5 | Consistent `LICENSE` files | MIT license across all repos | ❌ |

### 2E. Important Note: `docs/` Directory

The `docs/` directory is NOT a git repo — it's a standalone local folder. The sanitized files there
(`uaip_solution_architecture.md`, `aws_handoff_bedrock_agents_gateway.md`, `gap_analysis_report.md`,
`test-case-findings.md`, `test-case-action-plan.md`, `DEMO-SCRIPT.md`, `TELEMETRY-WALKTHROUGH.md`,
`SANITIZATION-PLAN.md`, `CONSOLIDATION-STATUS.md`) need to be moved into one of the repos
(likely the root of the consolidated agents repo or a dedicated docs repo) as part of repo consolidation.

---

## Repository Map (Current → Proposed)

### Current: 9 Repositories
```
uaip-workload-uc1-rag-agent        ← RAG Knowledge Agent
uaip-workload-uc2-supervisor-agent ← Multi-Agent Supervisor  
uaip-workload-uc3-governance-hub   ← Governance & Observability
uaip-workload-uc4-incident-resolution ← DEPRECATED (merged into UC3)
uaip-bedrock-agent                 ← AWS Bedrock Gateway
uaip-frontend                      ← React Chat UI
azure-ai-landing-zone-terraform    ← Azure AI Landing Zone
alz-customizations                 ← ALZ APIM customizations
docs/                              ← Shared documentation
```

### Proposed: 4 Repositories
```
ai-platform-agents/                ← UC1 + UC2 merged (+ optionally Bedrock)
  services/rag-agent/
  services/supervisor-api/
  services/bedrock-gateway/        (or keep separate repo)
  infra/

ai-platform-governance/            ← UC3 renamed (UC4 already merged)
  services/governance-api/
  infra/

ai-platform-frontend/              ← Frontend renamed
  src/
  infra/

azure-ai-landing-zone/             ← Landing Zone + ALZ customizations merged
  modules/
  examples/apim-ai-gateway/
```

---

## Global Find-Replace Reference

For any remaining manual cleanup:

```
"Worley's Knowledge Assistant"     → "Knowledge Assistant"
"Worley Unified AI Platform"       → "Unified AI Platform"
"Worley's engineering"             → "the organization's"
"Worley's internal"                → "your organization's"
"Copyright (c) Worley"             → "Licensed under the MIT License"
"Worley-AI-Sandbox"                → "{your-subscription}"
"worley-engineering-docs"          → "knowledge-base-docs"
"search_engineering_docs"          → "search_documents"
"Engineering Agent (Bedrock)"      → "External Agent (Cross-Cloud)"
"Engineering Agent (AWS)"          → "External Agent (AWS)"
"engineering document corpus"      → "document corpus"
"engineering knowledge base"       → "knowledge base"
"engineering specs"                → "technical documents"
"EPC"                              → (remove or replace with generic industry term)
"Project Alpha"                    → "Sample Project"
"Worley Standard"                  → "Organization Standard"
"mikefelder/"                      → "{your-github-org}/"
"@worley.com"                      → "@example.com"
"UC1"                              → "RAG Agent" (or remove prefix)
"UC2"                              → "Supervisor Agent"
"UC3"                              → "Governance Hub"
"UC4"                              → "(merged into Governance Hub)"
"uc1-rag-agent"                    → "rag-agent"
"uc2-supervisor"                   → "supervisor-agent"
"uc2-bedrock-agent"                → "bedrock-gateway"
"uc4-incident-agent"               → "incident-agent"
"uc3-governance-api"               → "governance-api"
```

---

## How To Resume

1. Open VS Code with the same workspace
2. All repos should be on `sanitize/genericize-for-public` branches with uncommitted changes
3. Start with **2A** (remaining file sanitization) — the P1 items
4. Then **2B** (commit & push)
5. Then **2C** (consolidation) — this is the big structural work
6. Finally **2D** (new docs)
