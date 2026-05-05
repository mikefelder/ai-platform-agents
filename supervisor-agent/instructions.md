# use-case-2 – Multi‑Agent Supervisor & Monitoring
## GitHub Copilot Development Specification

Audience: GitHub Copilot (code-first, implementation oriented)
Purpose: Begin implementation of Use Case 2 (use-case-2): Multi‑Agent Supervisor & Monitoring inside this repository.

---

## Technology & Constraints (Mandatory)
- Language: Python 3.11+
- Web framework: FastAPI
- Tracing: OpenTelemetry (OTLP exporter) + Azure Monitor/App Insights compatible
- HTTP client: httpx
- Testing: pytest
- No new orchestration frameworks beyond what is already referenced in /upstream

## 1. Objective

Implement Use Case 2 – Multi‑Agent Supervisor & Monitoring as a Python-based proof‑of‑concept that demonstrates:

1. A central supervisor/orchestrator running in Azure
2. Orchestration of multiple heterogeneous agents, including:
   - A native Azure agent
   - An AWS Bedrock agent (via proxy)
   - A ServiceNow agent (via proxy)
3. End‑to‑end observability using OpenTelemetry (OTEL)
4. Request‑level and step‑level tracing:
   - Supervisor → agent → tool/API calls
5. Telemetry export suitable for Azure Monitor / Application Insights

The goal of this PoC is governance and observability, not agent intelligence or business value.

---

## 2. Non‑Goals

The following are explicitly out of scope:

- Building a production‑grade agent platform
- Advanced agent reasoning or prompt tuning
- Full AWS or ServiceNow integrations (stub or proxy endpoints are acceptable)
- UI dashboards or front‑end applications
- Enterprise authentication hardening
- Cost optimization logic beyond basic telemetry attributes

---

## 3. Architectural Pattern

The solution follows a control‑plane / data‑plane architecture.

Control Plane (Supervisor):
- Receives incoming workflow requests
- Owns the root OpenTelemetry span
- Orchestrates agent execution
- Propagates trace context
- Handles errors gracefully

Data Plane (Agents):
- Perform delegated work
- May be Azure‑native or external
- Emit OpenTelemetry spans
- Return structured JSON responses

Reference example repos:
- https://github.com/microsoft/agent-framework
- https://github.com/PreiyaaKedia/agent-tracing-azure

Azure Landing Zone that is deployed to Subscription:
- https://github.com/Azure/terraform-azurerm-avm-ptn-aiml-landing-zone

All agent work must roll up under a single trace.

---

## 4. Repository Context

This repository already contains exactly four upstream reference repositories (as submodules or vendored directories):

1. Azure AI Landing Zones – infrastructure reference
2. AVM AI/ML Landing Zone (Terraform) – deployment baseline
3. microsoft/agent-framework – agent orchestration and telemetry reference patterns
4. agent-tracing-azure – OpenTelemetry best‑practice examples

Constraints:
- Do not introduce new orchestration frameworks
- Do not add additional upstream repositories
- Use upstream repos as reference implementations, not runtime dependencies

---

## 5. Primary Service to Implement

Service Name: supervisor-api
Language: Python
Framework: FastAPI

This service is the single entry point for Use Case 2.

---

## 6. API Contract

Endpoint:
    POST /use-case-2/run

Request Payload (example):

    {
      "request_id": "string",
      "task": "string describing the work",
      "bedrock_proxy_url": "http://bedrock-proxy/run",
      "servicenow_proxy_url": "http://servicenow-proxy/run"
    }

Response Payload (example):

    {
      "trace_id": "string",
      "results": {
        "azure_agent": {},
        "bedrock_agent": {},
        "servicenow_agent": {}
      }
    }

---

## 7. Agents to Implement

Exactly four agents must exist.

### 7.1 Supervisor Agent

- Coordinates workflow execution
- Creates the root OTEL span
- Invokes sub‑agents
- Sets attributes such as:
  - uc.name = use-case-2
  - workflow.type = multi_agent_supervisor

### 7.2 Azure Native Agent

- Minimal native agent
- May return static or mocked data
- Must emit its own OpenTelemetry span

### 7.3 Bedrock Proxy Agent

- Invokes an HTTP endpoint supplied in the request
- Represents an external cloud agent
- Does not embed AWS SDK logic
- Emits spans for:
  - agent invocation
  - HTTP or tool execution

### 7.4 ServiceNow Proxy Agent

- Same pattern as Bedrock agent
- Uses HTTP REST invocation
- Returns JSON payload
- Emits OpenTelemetry spans

---

## 8. OpenTelemetry Requirements

All code must be instrumented with OpenTelemetry.

Required trace structure:

- Root span:
  - name = use-case-2.workflow
- Child spans:
  - agent.azure_native
  - agent.aws_bedrock_proxy
  - agent.servicenow_proxy
- Nested spans for:
  - HTTP calls
  - Tool calls

Required span attributes (minimum):

- agent.name
- agent.type (native or external)
- tool.name (if applicable)
- uc = use-case-2
- error = true or false

---

## 9. Telemetry Export

Telemetry must be exportable via one of the following:

- OTLP to an OpenTelemetry Collector
- Azure Monitor / Application Insights exporter

All configuration must be environment‑driven and not hard‑coded.

---

## 10. Required File Structure

The following files must exist (create if missing):

    services/
    └── supervisor-api/
        ├── src/supervisor_api/
        │   ├── main.py
        │   ├── orchestration/
        │   │   └── supervisor.py
        │   ├── agents/
        │   │   ├── azure_agent.py
        │   │   ├── bedrock_proxy_agent.py
        │   │   └── servicenow_proxy_agent.py
        │   └── telemetry/
        │       └── otel.py

Each file must be small, single‑purpose, and easy to modify.

---

## 11. Error Handling Rules

- All exceptions must be recorded on spans
- error=true must be set on failed spans
- A single agent failure must not crash the entire workflow
- Partial results are acceptable

---

## 12. Testing Expectations

Minimum requirements:

- Smoke test for POST /use-case-2/run returning HTTP 200
- Downstream agent calls may be mocked
- Trace validation is best‑effort only

---

## 13. Coding Style Constraints

- Favor clarity over cleverness
- Avoid deep inheritance hierarchies
- Avoid unnecessary async complexity
- No global mutable state
- Keep dependencies minimal

---

## 14. Success Criteria

The implementation is successful if:

- A supervisor orchestrates three agents
- A single trace spans the entire workflow
- Each agent emits child spans
- External agents appear as first‑class telemetry participants
- The architecture is extensible and readable

---

## 15. Instruction to GitHub Copilot

Begin implementation in the following order:

1. telemetry/otel.py
2. orchestration/supervisor.py
3. One proxy agent (Bedrock or ServiceNow)

Prioritize trace correctness and structure over agent depth or features.