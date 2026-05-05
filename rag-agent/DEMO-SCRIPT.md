# UAIP PoC Demo Script

> **Date:** Monday 28 April 2026 — 9:00 PM AEST
> **Duration:** ~45 minutes (core) + extras if time permits
> **Audience:** Stakeholders

---

## Pre-Demo Setup (5 min before)

Open these tabs in order:

1. **Frontend Chat** — `https://ca-uaip-frontend.ambitiouscliff-ec38b96b.australiaeast.azurecontainerapps.io`
2. **Frontend Agent Flow** — same URL, switch to "Agent Flow" tab
3. **Grafana Dashboard** — `https://uaip-grafana-h8begbeph0fgdqhp.eau.grafana.azure.com/d/uaip-agent-finops-v3` (set time range to "Last 1 hour")
4. **Azure Portal — App Insights** — navigate to `ai-uc2-supervisor-appinsights` → Application Map
5. **Azure Portal — App Insights** — Transaction Search (for E2E trace view)
6. **Solution Architecture** — open `uaip_solution_architecture.md` in VS Code or browser
7. **GitHub** — `https://github.com/mikefelder/uaip-workload-uc2-supervisor-agent` (show repo structure)

**Warm-up (send these 5 min before):**
```
What are the product specifications for Sample Project?
```
```
What are the compliance requirements for our product specifications?
```
```
What is the current platform health status?
```

This pre-populates Grafana panels so they're not empty when you show them.

---

## CORE DEMO (~45 min)

---

### Part 1 — Platform Overview (5 min)

**[Show: Solution Architecture diagram]**

> "Welcome everyone. Tonight I'm going to walk you through the Unified AI Platform proof-of-concept we've built over the past week. This is a multi-cloud, multi-agent AI platform on Azure that demonstrates how organizations can centralize AI governance, orchestrate agents across cloud boundaries, and maintain full observability."

**Pause on the architecture diagram:**

> "Let me orient you to the architecture. At the top, we have API Management acting as our AI Gateway — every request goes through here for rate limiting, content safety, and tracing. Below that, Azure Container Apps hosts four services: the RAG Knowledge Agent, the Multi-Agent Supervisor, the Governance Hub, and the Frontend."

> "On the right, we have our supporting services — Azure OpenAI with three different model deployments, AI Search with our document index, Cosmos DB for incident state, Log Analytics feeding into Microsoft Sentinel for SIEM, and Grafana for dashboards."

> "At the bottom — and this is key — we have the AWS integration. An API Gateway and Lambda functions running on Amazon Bedrock with Claude Sonnet 4. The cross-cloud auth uses OIDC federation between Entra ID and AWS IAM — zero shared credentials."

**Key numbers to mention:**
- 7 GitHub repositories
- 64 tracked requirements, 61 implemented — 95% completion
- 4 use cases, all deployed and running
- 4 LLM models across 2 cloud providers
- Built on Microsoft Agent Framework SDK — Microsoft's latest agent platform
- 100% Terraform infrastructure-as-code

---

### Part 2 — UC1: RAG Knowledge Assistant (7 min)

**[Switch to: Frontend Chat tab — click "+ New Chat"]**

> "Let's start with Use Case 1 — a RAG knowledge assistant that searches the organization's internal document corpus. We've indexed six representative documents covering specifications, compliance reports, standards, data sheets, and contracts."

**Type this prompt:**
```
What are the product specifications for Sample Project?
```

**[Wait for response — ~10-15 seconds]**

> "A few things to notice here. First — the Knowledge Agent chip appeared, showing that the supervisor recognized this as a document retrieval question and routed it to the right agent."

> "In the response, notice the citations — SP-MECH-VAL-001 Rev 3, references to ASME B16.34 and API 6D. The agent isn't making this up — it's retrieving actual document content from our AI Search index and citing specific standards and revision numbers."

> "Behind the scenes, this is using gpt-4.1-mini — the fast, cost-efficient model — with the Microsoft Agent Framework SDK's tool-calling pattern. The search tool hits Azure AI Search, the results come back as context, and the LLM generates a cited response."

**Follow-up prompt:**
```
Tell me more about the instrument data sheet for ESD Valve XV-3042
```

> "This uses a follow-up QA tool that filters AI Search to the specific document. This is important for engineers who need to drill into a particular data sheet or spec — the agent maintains context from the previous search."

**Point out:**
- Specific instrument data (set points, response times, SIL ratings)
- Document reference DS-INS-XV3042 Rev 2
- Practical engineering detail, not generic text

---

### Part 3 — UC2: Multi-Agent Supervisor (10 min)

**[Click "+ New Chat" to start fresh]**

> "Now let me show you the multi-agent orchestration. Use Case 2 is a supervisor that coordinates four specialized agents concurrently — each with a different model and purpose. This is where the platform really shows its value."

**Type this prompt:**
```
What are the product specifications for Sample Project, are they compliant with ASME standards, and what does the cross-cloud knowledge database show from similar projects?
```

**[Wait for response — ~30-60 seconds]**

> "Watch the chips as they appear — Knowledge Agent, Compliance Agent, and External Agent (AWS). The supervisor is running all three concurrently."

**While waiting, explain the flow:**

> "Here's what's happening right now:
>
> Step 1 — The Supervisor agent reads the query. It's running gpt-4.1, the most capable model, because its job is planning — deciding which specialists to consult.
>
> Step 2 — It generates a routing plan. Our selection function parses that plan and identifies three agents to invoke: Knowledge, Compliance, and Engineering.
>
> Step 3 — All three execute concurrently. Knowledge is searching our document corpus using gpt-4.1-mini. Compliance is analyzing regulatory standards using o4-mini — that's a reasoning model that actually thinks through the problem step by step. And Engineering is calling across to AWS Bedrock running Claude Sonnet 4 for cross-project data.
>
> Step 4 — The responses fan back in through our custom aggregator, and a Synthesizer agent merges everything into a single coherent response."

**When response arrives:**

> "Look at the structure — you can see sections from each agent. Knowledge found the product spec document. Compliance identified specific ASME B16.34 and API 6D requirements. And Engineering brought in data from AWS Bedrock — that's a completely different cloud provider and LLM model."

> "That single query hit three different LLM models across two cloud providers in a concurrent orchestrated workflow. The total time was around [X] seconds — if these ran sequentially it would be three to four times longer."

**[Switch to: Agent Flow tab]**

> "This is the visual orchestration view. You can see the DAG — Supervisor fans out to the selected agents, they execute, aggregate, and the Synthesizer merges. Notice the cloud badges — Azure blue for Knowledge and Compliance, AWS orange for Engineering, and purple for Governance."

**Click on the Engineering node to show the AWS response payload.**

> "You can click any node to inspect its output. The Engineering node shows the Bedrock response including execution ID, duration, and token counts from AWS."

---

### Part 4 — Cross-Cloud Deep Dive (5 min)

**[Click "+ New Chat"]**

> "Let me highlight the cross-cloud capability specifically. This is the piece that proves multi-cloud interoperability."

**Type this prompt:**
```
What does the extended knowledge database show about historical lessons learned for corrosion-resistant materials?
```

**[Wait for response]**

> "This query routed exclusively to the External Agent, which calls across to AWS. Let me explain the security model:"

> "The Azure supervisor acquires a JWT token from Entra ID. It sends that token in the HTTP request to the AWS API Gateway. AWS has a Lambda authorizer that validates the token against Entra's OIDC discovery endpoint. There are no shared credentials — no API keys, no static tokens stored anywhere."

> "The AWS side runs a Lambda function that invokes Amazon Bedrock with Claude Sonnet 4. The contract follows an MCP-shaped async pattern — invoke, get a 202, poll for completion. This is resilient to variable cross-cloud latency."

> "Critically — and I'll show this in the Grafana dashboard — both the Azure side and the AWS side emit OpenTelemetry spans into the same Azure App Insights instance. The W3C traceparent propagates from Azure through the HTTP request to AWS, so you get end-to-end trace correlation across cloud boundaries."

---

### Part 5 — Observability & FinOps (8 min)

**[Switch to: Grafana Dashboard tab — ensure "Last 1 hour" time range]**

> "This is our real-time observability dashboard. Everything you've seen me demonstrate has been generating telemetry that flows here. This is Azure Managed Grafana pulling from Azure Monitor."

**Walk through each panel row by row:**

**Row 1 — Agent Performance:**
1. **Agent Invocations** — "Every agent call is counted. You can see Knowledge, Compliance, Engineering, Governance — the queries we just ran are all here."
2. **Token Usage by Model** — "This is the FinOps view. Token consumption broken down by model — gpt-4.1 for orchestration and synthesis, gpt-4.1-mini for retrieval, o4-mini for compliance reasoning. The Claude Sonnet 4 bar is the AWS Bedrock usage."
3. **LLM Latency** — "Response times per agent. Notice o4-mini is typically slower — it's a reasoning model that thinks before responding. The Bedrock calls include network latency to ap-southeast-2."

**Row 2 — Operations:**
4. **Token Usage Over Time** — "15-minute bins showing how token consumption changes. This is important for capacity planning and cost forecasting."
5. **Tool Executions** — "Every tool call is tracked — search_knowledge, analyze_compliance, invoke_bedrock_agent. This tells you what the agents are actually doing."
6. **Workflow Execution** — "End-to-end workflow durations."

**Row 3 — Cross-Cloud:**
7. **Bedrock Calls** — "Cross-cloud call volume to AWS."
8. **All External Dependencies** — "Every HTTP call the platform makes — Azure OpenAI, AI Search, AWS API Gateway, UC3 governance. You can see success rates and latency."

> "All of this is built on OpenTelemetry. The Agent Framework SDK emits spans automatically for LLM calls, and we added custom attributes — agent type, tool name, use case identifier — so you can filter and group by any dimension."

**[Switch to: Azure Portal — App Insights Application Map]**

> "In Application Insights, the application map shows the topology. The supervisor calling out to UC1 RAG, Azure OpenAI, and the AWS Bedrock gateway. Each connection shows request volume and average latency."

**[Switch to: App Insights Transaction Search — pick a recent operation]**

> "If I drill into a specific request, you can see the end-to-end trace — the supervisor, the agent calls, the tool executions, the LLM completions, all nested with timing. This is the same trace that spans both Azure and AWS."

---

### Part 6 — Governance, Incidents & SIEM (5 min)

**[Switch to: Frontend Chat — New Chat]**

> "Use Case 3 is our governance hub — the horizontal platform layer. Let me show the Governance Agent."

**Type this prompt:**
```
What is the current platform health status and cost summary?
```

**[Wait for response]**

> "The Governance Agent just queried our platform health and cost APIs. In a production deployment, this pulls real-time data from Log Analytics — token consumption, agent error rates, cross-cloud metrics."

> "But governance goes beyond dashboards. We have Microsoft Sentinel with five analytics rules monitoring for:"
> - "Anomalous token consumption — spikes greater than 3× the rolling average"
> - "High agent failure rates — any agent above 20% failure rate"
> - "Content safety violations — blocked prompt injection attempts"
> - "Rate limit breaches — excessive 429 errors"
> - "Cross-cloud latency degradation — P95 on Bedrock calls above 5 seconds"

> "On the incident resolution side — this is UC4, integrated into UC3 — we have a full workflow engine. When an incident comes in, the system runs a triage cascade:"
> - "First, it tries to route through the UC2 supervisor for multi-agent analysis"
> - "Then, AI triage with knowledge from UC1 injected into the prompt"
> - "Finally, rule-based fallback if AI is unavailable"

> "We also implemented a multi-agent voting engine with three strategies — weighted majority, unanimous, and quorum. P1 and P2 incidents always require human approval. P3/P4 with greater than 95% confidence can auto-approve."

---

### Part 7 — Security & Content Safety (3 min)

> "Every request passes through API Management as our AI Gateway. Let me talk about the security controls."

> "Content safety: We have 11 prompt injection and jailbreak patterns blocked at the APIM layer. Patterns like 'ignore previous instructions', 'developer mode', 'do anything now', and 'bypass safety' are detected and returned as 400 errors before they ever reach an agent."

> "Identity: All Azure services use user-assigned managed identity. The cross-cloud auth uses OIDC federation. Container apps run on an internal VNet with no public IPs. ACR has a default-deny firewall. Every role assignment follows least privilege — OpenAI User, Search Reader, AcrPull, nothing more."

> "Audit trail: All APIM gateway logs flow to Log Analytics, which feeds Sentinel. Every agent interaction is traceable from the HTTP request through to the LLM call and back."

---

### Part 8 — IaC, Reproducibility & Closing (5 min)

**[Show: GitHub repo — UC2 supervisor-agent]**

> "Everything you've seen is reproducible infrastructure-as-code. We have seven repositories."

**Show the repo structure briefly:**

> "Each repo has its own `infra/` directory with Terraform — container app definitions, RBAC role assignments, APIM routes, App Insights, the works. The Azure AI Landing Zone provides the foundation, and each use case layers on top."

**[Show: Solution Architecture — Requirements Traceability section]**

> "We tracked 64 requirements across all use cases. 61 are fully implemented — that's 95%. The only two deferred are per-department security filters, which requires enterprise Entra integration, and ServiceNow, which requires a ServiceNow instance we don't have access to."

> "Every requirement is mapped to specific implementation details — which file, which service, which API endpoint. Full traceability from the PoC proposal through to deployed code."

**Closing:**

> "To summarize:"
> 1. "**RAG Knowledge Retrieval** — AI Search over documents with cited responses"
> 2. "**Multi-Agent Orchestration** — dynamic fan-out/fan-in across 4 agents and 4 different LLM models"
> 3. "**Cross-Cloud Execution** — Azure to AWS Bedrock with OIDC federation and end-to-end trace correlation"
> 4. "**Centralized Governance** — cost tracking, SIEM integration, incident resolution with AI triage and multi-agent voting"
> 5. "**Full Observability** — OpenTelemetry across all agents and clouds, Grafana dashboards, App Insights, Sentinel"
> 6. "**Enterprise Security** — managed identity, content safety, network isolation, least-privilege RBAC"
> 7. "**Infrastructure as Code** — 100% Terraform, 7 repos, fully reproducible"

> "The platform is designed to be extensible. Adding a new agent is a matter of adding a definition to agents.yaml and a tool module. Adding a new cloud provider follows the same async MCP pattern we used for AWS. Adding a new use case follows the Terraform pattern already established."

> "Questions?"

---

## EXTRAS (if time permits)

---

### Extra A — Live Code Walkthrough (5 min)

**[Show: VS Code with `services/supervisor-api/main.py`]**

> "Let me show you the actual code. The supervisor is about 300 lines of Python."

**Walk through:**
- `agents.yaml` — show declarative agent definitions
- `main.py` — show `WorkflowBuilder`, `FanInAggregator`, `select_agents`
- `tools/bedrock.py` — show the MCP invoke+poll pattern and OIDC auth
- `tools/knowledge.py` — show the UC1 RAG HTTP call

> "The key design decision is declarative configuration. Changing an agent's model from gpt-4.1 to gpt-4.1-mini is a one-line YAML edit — no code changes required."

---

### Extra B — LLM-as-Judge Evaluation (3 min)

> "We also built an evaluation pipeline. This uses gpt-4.1 as a judge to score the RAG agent's responses on three dimensions: groundedness, relevance, and completeness."

**Show: `services/rag-agent/evaluation/judge.py`**

> "It sends 5 test questions to the agent, then asks gpt-4.1 to evaluate each response against expected topics. Scores are 1-5 on each dimension. This can run as a CI step or ad-hoc to verify agent quality after changes."

---

### Extra C — Incident Resolution Live Demo (5 min)

**[Show: Terminal — Bastion-connected jump VM]**

> "Let me show you the incident resolution workflow live. This is UC4 integrated into the governance hub. I'm running these from our jump VM inside the VNet."

**Step 1 — Create an incident (AI triage fires automatically):**

```bash
curl -s -X POST https://ca-uc3-governance.ambitiouscliff-ec38b96b.australiaeast.azurecontainerapps.io/api/incidents \
  -H "Content-Type: application/json" \
  -d '{"title": "High latency on Knowledge Agent", "description": "P95 latency exceeded 10s on product specification queries for 30 minutes", "severity": "p2", "category": "latency_degradation"}' | python3 -m json.tool
```

> "Notice the AI triage result in the response — it classified the severity, category, recommended action, and reasoning. Copy the incident_id."

**Step 2 — Agents submit votes:**

```bash
INCIDENT_ID="<paste from above>"

curl -s -X POST "https://ca-uc3-governance.ambitiouscliff-ec38b96b.australiaeast.azurecontainerapps.io/api/incidents/${INCIDENT_ID}/votes" \
  -H "Content-Type: application/json" \
  -d '{"agent_name": "triage-agent", "recommendation": "scale_up", "confidence": 0.85, "reasoning": "Latency correlates with token throughput limits"}' | python3 -m json.tool

curl -s -X POST "https://ca-uc3-governance.ambitiouscliff-ec38b96b.australiaeast.azurecontainerapps.io/api/incidents/${INCIDENT_ID}/votes" \
  -H "Content-Type: application/json" \
  -d '{"agent_name": "knowledge-agent", "recommendation": "scale_up", "confidence": 0.72, "reasoning": "Search response times normal — LLM throughput is the bottleneck"}' | python3 -m json.tool

curl -s -X POST "https://ca-uc3-governance.ambitiouscliff-ec38b96b.australiaeast.azurecontainerapps.io/api/incidents/${INCIDENT_ID}/votes" \
  -H "Content-Type: application/json" \
  -d '{"agent_name": "governance-agent", "recommendation": "investigate", "confidence": 0.60, "reasoning": "Cost impact of scaling needs assessment first"}' | python3 -m json.tool
```

> "Three agents voted — two for scale_up with high confidence, one for investigate with lower confidence."

**Step 3 — Run weighted majority vote:**

```bash
curl -s -X POST "https://ca-uc3-governance.ambitiouscliff-ec38b96b.australiaeast.azurecontainerapps.io/api/incidents/${INCIDENT_ID}/decide?strategy=weighted_majority" | python3 -m json.tool
```

> "The decision engine ran weighted majority — scale_up won because the two agents supporting it had higher confidence scores. Notice requires_approval is true — P2 incidents always need human sign-off."

**Step 4 — Human approval:**

```bash
curl -s -X POST "https://ca-uc3-governance.ambitiouscliff-ec38b96b.australiaeast.azurecontainerapps.io/api/approvals/${INCIDENT_ID}/respond" \
  -H "Content-Type: application/json" \
  -d '{"approved": true, "notes": "Approved — scale gpt-4.1 deployment to 50K TPM"}' | python3 -m json.tool
```

> "The full lifecycle: event → AI triage → agent voting → decision engine → human approval. All persisted to Cosmos DB with an audit trail to Sentinel."

---

### Extra D — Agent Flow Visualization Deep Dive (3 min)

**[Switch to: Agent Flow tab, run a multi-agent query]**

**Type:**
```
Full analysis: product specifications, compliance requirements, cross-project learnings, and platform health
```

> "Watch the nodes light up as each agent activates. You can see the models listed — gpt-4.1-mini for Knowledge, o4-mini for Compliance, Claude Sonnet 4 for Engineering, gpt-4.1 for Governance."

**Click through each node showing payloads.**

> "The Agent Flow gives you complete visibility into what happened during a request — which agents were consulted, what they returned, and how the synthesizer merged it."

---

## Backup Prompts

If a multi-agent query times out or fails:
```
What are the material specifications?
```
*(Single-agent Knowledge only — fast and reliable)*

If Bedrock is slow:
```
What are the safety compliance requirements for product specifications and do they meet ASME standards?
```
*(Knowledge + Compliance only — no AWS dependency)*

If governance queries fail:
```
What are the product specifications for Sample Project?
```
*(Falls back to just Knowledge — always works)*

**Note:** All container apps are on the internal VNet (ILB). curl commands must be run from the **Bastion-connected jump VM**, not from your laptop. The frontend browser works because it's accessed via VPN/Bastion.

---

## Timing Guide

| Section | Duration | Running Total |
|---------|----------|---------------|
| Part 1 — Platform Overview | 5 min | 5 min |
| Part 2 — UC1 RAG Knowledge | 7 min | 12 min |
| Part 3 — UC2 Multi-Agent Supervisor | 10 min | 22 min |
| Part 4 — Cross-Cloud AWS Bedrock | 5 min | 27 min |
| Part 5 — Observability & FinOps | 8 min | 35 min |
| Part 6 — Governance & Incidents | 5 min | 40 min |
| Part 7 — Security & Content Safety | 3 min | 43 min |
| Part 8 — IaC & Closing | 5 min | 48 min |
| **Core Total** | **~48 min** | |
| Extra A — Live Code Walkthrough | +5 min | |
| Extra B — LLM-as-Judge Evaluation | +3 min | |
| Extra C — Incident Resolution Live Demo | +5 min | |
| Extra D — Agent Flow Deep Dive | +3 min | |
