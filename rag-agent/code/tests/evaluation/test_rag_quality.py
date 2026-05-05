"""
RAG quality evaluation gate using azure-ai-evaluation.

Reads from data/rag_golden_dataset.jsonl and asserts mean scores >= 3.0
for groundedness, retrieval, and relevance.

Requires:
  AZURE_OPENAI_ENDPOINT      — AI Foundry / Azure OpenAI endpoint
  AZURE_OPENAI_DEPLOYMENT_NAME — Model deployment to use as evaluator judge (e.g. gpt-4o-mini)

Skipped automatically when env vars are not set (e.g. local dev without credentials).

Run:
  pytest code/tests/evaluation/test_rag_quality.py -v
  # or via Makefile:
  make eval
"""

import json
import os
import pathlib

import pytest

REQUIRED_ENV = ("AZURE_OPENAI_ENDPOINT", "AZURE_OPENAI_DEPLOYMENT_NAME")
GOLDEN_DATASET = pathlib.Path(__file__).parent / "data" / "rag_golden_dataset.jsonl"
PASS_THRESHOLD = 3.0  # Scores are 1–5; anything below 3 is poor quality


def _env_missing() -> bool:
    return any(os.environ.get(k, "").strip() == "" for k in REQUIRED_ENV)


@pytest.mark.skipif(_env_missing(), reason="Azure OpenAI env vars not set — skipping evaluation gate")
def test_rag_groundedness_mean_score():
    """Mean groundedness score across the golden dataset must be >= 3.0."""
    from azure.ai.evaluation import AzureOpenAIModelConfiguration, GroundednessEvaluator, evaluate

    model_config = AzureOpenAIModelConfiguration(
        azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
        azure_deployment=os.environ["AZURE_OPENAI_DEPLOYMENT_NAME"],
        api_version=os.environ.get("AZURE_OPENAI_API_VERSION", "2024-08-01-preview"),
    )

    result = evaluate(
        data=str(GOLDEN_DATASET),
        evaluators={"groundedness": GroundednessEvaluator(model_config)},
        evaluator_config={
            "groundedness": {
                "column_mapping": {
                    "query": "${data.query}",
                    "context": "${data.context}",
                    "response": "${data.response}",
                }
            }
        },
    )

    mean_score = result["metrics"].get("groundedness.groundedness", 0.0)
    assert mean_score >= PASS_THRESHOLD, (
        f"Groundedness mean score {mean_score:.2f} is below threshold {PASS_THRESHOLD}. "
        "Check that responses are grounded in the provided context."
    )


@pytest.mark.skipif(_env_missing(), reason="Azure OpenAI env vars not set — skipping evaluation gate")
def test_rag_retrieval_mean_score():
    """Mean retrieval score across the golden dataset must be >= 3.0."""
    from azure.ai.evaluation import AzureOpenAIModelConfiguration, RetrievalEvaluator, evaluate

    model_config = AzureOpenAIModelConfiguration(
        azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
        azure_deployment=os.environ["AZURE_OPENAI_DEPLOYMENT_NAME"],
        api_version=os.environ.get("AZURE_OPENAI_API_VERSION", "2024-08-01-preview"),
    )

    result = evaluate(
        data=str(GOLDEN_DATASET),
        evaluators={"retrieval": RetrievalEvaluator(model_config)},
        evaluator_config={
            "retrieval": {
                "column_mapping": {
                    "query": "${data.query}",
                    "context": "${data.context}",
                }
            }
        },
    )

    mean_score = result["metrics"].get("retrieval.retrieval", 0.0)
    assert mean_score >= PASS_THRESHOLD, (
        f"Retrieval mean score {mean_score:.2f} is below threshold {PASS_THRESHOLD}. "
        "Check that retrieved context is relevant to the query."
    )


@pytest.mark.skipif(_env_missing(), reason="Azure OpenAI env vars not set — skipping evaluation gate")
def test_rag_relevance_mean_score():
    """Mean relevance score across the golden dataset must be >= 3.0."""
    from azure.ai.evaluation import AzureOpenAIModelConfiguration, RelevanceEvaluator, evaluate

    model_config = AzureOpenAIModelConfiguration(
        azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
        azure_deployment=os.environ["AZURE_OPENAI_DEPLOYMENT_NAME"],
        api_version=os.environ.get("AZURE_OPENAI_API_VERSION", "2024-08-01-preview"),
    )

    result = evaluate(
        data=str(GOLDEN_DATASET),
        evaluators={"relevance": RelevanceEvaluator(model_config)},
        evaluator_config={
            "relevance": {
                "column_mapping": {
                    "query": "${data.query}",
                    "response": "${data.response}",
                }
            }
        },
    )

    mean_score = result["metrics"].get("relevance.relevance", 0.0)
    assert mean_score >= PASS_THRESHOLD, (
        f"Relevance mean score {mean_score:.2f} is below threshold {PASS_THRESHOLD}. "
        "Check that responses directly address the query."
    )


@pytest.mark.skipif(_env_missing(), reason="Azure OpenAI env vars not set — skipping evaluation gate")
def test_rag_all_metrics_combined():
    """
    Run groundedness, retrieval, and relevance in a single evaluate() call.
    All three mean scores must be >= 3.0. This is the primary CI gate.
    """
    from azure.ai.evaluation import (
        AzureOpenAIModelConfiguration,
        GroundednessEvaluator,
        RelevanceEvaluator,
        RetrievalEvaluator,
        evaluate,
    )

    model_config = AzureOpenAIModelConfiguration(
        azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
        azure_deployment=os.environ["AZURE_OPENAI_DEPLOYMENT_NAME"],
        api_version=os.environ.get("AZURE_OPENAI_API_VERSION", "2024-08-01-preview"),
    )

    result = evaluate(
        data=str(GOLDEN_DATASET),
        evaluators={
            "groundedness": GroundednessEvaluator(model_config),
            "retrieval": RetrievalEvaluator(model_config),
            "relevance": RelevanceEvaluator(model_config),
        },
        evaluator_config={
            "groundedness": {
                "column_mapping": {
                    "query": "${data.query}",
                    "context": "${data.context}",
                    "response": "${data.response}",
                }
            },
            "retrieval": {
                "column_mapping": {
                    "query": "${data.query}",
                    "context": "${data.context}",
                }
            },
            "relevance": {
                "column_mapping": {
                    "query": "${data.query}",
                    "response": "${data.response}",
                }
            },
        },
    )

    metrics = result["metrics"]
    failures = []

    for metric_key in (
        "groundedness.groundedness",
        "retrieval.retrieval",
        "relevance.relevance",
    ):
        score = metrics.get(metric_key, 0.0)
        if score < PASS_THRESHOLD:
            failures.append(f"{metric_key}: {score:.2f} (threshold {PASS_THRESHOLD})")

    assert not failures, (
        "RAG quality gate failed. The following metrics are below threshold:\n"
        + "\n".join(f"  - {f}" for f in failures)
    )


def test_golden_dataset_is_valid():
    """Sanity check: golden dataset file exists and all rows have required fields."""
    assert GOLDEN_DATASET.exists(), f"Golden dataset not found: {GOLDEN_DATASET}"

    rows = []
    with open(GOLDEN_DATASET) as f:
        for line_num, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            rows.append(row)
            for field in ("query", "context", "response"):
                assert field in row, f"Line {line_num}: missing field '{field}'"
                assert isinstance(row[field], str) and row[field].strip(), (
                    f"Line {line_num}: field '{field}' is empty"
                )

    assert len(rows) >= 5, f"Expected at least 5 rows in golden dataset, got {len(rows)}"
