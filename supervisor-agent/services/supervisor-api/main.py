# Licensed under the MIT License. See LICENSE file in the project root.
# Multi-Agent Supervisor (Microsoft Agent Framework SDK)
# Dynamic Multi-Selection Concurrent Orchestration Pattern

"""Entry point for the Supervisor — dynamic multi-agent workflow.

Uses the Microsoft Agent Framework SDK WorkflowBuilder with add_multi_selection_edge_group
for intelligent routing. The Supervisor plans which agents to invoke, a selection function
parses the plan and routes to only the relevant agents (concurrently), then the
Synthesizer merges results.

Architecture:
  User → Supervisor (plan) → Selection → [Selected Agents in parallel]
       → Fan-in → Synthesizer (merge) → Response
"""

import logging
import os
import sys
from pathlib import Path

import yaml
from agent_framework import Agent, WorkflowBuilder
from agent_framework.openai import OpenAIChatClient
from agent_framework._workflows._executor import Executor, handler
from agent_framework._workflows._agent_executor import AgentExecutorResponse, AgentExecutorRequest
from agent_framework._workflows._executor import WorkflowContext
from agent_framework_foundry_hosting import ResponsesHostServer
from azure.identity import ManagedIdentityCredential, DefaultAzureCredential
from dotenv import load_dotenv

from contextvars import ContextVar

from tools.knowledge import search_knowledge
from tools.compliance import analyze_compliance
from tools.bedrock import invoke_bedrock_agent
from tools.governance import query_governance_costs, query_governance_traces, query_agent_health
from tools.validators import run_validators

# TC-4 / TC-6 — last user prompt forwarded to the FanInAggregator validators.
_LAST_USER_TEXT: ContextVar[str] = ContextVar("last_user_text", default="")

load_dotenv()

# --- Observability ---
conn_str = os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING", "")

if conn_str:
    from azure.monitor.opentelemetry import configure_azure_monitor
    from agent_framework.observability import create_resource

    configure_azure_monitor(
        connection_string=conn_str,
        resource=create_resource(),
    )

    # Instrument httpx so Bedrock HTTP calls appear as dependencies
    from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
    HTTPXClientInstrumentor().instrument()

# Enable GenAI instrumentation via env var
os.environ.setdefault("ENABLE_INSTRUMENTATION", "true")

# --- Custom OTEL tracing for workflow orchestration ---
from opentelemetry import trace as otel_trace

_tracer = otel_trace.get_tracer("supervisor", "1.0.0")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s",
                    stream=sys.stdout, force=True)
logger = logging.getLogger("uaip.supervisor")

# =============================================================================
# Load agent definitions from agents.yaml
# =============================================================================

_AGENTS_YAML = Path(__file__).parent / "agents.yaml"

def _load_agent_defs() -> dict[str, dict]:
    """Load agent definitions from agents.yaml, keyed by name."""
    with open(_AGENTS_YAML) as f:
        agents = yaml.safe_load(f)
    return {a["name"]: a for a in agents}

AGENT_DEFS = _load_agent_defs()
logger.info("Loaded %d agent definitions from %s", len(AGENT_DEFS), _AGENTS_YAML.name)


class FanInAggregator(Executor):
    """Custom executor that collects AgentExecutorResponse(s) from selected agents
    and forwards combined text to the Synthesizer.

    Handles both single responses (from multi-selection routing 1 agent) and
    list responses (from fan-in when multiple agents are selected)."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._collected: list[str] = []
        self._expected = 0

    @handler
    async def aggregate_list(
        self,
        responses: list[AgentExecutorResponse],
        ctx: WorkflowContext[str],
    ) -> None:
        """Handle fan-in list of responses (multiple agents selected)."""
        with _tracer.start_as_current_span("uaip.aggregator.fan_in") as span:
            span.set_attribute("uc", "use-case-2")
            span.set_attribute("agents.count", len(responses))
            parts = []
            for resp in responses:
                agent_name = resp.executor_id or "Unknown"
                text = resp.agent_response.text if resp.agent_response else "(no response)"
                parts.append(f"## {agent_name}\n{text}")

            combined = "\n\n---\n\n".join(parts)
            span.set_attribute("agents.invoked", ",".join(r.executor_id or "?" for r in responses))
            logger.info("Aggregated %d agent responses (fan-in)", len(responses))
            user_text = _LAST_USER_TEXT.get() or ""
            try:
                reports, validation_block = run_validators(
                    user_text=user_text, combined_response=combined
                )
                span.set_attribute("validators.count", len(reports))
                span.set_attribute(
                    "validators.passed", sum(1 for r in reports if r.passed)
                )
                combined = f"{combined}\n\n---\n\n{validation_block}"
            except Exception:  # noqa: BLE001 — validators must never break the workflow
                logger.exception("Validator chain failed; forwarding raw aggregate")
            await ctx.send_message(combined)

    @handler
    async def aggregate_single(
        self,
        response: AgentExecutorResponse,
        ctx: WorkflowContext[str],
    ) -> None:
        """Handle single agent response — pass through with agent header."""
        with _tracer.start_as_current_span("uaip.aggregator.single") as span:
            agent_name = response.executor_id or "Unknown"
            span.set_attribute("uc", "use-case-2")
            span.set_attribute("agent.name", agent_name)
            text = response.agent_response.text if response.agent_response else "(no response)"
            body = f"## {agent_name}\n{text}"
            user_text = _LAST_USER_TEXT.get() or ""
            try:
                reports, validation_block = run_validators(
                    user_text=user_text, combined_response=body
                )
                span.set_attribute("validators.count", len(reports))
                span.set_attribute(
                    "validators.passed", sum(1 for r in reports if r.passed)
                )
                body = f"{body}\n\n---\n\n{validation_block}"
            except Exception:  # noqa: BLE001 — validators must never break the workflow
                logger.exception("Validator chain failed; forwarding raw response")
            # Use with_text to preserve AgentExecutorResponse type and conversation context
            forwarded = response.with_text(body)
            logger.info("Aggregated 1 agent response (%s)", agent_name)
            await ctx.send_message(forwarded)


def _get_credential():
    """Return ManagedIdentityCredential in production, DefaultAzureCredential locally."""
    client_id = os.environ.get("AZURE_CLIENT_ID", "")
    if client_id:
        return ManagedIdentityCredential(client_id=client_id)
    return DefaultAzureCredential()


def _extract_text(message) -> str:
    """Extract text content from a workflow message, trying multiple SDK paths."""
    # Path 1 (preferred): AgentExecutorResponse.agent_response.text
    if hasattr(message, "agent_response") and message.agent_response:
        resp_text = getattr(message.agent_response, "text", None)
        if resp_text:
            return resp_text.lower()

    # Path 2: full_conversation — look at assistant messages
    if hasattr(message, "full_conversation"):
        for msg in (message.full_conversation or []):
            role = getattr(msg, "role", "")
            if str(role) == "assistant" or str(role).endswith("assistant"):
                msg_text = getattr(msg, "text", None) or ""
                if not msg_text:
                    content = getattr(msg, "content", None)
                    if isinstance(content, str):
                        msg_text = content
                    elif isinstance(content, list):
                        msg_text = " ".join(str(c) for c in content)
                if msg_text:
                    return msg_text.lower()

    # Path 3: direct content/text attributes
    if hasattr(message, "text") and message.text:
        return str(message.text).lower()
    if hasattr(message, "content") and message.content:
        return str(message.content).lower()

    # Path 4: fallback to str()
    return str(message).lower()


# Keyword map for dynamic agent routing
_AGENT_KEYWORDS: dict[str, list[str]] = {
    "knowledge": [
        "knowledge", "search", "document", "spec", "data sheet",
        "contract", "find", "retrieve", "look up", "piping", "valve",
        "instrument", "drawing", "p&id", "datasheet", "material",
        "specification", "document", "project",
        "what are the", "tell me about", "show me", "details on",
        "full analysis", "comprehensive", "briefing", "review",
    ],
    "compliance": [
        "compliance", "safety", "regulatory", "standard", "asme",
        "api 6d", "iec", "iso", "nace", "osha", "ped", "sil",
        "certification", "inspection", "audit", "hazard", "risk",
        "requirement", "compliant", "regulation", "meet",
    ],
    "engineering": [
        "cross-cloud", "extended", "cross-project", "bedrock",
        "additional", "historical", "cross-cloud", "aws",
        "compare", "similar project", "lessons learned",
        "cross-cloud database", "similar", "learning",
    ],
    "governance": [
        "governance", "health", "cost", "trace", "monitor",
        "status", "usage", "platform", "metrics", "spend",
        "latency", "error rate", "dashboard", "agent health",
        "platform health", "full analysis", "comprehensive",
    ],
}


def main():
    credential = _get_credential()
    endpoint = os.environ["AZURE_OPENAI_ENDPOINT"]

    # --- Model clients (different models for different roles) ---
    main_client = OpenAIChatClient(
        azure_endpoint=endpoint,
        model=os.environ.get("AZURE_AI_MODEL_DEPLOYMENT_NAME", "gpt-4.1"),
        credential=credential,
    )
    mini_client = OpenAIChatClient(
        azure_endpoint=endpoint,
        model="gpt-4.1-mini",
        credential=credential,
    )

    # --- Tool registry (maps tool names from agents.yaml to actual functions) ---
    TOOL_REGISTRY = {
        "search_knowledge": search_knowledge,
        "analyze_compliance": analyze_compliance,
        "invoke_bedrock_agent": invoke_bedrock_agent,
        "query_governance_costs": query_governance_costs,
        "query_governance_traces": query_governance_traces,
        "query_agent_health": query_agent_health,
    }

    # --- Model client registry (maps model names to clients) ---
    MODEL_CLIENTS = {
        "gpt-4.1": main_client,
        "gpt-4.1-mini": mini_client,
        "o4-mini": main_client,  # o4-mini is called within the compliance tool
        "claude-sonnet-4": main_client,  # Bedrock is called via tool, agent uses main
    }

    # Agent type classification for OTEL attributes
    _AGENT_TYPES: dict[str, str] = {
        "Knowledge Agent": "native",
        "Compliance Agent": "native",
        "External Agent (Cross-Cloud)": "external",
        "Governance Agent": "native",
        "Supervisor Agent": "orchestrator",
        "Synthesizer Agent": "native",
    }

    def _build_agent(name: str) -> Agent:
        """Build an Agent from its YAML definition."""
        defn = AGENT_DEFS[name]
        client = MODEL_CLIENTS.get(defn["model"], main_client)
        tools = [TOOL_REGISTRY[t] for t in defn.get("tools", [])]
        agent_id = f"uaip-{name.lower()}"
        kwargs = dict(
            client=client,
            name=name,
            id=agent_id,
            description=defn["description"],
            instructions=defn["instructions"],
            default_options={"store": False},
        )
        if tools:
            kwargs["tools"] = tools
        return Agent(**kwargs)

    # --- Build agents from YAML definitions ---
    supervisor = _build_agent("Supervisor Agent")
    knowledge_agent = _build_agent("Knowledge Agent")
    compliance_agent = _build_agent("Compliance Agent")
    engineering_agent = _build_agent("External Agent (Cross-Cloud)")
    governance_agent = _build_agent("Governance Agent")
    synthesizer = _build_agent("Synthesizer Agent")

    # --- Build dynamic multi-selection workflow ---
    aggregator = FanInAggregator(id="Aggregator")
    agent_targets = [knowledge_agent, compliance_agent, engineering_agent, governance_agent]

    def select_agents(message, available_ids: list[str]) -> list[str]:
        """Parse the Supervisor's output to determine which agents to invoke."""
        with _tracer.start_as_current_span("supervisor.route") as span:
            span.set_attribute("workflow.type", "multi_agent_supervisor")
            text = _extract_text(message)
            try:
                _LAST_USER_TEXT.set(text)
            except Exception:  # noqa: BLE001 — contextvar set should never fail
                pass

            selected = []
            for aid in available_ids:
                # Extract base name: "Knowledge Agent" → "knowledge", "External Agent (Cross-Cloud)" → "engineering"
                base = aid.lower().split(" agent")[0].strip()
                keywords = _AGENT_KEYWORDS.get(base, [])
                if any(kw in text for kw in keywords):
                    selected.append(aid)

            if not selected:
                logger.warning("No agents matched from supervisor plan, defaulting to Knowledge. Text: %s", text[:200])
                selected = [aid for aid in available_ids if "knowledge" in aid.lower()]
                if not selected:
                    selected = available_ids[:1]

            span.set_attribute("agents.available", len(available_ids))
            span.set_attribute("agents.selected", len(selected))
            span.set_attribute("agents.selected_names", ",".join(selected))
            for name in selected:
                agent_type = _AGENT_TYPES.get(name, "unknown")
                span.add_event(f"agent.selected", attributes={
                    "agent.name": name,
                    "agent.type": agent_type,
                })

            logger.info("Dynamic selection: %d/%d agents → %s", len(selected), len(available_ids), selected)
            return selected

    builder = WorkflowBuilder(
        name="Supervisor",
        description="Unified AI Platform — Multi-Agent Supervisor with dynamic orchestration",
        start_executor=supervisor,
        output_executors=[synthesizer],
    )
    builder.add_multi_selection_edge_group(
        supervisor,
        agent_targets,
        selection_func=select_agents,
    )
    # Each agent routes individually to aggregator (not fan-in, since not all will run)
    for agent in agent_targets:
        builder.add_edge(agent, aggregator)
    builder.add_edge(aggregator, synthesizer)
    workflow = builder.build()

    # Wrap workflow as an agent for the hosting adapter
    workflow_agent = workflow.as_agent()

    logger.info("Starting UAIP Supervisor (fan-out/fan-in workflow) on port 8088")
    server = ResponsesHostServer(workflow_agent)
    server.run()


if __name__ == "__main__":
    main()
