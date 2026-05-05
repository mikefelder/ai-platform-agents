Test Case addressment plans:
Test Case 1 — User Identity on Incident Creation
Gap: Caller identity not captured on incident record
Effort: 1-2 days
Plan:
Add Entra ID **JWT** validation middleware to **UC3** FastAPI (fastapi-azure-auth or manual **JWKS** validation)
Extract oid, upn, name claims from the validated token
Add reported_by field to Incident model (**UPN**, object ID, timestamp)
Log identity as the root audit event in WorkflowEvent
**APIM** already passes the Authorization header — middleware just needs to decode it
 
Test Case 2 — Versioned Policy Enforcement
Gap: No first-class policy registry with version tracking
Effort: 3-5 days
Plan:
Create Policy model with version, effective_date, severity_rules, approval_thresholds
Store policies in Cosmos DB with version history (append-only, never delete)
On incident creation, resolve and attach the active policy version: incident.attributes[*policy_applied*] = {*id*: ***POL**-**001***, *version*: *1.3*, *resolved_at*: timestam…
Log policy.applied event in workflow history with full policy snapshot
Add /api/policies/{id}/versions endpoint to query policy history
**APIM** policies (rate limits, content safety) already have implicit versioning via Terraform — add a policy metadata endpoint that returns current **APIM** policy hash
 
Test Case 3 — Zero Bypass Gateway Enforcement
Gap: Inter-agent calls bypass **APIM** (direct container-to-container)
Effort: 3-5 days
Plan:
Route **UC2**→**UC1** Knowledge calls through **APIM** instead of direct **FQDN**: change UC1_RAG_ENDPOINT to [https://**192**.**168**.4.4/uc1](https://**192**.**168**.4.4/uc1) with **APIM** subscription key
Route **UC2**→**UC3** Governance calls through **APIM** similarly
Route **UC2**→**AWS** Bedrock through **APIM** as a named backend (already registered as aws-bedrock-agentcore)
Add Container Apps Environment network policy restricting egress to **APIM** IP only (**192**.**168**.4.4) + Azure OpenAI endpoints
**APIM** diagnostic logs already capture all routed requests — any bypass would show as missing **APIM** log entry for an agent call visible in App Insights
Add Sentinel analytics rule: "Agent dependency call without corresponding **APIM** GatewayLog entry"
Trade-off: Adds ~50-100ms latency per inter-agent call. Consider **APIM** caching for repeated patterns.
 
Test Case 4 — Agent Output Validation
Gap: No data quality/consistency checks on agent responses
Effort: 5-8 days
Plan:
Add ValidationExecutor between agent responses and the FanInAggregator in the WorkflowBuilder
Validation checks:
Completeness: Required fields present (configurable per agent in agents.yaml)
Consistency: Cross-reference conflicting claims across agent responses (e.g., Knowledge says *valve rated **300** **PSI*** but Compliance says *requires **600** **PSI** rating*)
Confidence: Flag low-confidence or hedging language (*I'm not sure*, *possibly*, *may*)
Use gpt-4.1-mini as a validation judge with a structured prompt: "Given these N agent responses, identify gaps, contradictions, and missing data"
If validation fails: log validation.failed event with details, optionally re-query the agent with a more specific prompt, or route to human review
Add validation_result to the aggregated response metadata visible in the frontend
 
Test Case 5 — **SLA** Enforcement with Escalation
Gap: Timeouts are per-tool, not policy-driven; no automatic escalation
Effort: 2-3 days
Plan:
Add sla_timeout_seconds to each agent definition in agents.yaml (e.g., Knowledge: 15s, Compliance: 30s, Bedrock: 60s)
Wrap each agent execution in an asyncio.wait_for() with the **SLA** timeout
On timeout: set span error=True with sla.breach=True, log agent.sla_breach event
Trigger escalation: transition incident to **ESCALATED** status, send notification via Service Bus
Add Sentinel rule: *Agent **SLA** breach detected* (query for sla.breach attribute in App Insights)
Optionally: retry with alternate agent or fallback model
 
Test Case 6 — Historical Pattern Matching
Gap: No comparison of diagnoses against historical incident data
Effort: 8-12 days
Plan:
Build historical incident knowledge base: after each incident resolution, store structured summary (root cause, resolution, affected systems, timeline) in a vector store or Cosmos DB
Create HistoricalAnalysisAgent that queries the knowledge base for similar past incidents
Add similarity scoring: compare new diagnostic output against historical root causes using embeddings
Flag inconsistencies: "Current diagnosis suggests X, but 3 similar incidents in the past 6 months were caused by Y"
Add confidence delta to the decision context: if current diagnosis diverges significantly from historical patterns, reduce confidence score and flag for review
This is the most complex remediation — consider using Azure AI Search with vector embeddings over historical incident data for semantic similarity
 
Test Case 9 — Approver Identity
Gap: Approver identity not formally captured from auth token
Effort: 1 day (same middleware as Test Case 1)
Plan:
Reuse the Entra **JWT** middleware from Test Case 1
On /api/approvals/{id}/respond, extract approver identity from **JWT**
Store in approval record: approved_by (**UPN**), approver_oid, approved_at, decision_notes
Link approval to incident via approval_id on the WorkflowState
All approval actions already log WorkflowEvent — just need to add identity fields
 
Test Case 10 — Agent Containment (Rogue Agent Detection)
Gap: No real-time scope monitoring or agent suspension
Effort: 10-15 days
Plan:
Scope definitions: Add allowed_endpoints to each agent in agents.yaml — list of **URL** patterns the agent's tools may call
Runtime enforcement: Create a custom httpx transport wrapper that validates every outbound **URL** against the agent's allowed scope before the request fires
Violation handling: On scope violation: (a) block the request, (b) set scope_violation=True span attribute, (c) increment violation counter, (d) if violations > threshold, suspend agent by removing it from agent_targets list
Gateway enforcement: Add **APIM** policy that cross-references the calling agent identity (via custom header) against allowed backends
Alert: Sentinel rule triggers on scope_violation events, sends plain-language alert to governance officer via Logic App or email action group
Forensic record: All violation attempts logged with: agent name, attempted **URL**, allowed scope, timestamp, request payload (truncated), parent trace ID
Architecture option: Use an Envoy sidecar proxy per container app with scope-based egress rules — more robust but higher infrastructure complexity
 
Test Case 11 — Full Workflow Durability
Gap: Some intermediate state (votes, workflow events) in-memory only; no real-time progress push
Effort: 3-5 days
Plan:
Persist all vote submissions to Cosmos DB (currently in-memory _votes dict)
Persist all workflow events to Cosmos DB (currently in-memory _workflow_events dict)
On container restart, lazy-load state from Cosmos on first access (same pattern as incidents)
Add /api/incidents/{id}/progress **SSE** (Server-Sent Events) endpoint for real-time progress streaming
Frontend polls or subscribes to progress endpoint to show live workflow state
Add **TTL**-based cleanup: archive resolved incidents after 30 days to cold storage
 
Test Case 13 — Audit Report Generation
Gap: No pre-built audit report endpoint
Effort: 3-5 days
Plan:
Create **POST** /api/incidents/{id}/audit endpoint
Query sources: Cosmos DB (incident record, workflow events, votes, decisions, approvals) + App Insights (**OTEL** spans for the incident's trace ID) + **APIM** GatewayLogs (via **KQL**)
3.Assemble structured **JSON** report:
