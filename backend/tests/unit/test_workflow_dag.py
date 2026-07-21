"""
Tests for the DAG scheduler: parallel branches, joins, skip propagation,
switch/filter routing, and error policy across concurrent paths.
"""
import asyncio
import uuid

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models.integration import Workflow
from app.services.workflows import graph as g
from app.services.workflows.channels import SimulatedChannel
from app.services.workflows.executor import GraphExecutor, NodeOutcome
from app.services.workflows.workflow_engine import WorkflowEngine

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


def _node(nid, ntype, config=None, settings=None):
    return {"id": nid, "type": ntype, "name": nid, "position": {"x": 0, "y": 0},
            "config": config or {}, "settings": settings or {}}


def _edge(src, tgt, handle="out"):
    return {"id": f"{src}->{tgt}:{handle}", "source": src, "sourceHandle": handle,
            "target": tgt, "targetHandle": "in"}


async def _run_graph(graph, trigger_data=None, workflow_kwargs=None, db=None):
    kwargs = {"error_handling": "stop", "max_retries": 0, "retry_delay": 0}
    kwargs.update(workflow_kwargs or {})
    wf = Workflow(user_id=uuid.uuid4(), organization_id=uuid.uuid4(), name="dag",
                  trigger_type="manual", trigger_config={}, workflow_steps=graph,
                  is_active=True, **kwargs)
    db.add(wf)
    await db.commit()
    await db.refresh(wf)

    execution = await WorkflowEngine(db).execute_workflow(
        workflow_id=str(wf.id), trigger_data=trigger_data or {},
        wait_for_completion=True, channel=SimulatedChannel())
    await db.refresh(execution)
    return execution


# ==================== Parallel execution ====================


async def test_independent_branches_run_concurrently():
    """Two branches off one node must overlap in time, not run back to back."""
    graph = g.normalize_graph({
        "nodes": [_node("trigger", "trigger"), _node("a", "speak"),
                  _node("b", "speak"), _node("c", "speak")],
        "edges": [_edge("trigger", "a"), _edge("a", "b"), _edge("a", "c")],
    })

    running = 0
    peak = 0

    async def run_node(node):
        nonlocal running, peak
        running += 1
        peak = max(peak, running)
        await asyncio.sleep(0.05)
        running -= 1
        return NodeOutcome(status="success", handles=["out"])

    results, counts = await GraphExecutor(graph, run_node).run()

    assert counts["executed"] == 3
    # b and c are independent, so both must be in flight at once
    assert peak == 2


async def test_join_runs_once_after_both_branches():
    """A node fed by two parallel branches runs a single time."""
    graph = g.normalize_graph({
        "nodes": [_node("trigger", "trigger"), _node("a", "speak"),
                  _node("b", "speak"), _node("join", "merge")],
        "edges": [_edge("trigger", "a"), _edge("trigger", "b"),
                  _edge("a", "join"), _edge("b", "join")],
    })

    order = []

    async def run_node(node):
        order.append(node["id"])
        return NodeOutcome(status="success", handles=["out"])

    results, counts = await GraphExecutor(graph, run_node).run()

    assert order.count("join") == 1
    # The join must come after both of its inputs
    assert order.index("join") > order.index("a")
    assert order.index("join") > order.index("b")


async def test_merge_first_arrival_does_not_wait():
    """first_arrival mode fires as soon as one branch reaches the merge."""
    graph = g.normalize_graph({
        "nodes": [
            _node("trigger", "trigger"),
            _node("fast", "speak"),
            _node("slow", "speak"),
            _node("join", "merge", settings={"merge_mode": "first_arrival"}),
        ],
        "edges": [_edge("trigger", "fast"), _edge("trigger", "slow"),
                  _edge("fast", "join"), _edge("slow", "join")],
    })

    async def run_node(node):
        if node["id"] == "slow":
            await asyncio.sleep(0.1)
        return NodeOutcome(status="success", handles=["out"])

    results, counts = await GraphExecutor(graph, run_node).run()

    assert [r["step_id"] for r in results].count("join") == 1


# ==================== Skip propagation ====================


async def test_untaken_branch_is_skipped_and_join_still_fires():
    """The classic if/else rejoin: the untaken side must not block the join."""
    graph = g.normalize_graph({
        "nodes": [_node("trigger", "trigger"), _node("if", "condition"),
                  _node("yes", "speak"), _node("no", "speak"),
                  _node("after", "speak")],
        "edges": [_edge("trigger", "if"),
                  _edge("if", "yes", "true"), _edge("if", "no", "false"),
                  _edge("yes", "after"), _edge("no", "after")],
    })

    ran = []

    async def run_node(node):
        ran.append(node["id"])
        if node["type"] == "condition":
            return NodeOutcome(status="success", handles=["true"])
        return NodeOutcome(status="success", handles=["out"])

    results, counts = await GraphExecutor(graph, run_node).run()

    assert "yes" in ran
    assert "no" not in ran
    assert ran.count("after") == 1
    assert counts["skipped"] >= 1


async def test_skip_propagates_through_a_chain():
    """Skipping cascades down a whole untaken branch, not just one node."""
    graph = g.normalize_graph({
        "nodes": [_node("trigger", "trigger"), _node("if", "condition"),
                  _node("x1", "speak"), _node("x2", "speak"), _node("x3", "speak"),
                  _node("ok", "speak")],
        "edges": [_edge("trigger", "if"),
                  _edge("if", "x1", "true"), _edge("x1", "x2"), _edge("x2", "x3"),
                  _edge("if", "ok", "false")],
    })

    ran = []

    async def run_node(node):
        ran.append(node["id"])
        if node["type"] == "condition":
            return NodeOutcome(status="success", handles=["false"])
        return NodeOutcome(status="success", handles=["out"])

    await GraphExecutor(graph, run_node).run()

    assert ran == ["if", "ok"]
    assert "x1" not in ran and "x2" not in ran and "x3" not in ran


# ==================== Switch / Filter ====================


async def test_switch_routes_to_matching_branch(db):
    graph = g.normalize_graph({
        "nodes": [
            _node("trigger", "trigger"),
            _node("sw", "switch", {"rules": [
                {"variable": "trigger.plan", "operator": "equals", "value": "pro"},
                {"variable": "trigger.plan", "operator": "equals", "value": "free"},
            ]}),
            _node("pro", "speak", {"message": "pro path"}),
            _node("free", "speak", {"message": "free path"}),
            _node("other", "speak", {"message": "fallback path"}),
        ],
        "edges": [_edge("trigger", "sw"),
                  _edge("sw", "pro", "branch-0"),
                  _edge("sw", "free", "branch-1"),
                  _edge("sw", "other", "fallback")],
    })

    execution = await _run_graph(graph, {"plan": "free"}, db=db)
    path = [s["step_id"] for s in execution.result_data["steps"]]

    assert "free" in path
    assert "pro" not in path and "other" not in path


async def test_switch_falls_back_when_nothing_matches(db):
    graph = g.normalize_graph({
        "nodes": [
            _node("trigger", "trigger"),
            _node("sw", "switch", {"rules": [
                {"variable": "trigger.plan", "operator": "equals", "value": "pro"},
            ]}),
            _node("pro", "speak", {"message": "pro"}),
            _node("other", "speak", {"message": "fallback"}),
        ],
        "edges": [_edge("trigger", "sw"),
                  _edge("sw", "pro", "branch-0"),
                  _edge("sw", "other", "fallback")],
    })

    execution = await _run_graph(graph, {"plan": "enterprise"}, db=db)
    path = [s["step_id"] for s in execution.result_data["steps"]]

    assert "other" in path and "pro" not in path


async def test_filter_blocks_the_path_when_condition_fails(db):
    graph = g.normalize_graph({
        "nodes": [
            _node("trigger", "trigger"),
            _node("f", "filter", {"variable": "trigger.score", "operator": "greater_than",
                                  "value": "10"}),
            _node("after", "speak", {"message": "passed"}),
        ],
        "edges": [_edge("trigger", "f"), _edge("f", "after")],
    })

    blocked = await _run_graph(graph, {"score": "5"}, db=db)
    assert [s["step_id"] for s in blocked.result_data["steps"]] == ["f"]


async def test_filter_allows_the_path_when_condition_passes(db):
    graph = g.normalize_graph({
        "nodes": [
            _node("trigger", "trigger"),
            _node("f", "filter", {"variable": "trigger.score", "operator": "greater_than",
                                  "value": "10"}),
            _node("after", "speak", {"message": "passed"}),
        ],
        "edges": [_edge("trigger", "f"), _edge("f", "after")],
    })

    passed = await _run_graph(graph, {"score": "50"}, db=db)
    path = [s["step_id"] for s in passed.result_data["steps"]]
    assert path == ["f", "after"]


# ==================== Error policy across branches ====================


async def test_stop_on_error_halts_the_run(db):
    graph = g.normalize_graph({
        "nodes": [
            _node("trigger", "trigger"),
            _node("bad", "webhook", {"url": "http://127.0.0.1:9/x", "timeout": 1}),
            _node("after", "speak", {"message": "should not run"}),
        ],
        "edges": [_edge("trigger", "bad"), _edge("bad", "after")],
    })

    execution = await _run_graph(graph, workflow_kwargs={"error_handling": "stop"}, db=db)
    path = [s["step_id"] for s in execution.result_data["steps"]]

    assert "bad" in path
    assert "after" not in path
    assert execution.status == "failed"


async def test_continue_on_error_keeps_downstream_running(db):
    graph = g.normalize_graph({
        "nodes": [
            _node("trigger", "trigger"),
            _node("bad", "webhook", {"url": "http://127.0.0.1:9/x", "timeout": 1},
                  settings={"on_error": "continue"}),
            _node("after", "speak", {"message": "still runs"}),
        ],
        "edges": [_edge("trigger", "bad"), _edge("bad", "after")],
    })

    execution = await _run_graph(graph, workflow_kwargs={"error_handling": "stop"}, db=db)
    path = [s["step_id"] for s in execution.result_data["steps"]]

    assert "bad" in path and "after" in path


# ==================== Handles ====================


async def test_output_handles_are_type_driven():
    assert g.output_handles("condition") == ["true", "false"]
    assert g.output_handles("speak") == ["out"]
    assert g.output_handles("end") == []
    assert g.output_handles("loop") == ["loop", "done"]
    assert g.output_handles("switch", {"rules": [{}, {}]}) == [
        "branch-0", "branch-1", "fallback"]


# ==================== Loop over items ====================


async def test_loop_runs_body_once_per_item(db):
    """The body sub-graph executes for every item, then `done` continues."""
    graph = g.normalize_graph({
        "nodes": [
            _node("trigger", "trigger"),
            _node("lp", "loop", {"items": "trigger.names"}),
            _node("body", "speak", {"message": "hello {{loop.item}}"}),
            _node("after", "speak", {"message": "finished"}),
        ],
        "edges": [_edge("trigger", "lp"),
                  _edge("lp", "body", "loop"),
                  _edge("lp", "after", "done")],
    })

    execution = await _run_graph(graph, {"names": ["ana", "bo", "cy"]}, db=db)
    steps = {s["step_id"]: s for s in execution.result_data["steps"]}

    assert steps["lp"]["result"]["iterations"] == 3
    # `done` continues after the loop finishes
    assert "after" in steps
    # each item was spoken
    spoken = [e["text"] for e in execution.result_data["transcript"]
              if e.get("type") == "speak"]
    assert "hello ana" in spoken and "hello cy" in spoken


async def test_loop_respects_max_iterations(db):
    graph = g.normalize_graph({
        "nodes": [
            _node("trigger", "trigger"),
            _node("lp", "loop", {"items": "trigger.nums", "max_iterations": 2}),
            _node("body", "speak", {"message": "n={{loop.item}}"}),
        ],
        "edges": [_edge("trigger", "lp"), _edge("lp", "body", "loop")],
    })

    execution = await _run_graph(graph, {"nums": [1, 2, 3, 4, 5]}, db=db)
    steps = {s["step_id"]: s for s in execution.result_data["steps"]}

    assert steps["lp"]["result"]["iterations"] == 2


async def test_loop_with_count_and_empty_body(db):
    graph = g.normalize_graph({
        "nodes": [
            _node("trigger", "trigger"),
            _node("lp", "loop", {"count": 3}),
            _node("after", "speak", {"message": "done"}),
        ],
        "edges": [_edge("trigger", "lp"), _edge("lp", "after", "done")],
    })

    execution = await _run_graph(graph, db=db)
    steps = {s["step_id"]: s for s in execution.result_data["steps"]}

    # No body wired to the `loop` output
    assert steps["lp"]["result"]["iterations"] == 0
    assert "after" in steps


async def test_loop_body_is_isolated_from_the_done_path():
    """subgraph_from must not pull `done` nodes into the body."""
    graph = g.normalize_graph({
        "nodes": [_node("lp", "loop"), _node("body", "speak"),
                  _node("after", "speak")],
        "edges": [_edge("lp", "body", "loop"), _edge("lp", "after", "done")],
    })

    body = g.subgraph_from(graph, "lp", "loop")
    ids = {n["id"] for n in body["nodes"]}

    assert ids == {"body"}
