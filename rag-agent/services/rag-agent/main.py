# Licensed under the MIT License. See LICENSE file in the project root.
# RAG Knowledge Agent (Microsoft Agent Framework SDK)

"""Entry point for the RAG Knowledge Agent.

Uses Azure AI Search as a native tool for retrieval-augmented generation
over a configurable document corpus. Serves the OpenAI Responses API.
"""

import logging
import os
import sys

from agent_framework import Agent
from agent_framework.openai import OpenAIChatClient
from agent_framework_foundry_hosting import ResponsesHostServer
from azure.identity import ManagedIdentityCredential, DefaultAzureCredential
from dotenv import load_dotenv

from tools.search import search_documents
from tools.document_qa import answer_from_document

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

# Enable GenAI instrumentation via env var
os.environ.setdefault("ENABLE_INSTRUMENTATION", "true")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s",
                    stream=sys.stdout, force=True)
logger = logging.getLogger("uaip.rag-agent")

RAG_AGENT_INSTRUCTIONS = """You are a Knowledge Assistant for the Unified AI Platform.

You help users find and understand information from the organization's
internal document corpus.

## Your Capabilities

You have access to these tools:
- **search_documents** — Search the knowledge base for specifications,
  reports, contracts, policies, and project data.
  Returns the most relevant document excerpts with citations.
- **answer_from_document** — Answer a specific question using context from a
  retrieved document. Use this for follow-up questions about a specific document.

## Guidelines

1. **Always search first**: Use `search_documents` before answering any
   question about projects, specifications, policies, or compliance.
2. **Cite sources**: Always reference the document name and section when
   providing information from the knowledge base.
3. **Be precise**: Users need exact specifications, standards references,
   and actionable data — not general advice.
4. **Acknowledge limitations**: If the knowledge base doesn't contain relevant
   information, say so clearly rather than guessing.
5. **Flag critical info**: Flag any safety-critical or compliance-sensitive
   information with appropriate warnings and reference the relevant standards.
"""


def _get_credential():
    """Return ManagedIdentityCredential in production, DefaultAzureCredential locally."""
    client_id = os.environ.get("AZURE_CLIENT_ID", "")
    if client_id:
        return ManagedIdentityCredential(client_id=client_id)
    return DefaultAzureCredential()


def main():
    credential = _get_credential()

    client = OpenAIChatClient(
        azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
        model=os.environ.get("AZURE_AI_MODEL_DEPLOYMENT_NAME", "gpt-4.1-mini"),
        credential=credential,
    )

    agent = Agent(
        client=client,
        name="Knowledge",
        id="uaip-knowledge",
        instructions=RAG_AGENT_INSTRUCTIONS,
        tools=[
            search_documents,
            answer_from_document,
        ],
        default_options={"store": False},
    )

    logger.info("Starting RAG Knowledge Agent on port 8088")
    server = ResponsesHostServer(agent)
    server.run()


if __name__ == "__main__":
    main()
