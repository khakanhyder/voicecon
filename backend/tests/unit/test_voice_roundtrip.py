"""
End-to-end proof of the voice round-trip:

  caller speaks -> LLM picks a tool -> workflow runs -> workflow calls a real
  third-party HTTP API -> data returns -> LLM speaks that data back.

A real local HTTP server stands in for the third-party API, so the network hop
is genuinely exercised rather than mocked away.
"""
import json
import uuid
from types import SimpleNamespace

import pytest
import pytest_asyncio
from aiohttp import web
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models.integration import Workflow
from app.models.tool import Tool
from app.services.function_executor import FunctionExecutor
from app.services.voice.providers.base import ChatMessage

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


@pytest_asyncio.fixture
async def crm_api():
    """A stand-in third-party API the workflow will call."""
    received = {}

    async def handler(request):
        received["body"] = await request.json()
        # What a real booking API would return
        return web.json_response(
            {"booking_id": "BK-4471", "slot": "Tuesday 3:00 PM", "status": "confirmed"}
        )

    app = web.Application()
    app.router.add_post("/book", handler)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = runner.addresses[0][1]

    yield SimpleNamespace(url=f"http://127.0.0.1:{port}/book", received=received)

    await runner.cleanup()


async def _build(db, api_url):
    """A workflow that calls the third-party API, plus a tool pointing at it."""
    graph = {
        "schema_version": 2,
        "nodes": [
            {"id": "trigger", "type": "trigger", "name": "Start",
             "position": {"x": 0, "y": 0},
             "config": {"inputs": [
                 {"name": "date", "type": "string",
                  "description": "Requested day", "required": True},
             ]}},
            # The third-party call
            {"id": "api", "type": "webhook", "name": "Create booking",
             "position": {"x": 0, "y": 170},
             "config": {"url": api_url, "method": "POST",
                        "body": '{"date": "{{trigger.date}}"}'}},
            # Shape the reply for the agent
            {"id": "shape", "type": "transform", "name": "Build reply",
             "position": {"x": 0, "y": 340},
             "config": {"transformations": {
                 "booking_reference": "{{steps.api.body.booking_id}}",
                 "slot": "{{steps.api.body.slot}}",
             }}},
        ],
        "edges": [
            {"id": "e1", "source": "trigger", "sourceHandle": "out",
             "target": "api", "targetHandle": "in"},
            {"id": "e2", "source": "api", "sourceHandle": "out",
             "target": "shape", "targetHandle": "in"},
        ],
    }

    workflow = Workflow(
        user_id=uuid.uuid4(), organization_id=uuid.uuid4(), name="Book appointment",
        trigger_type="manual", trigger_config={}, workflow_steps=graph,
        is_active=True, error_handling="stop", max_retries=0, retry_delay=0,
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


async def test_workflow_tool_calls_third_party_api_and_returns_data(db, crm_api):
    """The workflow must reach the API and hand its data back to the caller."""
    _, tool = await _build(db, crm_api.url)

    result = await FunctionExecutor().execute_global_tool(
        tool=tool, parameters={"date": "Tuesday"}, db=db
    )

    # The API actually received the parameter the caller supplied
    assert crm_api.received["body"] == {"date": "Tuesday"}

    inner = result["result"]
    assert inner["success"] is True
    # ...and its response came back through the workflow
    assert inner["variables"]["booking_reference"] == "BK-4471"
    assert inner["variables"]["slot"] == "Tuesday 3:00 PM"


async def test_agent_speaks_the_data_returned_by_the_workflow(db, crm_api):
    """The full turn: tool call -> workflow -> API -> agent's spoken reply.

    Drives the real _generate_with_functions loop with a scripted LLM: the
    first turn requests the tool, the second sees the tool result and produces
    the sentence the caller hears.
    """
    from app.services.websocket.voice_session import VoiceSession

    _, tool = await _build(db, crm_api.url)

    turns = []

    async def fake_chat_stream(messages, **kwargs):
        turns.append(list(messages))
        if len(turns) == 1:
            # The model decides to call the tool and extracts the parameter
            yield {
                "function_call": {
                    "id": "call_1",
                    "name": "book_appointment",
                    "arguments": json.dumps({"date": "Tuesday"}),
                }
            }
            return

        # Second turn: the tool result is in context, so answer from it.
        tool_msg = next(m for m in messages if m.role == "function")
        payload = json.loads(tool_msg.content.split("returned: ", 1)[1])
        variables = payload["variables"]
        yield (
            f"You're all set for {variables['slot']}. "
            f"Your reference is {variables['booking_reference']}."
        )

    # A session with only the pieces this loop touches.
    session = VoiceSession.__new__(VoiceSession)
    session.db = db
    session.call_id = "test-call"
    session.agent_functions = []
    session.agent_tools = [tool]
    session.function_executor = FunctionExecutor()
    session.llm_service = SimpleNamespace(chat_stream=fake_chat_stream)

    spoken = []

    async def fake_speak(text):
        spoken.append(text)

    session.speak = fake_speak

    reply = await session._generate_with_functions(
        messages=[ChatMessage(role="user", content="Book me an appointment Tuesday")],
        provider="openai",
        model="gpt-4o-mini",
        temperature=0.7,
        functions=[],
    )

    # The caller heard a holding line while the workflow ran
    assert spoken == ["One moment while I check that."]

    # The agent's reply carries the third-party API's real data
    assert "Tuesday 3:00 PM" in reply
    assert "BK-4471" in reply

    # The second LLM turn saw both the assistant's tool request and its result,
    # in that order — an orphan tool message would be rejected by OpenAI.
    roles = [m.role for m in turns[1]]
    assert roles.index("assistant") < roles.index("function")
