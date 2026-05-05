# End-to-End Telemetry Walkthrough — Chat → Logs

> Use this script to demonstrate that a single user prompt is observable
> at every hop: frontend → APIM → supervisor → tools/agents → governance →
> Cosmos / Log Analytics / Sentinel.
>
> **Duration:** ~10 minutes
> **Pre-reqs:** valid Entra session on the jumpbox, Grafana + App Insights tabs open.

---

## The story in one sentence

> "One user message creates one `traceparent`. That trace ID survives every
> hop — across services, across clouds — and we can pull every span, log,
> cost line, and audit event for it from a single query."

---

## Tabs to open before you start

> **Subscription:** `ai-lz-msdn-mb44x` (`1784740a-1cf6-416b-b3db-bda6985970aa`)
> **Resource group:** `ai-lz-rg-msdn-mb44x`
> **Tenant:** `ac145ec2-a5e4-480a-bfb8-88d1a01ba552`

| # | Tab | URL |
|---|-----|-----|
| 1 | Frontend chat | https://ca-uaip-frontend.ambitiouscliff-ec38b96b.australiaeast.azurecontainerapps.io |
| 2 | App Insights (UC2 supervisor) — Transaction Search | https://portal.azure.com/#@ac145ec2-a5e4-480a-bfb8-88d1a01ba552/resource/subscriptions/1784740a-1cf6-416b-b3db-bda6985970aa/resourceGroups/ai-lz-rg-msdn-mb44x/providers/Microsoft.Insights/components/ai-uc2-supervisor-appinsights/searchV1 |
| 3 | App Insights (UC2 supervisor) — Application Map | https://portal.azure.com/#@ac145ec2-a5e4-480a-bfb8-88d1a01ba552/resource/subscriptions/1784740a-1cf6-416b-b3db-bda6985970aa/resourceGroups/ai-lz-rg-msdn-mb44x/providers/Microsoft.Insights/components/ai-uc2-supervisor-appinsights/applicationMap |
| 4 | Log Analytics — Logs (KQL) | https://portal.azure.com/#@ac145ec2-a5e4-480a-bfb8-88d1a01ba552/resource/subscriptions/1784740a-1cf6-416b-b3db-bda6985970aa/resourceGroups/ai-lz-rg-msdn-mb44x/providers/Microsoft.OperationalInsights/workspaces/ai-alz-law/logs |
| 5 | Grafana — UAIP Agent FinOps | https://uaip-grafana-h8begbeph0fgdqhp.eau.grafana.azure.com/d/uaip-agent-finops-v3 |
| 6 | UC3 Governance API — Swagger | https://ca-uc3-governance.ambitiouscliff-ec38b96b.australiaeast.azurecontainerapps.io/docs |
| 7 | Sentinel — Incidents | https://portal.azure.com/#@ac145ec2-a5e4-480a-bfb8-88d1a01ba552/resource/subscriptions/1784740a-1cf6-416b-b3db-bda6985970aa/resourceGroups/ai-lz-rg-msdn-mb44x/providers/Microsoft.OperationalInsights/workspaces/ai-alz-law/Microsoft_Azure_Security_Insights/Incidents |
| 8 | App Insights (UC3 governance) — Transaction Search | https://portal.azure.com/#@ac145ec2-a5e4-480a-bfb8-88d1a01ba552/resource/subscriptions/1784740a-1cf6-416b-b3db-bda6985970aa/resourceGroups/ai-lz-rg-msdn-mb44x/providers/Microsoft.Insights/components/ai-uc3-governance-appinsights/searchV1 |
| 9 | App Insights (UC1 RAG) — Transaction Search | https://portal.azure.com/#@ac145ec2-a5e4-480a-bfb8-88d1a01ba552/resource/subscriptions/1784740a-1cf6-416b-b3db-bda6985970aa/resourceGroups/ai-lz-rg-msdn-mb44x/providers/Microsoft.Insights/components/ai-uc1-rag-agent/searchV1 |

---

## Step 1 — Send a single chat message (frontend)

In the **Frontend Chat** tab, ask:

> *"My P2 incident — pump P-101 vibration alarm at 0300. Get me telemetry,
> a root cause, and remediation options."*

Expected UI response (within ~15s):
- Streaming reply with citations
- "Agent Flow" tab populates a DAG of fan-out → fan-in
- A **Validation Report** appears at the bottom listing `MON_*`, `DIAG_*` checks

> **Talking point:** "That single message has just touched 4 services across
> 2 clouds. Let's follow the trace."

---

## Step 2 — Grab the `operation_Id` from the browser

Open Chrome DevTools (F12) → **Network** tab → click the `/api/chat` request →
**Response Headers** → copy the value of **`x-ms-request-id`** (or look at the
streamed response body — the supervisor echoes the `traceparent` in its first
SSE frame).

Save it as `$TRACE_ID` in your terminal. Example: `0a1b2c3d4e5f6789...`

---

## Step 3 — Application Map (visual confirmation)

Switch to the **Application Map** tab.

> **Talking point:** "This map is auto-rendered from OTEL spans — no custom
> code. Each node is a service, each line is a real call. Notice the call
> from `uc2-supervisor` to `apim-ai-alz` to `aws-bedrock-gateway` — that's
> our cross-cloud hop."

Click any edge → **View in Transaction Search** to drill in.

---

## Step 4 — Transaction Search (full timeline)

In the **Transaction Search** tab paste the trace ID into the search box →
select **"Operation ID"** → run.

You should see, ordered by timestamp:

| Span | Source | What it shows |
|------|--------|----------------|
| `POST /api/chat` | uaip-frontend | User entry, JWT subject |
| `apim:uc2-supervisor:inbound` | APIM | Subscription key, content-safety verdict, rate-limit budget |
| `supervisor.invoke` | uc2-supervisor | Selected agents, prompt tokens |
| `tool:knowledge` | uc2-supervisor | AI Search query, citation count |
| `tool:bedrock` | uc2-supervisor | AWS region, Claude Sonnet model id |
| `apim:uc2-bedrock:outbound` | APIM | Cross-cloud egress, content-safety on the **prompt** |
| `bedrock.invoke_model` | aws-bedrock-gateway | AWS span, same `traceparent` |
| `tool:governance` | uc2-supervisor | Calls UC3 governance-api |
| `POST /api/incidents` | uc3-governance-api | Creates audit root event |
| `policy.applied` | uc3-governance-api | Embedded policy version |
| `aggregator.fan_in` | uc2-supervisor | Validators ran (TC-4, TC-6) |

> **Talking point:** "Notice the same trace ID is present on the AWS spans.
> That is W3C trace context propagating end-to-end. We didn't build that —
> the framework gives us that for free because every hop honours the
> `traceparent` header."

---

## Step 5 — KQL: pull everything for one trace

Switch to **Log Analytics — Logs**. Paste:

```kusto
let TraceId = "<paste $TRACE_ID here>";
union AppRequests, AppDependencies, AppTraces, AppExceptions
| where OperationId == TraceId
| project TimeGenerated, ItemType, Name, Target, ResultCode, DurationMs,
          AppRoleName, OperationId, ParentId, Id, Message
| order by TimeGenerated asc
```

> **Talking point:** "One query, one trace ID, every signal — requests,
> dependencies, traces, exceptions — in chronological order across every
> service involved. This is the level of observability that makes
> root-causing production incidents tractable."

---

## Step 6 — KQL: token, cost, and latency by agent

Same workspace, paste:

```kusto
let TraceId = "<paste $TRACE_ID here>";
AppDependencies
| where OperationId == TraceId
| where Name startswith "tool:" or Name startswith "supervisor"
| extend tokens_in   = toint(Properties.["llm.usage.prompt_tokens"]),
         tokens_out  = toint(Properties.["llm.usage.completion_tokens"]),
         model       = tostring(Properties.["llm.model"]),
         cloud       = tostring(Properties.["cloud.provider"]),
         agent       = AppRoleName
| project TimeGenerated, agent, cloud, model, tokens_in, tokens_out,
          DurationMs
| order by TimeGenerated asc
```

> **Talking point:** "Same trace ID, but now broken down by agent and by
> cloud — you can see exactly which agent burned which tokens against
> which model on which cloud, and how long each step took."

---

## Step 7 — KQL: governance audit chain for the same incident

The supervisor stamps the resulting `incident_id` into the response header
`x-uaip-incident-id`. Copy it and run:

```kusto
let IncidentId = "<paste incident_id here>";
AppTraces
| where Properties.["incident.id"] == IncidentId
| project TimeGenerated, AppRoleName,
          event = tostring(Properties.["workflow_event.type"]),
          actor = tostring(Properties.["workflow_event.actor"]),
          policy_version = tostring(Properties.["policy_applied.version"]),
          message = Message
| order by TimeGenerated asc
```

You will see, in order: `incident.reported` → `policy.applied` →
`agent.invoked` (×N) → `validation.report` → `decision.recorded` →
(optional) `approval.requested` / `approval.granted` → `remediation.option_added` →
`remediation.option_selected` → `incident.resolved`.

> **Talking point:** "Every governance event is structured, queryable,
> and tied back to the same trace. This is what feeds the audit bundle in
> step 9."

---

## Step 8 — Grafana: business view of the same data

Switch to the **Grafana — UAIP Agent FinOps** dashboard.

Set the time range to **Last 15 minutes**.

Point out four panels:

1. **Tokens by Agent (stacked)** — your message just added a slice.
2. **Cost by Cloud (Azure vs AWS)** — both bars moved.
3. **p95 Latency by Agent** — the bedrock agent is the tallest bar.
4. **Validator Verdicts** — a +1 on `MON_METRICS_PRESENT` and a +1 on
   `DIAG_MATCH` (or `DIAG_NO_MATCH`) from this run.

> **Talking point:** "Stakeholders don't read trace timelines — they read
> dashboards. Same data, different audience. FinOps, platform engineering,
> and the security team all consume the same source."

---

## Step 9 — One-click audit bundle (TC-13)

Back in the **UC3 Governance API — Swagger** tab, expand
`GET /api/incidents/{id}/audit-bundle`, paste your incident ID, hit
**Execute**.

> **Talking point:** "This is the regulator-ready packet. One JSON document
> with every event, every agent action, every decision, every approval,
> every policy version applied, and direct KQL drill-down links. SIEM
> ingests this; auditors review this; nothing assembled by hand."

---

## Step 10 — Sentinel: the security view

Switch to **Sentinel — Incidents**.

If you triggered a TC-3 bypass attempt or a TC-5 SLA breach during the
demo, you'll see a Sentinel incident with the same `incident_id` in its
entities. Click in → **Investigate** → graph view shows the same
`traceparent` chain.

> **Talking point:** "Same trace ID, third tool, this time from a security
> analyst's seat. The trace is the spine the entire platform agrees on."

---

## Closing line

> "From one chat message we just rendered: a real-time agent flow DAG, a
> cross-cloud trace timeline, a token/cost rollup, a governance audit
> chain, a FinOps dashboard, an audit bundle, and a Sentinel incident —
> all keyed off a single trace ID. **That is what unified observability
> across multi-cloud agents looks like.**"
