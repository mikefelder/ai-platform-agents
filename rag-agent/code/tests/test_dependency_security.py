import pytest
from langchain.agents import AgentExecutor, Tool, ZeroShotAgent
from langchain.chains.llm import LLMChain
from langchain.memory import ConversationBufferMemory
from langchain_core.documents import Document
from langchain_core.load import dumpd, dumps, load, loads
from langchain_core.language_models.fake import FakeListLLM
from langchain_core.messages import AIMessage


@pytest.mark.parametrize("serialize,deserialize", [(dumpd, load), (dumps, loads)])
@pytest.mark.parametrize("as_message", [False, True])
def test_serialized_user_data_cannot_resolve_environment_secrets(
    monkeypatch, serialize, deserialize, as_message
):
    secret_name = "LANGCHAIN_SERIALIZATION_TEST_SECRET"
    monkeypatch.setenv(secret_name, "synthetic-secret-must-not-be-resolved")
    untrusted_data = {
        "nested": [{"lc": 1, "type": "secret", "id": [secret_name]}]
    }
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
