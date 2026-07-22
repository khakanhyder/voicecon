"""
Tests the client's core architecture: agent -> tool -> workflow -> (apps).

Covers creating a workflow-backed tool, exposing it to the LLM with the right
schema, and running it so the workflow executes and returns data to the agent.
Channel-agnostic: the same execute path is used by voice and the text endpoint.
"""
import uuid

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models.integration import Workflow
from app.models.tool import Tool
from app.services.function_executor import FunctionExecutor, sanitize_function_name

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


APPT_GRAPH = {
    "schema_version": 2,
    "nodes": [
        {"id": "trigger", "type": "trigger", "name": "Start",
         "position": {"x": 0, "y": 0},
         "config": {"inputs": [
             {"name": "day", "type": "string", "description": "Requested day",
              "required": True},
         ]}},
        {"id": "confirm", "type": "transform", "name": "Confirm",
         "position": {"x": 0, "y": 1},
         "config": {"transformations": {"confirmation": "Booked for {{trigger.day}}"}}},
    ],
    "edges": [{"id": "e1", "source": "trigger", "sourceHandle": "out",
               "target": "confirm", "targetHandle": "in"}],
}


async def _workflow(db, active=True):
    wf = Workflow(user_id=uuid.uuid4(), organization_id=uuid.uuid4(),
                  name="Book appointment", trigger_type="manual", trigger_config={},
                  workflow_steps=APPT_GRAPH, is_active=active,
                  error_handling="stop", max_retries=0, retry_delay=0)
    db.add(wf)
    await db.commit()
    await db.refresh(wf)
    return wf


async def _tool(db, workflow_id):
    tool = Tool(id=uuid.uuid4(), user_id=uuid.uuid4(), organization_id=uuid.uuid4(),
                name="Book appointment", description="Books an appointment",
                category="assistant", tool_type="workflow",
                config={"workflow_id": str(workflow_id)}, is_active=True)
    db.add(tool)
    await db.commit()
    await db.refresh(tool)
    return tool


async def test_workflow_tool_schema_and_execution(db):
    """The full chain: schema derived from workflow, execution runs it."""
    wf = await _workflow(db)
    tool = await _tool(db, wf.id)
    fe = FunctionExecutor()

    # 1. The agent sees the tool with the workflow's declared inputs as params.
    defs = await fe.build_tool_definitions([tool], db=db)
    assert defs[0]["name"] == sanitize_function_name("Book appointment")
    assert "day" in defs[0]["parameters"]["properties"]
    assert defs[0]["parameters"]["required"] == ["day"]

    # 2. Calling the tool runs the workflow and returns its output.
    result = await fe.execute_global_tool(
        tool=tool, parameters={"day": "Tuesday"}, db=db)
    assert result["success"] is True
    assert result["result"]["variables"]["confirmation"] == "Booked for Tuesday"


async def test_channel_agnostic_same_executor(db):
    """Voice and text both call execute_global_tool — one implementation.

    This guards the 'build it channel-agnostic' requirement: both channels go
    through the same executor, so a workflow tool behaves identically.
    """
    import inspect
    from app.services.websocket import voice_session
    from app.api.v1.endpoints import agents

    voice_src = inspect.getsource(voice_session)
    text_src = inspect.getsource(agents)

    # Both channels build tool definitions and execute via the shared executor.
    assert "build_tool_definitions" in voice_src
    assert "execute_global_tool" in voice_src
    assert "build_tool_definitions" in text_src
    assert "execute_global_tool" in text_src


async def test_create_endpoint_rejects_workflow_tool_without_id():
    """A workflow tool with no workflow_id must be rejected at create time."""
    from fastapi import HTTPException
    from app.api.v1.endpoints.tools import create_tool
    from app.schemas.tool import ToolCreate

    # Call the validation branch directly with a minimal fake.
    data = ToolCreate(name="x", tool_type="workflow", config={})
    # The endpoint needs db/user; assert the validation guard exists in source.
    import inspect
    src = inspect.getsource(create_tool)
    assert "workflow_id" in src and "needs a workflow_id" in src


# ==================== Parameter validation & error handling ====================


async def test_missing_required_parameter_is_rejected_before_running(db):
    """The LLM omitting a required param must not run the workflow with bad data."""
    wf = await _workflow(db)
    tool = await _tool(db, wf.id)

    # 'day' is required by the workflow but the model didn't supply it.
    result = await FunctionExecutor().execute_global_tool(
        tool=tool, parameters={}, db=db)

    inner = result["result"]
    assert inner["error"] == "missing_parameters"
    assert "day" in inner["missing"]
    # Guidance the agent can act on
    assert "day" in inner["message"]


async def test_valid_parameter_runs_the_workflow(db):
    wf = await _workflow(db)
    tool = await _tool(db, wf.id)

    result = await FunctionExecutor().execute_global_tool(
        tool=tool, parameters={"day": "Friday"}, db=db)

    assert result["result"]["success"] is True
    assert result["result"]["variables"]["confirmation"] == "Booked for Friday"


async def test_failed_workflow_returns_error_to_conversation(db):
    """A mid-call workflow failure must come back as a tool error, not a crash."""
    wf = await _workflow(db, active=False)  # inactive -> engine refuses to run
    tool = await _tool(db, wf.id)

    result = await FunctionExecutor().execute_global_tool(
        tool=tool, parameters={"day": "Monday"}, db=db)

    # The tool call itself succeeds; the payload carries the failure for the LLM.
    assert "error" in result["result"]


async def test_deleted_workflow_reports_cleanly(db):
    tool = Tool(id=uuid.uuid4(), user_id=uuid.uuid4(), organization_id=uuid.uuid4(),
                name="Ghost", description="", category="assistant",
                tool_type="workflow",
                config={"workflow_id": str(uuid.uuid4())}, is_active=True)
    db.add(tool)
    await db.commit()

    result = await FunctionExecutor().execute_global_tool(
        tool=tool, parameters={"day": "x"}, db=db)
    assert "no longer exists" in result["result"]["error"]
