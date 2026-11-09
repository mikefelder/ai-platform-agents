from importlib.metadata import version

import pytest
from packaging.version import Version
from langchain_classic.agents import AgentExecutor, ZeroShotAgent
from langchain_classic.chains.llm import LLMChain
from langchain_classic.memory import ConversationBufferMemory
from langchain_core.tools import Tool
from langchain_core.documents import Document
from langchain_core.load import dumpd, dumps, load, loads
from langchain_core.language_models.fake import FakeListLLM
from langchain_core.messages import AIMessage


@pytest.mark.parametrize(
    "package,minimum",
    [
        ("langchain-classic", "1.0.7"),
        ("langsmith", "0.8.0"),
        ("langchain-core", "1.2.22"),
        ("langchain-openai", "1.1.14"),
        ("langchain-text-splitters", "1.1.2"),
        ("oauthlib", "4.0.1"),
        ("httpx2", "2.12.0"),
        ("httpcore2", "2.10.0"),
        ("dnspython", "2.9.0"),
        ("opentelemetry-api", "1.45.1"),
        ("filelock", "4.2.1"),
        ("virtualenv", "21.14.9"),
        ("nbconvert", "7.17.2"),
        ("black", "26.10.1"),
    ],
)
def test_dependency_versions_include_reported_security_fixes(package, minimum):
    assert Version(version(package)) >= Version(minimum)


@pytest.mark.parametrize("serialize,deserialize", [(dumpd, load), (dumps, loads)])
@pytest.mark.parametrize("as_message", [False, True])
def test_serialized_user_data_cannot_resolve_environment_secrets(
    monkeypatch, serialize, deserialize, as_message
):
    secret_name = "LANGCHAIN_SERIALIZATION_TEST_SECRET"
    monkeypatch.setenv(secret_name, "synthetic-secret-must-not-be-resolved")
    untrusted_data = {"nested": [{"lc": 1, "type": "secret", "id": [secret_name]}]}
    value = (
        AIMessage(content="Test response", additional_kwargs=untrusted_data)
        if as_message
        else untrusted_data
    )

    restored = deserialize(serialize(value), secrets_from_env=True)

    assert restored == value
    if as_message:
        assert restored.additional_kwargs == untrusted_data


@pytest.mark.parametrize("serialize,deserialize", [(dumpd, load), (dumps, loads)])
def test_standard_document_serialization_remains_supported(serialize, deserialize):
    document = Document(page_content="Test document", metadata={"source": "test"})

    assert deserialize(serialize(document)) == document


def test_legacy_agent_can_execute_a_tool_with_patched_dependencies():
    tools = [
        Tool(
            name="lookup",
            func=lambda question: f"Answer for {question}",
            description="Look up an answer.",
            return_direct=True,
        )
    ]
    prompt = ZeroShotAgent.create_prompt(
        tools,
        suffix="{chat_history}\nQuestion: {input}\n{agent_scratchpad}",
        input_variables=["input", "chat_history", "agent_scratchpad"],
    )
    llm = FakeListLLM(
        responses=["Thought: Look up the answer.\nAction: lookup\nAction Input: test"]
    )
    agent = ZeroShotAgent(llm_chain=LLMChain(llm=llm, prompt=prompt), tools=tools)
    executor = AgentExecutor.from_agent_and_tools(
        agent=agent,
        tools=tools,
        memory=ConversationBufferMemory(
            memory_key="chat_history", return_messages=True
        ),
    )

    assert executor.invoke({"input": "test"})["output"] == "Answer for test"


def test_azure_openai_integrations_initialize_with_the_upgraded_sdk():
    from langchain_openai import AzureChatOpenAI, AzureOpenAIEmbeddings
    from semantic_kernel.connectors.ai.open_ai import AzureChatCompletion

    config = {
        "azure_endpoint": "https://security-regression.openai.azure.com",
        "api_key": "synthetic-test-key",
        "api_version": "2024-10-21",
        "azure_deployment": "test-deployment",
    }

    chat = AzureChatOpenAI(**config)
    embeddings = AzureOpenAIEmbeddings(**config)
    service = AzureChatCompletion(
        endpoint=config["azure_endpoint"],
        api_key=config["api_key"],
        api_version=config["api_version"],
        deployment_name=config["azure_deployment"],
    )

    assert chat.root_client.base_url.host == "security-regression.openai.azure.com"
    assert embeddings.client is not None
    assert service.client.base_url.host == "security-regression.openai.azure.com"


def test_opentelemetry_can_export_spans_with_the_upgraded_api():
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
        InMemorySpanExporter,
    )

    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    try:
        with provider.get_tracer(__name__).start_as_current_span(
            "dependency-regression"
        ):
            pass

        assert [span.name for span in exporter.get_finished_spans()] == [
            "dependency-regression"
        ]
    finally:
        provider.shutdown()
