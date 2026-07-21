"""
Tests for the v2 workflow graph: migration, traversal, validation, and
end-to-end branching execution through the engine.
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
from app.services.workflows.workflow_engine import WorkflowEngine


pytestmark = pytest.mark.asyncio


BRANCHING_GRAPH = {
    "schema_version": 2,
    "nodes": [
        {"id": "trigger", "type": "trigger", "name": "Start", "position": {"x": 0, "y": 0}, "config": {}},
        {
            "id": "n_ask",
            "type": "ask",
            "name": "Ask",
            "position": {"x": 0, "y": 170},
            "config": {"question": "Are you a customer?", "variable": "is_customer"},
        },
        {
            "id": "n_if",
            "type": "condition",
            "name": "Check",
            "position": {"x": 0, "y": 340},
            "config": {"variable": "is_customer", "operator": "equals", "value": "yes"},
        },
        {
            "id": "n_yes",
            "type": "speak",
            "name": "Welcome back",
            "position": {"x": -200, "y": 510},
            "config": {"message": "Welcome back!"},
        },
        {
            "id": "n_no",
            "type": "speak",
            "name": "Sign up",
            "position": {"x": 200, "y": 510},
            "config": {"message": "Let me sign you up."},
        },
        {
            "id": "n_end",
            "type": "end",
            "name": "End",
            "position": {"x": 0, "y": 680},
            "config": {"farewell": "Bye"},
        },
    ],
    "edges": [
        {"id": "e1", "source": "trigger", "sourceHandle": "out", "target": "n_ask", "targetHandle": "in"},
        {"id": "e2", "source": "n_ask", "sourceHandle": "out", "target": "n_if", "targetHandle": "in"},
        {"id": "e3", "source": "n_if", "sourceHandle": "true", "target": "n_yes", "targetHandle": "in"},
        {"id": "e4", "source": "n_if", "sourceHandle": "false", "target": "n_no", "targetHandle": "in"},
        {"id": "e5", "source": "n_yes", "sourceHandle": "out", "target": "n_end", "targetHandle": "in"},
        {"id": "e6", "source": "n_no", "sourceHandle": "out", "target": "n_end", "targetHandle": "in"},
    ],
}


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


# ==================== Migration ====================


async def test_migrate_v1_builds_edges_from_order():
    steps = [
        {"id": "s1", "type": "speak", "name": "One", "config": {"message": "1"}},
        {"id": "s2", "type": "speak", "name": "Two", "config": {"message": "2"}},
    ]
    graph = g.migrate_v1_to_v2(steps)

    assert [n["id"] for n in graph["nodes"]] == ["trigger", "s1", "s2"]
    assert g.entry_node_id(graph) == "s1"
    assert g.next_node_id(graph, "s1") == "s2"
    assert g.next_node_id(graph, "s2") is None


async def test_migrate_v1_builds_branch_edges():
    """v1 stored branch targets in config; they become true/false edges."""
    steps = [
        {
            "id": "s1",
            "type": "condition",
            "name": "Check",
            "config": {"variable": "x", "operator": "equals", "value": "1",
                       "on_true": "s2", "on_false": "s3"},
        },
        {"id": "s2", "type": "speak", "name": "Yes", "config": {"message": "y"}},
        {"id": "s3", "type": "speak", "name": "No", "config": {"message": "n"}},
    ]
    graph = g.migrate_v1_to_v2(steps)

    assert g.next_node_id(graph, "s1", branch=True) == "s2"
    assert g.next_node_id(graph, "s1", branch=False) == "s3"


async def test_migrate_tolerates_list_shaped_branch_targets():
    """The v1 schema typed on_true as List[str] while the engine read a scalar."""
    steps = [
        {"id": "s1", "type": "condition", "name": "C",
         "config": {"variable": "x", "operator": "equals", "value": "1",
                    "on_true": ["s2"], "on_false": ["s3"]}},
        {"id": "s2", "type": "speak", "name": "Y", "config": {"message": "y"}},
        {"id": "s3", "type": "speak", "name": "N", "config": {"message": "n"}},
    ]
    graph = g.migrate_v1_to_v2(steps)

    assert g.next_node_id(graph, "s1", branch=True) == "s2"
    assert g.next_node_id(graph, "s1", branch=False) == "s3"


async def test_load_graph_accepts_both_schemas():
    v1 = {"steps": [{"id": "s1", "type": "end", "name": "E", "config": {}}]}
    assert g.load_graph(v1)["schema_version"] == 2

    v2 = g.load_graph(BRANCHING_GRAPH)
    assert [n["id"] for n in v2["nodes"]] == [n["id"] for n in BRANCHING_GRAPH["nodes"]]

    assert g.load_graph(None)["nodes"][0]["type"] == "trigger"


async def test_positions_survive_a_round_trip():
    """The whole point of v2: the canvas layout must persist."""
    loaded = g.load_graph(BRANCHING_GRAPH)
    positions = {n["id"]: n["position"] for n in loaded["nodes"]}

    assert positions["n_yes"] == {"x": -200.0, "y": 510.0}
    assert positions["n_no"] == {"x": 200.0, "y": 510.0}


# ==================== Response serialization ====================


async def test_response_exposes_steps_and_graph_separately():
    """workflow_steps must stay a list while graph is the v2 object.

    FastAPI serializes responses with by_alias=True. When `graph` carried a
    plain alias of "workflow_steps" it was emitted under that key and replaced
    the step list, so the detail page crashed on workflow_steps.map().
    """
    from datetime import datetime
    from app.schemas.workflow import WorkflowResponse

    class Row:
        id = uuid.uuid4()
        user_id = uuid.uuid4()
        organization_id = uuid.uuid4()
        name = "w"
        description = None
        trigger_type = "manual"
        trigger_config: dict = {}
        workflow_steps = {
            "steps": [{"id": "s1", "type": "speak", "name": "Hi", "config": {}}]
        }
        is_active = True
        execution_mode = "async"
        error_handling = "stop"
        max_retries = 3
        retry_delay = 60
        total_executions = 0
        successful_executions = 0
        failed_executions = 0
        last_executed_at = None
        version = 1
        created_at = datetime(2026, 1, 1)
        updated_at = datetime(2026, 1, 1)

    payload = WorkflowResponse.model_validate(Row()).model_dump(
        by_alias=True, mode="json"
    )

    assert isinstance(payload["workflow_steps"], list)
    assert [s["id"] for s in payload["workflow_steps"]] == ["s1"]
    assert isinstance(payload["graph"], dict)
    assert [n["id"] for n in payload["graph"]["nodes"]] == ["trigger", "s1"]


async def test_response_serializes_a_v2_row():
    """A stored graph must round-trip without losing positions."""
    from datetime import datetime
    from app.schemas.workflow import WorkflowResponse

    class Row:
        id = uuid.uuid4()
        user_id = uuid.uuid4()
        organization_id = uuid.uuid4()
        name = "w"
        description = None
        trigger_type = "manual"
        trigger_config: dict = {}
        workflow_steps = BRANCHING_GRAPH
        is_active = True
        execution_mode = "async"
        error_handling = "stop"
        max_retries = 3
        retry_delay = 60
        total_executions = 0
        successful_executions = 0
        failed_executions = 0
        last_executed_at = None
        version = 1
        created_at = datetime(2026, 1, 1)
        updated_at = datetime(2026, 1, 1)

    payload = WorkflowResponse.model_validate(Row()).model_dump(
        by_alias=True, mode="json"
    )

    assert isinstance(payload["workflow_steps"], list)
    # The trigger is a canvas anchor, not a step
    assert "trigger" not in [s["id"] for s in payload["workflow_steps"]]

    positions = {n["id"]: n["position"] for n in payload["graph"]["nodes"]}
    assert positions["n_yes"] == {"x": -200.0, "y": 510.0}


# ==================== Validation ====================


async def test_validate_flags_cycle():
    graph = {
        "schema_version": 2,
        "nodes": [
            {"id": "a", "type": "speak", "name": "A", "position": {"x": 0, "y": 0}, "config": {}},
            {"id": "b", "type": "speak", "name": "B", "position": {"x": 0, "y": 1}, "config": {}},
        ],
        "edges": [
            {"id": "e1", "source": "a", "sourceHandle": "out", "target": "b"},
            {"id": "e2", "source": "b", "sourceHandle": "out", "target": "a"},
        ],
    }
    report = g.validate_graph(g.normalize_graph(graph))
    assert any("loop" in e["message"] for e in report["errors"])


async def test_validate_flags_unreachable_node():
    graph = g.normalize_graph({
        "nodes": [
            {"id": "trigger", "type": "trigger", "name": "T", "position": {"x": 0, "y": 0}, "config": {}},
            {"id": "a", "type": "speak", "name": "A", "position": {"x": 0, "y": 1}, "config": {}},
            {"id": "orphan", "type": "speak", "name": "Orphan", "position": {"x": 0, "y": 2}, "config": {}},
        ],
        "edges": [{"id": "e1", "source": "trigger", "sourceHandle": "out", "target": "a"}],
    })
    report = g.validate_graph(graph)
    assert any("Orphan" in w["message"] for w in report["warnings"])


async def test_validate_accepts_a_healthy_graph():
    report = g.validate_graph(g.load_graph(BRANCHING_GRAPH))
    assert report["errors"] == []


# ==================== Execution ====================


async def _run(db: AsyncSession, answer: str):
    """Execute the branching graph with a scripted caller answer."""
    workflow = Workflow(
        user_id=uuid.uuid4(),
        organization_id=uuid.uuid4(),
        name="branching",
        trigger_type="manual",
        trigger_config={},
        workflow_steps=BRANCHING_GRAPH,
        is_active=True,
    )
    db.add(workflow)
    await db.commit()
    await db.refresh(workflow)

    channel = SimulatedChannel(answers={"is_customer": answer})
    execution = await WorkflowEngine(db).execute_workflow(
        workflow_id=str(workflow.id),
        trigger_data={},
        wait_for_completion=True,
        channel=channel,
    )
    await db.refresh(execution)
    return execution


async def test_execution_takes_the_true_branch(db):
    execution = await _run(db, "yes")
    path = [s["step_id"] for s in execution.result_data["steps"]]

    assert execution.status == "completed"
    assert "n_yes" in path
    assert "n_no" not in path
    assert path[-1] == "n_end"


async def test_execution_takes_the_false_branch(db):
    execution = await _run(db, "no")
    path = [s["step_id"] for s in execution.result_data["steps"]]

    assert execution.status == "completed"
    assert "n_no" in path
    assert "n_yes" not in path


async def test_execution_records_the_transcript(db):
    execution = await _run(db, "yes")
    spoken = [
        entry["text"]
        for entry in execution.result_data["transcript"]
        if entry.get("type") == "speak"
    ]

    assert "Welcome back!" in spoken
    assert "Let me sign you up." not in spoken


async def test_v1_workflow_still_executes(db):
    """Existing stored workflows must keep running after the graph migration."""
    workflow = Workflow(
        user_id=uuid.uuid4(),
        organization_id=uuid.uuid4(),
        name="legacy",
        trigger_type="manual",
        trigger_config={},
        workflow_steps={
            "steps": [
                {"id": "s1", "type": "speak", "name": "Hi", "config": {"message": "Hello"}},
                {"id": "s2", "type": "end", "name": "End", "config": {"farewell": "Bye"}},
            ]
        },
        is_active=True,
    )
    db.add(workflow)
    await db.commit()
    await db.refresh(workflow)

    channel = SimulatedChannel()
    execution = await WorkflowEngine(db).execute_workflow(
        workflow_id=str(workflow.id),
        trigger_data={},
        wait_for_completion=True,
        channel=channel,
    )
    await db.refresh(execution)

    assert execution.status == "completed"
    assert [s["step_id"] for s in execution.result_data["steps"]] == ["s1", "s2"]


async def test_branch_with_no_edge_ends_that_path(db):
    """An unconnected branch output must stop, not fall through to a sibling."""
    graph = {
        "schema_version": 2,
        "nodes": [
            {"id": "trigger", "type": "trigger", "name": "T", "position": {"x": 0, "y": 0}, "config": {}},
            {"id": "n_if", "type": "condition", "name": "C", "position": {"x": 0, "y": 1},
             "config": {"variable": "x", "operator": "equals", "value": "yes"}},
            {"id": "n_true", "type": "speak", "name": "T", "position": {"x": 0, "y": 2},
             "config": {"message": "true path"}},
        ],
        "edges": [
            {"id": "e1", "source": "trigger", "sourceHandle": "out", "target": "n_if"},
            {"id": "e2", "source": "n_if", "sourceHandle": "true", "target": "n_true"},
        ],
    }
    workflow = Workflow(
        user_id=uuid.uuid4(), organization_id=uuid.uuid4(), name="partial",
        trigger_type="manual", trigger_config={}, workflow_steps=graph, is_active=True,
    )
    db.add(workflow)
    await db.commit()
    await db.refresh(workflow)

    execution = await WorkflowEngine(db).execute_workflow(
        workflow_id=str(workflow.id),
        trigger_data={"x": "no"},
        wait_for_completion=True,
        channel=SimulatedChannel(),
    )
    await db.refresh(execution)

    path = [s["step_id"] for s in execution.result_data["steps"]]
    assert path == ["n_if"]


# ==================== Per-node settings ====================


def _wf(graph):
    return Workflow(
        user_id=uuid.uuid4(), organization_id=uuid.uuid4(), name="settings",
        trigger_type="manual", trigger_config={}, workflow_steps=graph,
        is_active=True, error_handling="stop", max_retries=0, retry_delay=0,
    )


def _one_node_graph(node_type, config, settings):
    return {
        "schema_version": 2,
        "nodes": [
            {"id": "trigger", "type": "trigger", "name": "T",
             "position": {"x": 0, "y": 0}, "config": {}},
            {"id": "n1", "type": node_type, "name": "Step",
             "position": {"x": 0, "y": 1}, "config": config, "settings": settings},
            {"id": "n2", "type": "speak", "name": "After",
             "position": {"x": 0, "y": 2}, "config": {"message": "after"}},
        ],
        "edges": [
            {"id": "e1", "source": "trigger", "sourceHandle": "out", "target": "n1"},
            {"id": "e2", "source": "n1", "sourceHandle": "out", "target": "n2"},
        ],
    }


async def test_node_on_error_continue_overrides_workflow_stop(db):
    """A tolerant node must not be forced to stop by the workflow default."""
    # A webhook to an unroutable address fails fast.
    graph = _one_node_graph(
        "webhook",
        {"url": "http://127.0.0.1:9/none", "method": "POST", "timeout": 1},
        {"on_error": "continue"},
    )
    workflow = _wf(graph)
    db.add(workflow)
    await db.commit()
    await db.refresh(workflow)

    execution = await WorkflowEngine(db).execute_workflow(
        workflow_id=str(workflow.id), trigger_data={},
        wait_for_completion=True, channel=SimulatedChannel(),
    )
    await db.refresh(execution)

    path = [s["step_id"] for s in execution.result_data["steps"]]
    # n1 failed but the flow continued to n2
    assert "n1" in path and "n2" in path


async def test_node_settings_survive_a_graph_round_trip():
    """settings must not be dropped by normalization, or config is lost."""
    graph = _one_node_graph(
        "webhook", {"url": "https://example.com"},
        {"on_error": "continue", "timeout_seconds": 12,
         "retry": {"enabled": True, "max_tries": 5, "backoff": "exponential"}},
    )
    loaded = g.load_graph(graph)
    node = next(n for n in loaded["nodes"] if n["id"] == "n1")

    assert node["settings"]["timeout_seconds"] == 12
    assert node["settings"]["retry"]["max_tries"] == 5
    assert node["settings"]["retry"]["backoff"] == "exponential"


async def test_normalize_defaults_settings_to_empty_dict():
    """Nodes saved before settings existed must still load."""
    loaded = g.load_graph({
        "schema_version": 2,
        "nodes": [{"id": "a", "type": "speak", "name": "A",
                   "position": {"x": 0, "y": 0}, "config": {}}],
        "edges": [],
    })
    assert loaded["nodes"][0]["settings"] == {}
