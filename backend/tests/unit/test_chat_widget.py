"""
Tests for the chat widget channel.

Covers the models, the AgentChatService text brain (with a stubbed LLM), and
that the SAME tool executor fires a workflow from chat — proving the channel is
agnostic (same brain as voice, different mouth).
"""
import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models.agent import Agent
from app.models.chat import ChatMessage, ChatSession, ChatWidget
from app.models.integration import Workflow
from app.models.tool import Tool, AgentToolAssignment
from app.services.chat.agent_chat_service import AgentChatService
from app.services.voice.providers.base import ChatCompletionResult, FunctionCall

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def db() -> AsyncSession:
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False}, poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


async def _agent(db, system_prompt="You are Aria."):
    agent = Agent(
        user_id=uuid.uuid4(), organization_id=uuid.uuid4(), name="Aria",
        system_prompt=system_prompt, llm_provider="openai", llm_model="gpt-4o-mini",
        is_active=True,
    )
    db.add(agent)
    await db.commit()
    await db.refresh(agent)
    return agent


# ==================== Models ====================


async def test_chat_tables_exist_and_relate(db):
    """The three chat tables create and cascade correctly."""
    agent = await _agent(db)
    widget = ChatWidget(
        agent_id=agent.id, organization_id=agent.organization_id,
        public_key="k" * 20, enabled=True, config={"title": "Hi"},
    )
    db.add(widget)
    await db.commit()
    await db.refresh(widget)

    session = ChatSession(
        widget_id=widget.id, agent_id=agent.id,
        organization_id=agent.organization_id, visitor_id="v1",
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)

    db.add(ChatMessage(session_id=session.id, role="user", content="hello"))
    await db.commit()

    rows = (await db.execute(
        select(ChatMessage).where(ChatMessage.session_id == session.id)
    )).scalars().all()
    assert len(rows) == 1
    assert rows[0].content == "hello"


# ==================== AgentChatService (stubbed LLM) ====================


def _stub_llm(service, replies):
    """Replace the service's LLM with a scripted sequence of completions."""
    calls = {"n": 0}

    async def fake_chat(messages, **kwargs):
        r = replies[min(calls["n"], len(replies) - 1)]
        calls["n"] += 1
        return r

    service.llm.chat = fake_chat  # type: ignore
    return calls


async def test_plain_text_reply(db):
    agent = await _agent(db)
    service = AgentChatService(db)
    _stub_llm(service, [ChatCompletionResult(content="Hello there!")])

    result = await service.respond(agent, history=[], user_message="hi")
    assert result.reply == "Hello there!"
    assert result.tool_name is None


async def test_history_and_system_prompt_are_used(db):
    agent = await _agent(db, system_prompt="You are Bob.")
    service = AgentChatService(db)
    captured = {}

    async def fake_chat(messages, **kwargs):
        captured["messages"] = messages
        return ChatCompletionResult(content="ok")

    service.llm.chat = fake_chat  # type: ignore

    await service.respond(
        agent,
        history=[{"role": "user", "content": "earlier"},
                 {"role": "assistant", "content": "sure"}],
        user_message="now",
    )

    roles = [m.role for m in captured["messages"]]
    assert roles[0] == "system"
    assert "You are Bob." in captured["messages"][0].content
    # Text-channel guidance is appended so it writes, not speaks.
    assert "text" in captured["messages"][0].content.lower()
    # History + new message present, in order.
    assert captured["messages"][-1].content == "now"
    assert any(m.content == "earlier" for m in captured["messages"])


async def test_chat_fires_a_workflow_tool(db):
    """The client's core: a chat message triggers the tool → workflow chain."""
    agent = await _agent(db)

    # A workflow whose transform confirms a booking.
    graph = {
        "schema_version": 2,
        "nodes": [
            {"id": "trigger", "type": "trigger", "name": "S",
             "position": {"x": 0, "y": 0},
             "config": {"inputs": [
                 {"name": "day", "type": "string", "description": "Day",
                  "required": True}]}},
            {"id": "confirm", "type": "transform", "name": "C",
             "position": {"x": 0, "y": 1},
             "config": {"transformations": {"confirmation": "Booked {{trigger.day}}"}}},
        ],
        "edges": [{"id": "e1", "source": "trigger", "sourceHandle": "out",
                   "target": "confirm", "targetHandle": "in"}],
    }
    wf = Workflow(user_id=agent.user_id, organization_id=agent.organization_id,
                  name="Book", trigger_type="manual", trigger_config={},
                  workflow_steps=graph, is_active=True,
                  error_handling="stop", max_retries=0, retry_delay=0)
    db.add(wf)
    await db.commit()
    await db.refresh(wf)

    tool = Tool(id=uuid.uuid4(), user_id=agent.user_id,
                organization_id=agent.organization_id, name="book_it",
                description="Books", category="assistant", tool_type="workflow",
                config={"workflow_id": str(wf.id)}, is_active=True)
    db.add(tool)
    await db.commit()
    await db.refresh(tool)
    db.add(AgentToolAssignment(agent_id=agent.id, tool_id=tool.id))
    await db.commit()

    service = AgentChatService(db)
    import json

    # Turn 1: the model asks for the tool. Turn 2: it answers from the result.
    _stub_llm(service, [
        ChatCompletionResult(
            content="",
            function_call=FunctionCall(name="book_it",
                                       arguments=json.dumps({"day": "Tuesday"})),
        ),
        ChatCompletionResult(content="You're booked for Tuesday."),
    ])

    result = await service.respond(agent, history=[], user_message="book me Tuesday")

    assert result.tool_name == "book_it"
    assert "Tuesday" in result.reply


async def test_same_executor_as_voice():
    """Channel-agnostic: chat uses execute_global_tool, same as voice."""
    import inspect
    from app.services.chat import agent_chat_service

    src = inspect.getsource(agent_chat_service)
    assert "execute_global_tool" in src
    assert "build_tool_definitions" in src
