# Licensed under the MIT License. See LICENSE file in the project root.
"""Document QA tool — answer follow-up questions using document context."""

import os

import httpx
from agent_framework import tool
from azure.identity import ManagedIdentityCredential, DefaultAzureCredential
from pydantic import Field
from typing_extensions import Annotated


@tool(approval_mode="never_require")
def answer_from_document(
    question: Annotated[str, Field(description="The specific question to answer from the document context.")],
    document_title: Annotated[str, Field(description="Title of the document to query (from a previous search result).")],
) -> str:
    """Answer a specific question using context from a previously retrieved document.

    Use this for follow-up questions about a document found via search_documents.
    Retrieves the full document content and uses the LLM to answer the question.
    """
    search_endpoint = os.environ.get("AZURE_AI_SEARCH_ENDPOINT", "")
    index_name = os.environ.get("AZURE_AI_SEARCH_INDEX", "knowledge-base-docs")

    if not search_endpoint:
        return "AI Search not configured."

    try:
        client_id = os.environ.get("AZURE_CLIENT_ID", "")
        credential = ManagedIdentityCredential(client_id=client_id) if client_id else DefaultAzureCredential()
        token = credential.get_token("https://search.azure.com/.default")

        # Search for the specific document by title
        url = f"{search_endpoint}/indexes/{index_name}/docs/search?api-version=2024-07-01"
        body = {
            "search": document_title,
            "queryType": "simple",
            "top": 1,
            "select": "title,content,source,category",
        }

        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                url,
                json=body,
                headers={
                    "Authorization": f"Bearer {token.token}",
                    "Content-Type": "application/json",
                },
            )
            response.raise_for_status()
            data = response.json()

        results = data.get("value", [])
        if not results:
            return f"Document '{document_title}' not found in the knowledge base."

        # Combine content from matching chunks
        context = "\n\n".join(doc.get("content", "") for doc in results)

        return (
            f"**Document: {document_title}**\n\n"
            f"Based on the document content:\n{context[:2000]}\n\n"
            f"(Use this context to answer: {question})"
        )

    except Exception as e:
        return f"Document query failed: {e}"
