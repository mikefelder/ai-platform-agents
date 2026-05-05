# Licensed under the MIT License. See LICENSE file in the project root.
"""AI Search tool — keyword search over indexed documents."""

import json
import logging
import os
import sys

import httpx
from agent_framework import tool
from azure.identity import ManagedIdentityCredential, DefaultAzureCredential
from pydantic import Field
from typing_extensions import Annotated

logging.basicConfig(level=logging.INFO, stream=sys.stdout, force=True)
logger = logging.getLogger("uaip.search")


def _get_search_token() -> str:
    """Get a bearer token for Azure AI Search using managed identity."""
    client_id = os.environ.get("AZURE_CLIENT_ID", "")
    credential = ManagedIdentityCredential(client_id=client_id) if client_id else DefaultAzureCredential()
    token = credential.get_token("https://search.azure.com/.default")
    return token.token


@tool(approval_mode="never_require")
def search_documents(
    query: Annotated[str, Field(description="Search query for indexed documents (specs, reports, policies, contracts).")],
    top: Annotated[int, Field(description="Number of results to return (1-10).", ge=1, le=10)] = 5,
) -> str:
    """Search the knowledge base using hybrid vector + semantic search.

    Searches across specifications, compliance reports, contracts, policies,
    and project documentation. Returns the most relevant excerpts with
    document citations.
    """
    search_endpoint = os.environ.get("AZURE_AI_SEARCH_ENDPOINT", "")
    index_name = os.environ.get("AZURE_AI_SEARCH_INDEX", "knowledge-base-docs")

    if not search_endpoint:
        return "AI Search not configured (AZURE_AI_SEARCH_ENDPOINT not set)."

    try:
        logger.info("SEARCH: query='%s', endpoint='%s', index='%s'", query, search_endpoint, index_name)
        token = _get_search_token()
        logger.info("SEARCH: got token (len=%d)", len(token))

        # Use the REST API for search (simple keyword; semantic requires S2+ tier)
        url = f"{search_endpoint}/indexes/{index_name}/docs/search?api-version=2024-07-01"

        body = {
            "search": query,
            "queryType": "simple",
            "top": top,
            "select": "title,content,source,category",
        }

        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                url,
                json=body,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
            )
            logger.info("SEARCH: HTTP %d, body[:200]=%s", response.status_code, response.text[:200])
            response.raise_for_status()
            data = response.json()

        results = data.get("value", [])
        logger.info("SEARCH: got %d results", len(results))
        if not results:
            return f"No documents found matching: '{query}'"

        # Format results with citations
        formatted = []
        for i, doc in enumerate(results, 1):
            title = doc.get("title", "Untitled")
            source = doc.get("source", "Unknown")
            category = doc.get("category", "General")
            content = doc.get("content", "")[:500]  # Truncate for readability

            formatted.append(
                f"**[{i}] {title}**\n"
                f"Source: {source} | Category: {category}\n"
                f"{content}\n"
            )

        return "\n---\n".join(formatted)

    except httpx.HTTPStatusError as e:
        logger.error("SEARCH: HTTP error %d: %s", e.response.status_code, e.response.text[:300])
        return f"Search failed (HTTP {e.response.status_code}): {e.response.text[:200]}"
    except Exception as e:
        logger.error("SEARCH: exception: %s", e)
        return f"Search unavailable: {e}"
