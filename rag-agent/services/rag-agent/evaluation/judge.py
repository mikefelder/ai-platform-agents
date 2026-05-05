"""LLM-as-Judge evaluation pipeline for RAG Knowledge Agent.

Scores agent responses on three dimensions using Azure OpenAI:
  1. Groundedness — Is the response grounded in the retrieved documents?
  2. Relevance — Does the response actually answer the question?
  3. Completeness — Does it cover all relevant aspects?

Usage:
  python -m evaluation.judge --endpoint https://rag-agent.<fqdn> --questions evaluation/test_questions.json

Environment:
  AZURE_OPENAI_ENDPOINT — Azure OpenAI endpoint
  AZURE_CLIENT_ID       — Managed identity client ID (optional)
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone

import httpx
from azure.identity import DefaultAzureCredential

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("rag.evaluation")

# Default test questions with expected topics
DEFAULT_QUESTIONS = [
    {
        "query": "What are the product specifications for Sample Project?",
        "expected_topics": ["SPEC-001", "specification", "requirements"],
    },
    {
        "query": "What compliance requirements apply to our operations?",
        "expected_topics": ["compliance", "audit", "requirements"],
    },
    {
        "query": "What are the material standards in the reference guide?",
        "expected_topics": ["STD-002", "material", "standard"],
    },
    {
        "query": "Summarize the equipment maintenance data sheet",
        "expected_topics": ["DS-003", "equipment", "maintenance"],
    },
    {
        "query": "What does the AI Governance Policy cover?",
        "expected_topics": ["POL-GOV-001", "governance", "policy"],
    },
]

JUDGE_PROMPT = """You are an expert evaluation judge. Score the following AI agent response on three dimensions.

**Question asked:** {question}

**Agent response:** {response}

**Expected topics that should be covered:** {expected_topics}

Score each dimension from 1-5:
- **Groundedness** (1-5): Is the response grounded in specific documents/sources? Does it cite references?
- **Relevance** (1-5): Does it directly answer the question asked?
- **Completeness** (1-5): Does it cover the expected topics comprehensively?

Respond in JSON format only:
{{"groundedness": <int>, "relevance": <int>, "completeness": <int>, "reasoning": "<brief explanation>"}}"""


def query_agent(endpoint: str, question: str) -> str:
    """Send a question to the RAG agent and get the response."""
    with httpx.Client(timeout=120.0) as client:
        resp = client.post(
            f"{endpoint.rstrip('/')}/responses",
            json={"input": question},
            headers={"Content-Type": "application/json"},
        )
        resp.raise_for_status()
        data = resp.json()
        outputs = data.get("output", [])
        messages = [o for o in outputs if o.get("type") == "message" and o.get("role") == "assistant"]
        if messages:
            content = messages[-1].get("content", [{}])
            return content[0].get("text", "") if content else str(data)
        return str(data)


def judge_response(
    question: str, response: str, expected_topics: list[str],
    openai_endpoint: str, credential,
) -> dict:
    """Use LLM-as-Judge to score the response."""
    prompt = JUDGE_PROMPT.format(
        question=question,
        response=response[:3000],  # Truncate to avoid token limits
        expected_topics=", ".join(expected_topics),
    )

    token = credential.get_token("https://cognitiveservices.azure.com/.default")
    url = f"{openai_endpoint}openai/deployments/gpt-4.1/chat/completions?api-version=2025-04-01-preview"

    with httpx.Client(timeout=60.0) as client:
        resp = client.post(
            url,
            json={
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 300,
                "temperature": 0.0,
            },
            headers={
                "Authorization": f"Bearer {token.token}",
                "Content-Type": "application/json",
            },
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"].strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[1].rsplit("```", 1)[0]
        return json.loads(content)


def run_evaluation(
    agent_endpoint: str,
    questions: list[dict] | None = None,
    openai_endpoint: str | None = None,
) -> dict:
    """Run the full evaluation pipeline."""
    questions = questions or DEFAULT_QUESTIONS
    openai_endpoint = openai_endpoint or os.environ.get("AZURE_OPENAI_ENDPOINT", "")
    credential = DefaultAzureCredential()

    results = []
    totals = {"groundedness": 0, "relevance": 0, "completeness": 0}

    for i, q in enumerate(questions, 1):
        logger.info("Evaluating question %d/%d: %s", i, len(questions), q["query"][:60])

        try:
            response = query_agent(agent_endpoint, q["query"])
            scores = judge_response(
                q["query"], response, q.get("expected_topics", []),
                openai_endpoint, credential,
            )
            for k in totals:
                totals[k] += scores.get(k, 0)

            results.append({
                "question": q["query"],
                "expected_topics": q.get("expected_topics", []),
                "response_preview": response[:200],
                "scores": scores,
            })
            logger.info("  Scores: G=%d R=%d C=%d", scores.get("groundedness", 0), scores.get("relevance", 0), scores.get("completeness", 0))
        except Exception as e:
            logger.error("  Failed: %s", e)
            results.append({
                "question": q["query"],
                "error": str(e),
                "scores": {"groundedness": 0, "relevance": 0, "completeness": 0},
            })

    n = len(questions)
    summary = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "agent_endpoint": agent_endpoint,
        "total_questions": n,
        "average_scores": {k: round(v / n, 2) if n > 0 else 0 for k, v in totals.items()},
        "overall_score": round(sum(totals.values()) / (n * 3), 2) if n > 0 else 0,
        "results": results,
    }

    return summary


def main():
    parser = argparse.ArgumentParser(description="LLM-as-Judge evaluation for RAG Agent")
    parser.add_argument("--endpoint", required=True, help="RAG agent endpoint URL")
    parser.add_argument("--questions", help="Path to JSON file with test questions")
    parser.add_argument("--output", help="Path to write results JSON")
    args = parser.parse_args()

    questions = None
    if args.questions:
        with open(args.questions) as f:
            questions = json.load(f)

    summary = run_evaluation(args.endpoint, questions)

    if args.output:
        with open(args.output, "w") as f:
            json.dump(summary, f, indent=2)
        logger.info("Results written to %s", args.output)
    else:
        print(json.dumps(summary, indent=2))

    overall = summary["average_scores"]
    logger.info(
        "Overall: Groundedness=%.1f Relevance=%.1f Completeness=%.1f (%.1f/5.0)",
        overall["groundedness"], overall["relevance"], overall["completeness"],
        summary["overall_score"],
    )


if __name__ == "__main__":
    main()
