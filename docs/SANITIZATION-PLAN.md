# UAIP Sanitization & Genericization Plan

> **Goal:** Transform the Worley-specific UAIP codebase into a public-facing, domain-agnostic **Multi-Cloud AI Platform Accelerator** with strong documentation and a clean starting point.

---

## Table of Contents

1. [Naming & Branding](#1-naming--branding)
2. [Repository Consolidation](#2-repository-consolidation)
3. [Domain De-Coupling (Engineering → Generic)](#3-domain-de-coupling)
4. [Copyright & Legal](#4-copyright--legal)
5. [Documentation Overhaul](#5-documentation-overhaul)
6. [Code Changes](#6-code-changes)
7. [Frontend Sanitization](#7-frontend-sanitization)
8. [Infrastructure Sanitization](#8-infrastructure-sanitization)
9. [Sample Data Replacement](#9-sample-data-replacement)
10. [Recommended Final Repository Structure](#10-recommended-final-repository-structure)
11. [File-by-File Change Inventory](#11-file-by-file-change-inventory)

---

## 1. Naming & Branding

### Current State
- **"Worley"** appears 100+ times across all repos (READMEs, code, Terraform, docs, YAML)
- **"UAIP"** (Unified AI Platform) — this name is fine and can stay or be renamed
- GitHub URLs point to `mikefelder/uaip-*` — need a neutral org or placeholder
- `worley-logo.png` bundled in frontend
- "Worley-AI-Sandbox" used in Makefiles and tfvars

### Actions

| Find | Replace With | Scope |
|------|-------------|-------|
| `Worley` (company name) | `{YourOrg}` or remove entirely | All repos |
| `Worley Unified AI Platform` | `Unified AI Platform` or `Multi-Cloud AI Platform Accelerator` | All repos |
| `Worley-AI-Sandbox` | `ai-platform-sandbox` or `{your-subscription}` | Makefiles, tfvars |
| `mikefelder/` (GitHub URLs) | `{your-github-org}/` | All docs |
| `worley-logo.png` | `logo.png` (replace with a generic placeholder) | Frontend |
| `Worley corporate branding` | `Custom branding` | Docs |

### Files Containing "Worley" (non-exhaustive)

| Repository | Files |
|-----------|-------|
| **uc1-rag-agent** | `README.md`, `DEMO-SCRIPT.md`, `services/rag-agent/main.py`, `services/rag-agent/tools/search.py`, `services/rag-agent/tools/document_qa.py`, `scripts/populate_index.py`, `infra/variables.tf`, `infra/terraform.tfvars.msdn` |
| **uc2-supervisor** | `README.md`, `DEPLOYMENT-RUNBOOK.md`, `Makefile`, `services/supervisor-api/main.py`, `services/supervisor-api/tools/*.py` (7 files), `services/supervisor-api/tests/*.py` (3 files), `services/supervisor-api/agents.yaml`, `infra/terraform.tfvars.example` |
| **uc3-governance** | `README.md`, `Makefile`, `docs/uaip_solution_architecture.md`, `infra/main.workbook.tf`, `scripts/tc2.ps1` |
| **uc4-incident** | `infra/terraform.tfvars.example` |
| **bedrock-agent** | `README.md`, `Makefile`, `openapi.yaml` |
| **frontend** | `README.md`, `src/App.tsx`, `mock-server.mjs`, `public/worley-logo.png` |
| **docs/** | `uaip_solution_architecture.md`, `aws_handoff_bedrock_agents_gateway.md`, `gap_analysis_report.md`, `worley_unified_ai_platform_Draft.md`, `uaip_poc_proposal_30_march_2026.md` |

---

## 2. Repository Consolidation

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

| New Repo | Merges | Rationale |
|----------|--------|-----------|
| **`ai-platform-agents`** | UC1 + UC2 | UC2 directly depends on UC1. Same SDK, runtime, infra patterns. Becomes `services/rag-agent/` + `services/supervisor-api/` with shared `infra/`. |
| **`ai-platform-governance`** | UC3 + UC4 (already done) | UC4 is already merged. Keep as-is but rename and drop "UC3" branding. |
| **`ai-platform-frontend`** | Frontend (standalone) | Different tech stack (React/TS). Clean separation. |
| **`azure-ai-landing-zone`** | Landing Zone + ALZ customizations | Merge `alz-customizations/` into the landing zone repo as a module or example. |

### What Happens to Other Repos

| Repo | Action |
|------|--------|
| `uaip-workload-uc4-incident-resolution` | **Archive** — all code lives in UC3 now. Keep as read-only reference or delete. |
| `uaip-bedrock-agent` | **Move into `ai-platform-agents/services/bedrock-gateway/`** or keep separate (different cloud/provider). Both are defensible. |
| `docs/` | **Move into root of `ai-platform-agents/`** or keep as a standalone `ai-platform-docs` repo. |
| `alz-customizations/` | **Merge into `azure-ai-landing-zone/`** as `examples/apim-ai-gateway/`. |

### "Use Case" Concept Refactoring

The "UC1/UC2/UC3/UC4" naming is internal project management jargon. Replace with descriptive, capability-based names:

| Old Name | New Name | Description |
|----------|----------|-------------|
| UC1 — RAG Knowledge Assistant | **RAG Agent** | Document retrieval and cited response generation |
| UC2 — Multi-Agent Supervisor | **Supervisor Agent** | Multi-agent orchestration with fan-out/fan-in |
| UC3 — Governance Hub | **Governance Hub** | Observability, cost tracking, policy, incidents |
| UC4 — Incident Resolution | *(merged into Governance Hub)* | AI-driven incident triage and resolution |

In code, replace all `uc1`, `uc2`, `uc3`, `uc4` identifiers with descriptive names:

| Find (code/config) | Replace |
|--------------------|---------|
| `uc1-rag-agent` | `rag-agent` |
| `uc2-supervisor` | `supervisor-agent` |
| `uc2-bedrock-agent` | `bedrock-gateway` |
| `uc4-incident-agent` | `incident-agent` |
| `ca-uc1-*` | `ca-rag-*` |
| `ca-uc2-*` | `ca-supervisor-*` |
| `ca-uc3-*` | `ca-governance-*` |

---

## 3. Domain De-Coupling

### Current State: Hardcoded to Engineering/EPC Domain

The entire solution is built around a specific industry vertical:
- **Agent instructions**: "You are Worley's Knowledge Assistant... engineering document corpus"
- **Sample documents**: Valve specs, piping standards, safety compliance, ESD instrument data sheets
- **Tool names**: `search_engineering_docs`
- **Index name**: `worley-engineering-docs`
- **Agent names**: "Engineering Agent (Bedrock)", "Engineering Agent (AWS)"
- **Frontend**: "Engineering specs, safety compliance, EPC contracts..."
- **Demo script**: Entirely engineering/EPC focused
- **Mock data**: Valve specifications, ASME standards, LNG facility

### Actions

| Component | Current | Generic Replacement |
|-----------|---------|-------------------|
| Agent instructions | "Worley's Knowledge Assistant...engineering document corpus" | "Knowledge Assistant...your organization's document corpus" |
| Tool name | `search_engineering_docs` | `search_documents` |
| Index name | `worley-engineering-docs` | `knowledge-base-docs` (configurable via env var) |
| Sample documents | EPC valve specs, piping standards, safety reports | **Generic business documents** — e.g., product specs, compliance policies, HR handbook, project proposals, technical architecture docs |
| Agent name | "Engineering Agent (Bedrock)" | "Cross-Cloud Agent (Bedrock)" or "External Agent (AWS)" |
| Frontend prompts | "Ask about engineering specs, safety compliance, EPC projects..." | "Ask about your documents, policies, projects..." |
| Demo script | Engineering/EPC focused | Rewrite with generic domain examples |

### Sample Data Replacement Strategy

Replace the 6 EPC documents in `scripts/populate_index.py` with domain-neutral sample documents:

| Current Document | Replacement |
|-----------------|-------------|
| Valve Specification Matrix | Product Technical Specification |
| Safety Compliance Report | Quarterly Compliance Audit Report |
| Piping Material Specification | Material Standards Reference Guide |
| Master Services Agreement | Service Level Agreement Template |
| Instrument Data Sheet: ESD Valve | Equipment Data Sheet (generic) |
| AI Model Governance Policy | AI Governance & Ethics Policy (keep — this one is already generic) |

---

## 4. Copyright & Legal

### Files with Worley Copyright Headers (13 files)

All Python source files in UC1 and UC2 start with:
```python
# Copyright (c) Worley. All rights reserved.
```

**Action:** Replace with an appropriate open-source license header. For a public accelerator, use MIT:

```python
# Licensed under the MIT License. See LICENSE file in the project root.
```

### License Files

| File | Current | Action |
|------|---------|--------|
| `uc1-rag-agent/LICENSE.md` | Check current license | Ensure MIT or Apache 2.0 |
| `uc1-rag-agent/CDLA-Permissive-2.md` | Community Data License Agreement | Review — may be for sample data only |
| `azure-ai-landing-zone-terraform/LICENSE` | Check current | Ensure consistent |

### Proprietary Documents to Remove or Redact

| File | Action |
|------|--------|
| `docs/uaip_poc_proposal_30_march_2026.md` | **Remove entirely** — contains "Worley Limited", "© Copyright 2023 Worley ACN 096 090 158", proprietary proposal content |
| `docs/worley_unified_ai_platform_Draft.md` | **Remove or heavily redact** — Worley-specific platform strategy doc |

---

## 5. Documentation Overhaul

### Duplicate Document Cleanup

| File | Location | Action |
|------|----------|--------|
| `uaip_solution_architecture.md` | `docs/` (canonical) | **Keep and genericize** |
| `uaip_solution_architecture.md` | `uc1/` root | **Delete** |
| `uaip_solution_architecture.md` | `uc2/` root | **Delete** |
| `uaip_solution_architecture.md` | `uc2/docs/` | **Delete** |
| `uaip_solution_architecture.md` | `uc3/docs/` | **Delete** |

### READMEs to Rewrite

Every README needs to be rewritten to:
1. Remove all Worley/engineering references
2. Position as an accelerator/starter template
3. Add "Getting Started" and "Customization" sections
4. Explain how to bring your own documents/domain

| README | Key Changes |
|--------|------------|
| **uc1/README.md** | Remove "Worley engineering knowledge base", replace EPC examples with generic |
| **uc2/README.md** | Remove "Worley's Unified AI Platform", make agent descriptions generic |
| **uc3/README.md** | Remove "Worley" references, genericize governance descriptions |
| **bedrock/README.md** | Remove "Worley UAIP" |
| **frontend/README.md** | Remove "Worley corporate branding", replace with "customizable branding" |
| **docs/uaip_solution_architecture.md** | Major rewrite — remove all Worley references, make it an architecture guide |

### New Documentation to Add

For a good public accelerator, add:

| Document | Purpose |
|----------|---------|
| **QUICKSTART.md** | 5-minute setup: deploy landing zone → deploy agents → chat |
| **CUSTOMIZATION.md** | How to bring your own documents, change agent instructions, add new agents |
| **ARCHITECTURE.md** | Clean architecture diagram (replace ASCII art with Mermaid) |
| **CONTRIBUTING.md** | Standard open-source contribution guide |
| **CHANGELOG.md** | Version history |

---

## 6. Code Changes

### Python Source Files

| File | Changes |
|------|---------|
| `uc1/services/rag-agent/main.py` | Remove copyright header, replace agent instructions (remove "Worley", "engineering"), rename `search_engineering_docs` → `search_documents` |
| `uc1/services/rag-agent/tools/search.py` | Remove copyright, rename function, change default index name |
| `uc1/services/rag-agent/tools/document_qa.py` | Remove copyright, change default index name |
| `uc1/services/rag-agent/evaluation/judge.py` | Replace engineering-specific test questions with generic ones |
| `uc1/scripts/populate_index.py` | **Full rewrite** — replace all 6 EPC documents with generic sample documents |
| `uc2/services/supervisor-api/main.py` | Remove copyright, remove "Engineering Agent" references, genericize routing keywords |
| `uc2/services/supervisor-api/tools/*.py` | Remove copyrights (7 files), genericize docstrings |
| `uc2/services/supervisor-api/tests/*.py` | Remove copyrights (3 files) |
| `uc2/services/supervisor-api/agents.yaml` | Remove engineering references, genericize agent descriptions |
| `uc1/services/rag-agent/agent.yaml` | Remove engineering references |
| `uc3/services/governance-api/src/.../schema_normalizer.py` | Replace `uc1-*`, `uc2-*`, `uc4-*` service name mappings |
| `uc3/services/mock-telemetry/main.py` | Replace UC-numbered service names |
| `bedrock/services/gateway/src/gateway/*.py` | Remove `uc` span attributes |

### Agent Instructions (Critical)

In `uc1/services/rag-agent/main.py`:
```python
# CURRENT
RAG_AGENT_INSTRUCTIONS = """You are Worley's Knowledge Assistant for the Unified AI Platform (UAIP).
Your role is to help users find accurate, relevant, and well-cited
information from Worley's internal engineering document corpus.
...
1. **Always search first**: Use `search_engineering_docs` before answering any
   question about Worley projects, engineering specs, or compliance.
"""

# REPLACEMENT
RAG_AGENT_INSTRUCTIONS = """You are a Knowledge Assistant for the Unified AI Platform.
Your role is to help users find accurate, relevant, and well-cited
information from the organization's internal document corpus.
...
1. **Always search first**: Use `search_documents` before answering any
   question about projects, specifications, policies, or compliance.
"""
```

### Routing Keywords in Supervisor (uc2/services/supervisor-api/main.py)

```python
# CURRENT
"engineering": [
    "engineering", "extended", "cross-project", "bedrock",
    ...
]

# REPLACEMENT
"external": [
    "cross-cloud", "extended", "cross-project", "bedrock",
    ...
]
```

---

## 7. Frontend Sanitization

| File | Changes |
|------|---------|
| `src/App.tsx` | Remove `worley-logo.png` reference, replace with generic logo; change "Unified AI Platform" subtitle |
| `src/pages/ChatPage.tsx` | Remove "Engineering specs, safety compliance, EPC contracts" text; replace placeholder text; remove `isEngineering` variable and "Engineering Agent (AWS)" label |
| `src/api.ts` | Rename "Engineering Agent (AWS)" → "External Agent (AWS)"; remove engineering-specific regex patterns |
| `mock-server.mjs` | Replace all mock responses — currently contains Worley-specific valve/EPC content |
| `public/worley-logo.png` | **Delete** — replace with a generic placeholder or SVG |
| `README.md` | Remove Worley branding references |

---

## 8. Infrastructure Sanitization

### Terraform Variables

| File | Change |
|------|--------|
| `uc1/infra/variables.tf` | Change default `search_index_name` from `worley-engineering-docs` to `knowledge-base-docs` |
| `uc1/infra/terraform.tfvars.msdn` | Change `search_index_name = "worley-engineering-docs"` |
| `uc2/infra/terraform.tfvars.example` | Remove "Worley-AI-Sandbox deployment values" comment |
| `uc3/infra/main.workbook.tf` | Remove "Worley UAIP" from workbook title |
| `uc4/infra/terraform.tfvars.example` | Remove "Worley-AI-Sandbox" (if keeping repo at all) |

### OpenAPI Spec

| File | Change |
|------|--------|
| `bedrock/openapi.yaml` | Change title from "Worley AWS Agent Gateway" to "AWS Agent Gateway" |

### Makefiles

| File | Change |
|------|--------|
| `uc2/Makefile` | Remove "Worley-AI-Sandbox" comment |
| `uc3/Makefile` | Remove "Worley-AI-Sandbox" comment |
| `bedrock/Makefile` | Remove "Worley UAIP" from echo and comment |

---

## 9. Sample Data Replacement

The file `uc1/scripts/populate_index.py` contains ~300 lines of EPC/engineering sample documents. Replace with **domain-neutral** sample documents that demonstrate the same RAG capabilities:

### Proposed Generic Sample Documents

1. **Product Technical Specification** — demonstrates cited technical content retrieval
2. **Quarterly Compliance Audit Report** — demonstrates compliance/safety query handling
3. **Material Standards Reference Guide** — demonstrates standards-based Q&A
4. **Service Level Agreement** — demonstrates contract/legal document retrieval
5. **Equipment Maintenance Data Sheet** — demonstrates structured data retrieval
6. **AI Governance & Ethics Policy** — keep existing (already mostly generic)

These should be industry-neutral: cloud infrastructure specs, SaaS product docs, generic compliance, etc.

---

## 10. Recommended Final Repository Structure

```
ai-platform-accelerator/                    ← Monorepo (or keep separate repos)
├── README.md                               ← Accelerator overview + quickstart
├── ARCHITECTURE.md                         ← Clean architecture guide with Mermaid diagrams
├── CUSTOMIZATION.md                        ← "Bring your own domain" guide
├── QUICKSTART.md                           ← 5-minute deploy guide
├── LICENSE                                 ← MIT
│
├── services/
│   ├── rag-agent/                          ← (was UC1)
│   │   ├── main.py
│   │   ├── tools/
│   │   ├── evaluation/
│   │   ├── Dockerfile
│   │   └── README.md
│   │
│   ├── supervisor-agent/                   ← (was UC2)
│   │   ├── main.py
│   │   ├── tools/
│   │   ├── agents.yaml
│   │   ├── Dockerfile
│   │   └── README.md
│   │
│   ├── governance-hub/                     ← (was UC3+UC4)
│   │   ├── governance-api/
│   │   ├── mock-telemetry/
│   │   ├── otel-collector/
│   │   └── README.md
│   │
│   └── bedrock-gateway/                    ← (was uaip-bedrock-agent)
│       ├── gateway/
│       ├── openapi.yaml
│       └── README.md
│
├── frontend/                               ← (was uaip-frontend)
│   ├── src/
│   ├── public/
│   └── README.md
│
├── infra/
│   ├── landing-zone/                       ← (was azure-ai-landing-zone-terraform)
│   ├── workloads/
│   │   ├── rag-agent/
│   │   ├── supervisor-agent/
│   │   ├── governance-hub/
│   │   ├── frontend/
│   │   └── _shared/                        ← Shared Terraform module
│   │       ├── data.tf
│   │       └── modules/workload/
│   └── aws/
│       └── bedrock-gateway/
│
├── scripts/
│   ├── populate_index.py                   ← Generic sample documents
│   └── deploy.sh
│
└── docs/
    ├── architecture.md
    ├── deployment-runbook.md
    └── telemetry-walkthrough.md
```

---

## 11. File-by-File Change Inventory

### Priority 1 — Must Change (Worley-specific, blocks public release)

| # | File | Action |
|---|------|--------|
| 1 | `uc1/services/rag-agent/main.py` | Remove copyright, genericize agent instructions |
| 2 | `uc1/services/rag-agent/tools/search.py` | Remove copyright, rename function |
| 3 | `uc1/services/rag-agent/tools/document_qa.py` | Remove copyright, change index default |
| 4 | `uc1/scripts/populate_index.py` | Full rewrite — replace EPC docs with generic samples |
| 5 | `uc1/infra/variables.tf` | Change default index name |
| 6 | `uc1/infra/terraform.tfvars.msdn` | Change index name |
| 7 | `uc1/README.md` | Full rewrite |
| 8 | `uc1/DEMO-SCRIPT.md` | Full rewrite |
| 9 | `uc2/services/supervisor-api/main.py` | Remove copyright, genericize |
| 10 | `uc2/services/supervisor-api/tools/*.py` (7 files) | Remove copyrights, genericize |
| 11 | `uc2/services/supervisor-api/tests/*.py` (3 files) | Remove copyrights |
| 12 | `uc2/services/supervisor-api/agents.yaml` | Genericize |
| 13 | `uc2/README.md` | Full rewrite |
| 14 | `uc2/DEPLOYMENT-RUNBOOK.md` | Replace worley-engineering-docs references |
| 15 | `uc2/Makefile` | Remove Worley-AI-Sandbox comment |
| 16 | `uc2/infra/terraform.tfvars.example` | Remove Worley-AI-Sandbox |
| 17 | `uc3/README.md` | Remove Worley references |
| 18 | `uc3/Makefile` | Remove Worley-AI-Sandbox comment |
| 19 | `uc3/infra/main.workbook.tf` | Remove "Worley UAIP" |
| 20 | `frontend/src/App.tsx` | Remove Worley logo/branding |
| 21 | `frontend/src/pages/ChatPage.tsx` | Genericize UI text |
| 22 | `frontend/src/api.ts` | Rename Engineering Agent references |
| 23 | `frontend/mock-server.mjs` | Replace Worley-specific mock data |
| 24 | `frontend/public/worley-logo.png` | Delete |
| 25 | `frontend/README.md` | Remove branding references |
| 26 | `bedrock/README.md` | Remove Worley references |
| 27 | `bedrock/openapi.yaml` | Change title |
| 28 | `bedrock/Makefile` | Remove Worley references |

### Priority 2 — Should Change (documentation, polish)

| # | File | Action |
|---|------|--------|
| 29 | `docs/uaip_solution_architecture.md` | Major genericization |
| 30 | `docs/aws_handoff_bedrock_agents_gateway.md` | Remove all Worley references |
| 31 | `docs/gap_analysis_report.md` | Remove Worley references or delete (PoC artifact) |
| 32 | `docs/TELEMETRY-WALKTHROUGH.md` | Review for Worley references |
| 33 | `docs/DEMO-SCRIPT.md` | Review/rewrite for generic domain |
| 34 | `uc3/docs/uaip_solution_architecture.md` | **Delete** (stale duplicate) |
| 35 | `uc2/uaip_solution_architecture.md` | **Delete** (stale duplicate) |
| 36 | `uc2/docs/uaip_solution_architecture.md` | **Delete** (stale duplicate) |
| 37 | `uc1/uaip_solution_architecture.md` | **Delete** (stale duplicate) |

### Priority 3 — Should Delete (dead/proprietary)

| # | File | Action |
|---|------|--------|
| 38 | `docs/uaip_poc_proposal_30_march_2026.md` | **Delete** — proprietary Worley proposal |
| 39 | `docs/worley_unified_ai_platform_Draft.md` | **Delete** — proprietary Worley strategy |
| 40 | Entire `uaip-workload-uc4-incident-resolution/` repo | **Archive** — deprecated, code lives in UC3 |
| 41 | `uc3/scripts/tc2.ps1` | Remove "Worley jumpbox" reference |

### Priority 4 — Consolidation (separate effort)

| # | Action |
|---|--------|
| 42 | Extract shared Terraform module from duplicated `data.tf` / Container App / APIM / identity patterns |
| 43 | Merge UC1 + UC2 into single agents repo |
| 44 | Merge `alz-customizations/` into landing zone repo |
| 45 | Clean up UC2's 14 stale `tfplan*` files |

---

## Execution Approach

### Phase 1: Sanitize in Place (keep current repo structure)
1. Find-and-replace all Worley references
2. Replace copyright headers
3. Genericize agent instructions and sample data
4. Delete proprietary documents
5. Delete stale duplicate docs
6. Update all READMEs

### Phase 2: Consolidate Repositories
1. Merge UC1 + UC2 into `ai-platform-agents`
2. Rename UC3 to `ai-platform-governance`
3. Archive UC4
4. Rename frontend
5. Merge ALZ customizations

### Phase 3: Polish for Public Release
1. Write QUICKSTART.md, CUSTOMIZATION.md, ARCHITECTURE.md
2. Add GitHub Actions CI
3. Add proper LICENSE files
4. Create GitHub release tags
5. Write blog post / announcement

---

## String Replacement Summary

Quick reference for global find-and-replace operations:

```
"Worley's Knowledge Assistant"     → "Knowledge Assistant"
"Worley Unified AI Platform"       → "Unified AI Platform"  
"Worley's engineering"             → "the organization's"
"Worley's internal"                → "your organization's"
"Copyright (c) Worley"             → "Licensed under the MIT License"
"Worley-AI-Sandbox"                → "{your-subscription}"
"worley-engineering-docs"          → "knowledge-base-docs"
"search_engineering_docs"          → "search_documents"
"Engineering Agent (Bedrock)"      → "External Agent (AWS)"
"Engineering Agent (AWS)"          → "External Agent (AWS)"
"engineering document corpus"      → "document corpus"
"engineering knowledge base"       → "knowledge base"
"engineering specs"                → "technical documents"
"EPC"                              → (remove or replace with generic industry term)
"Project Alpha"                    → "Sample Project"
"Worley Standard"                  → "Organization Standard"
"mikefelder/"                      → "{your-github-org}/"
```
