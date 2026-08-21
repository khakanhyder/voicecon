"""
The Run Tool step, end to end.

A workflow that calls a tool is the path a new user takes as soon as they want
an agent to do anything real, and it crosses three boundaries that each used to
break it: the tool id has to be resolvable from the builder, the lookup has to
be scoped to the workspace, and the tool's own configuration has to be readable
by the executor.
"""
import json
import uuid

import httpx
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models.integration import Workflow
from app.models.tool import Tool
from app.services.workflows.workflow_engine import WorkflowEngine

pytestmark = pytest.mark.asyncio

ORG = uuid.uuid4()
OTHER_ORG = uuid.uuid4()


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


@pytest.fixture
def outbound(monkeypatch):
    """Answer the tool's HTTP call locally and record what it sent."""
    seen = {}
    real_init = httpx.AsyncClient.__init__

    def handler(request: httpx.Request) -> httpx.Response:
        seen["request"] = request
        return httpx.Response(200, text='{"status": "ok", "ticket": 4021}')

    def patched(self, *args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        real_init(self, *args, **kwargs)

    monkeypatch.setattr(httpx.AsyncClient, "__init__", patched)
    return seen


async def make_tool(db: AsyncSession, org=ORG, **config) -> Tool:
    tool = Tool(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        organization_id=org,
        name="Raise a ticket",
        tool_type="api_request",
        category="integration",
        config={
            "url": "https://api.example.com/tickets",
            "method": "POST",
            # Exactly what the builder form stores: JSON as typed text.
            "headers": '{\n  "Content-Type": "application/json"\n}',
            "body": '{"summary": "{{summary}}"}',
            **config,
        },
        is_active=True,
    )
    db.add(tool)
    await db.commit()
    return tool


async def make_workflow(db: AsyncSession, tool_id, org=ORG) -> Workflow:
    workflow = Workflow(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        organization_id=org,
        name="Raise a ticket after the call",
        trigger_type="manual",
        trigger_config={},
        is_active=True,
        # A failure here is the assertion; retrying only slows the test down.
        max_retries=0,
        workflow_steps={
            "nodes": [
                {"id": "t", "type": "trigger", "config": {}},
                {
                    "id": "n_run",
                    "type": "tool",
                    "name": "Raise a ticket",
                    "config": {
                        # The builder now writes the tool's real UUID here,
                        # because the field is a picker rather than a free-text
                        # box asking for something the UI never showed.
                        "tool_id": str(tool_id),
                        # And the builder stores this as a JSON string.
                        "parameters": '{"summary": "{{trigger.summary}}"}',
                    },
                },
            ],
            "edges": [{"source": "t", "target": "n_run"}],
        },
    )
    db.add(workflow)
    await db.commit()
    await db.refresh(workflow)
    return workflow


async def run(db, workflow, trigger_data):
    """Execute to completion and hand back the refreshed execution row."""
    execution = await WorkflowEngine(db).execute_workflow(
        workflow_id=str(workflow.id),
        trigger_data=trigger_data,
        wait_for_completion=True,
    )
    await db.refresh(execution)
    return execution


class TestRunToolStep:
    async def test_a_workflow_can_run_a_tool_the_builder_configured(
        self, db, outbound
    ):
        tool = await make_tool(db)
        workflow = await make_workflow(db, tool.id)

        execution = await run(db, workflow, {"summary": "Line was noisy"})

        assert execution.status == "completed", execution.error_message
        # The tool's headers were stored as text; unpacking them used to raise
        # TypeError here, on a live call.
        assert outbound["request"].headers["content-type"] == "application/json"
        # And the body template was filled, not shipped with the placeholder in.
        assert json.loads(outbound["request"].content) == {
            "summary": "Line was noisy"
        }

    async def test_the_response_is_available_to_later_steps(self, db, outbound):
        tool = await make_tool(db)
        workflow = await make_workflow(db, tool.id)

        execution = await run(db, workflow, {"summary": "x"})

        steps = {s["step_id"]: s for s in execution.result_data["steps"]}
        assert steps["n_run"]["result"]["json"] == {"status": "ok", "ticket": 4021}

    async def test_a_tool_from_another_workspace_is_refused(self, db, outbound):
        # The id is real, but it belongs to someone else.
        tool = await make_tool(db, org=OTHER_ORG)
        workflow = await make_workflow(db, tool.id, org=ORG)

        execution = await run(db, workflow, {})

        assert execution.status == "failed"
        assert "request" not in outbound, "the other tenant's tool must not run"

    async def test_a_deleted_tool_fails_the_step_rather_than_the_platform(
        self, db, outbound
    ):
        workflow = await make_workflow(db, uuid.uuid4())
        execution = await run(db, workflow, {})
        assert execution.status == "failed"
        assert "not found" in json.dumps(execution.result_data).lower()

    async def test_a_misconfigured_tool_reports_what_to_fix(self, db, outbound):
        tool = await make_tool(db, headers="{not json")
        workflow = await make_workflow(db, tool.id)

        execution = await run(db, workflow, {})

        assert execution.status == "failed"
        # Naming the field is the whole point; "TypeError" was not actionable.
        assert "Headers is not valid JSON" in json.dumps(execution.result_data)
