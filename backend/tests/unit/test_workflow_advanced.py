"""
Tests for the advanced features: Code node sandbox, and live execution events.
"""
import uuid

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models.integration import Workflow
from app.services.workflows import graph as g
from app.services.workflows.channels import SimulatedChannel
from app.services.workflows.sandbox import run_code, SandboxError
from app.services.workflows.workflow_engine import WorkflowEngine

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


# ==================== Sandbox ====================


async def test_code_returns_result_assignment():
    out = await run_code("result = input['trigger']['n'] * 2", {"trigger": {"n": 21}})
    assert out == 42


async def test_code_supports_main_function():
    out = await run_code("def main(data):\n    return sorted(data['xs'])",
                         {"xs": [3, 1, 2]})
    assert out == [1, 2, 3]


async def test_code_allows_safe_imports():
    out = await run_code("import math\nresult = math.floor(input['x'])", {"x": 3.9})
    assert out == 3


async def test_code_blocks_open():
    with pytest.raises(SandboxError):
        await run_code("result = open('/etc/passwd').read()", {})


async def test_code_blocks_dangerous_import():
    with pytest.raises(SandboxError, match="not allowed"):
        await run_code("import os\nresult = os.listdir('/')", {})


async def test_code_blocks_infinite_loop():
    with pytest.raises(SandboxError):
        await run_code("while True:\n    pass", {}, timeout_seconds=2)


async def test_code_rejects_non_serialisable_result():
    # A circular reference is the case json.dumps cannot handle even with a
    # str fallback.
    with pytest.raises(SandboxError, match="not JSON serialisable"):
        await run_code("a = {}\na['self'] = a\nresult = a", {})


async def test_code_reports_runtime_error():
    with pytest.raises(SandboxError, match="ZeroDivisionError"):
        await run_code("result = 1 / 0", {})


# ==================== Code node in a workflow ====================


async def test_code_node_runs_in_a_workflow(db):
    graph = {
        "schema_version": 2,
        "nodes": [
            {"id": "trigger", "type": "trigger", "name": "T",
             "position": {"x": 0, "y": 0}, "config": {}},
            {"id": "calc", "type": "code", "name": "Compute",
             "position": {"x": 0, "y": 1},
             "config": {"code": "result = {'total': sum(input['trigger']['nums'])}"}},
            {"id": "say", "type": "speak", "name": "Say",
             "position": {"x": 0, "y": 2},
             "config": {"message": "The total is {{total}}"}},
        ],
        "edges": [
            {"id": "e1", "source": "trigger", "sourceHandle": "out", "target": "calc"},
            {"id": "e2", "source": "calc", "sourceHandle": "out", "target": "say"},
        ],
    }
    wf = Workflow(user_id=uuid.uuid4(), organization_id=uuid.uuid4(), name="code",
                  trigger_type="manual", trigger_config={}, workflow_steps=graph,
                  is_active=True, error_handling="stop", max_retries=0, retry_delay=0)
    db.add(wf)
    await db.commit()
    await db.refresh(wf)

    channel = SimulatedChannel()
    execution = await WorkflowEngine(db).execute_workflow(
        workflow_id=str(wf.id), trigger_data={"nums": [10, 20, 12]},
        wait_for_completion=True, channel=channel)
    await db.refresh(execution)

    steps = {s["step_id"]: s for s in execution.result_data["steps"]}
    assert steps["calc"]["result"] == {"total": 42}
    # The published variable interpolated into the speak step
    spoken = [e["text"] for e in execution.result_data["transcript"]
              if e.get("type") == "speak"]
    assert "The total is 42" in spoken


# ==================== Live execution events ====================


async def test_execution_emits_node_events(db):
    graph = g.normalize_graph({
        "nodes": [
            {"id": "trigger", "type": "trigger", "name": "T",
             "position": {"x": 0, "y": 0}, "config": {}},
            {"id": "a", "type": "speak", "name": "A",
             "position": {"x": 0, "y": 1}, "config": {"message": "hi"}},
            {"id": "if", "type": "condition", "name": "C",
             "position": {"x": 0, "y": 2},
             "config": {"variable": "trigger.x", "operator": "equals", "value": "yes"}},
            {"id": "yes", "type": "speak", "name": "Yes",
             "position": {"x": 0, "y": 3}, "config": {"message": "y"}},
            {"id": "no", "type": "speak", "name": "No",
             "position": {"x": 0, "y": 3}, "config": {"message": "n"}},
        ],
        "edges": [
            {"id": "e1", "source": "trigger", "sourceHandle": "out", "target": "a"},
            {"id": "e2", "source": "a", "sourceHandle": "out", "target": "if"},
            {"id": "e3", "source": "if", "sourceHandle": "true", "target": "yes"},
            {"id": "e4", "source": "if", "sourceHandle": "false", "target": "no"},
        ],
    })
    wf = Workflow(user_id=uuid.uuid4(), organization_id=uuid.uuid4(), name="events",
                  trigger_type="manual", trigger_config={}, workflow_steps=graph,
                  is_active=True, error_handling="stop", max_retries=0, retry_delay=0)
    db.add(wf)
    await db.commit()
    await db.refresh(wf)

    events = []

    async def on_event(e):
        events.append(e)

    execution = await WorkflowEngine(db).execute_workflow(
        workflow_id=str(wf.id), trigger_data={"x": "no"},
        wait_for_completion=True, channel=SimulatedChannel(), on_event=on_event)
    await db.refresh(execution)

    kinds = {(e["event"], e["node_id"]) for e in events}
    # Every executed node reports started then finished
    assert ("node_started", "a") in kinds
    assert ("node_finished", "a") in kinds
    assert ("node_started", "no") in kinds
    # The untaken branch is reported as skipped, not run
    assert ("node_skipped", "yes") in kinds
    assert ("node_started", "yes") not in kinds


async def test_event_callback_failure_does_not_break_run(db):
    graph = g.normalize_graph({
        "nodes": [
            {"id": "trigger", "type": "trigger", "name": "T",
             "position": {"x": 0, "y": 0}, "config": {}},
            {"id": "a", "type": "speak", "name": "A",
             "position": {"x": 0, "y": 1}, "config": {"message": "hi"}},
        ],
        "edges": [{"id": "e1", "source": "trigger", "sourceHandle": "out", "target": "a"}],
    })
    wf = Workflow(user_id=uuid.uuid4(), organization_id=uuid.uuid4(), name="broken-cb",
                  trigger_type="manual", trigger_config={}, workflow_steps=graph,
                  is_active=True, error_handling="stop", max_retries=0, retry_delay=0)
    db.add(wf)
    await db.commit()
    await db.refresh(wf)

    async def bad_event(e):
        raise RuntimeError("subscriber blew up")

    execution = await WorkflowEngine(db).execute_workflow(
        workflow_id=str(wf.id), trigger_data={},
        wait_for_completion=True, channel=SimulatedChannel(), on_event=bad_event)
    await db.refresh(execution)

    # The run still completes despite the failing callback
    assert execution.status == "completed"


# ==================== JavaScript sandbox ====================


async def test_js_returns_result():
    from app.services.workflows.js_sandbox import run_js
    out = await run_js("result = { doubled: input.trigger.n * 2 }", {"trigger": {"n": 21}})
    assert out == {"doubled": 42}


async def test_js_supports_main():
    from app.services.workflows.js_sandbox import run_js
    out = await run_js(
        "function main(d){ return d.xs.reduce((a,b)=>a+b,0) }", {"xs": [1, 2, 3, 4]}
    )
    assert out == 10


async def test_js_blocks_require():
    from app.services.workflows.js_sandbox import run_js, JSSandboxError
    with pytest.raises(JSSandboxError, match="require"):
        await run_js("result = require('fs').readFileSync('/etc/passwd')", {})


async def test_js_blocks_process():
    from app.services.workflows.js_sandbox import run_js, JSSandboxError
    with pytest.raises(JSSandboxError, match="process"):
        await run_js("result = process.env", {})


async def test_js_blocks_infinite_loop():
    from app.services.workflows.js_sandbox import run_js, JSSandboxError
    with pytest.raises(JSSandboxError):
        await run_js("while (true) {}", {}, timeout_seconds=2)


async def test_js_reports_runtime_error():
    from app.services.workflows.js_sandbox import run_js, JSSandboxError
    with pytest.raises(JSSandboxError):
        await run_js("result = notDefined.foo", {})


async def test_js_code_node_runs_in_a_workflow(db):
    graph = {
        "schema_version": 2,
        "nodes": [
            {"id": "trigger", "type": "trigger", "name": "T",
             "position": {"x": 0, "y": 0}, "config": {}},
            {"id": "calc", "type": "code", "name": "Compute",
             "position": {"x": 0, "y": 1},
             "config": {"language": "javascript",
                        "code": "result = { total: input.trigger.nums.reduce((a,b)=>a+b,0) }"}},
            {"id": "say", "type": "speak", "name": "Say",
             "position": {"x": 0, "y": 2},
             "config": {"message": "The total is {{total}}"}},
        ],
        "edges": [
            {"id": "e1", "source": "trigger", "sourceHandle": "out", "target": "calc"},
            {"id": "e2", "source": "calc", "sourceHandle": "out", "target": "say"},
        ],
    }
    wf = Workflow(user_id=uuid.uuid4(), organization_id=uuid.uuid4(), name="jscode",
                  trigger_type="manual", trigger_config={}, workflow_steps=graph,
                  is_active=True, error_handling="stop", max_retries=0, retry_delay=0)
    db.add(wf)
    await db.commit()
    await db.refresh(wf)

    execution = await WorkflowEngine(db).execute_workflow(
        workflow_id=str(wf.id), trigger_data={"nums": [10, 20, 12]},
        wait_for_completion=True, channel=SimulatedChannel())
    await db.refresh(execution)

    steps = {s["step_id"]: s for s in execution.result_data["steps"]}
    assert steps["calc"]["result"] == {"total": 42}
    spoken = [e["text"] for e in execution.result_data["transcript"]
              if e.get("type") == "speak"]
    assert "The total is 42" in spoken


async def test_python_code_node_still_default(db):
    """No language set must still run as Python (backward compatible)."""
    graph = {
        "schema_version": 2,
        "nodes": [
            {"id": "trigger", "type": "trigger", "name": "T",
             "position": {"x": 0, "y": 0}, "config": {}},
            {"id": "calc", "type": "code", "name": "Compute",
             "position": {"x": 0, "y": 1},
             "config": {"code": "result = {'n': len(input['trigger']['xs'])}"}},
        ],
        "edges": [{"id": "e1", "source": "trigger", "sourceHandle": "out", "target": "calc"}],
    }
    wf = Workflow(user_id=uuid.uuid4(), organization_id=uuid.uuid4(), name="pycode",
                  trigger_type="manual", trigger_config={}, workflow_steps=graph,
                  is_active=True, error_handling="stop", max_retries=0, retry_delay=0)
    db.add(wf)
    await db.commit()
    await db.refresh(wf)

    execution = await WorkflowEngine(db).execute_workflow(
        workflow_id=str(wf.id), trigger_data={"xs": [1, 2, 3]},
        wait_for_completion=True, channel=SimulatedChannel())
    await db.refresh(execution)
    steps = {s["step_id"]: s for s in execution.result_data["steps"]}
    assert steps["calc"]["result"] == {"n": 3}
