Unified AI Platform

UC2 – AWS Bedrock Agent Gateway

Technical Handoff Specification

Prepared for: the organization

Program: Unified AI Platform (UAIP)

Use Case: UC2 – Multi‑Agent Supervisor & Monitoring

Purpose: AWS Technical Handoff for PoC Enablement

Azure‑Side Architecture Overview (High Level)

The Unified AI Platform is architected with Microsoft Azure as the central
governance, orchestration, and observability control plane, while other cloud
environments (including AWS) operate as distributed agent execution environments.

Within UC2, Azure is responsible for coordinating all agent interactions across clouds.
Specifically, Azure:

•  Receives user‑ and system‑initiated requests that require agent execution
•  Determines which specialized agents (Azure‑hosted or AWS‑hosted) should be

invoked based on intent and policy

•  Orchestrates multi‑agent workflows, including fan‑out, fan‑in, retries, escalation,

and conflict resolution

•  Enforces enterprise policies such as identity enforcement, rate limiting, circuit

breaking, and execution guardrails

•  Serves as the single source of truth for observability, audit, and cost governance

Key Azure Components in UC2

•  Azure AI Foundry & Microsoft Agent Framework

Hosts the primary (supervisor) agent. This agent performs agent selection, manages
orchestration logic, tracks execution state, and aggregates results across multiple
sub‑agents, regardless of where they run.

•  Azure API Management (APIM)

Acts as the Unified AI Gateway. APIM enforces governance policies, routes requests to
Azure and AWS agent endpoints, propagates W3C trace context, and provides a consistent
control point for multi‑cloud agent execution.

Classified as Microsoft Confidential

•  Azure Monitor, Application Insights, and Microsoft Sentinel

Provide centralized observability and security monitoring. All agent executions emit
OpenTelemetry (OTEL) signals that are ingested into Azure for cross‑cloud correlation,
auditing, and analysis.

This design enables the organization to scale agent adoption across clouds while maintaining uniform
governance and visibility.

1. Purpose of This Document

This document is an official Unified AI Platform technical handoff
specification for AWS engineering teams supporting UC2: Multi‑Agent Supervisor &
Monitoring, as defined in Unified AI Platform_POCProposal_13‑April for MS.pdf.

It defines the mandatory AWS‑side architecture, services, APIs, security controls,
telemetry requirements, and execution models needed to integrate Amazon Bedrock
agents into the UAIP, where Azure operates as the centralized orchestration and
governance layer.

This document is authoritative for the AWS scope of the UC2 Proof of Concept and
establishes the baseline expectations for AWS implementation.

2. UC2 Constraints and Assumptions

For UC2, AWS engineering teams must operate under the following non‑negotiable
constraints:

•  AWS functions strictly as an agent execution environment, not as a governance or

observability platform

•  Azure owns:

o  Agent orchestration and workflow control
o  Execution routing and retries
o  Policy enforcement and guardrails
o  Observability dashboards, reporting, and audit UX

•  All AWS‑hosted agents must be:

o  Externally callable via well‑defined APIs
o  Asynchronous in execution
o  Observable via OpenTelemetry

•  Agent functional sophistication is not evaluated in this PoC; platform‑level

governance, traceability, and visibility are the success criteria

Classified as Microsoft Confidential

3. AWS Responsibilities within the Unified AI Platform

AWS is responsible for exposing Amazon Bedrock agents through a controlled integration
boundary referred to as the AWS Agent Gateway.

The AWS Agent Gateway must:

•  Accept agent‑aware, Model Context Protocol (MCP)‑compatible invocation

requests from the UAIP
Initiate Bedrock agent execution asynchronously

•
•  Return immediate execution acknowledgements to Azure
•  Emit OpenTelemetry‑compliant telemetry that can be ingested and correlated

centrally in Azure

•  Expose execution status and final results through defined APIs

Important: Direct, synchronous use of the Amazon Bedrock InvokeAgent API without async
handling, trace propagation, and an explicit gateway layer does not satisfy UC2
requirements.

4. AWS Agent Gateway – Required API Surface

Each Bedrock agent participating in UC2 must be exposed through a stable, versioned API
surface that acts as the authoritative contract between Azure UAIP and AWS.

4.1 Canonical Agent Invoke Endpoint

1     POST /agents/{agentName}/invoke
2
Responsibilities:

•  Accept UAIP‑issued, MCP‑compatible invocation payloads over HTTPS
•  Propagate W3C traceparent headers without modification
•
•  Return an acknowledgment containing a UAIP‑correlatable executionId

Initiate Bedrock agent execution asynchronously

4.2 Canonical Execution Status Endpoint

1     GET /executions/{executionId}
2
Responsibilities:

•  Return execution state (accepted, running, completed, failed)
•  Provide final agent output and execution metadata when available

Classified as Microsoft Confidential

4.3 Canonical Request & Response Payloads (Azure ↔ AWS)

This section defines the explicit JSON contracts exchanged between the Unified AI
Platform (Azure) and the AWS Agent Gateway. These payloads are authoritative and
represent the minimum fields required to satisfy UC2 requirements for orchestration,
traceability, and observability.

4.3.1 Agent Invocation Request (Azure → AWS)

This request is issued by the Azure Supervisor Agent (via Azure API Management) when
invoking an AWS‑hosted Bedrock agent.

1     {
2       "mcpVersion": "1.0",
3       "traceparent": "00-4bf92f3577b34da6a3ce929d0e0e4736-
00f067aa0ba902b7-01",
4       "invocation": {
5         "invocationId": "inv-7f3b2c",
6         "parentAgent": "uaip-supervisor",
7         "targetAgent": "aws-bedrock-kb-agent",
8         "async": true
9       },
10       "input": {
11         "taskType": "knowledge_retrieval",
12         "payload": {
13           "query": "Retrieve EPC documents related to valve X",
14           "context": {
15             "project": "Project Alpha",
16             "businessUnit": "Energy"
17           }
18         }
19       }
20     }
Key Expectations:

•
traceparent must be propagated unchanged across all AWS processing layers
•
invocationId is generated by Azure and used for cross‑cloud correlation
•  async must be honored; the gateway must not block on agent execution

Classified as Microsoft Confidential

4.3.2 Invocation Acknowledgement (AWS → Azure)

This is the immediate response returned by the AWS Agent Gateway acknowledging receipt
of the request.

1     {
2       "executionId": "aws-exec-98213",
3       "status": "accepted"
4     }
Key Expectations:

•  Returned synchronously (HTTP 202)
•  executionId is AWS‑generated and becomes the primary execution handle

4.3.3 Execution Completion / Status Response (AWS → Azure)

This response is returned when Azure polls the execution status endpoint, or when
execution has completed.

1     {
2       "executionId": "aws-exec-98213",
3       "status": "completed",
4       "result": {
5         "content": "Relevant EPC documentation retrieved
successfully",
6         "citations": ["doc-123", "doc-456"]
7       },
8       "telemetry": {
9         "durationMs": 8423,
10         "tokens": {
11           "input": 1180,
12           "output": 640
13         }
14       }
15     }
Key Expectations:

•  status must accurately reflect execution state
•
•  Additional metadata may be included but must not remove or rename required

telemetry fields enable cost and performance tracking in Azure

fields

Classified as Microsoft Confidential

5. OpenAPI Specification – Unified AI Platform AWS Agent Gateway

An OpenAPI Specification (OAS) is a formal, machine‑readable description of an API’s
request formats, response schemas, authentication requirements, and lifecycle behavior.

Role of OpenAPI in the UAIP Architecture

Within the Unified AI Platform, the OpenAPI specification for the AWS Agent
Gateway provides:

•  Architectural assurance that AWS agent entry points are stable, explicit, and

versioned

•  A contract that Azure API Management can import to:
o  Validate request and response structures
o  Enforce security, throttling, and policy controls
o  Apply governance consistently across clouds

•  A shared artifact that enables repeatable implementation, testing, and auditing

Why This Matters for UC2

By codifying the AWS Agent Gateway using OpenAPI:

•  Asynchronous behavior is made explicit (202 Accepted semantics)
•  Execution correlation via executionId is enforced
•  Trace propagation is mandated as part of the contract
•  Azure can apply gateway‑level assurances (rate limits, circuit breakers, logging)

This gives the organization confidence that cross‑cloud agent execution is predictable, auditable, and
governable.

Reference Documentation:

•  AWS API Gateway & OpenAPI:

https://docs.aws.amazon.com/apigateway/latest/developerguide/api-gateway-api-
definition.html

•  Azure API Management OpenAPI support:
•  https://learn.microsoft.com/en-us/azure/api-management/import-api-from-oas

OpenAPI Specification (AWS Agent Gateway)

1     openapi: 3.0.3
2     info:
3       title: AWS Agent Gateway
4       version: 1.0.0
5     tags:
6       - name: Agents

Classified as Microsoft Confidential

7     paths:
8       /agents/{agentName}/invoke:
9         post:
10           summary: Invoke Bedrock Agent (Async)
11           tags: [Agents]
12           parameters:
13             - name: agentName
14               in: path
15               required: true
16               schema: { type: string }
17             - name: traceparent
18               in: header
19               required: true
20               schema: { type: string }
21           requestBody:
22             required: true
23             content:
24               application/json:
25                 schema:
26                   $ref: '#/components/schemas/MCPInvocation'
27           responses:
28             '202':
29               description: Accepted
30               content:
31                 application/json:
32                   schema:
33                     $ref: '#/components/schemas/InvokeAck'
34       /executions/{executionId}:
35         get:
36           summary: Get Agent Execution Status
37           tags: [Agents]
38           parameters:
39             - name: executionId
40               in: path
41               required: true
42               schema: { type: string }
43           responses:
44             '200':
45               description: Execution Status
46               content:

Classified as Microsoft Confidential

47                 application/json:
48                   schema:
49                     $ref: '#/components/schemas/ExecutionResult'
50     components:
51       schemas:
52         MCPInvocation:
53           type: object
54           required: [mcpVersion, traceparent, invocation, input]
55           properties:
56             mcpVersion: { type: string, example: '1.0' }
57             traceparent: { type: string }
58             invocation:
59               type: object
60               properties:
61                 invocationId: { type: string }
62                 parentAgent: { type: string }
63                 targetAgent: { type: string }
64                 async: { type: boolean }
65             input:
66               type: object
67               properties:
68                 taskType: { type: string }
69                 payload: { type: object, additionalProperties:
true }
70         InvokeAck:
71           type: object
72           properties:
73             executionId: { type: string }
74             status: { type: string, enum: [accepted] }
75         ExecutionResult:
76           type: object
77           properties:
78             executionId: { type: string }
79             status:
80               type: string
81               enum: [accepted, running, completed, failed]
82             result:
83               type: object
84               nullable: true
85             telemetry:

Classified as Microsoft Confidential

86               type: object
87               properties:
88                 durationMs: { type: number }
89                 tokens:
90                   type: object
91                   properties:
92                     input: { type: number }
93                     output: { type: number }

6. Asynchronous Execution Model (Mandatory)

All AWS agent executions must follow this non‑blocking lifecycle:

1     Invoke → Acknowledge → Execute → Complete
2
Immediate acknowledgement is mandatory because agent execution time varies widely and
agents may call other agents as part of their workflow.

7. Telemetry and Observability Requirements

AWS must emit OpenTelemetry (OTEL) spans for every agent invocation, including:

•  Shared traceId originating from Azure
•  Unique span identifiers per execution step
•  Agent identity and type
•  Execution duration
•  Token usage where available

Telemetry may be exported via:

•  OTLP/HTTP directly to Azure Monitor
•  OTLP to an intermediate collector that forwards to Azure

Reference Documentation:

•  AWS OTEL for Lambda: https://docs.aws.amazon.com/lambda/latest/dg/services-

otel.html

•  Azure Monitor OpenTelemetry: https://learn.microsoft.com/azure/azure-

monitor/app/opentelemetry-enable

Classified as Microsoft Confidential

8. Identity and Security Requirements

AWS must implement OIDC federation with Azure Entra ID:

•  No static AWS credentials
•  Least‑privilege IAM roles
•  Permissions limited to agent execution and telemetry emission

Reference Documentation:

•  AWS IAM OIDC federation:

https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_providers_oidc.html

•  Azure Entra workload identity federation:

https://learn.microsoft.com/en-us/entra/workload-id/workload-identity-federation

9. What This Enables for the organization

With the above in place, the Unified AI Platform can demonstrate:

•  Multi‑agent orchestration across clouds
•  Centralized governance and policy enforcement
•  End‑to‑end observability and traceability
•  Asynchronous, resilient agent execution
•  Vendor‑neutral telemetry and auditability

This capability set directly satisfies the UC2 evaluation criteria.

End of AWS handoff specification

Classified as Microsoft Confidential


