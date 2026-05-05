# Use Case 1 — Development Instructions

## Base Accelerator

This use case is a customised fork of [chat-with-your-data-solution-accelerator](https://github.com/Azure-Samples/chat-with-your-data-solution-accelerator).

Follow that repo's language and framework choices (Python backend, React/TypeScript frontend, Bicep infra, `azd` deployment) unless explicitly overridden below.

## Platform Alignment

This use case follows the shared platform principles defined in the repository root, while intentionally using a web UI and RAG architecture specific to document chat scenarios.

## Customisation Priorities (ordered)

1. **OpenTelemetry instrumentation** — add spans for query, retrieval, and LLM inference
2. **Azure API Management AI Gateway** — front Azure OpenAI with rate limiting, failover, token tracking
3. **Azure Content Safety guardrails** — prompt injection detection, content filtering
4. **LLM-as-Judge evaluation pipeline** — automated correctness/relevance/groundedness scoring
5. **Governance / access control** — Entra ID auth + AI Search security filters for per-department data access
6. **Cost management dashboards** — token usage, estimated spend, budget alerts

## Key Constraints

- Do NOT introduce additional agent/orchestration frameworks beyond what the accelerator provides (Semantic Kernel, LangChain, OpenAI Functions)
- Use PostgreSQL as the chat history database (supports relational ACL patterns)
- All observability must export via OpenTelemetry to Azure Monitor / Application Insights
- Infrastructure is Bicep-based, deployed via `azd`

See [README.md](README.md) for the full architecture, implementation plan, and requirement traceability.