"""
Tests for the voice-to-workflow path: streaming tool-call extraction, workflow
input schemas, and running a workflow as an agent tool.
"""
import uuid
from types import SimpleNamespace

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models.integration import Workflow
from app.models.tool import Tool
from app.services.function_executor import FunctionExecutor
from app.services.workflows.graph import input_schema, load_graph

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def db() -> AsyncSession:
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


BOOKING_GRAPH = {
    "schema_version": 2,
    "nodes": [
        {"id": "trigger", "type": "trigger", "name": "Start",
         "position": {"x": 0, "y": 0},
         "config": {"inputs": [
             {"name": "date", "type": "string",
              "description": "Requested appointment date", "required": True},
             {"name": "notes", "type": "string",
              "description": "Anything else", "required": False},
         ]}},
        {"id": "confirm", "type": "transform", "name": "Build confirmation",
         "position": {"x": 0, "y": 170},
         "config": {"transformations": {"confirmation": "Booked for {{trigger.date}}"}}},
    ],
    "edges": [{"id": "e1", "source": "trigger", "sourceHandle": "out",
               "target": "confirm", "targetHandle": "in"}],
}


# ==================== Streaming tool-call extraction ====================


def _delta_chunk(index, call_id=None, name=None, args=None, content=None):
    """Build a fake OpenAI streaming chunk."""
    tool_calls = None
    if call_id or name or args:
        tool_calls = [SimpleNamespace(
            index=index, id=call_id,
            function=SimpleNamespace(name=name, arguments=args),
        )]
    return SimpleNamespace(choices=[SimpleNamespace(
        delta=SimpleNamespace(content=content, tool_calls=tool_calls))])


class _FakeStream:
    def __init__(self, chunks):
        self._chunks = chunks

    def __aiter__(self):
        async def gen():
            for c in self._chunks:
                yield c
        return gen()


async def test_streaming_emits_accumulated_tool_call(monkeypatch):
    """Tool-call fragments must be reassembled and emitted.

    The stream previously only yielded delta.content, so a tool call was
    silently dropped and no tool ever ran on a live call.
    """
    from app.services.voice.providers.openai_llm import OpenAILLM

    llm = OpenAILLM(api_key="test", model="gpt-4o-mini")

    chunks = [
        _delta_chunk(0, call_id="call_1", name="book_appointment", args='{"da'),
        _delta_chunk(0, args='te": "Tue'),
        _delta_chunk(0, args='sday"}'),
    ]

    async def fake_create(**kwargs):
        return _FakeStream(chunks)

    monkeypatch.setattr(llm.client.chat.completions, "create", fake_create)

    emitted = [c async for c in llm.chat_completion_stream(messages=[])]

    tool_calls = [c for c in emitted if isinstance(c, dict)]
    assert len(tool_calls) == 1
    assert tool_calls[0]["function_call"]["name"] == "book_appointment"
    assert tool_calls[0]["function_call"]["arguments"] == '{"date": "Tuesday"}'


async def test_streaming_still_yields_plain_text(monkeypatch):
    """A normal reply must be unaffected by the tool-call handling."""
    from app.services.voice.providers.openai_llm import OpenAILLM

    llm = OpenAILLM(api_key="test", model="gpt-4o-mini")

    async def fake_create(**kwargs):
        return _FakeStream([
            _delta_chunk(0, content="Hello "),
            _delta_chunk(0, content="there"),
        ])

    monkeypatch.setattr(llm.client.chat.completions, "create", fake_create)

    emitted = [c async for c in llm.chat_completion_stream(messages=[])]

    assert emitted == ["Hello ", "there"]
    assert not any(isinstance(c, dict) for c in emitted)


# ==================== Workflow input schema ====================


async def test_input_schema_from_trigger_inputs():
    schema = input_schema(load_graph(BOOKING_GRAPH))

    assert schema["type"] == "object"
    assert schema["properties"]["date"]["description"] == "Requested appointment date"
    assert schema["required"] == ["date"]
    assert "notes" in schema["properties"]


async def test_input_schema_is_empty_without_declared_inputs():
    schema = input_schema(load_graph({"steps": []}))

    assert schema["properties"] == {}
    assert schema["required"] == []


# ==================== Workflow as a tool ====================


async def _make(db, graph=BOOKING_GRAPH, is_active=True):
    workflow = Workflow(
        user_id=uuid.uuid4(), organization_id=uuid.uuid4(), name="Book appointment",
        trigger_type="manual", trigger_config={}, workflow_steps=graph,
        is_active=is_active, error_handling="stop", max_retries=0, retry_delay=0,
    )
    db.add(workflow)
    await db.commit()
    await db.refresh(workflow)

    tool = Tool(
        id=uuid.uuid4(), user_id=uuid.uuid4(), organization_id=uuid.uuid4(),
        name="Book appointment", description="Books an appointment for the caller",
        category="assistant", tool_type="workflow",
        config={"workflow_id": str(workflow.id)}, is_active=True,
    )
    db.add(tool)
    await db.commit()
    await db.refresh(tool)
    return workflow, tool


async def test_tool_definition_uses_the_workflow_schema(db):
    """The LLM must see the workflow's declared inputs as tool parameters."""
    _, tool = await _make(db)

    definitions = await FunctionExecutor().build_tool_definitions([tool], db=db)

    assert len(definitions) == 1
    definition = definitions[0]
    assert definition["name"] == "book_appointment"
    assert definition["description"] == "Books an appointment for the caller"
    assert "date" in definition["parameters"]["properties"]
    assert definition["parameters"]["required"] == ["date"]


async def test_executing_a_workflow_tool_passes_parameters_through(db):
    """Parameters the LLM extracted become the workflow's trigger data."""
    _, tool = await _make(db)

    result = await FunctionExecutor().execute_global_tool(
        tool=tool, parameters={"date": "Tuesday"}, db=db
    )

    assert result["success"] is True
    inner = result["result"]
    assert inner["success"] is True
    # The transform step interpolated {{trigger.date}}
    assert inner["variables"]["confirmation"] == "Booked for Tuesday"


async def test_workflow_tool_reports_a_failure_instead_of_raising(db):
    """An inactive workflow must surface as a tool error, not blow up the turn."""
    _, tool = await _make(db, is_active=False)

    result = await FunctionExecutor().execute_global_tool(
        tool=tool, parameters={"date": "Tuesday"}, db=db
    )

    # The call itself succeeds; the payload carries the failure.
    assert "error" in result["result"]
    assert "not active" in result["result"]["error"]


async def test_workflow_tool_without_a_linked_workflow(db):
    tool = Tool(
        id=uuid.uuid4(), user_id=uuid.uuid4(), organization_id=uuid.uuid4(),
        name="Broken", description="", category="assistant",
        tool_type="workflow", config={}, is_active=True,
    )
    db.add(tool)
    await db.commit()

    result = await FunctionExecutor().execute_global_tool(
        tool=tool, parameters={}, db=db
    )

    assert "not linked to a workflow" in result["result"]["error"]


async def test_live_channel_is_forwarded_into_the_workflow(db):
    """speak/ask steps must reach the caller, not the simulated channel."""
    graph = {
        "schema_version": 2,
        "nodes": [
            {"id": "trigger", "type": "trigger", "name": "S",
             "position": {"x": 0, "y": 0}, "config": {}},
            {"id": "say", "type": "speak", "name": "Say",
             "position": {"x": 0, "y": 1}, "config": {"message": "Your booking is confirmed"}},
        ],
        "edges": [{"id": "e1", "source": "trigger", "sourceHandle": "out",
                   "target": "say", "targetHandle": "in"}],
    }
    _, tool = await _make(db, graph=graph)

    spoken = []

    class FakeVoiceChannel:
        is_live = True

        async def speak(self, text, voice=None):
            spoken.append(text)

        async def ask(self, *a, **k):
            return None

        async def transfer(self, *a, **k):
            pass

        async def end(self, farewell=None):
            if farewell:
                spoken.append(farewell)

    await FunctionExecutor().execute_global_tool(
        tool=tool, parameters={}, db=db, channel=FakeVoiceChannel()
    )

    assert spoken == ["Your booking is confirmed"]
