"""
Tests for the no-code data steps (Set Fields transforms, Calculate) and live
execution events.

These replace the former Code node sandbox tests. The builder is deliberately
code-free, so the cases below assert that the arithmetic and formatting a user
previously had to write Python for is reachable from configuration alone.
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
from app.services.workflows.step_handlers import (
    CalculateStepHandler,
    StepExecutionError,
    TransformStepHandler,
    WorkflowContext,
)
from app.services.workflows.workflow_engine import WorkflowEngine

pytestmark = pytest.mark.asyncio

ORDERS = [{"sku": "A", "amount": 120.5},
          {"sku": "B", "amount": 430.25},
          {"sku": "C", "amount": 19.99}]


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


async def set_fields(transformations, trigger=None):
    """Run a Set Fields step and return both its output and the context."""
    context = WorkflowContext(trigger if trigger is not None else {"orders": ORDERS})
    result = await TransformStepHandler().execute(
        {"id": "s", "type": "transform", "config": {"transformations": transformations}},
        context,
    )
    return result["result"], context


async def calculate(rows, trigger=None, **config):
    """Run a Calculate step and return its output."""
    context = WorkflowContext(trigger or {})
    result = await CalculateStepHandler().execute(
        {"id": "c", "type": "calculate", "config": {"calculations": rows, **config}},
        context,
    )
    return result["result"]


# ==================== Set Fields: transforms ====================


async def test_sum_over_a_list_of_objects():
    """The order-total case that previously required a Code node."""
    out, _ = await set_fields(
        {"total": {"source": "{{trigger.orders}}", "transform": "sum", "args": "amount"}}
    )
    assert out["total"] == 570.74


async def test_count_average_min_and_max():
    out, _ = await set_fields({
        "n": {"source": "{{trigger.orders}}", "transform": "count"},
        "biggest": {"source": "{{trigger.orders}}", "transform": "max_value", "args": "amount"},
        "smallest": {"source": "{{trigger.orders}}", "transform": "min_value", "args": "amount"},
    })
    assert out == {"n": 3, "biggest": 430.25, "smallest": 19.99}


async def test_transform_result_is_published_as_a_variable():
    """Later steps reference the field by bare name, e.g. {{total}}."""
    _, context = await set_fields(
        {"total": {"source": "{{trigger.orders}}", "transform": "sum", "args": "amount"}}
    )
    assert context.get_variable("total") == 570.74
    assert context.interpolate("You owe {{total}}") == "You owe 570.74"


async def test_string_and_currency_formatting():
    out, _ = await set_fields(
        {
            "name": {"source": "{{trigger.first}}", "transform": "capitalize"},
            "price": {"source": "{{trigger.amount}}", "transform": "format_currency",
                      "args": "USD"},
        },
        trigger={"first": "sajid", "amount": 570.74},
    )
    assert out == {"name": "Sajid", "price": "$570.74"}


async def test_unbraced_source_path_also_resolves():
    """The dict form predates the builder and used bare paths; both must work."""
    out, _ = await set_fields(
        {"n": {"source": "trigger.orders", "transform": "count"}}
    )
    assert out["n"] == 3


async def test_default_fills_in_a_missing_value():
    out, _ = await set_fields(
        {"tier": {"source": "{{trigger.tier}}", "default": "standard"}}
    )
    assert out["tier"] == "standard"


async def test_plain_string_fields_still_interpolate():
    """v1 workflows wrote plain strings here; they must keep working untouched."""
    out, _ = await set_fields(
        {"greeting": "Hello {{trigger.first}}"}, trigger={"first": "Sajid"}
    )
    assert out["greeting"] == "Hello Sajid"


# ==================== Calculate ====================


async def test_basic_arithmetic():
    out = await calculate(
        [{"name": "total", "left": "{{trigger.price}}", "operator": "multiply",
          "right": "{{trigger.qty}}"}],
        trigger={"price": 25, "qty": 4},
    )
    assert out["total"] == 100


async def test_rows_build_on_earlier_rows():
    """Sequential evaluation: subtotal -> tax -> total, in one node."""
    out = await calculate(
        [
            {"name": "subtotal", "left": "{{trigger.price}}", "operator": "multiply",
             "right": "{{trigger.qty}}"},
            {"name": "tax", "left": "15", "operator": "percent_of", "right": "{{subtotal}}"},
            {"name": "total", "left": "{{subtotal}}", "operator": "add", "right": "{{tax}}"},
        ],
        trigger={"price": 100, "qty": 2},
    )
    assert out == {"subtotal": 200, "tax": 30, "total": 230}


async def test_floating_point_noise_is_not_spoken():
    """0.1 + 0.2 must not reach a caller as 0.30000000000000004."""
    out = await calculate(
        [{"name": "x", "left": "0.1", "operator": "add", "right": "0.2"}]
    )
    assert out["x"] == 0.3


async def test_decimals_setting_rounds_the_result():
    out = await calculate(
        [{"name": "x", "left": "10", "operator": "divide", "right": "3"}], decimals=2
    )
    assert out["x"] == 3.33


async def test_missing_operand_fails_loudly():
    """A blank must stop the step, not flow on to be read out as silence."""
    with pytest.raises(StepExecutionError) as excinfo:
        await calculate(
            [{"name": "total", "left": "{{nope}}", "operator": "add", "right": "1"}]
        )
    assert "total" in str(excinfo.value)


async def test_non_numeric_operand_names_the_row():
    with pytest.raises(StepExecutionError) as excinfo:
        await calculate(
            [{"name": "total", "left": "abc", "operator": "add", "right": "1"}]
        )
    assert "not a number" in str(excinfo.value)


async def test_divide_by_zero_is_reported_not_raised_as_zerodivision():
    with pytest.raises(StepExecutionError) as excinfo:
        await calculate(
            [{"name": "x", "left": "1", "operator": "divide", "right": "0"}]
        )
    assert "divide by zero" in str(excinfo.value)


# ==================== The Code node's job, done without code ====================


async def test_order_total_workflow_needs_no_code_node(db):
    """
    End-to-end equivalent of the removed test_code_node_runs_in_a_workflow:
    same goal ("The total is 42"), expressed entirely in node configuration.
    """
    graph = {
        "schema_version": 2,
        "nodes": [
            {"id": "trigger", "type": "trigger", "name": "T",
             "position": {"x": 0, "y": 0}, "config": {}},
            {"id": "calc", "type": "transform", "name": "Compute",
             "position": {"x": 0, "y": 1},
             "config": {"transformations": {
                 "total": {"source": "{{trigger.nums}}", "transform": "sum"}}}},
            {"id": "say", "type": "speak", "name": "Say",
             "position": {"x": 0, "y": 2},
             "config": {"message": "The total is {{total}}"}},
        ],
        "edges": [
            {"id": "e1", "source": "trigger", "sourceHandle": "out", "target": "calc"},
            {"id": "e2", "source": "calc", "sourceHandle": "out", "target": "say"},
        ],
    }
    wf = Workflow(user_id=uuid.uuid4(), organization_id=uuid.uuid4(), name="no-code",
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
    spoken = [e["text"] for e in execution.result_data["transcript"]
              if e.get("type") == "speak"]
    assert "The total is 42" in spoken


async def test_calculate_node_runs_in_a_workflow(db):
    graph = {
        "schema_version": 2,
        "nodes": [
            {"id": "trigger", "type": "trigger", "name": "T",
             "position": {"x": 0, "y": 0}, "config": {}},
            {"id": "calc", "type": "calculate", "name": "Total",
             "position": {"x": 0, "y": 1},
             "config": {"calculations": [
                 {"name": "due", "left": "{{trigger.price}}",
                  "operator": "multiply", "right": "{{trigger.months}}"}]}},
            {"id": "say", "type": "speak", "name": "Say",
             "position": {"x": 0, "y": 2},
             "config": {"message": "You owe {{due}} dollars."}},
        ],
        "edges": [
            {"id": "e1", "source": "trigger", "sourceHandle": "out", "target": "calc"},
            {"id": "e2", "source": "calc", "sourceHandle": "out", "target": "say"},
        ],
    }
    wf = Workflow(user_id=uuid.uuid4(), organization_id=uuid.uuid4(), name="calc",
                  trigger_type="manual", trigger_config={}, workflow_steps=graph,
                  is_active=True, error_handling="stop", max_retries=0, retry_delay=0)
    db.add(wf)
    await db.commit()
    await db.refresh(wf)

    channel = SimulatedChannel()
    execution = await WorkflowEngine(db).execute_workflow(
        workflow_id=str(wf.id), trigger_data={"price": 49, "months": 3},
        wait_for_completion=True, channel=channel)
    await db.refresh(execution)

    spoken = [e["text"] for e in execution.result_data["transcript"]
              if e.get("type") == "speak"]
    assert "You owe 147 dollars." in spoken


async def test_removed_code_node_fails_cleanly(db):
    """
    A workflow saved before the Code node was removed must not crash the engine.
    The node fails with a clear message and the run is marked failed.
    """
    graph = {
        "schema_version": 2,
        "nodes": [
            {"id": "trigger", "type": "trigger", "name": "T",
             "position": {"x": 0, "y": 0}, "config": {}},
            {"id": "old", "type": "code", "name": "Legacy code",
             "position": {"x": 0, "y": 1}, "config": {"code": "result = 1"}},
        ],
        "edges": [
            {"id": "e1", "source": "trigger", "sourceHandle": "out", "target": "old"},
        ],
    }
    wf = Workflow(user_id=uuid.uuid4(), organization_id=uuid.uuid4(), name="legacy",
                  trigger_type="manual", trigger_config={}, workflow_steps=graph,
                  is_active=True, error_handling="continue", max_retries=0, retry_delay=0)
    db.add(wf)
    await db.commit()
    await db.refresh(wf)

    execution = await WorkflowEngine(db).execute_workflow(
        workflow_id=str(wf.id), trigger_data={}, wait_for_completion=True,
        channel=SimulatedChannel())
    await db.refresh(execution)

    assert execution.status == "failed"
    steps = {s["step_id"]: s for s in execution.result_data["steps"]}
    assert "Unknown step type: code" in steps["old"]["error"]


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


async def test_date_transforms_accept_iso_timestamps():
    """
    Triggers and APIs send ISO timestamps, not bare dates. Add days / Add hours
    used to reject every one of them with "unconverted data remains: T09:30:00".
    """
    out, _ = await set_fields(
        {
            "followup": {"source": "{{trigger.when}}", "transform": "add_days", "args": "7"},
            "later": {"source": "{{trigger.when}}", "transform": "add_hours", "args": "2"},
            "day": {"source": "{{trigger.when}}", "transform": "format_date",
                    "args": "%d %b %Y"},
        },
        trigger={"when": "2026-08-20T09:30:00"},
    )
    assert str(out["followup"]).startswith("2026-08-27")
    assert str(out["later"]).startswith("2026-08-20 11:30")
    assert out["day"] == "20 Aug 2026"


async def test_plain_date_strings_still_parse():
    out, _ = await set_fields(
        {"followup": {"source": "{{trigger.when}}", "transform": "add_days", "args": "7"}},
        trigger={"when": "2026-08-20"},
    )
    assert str(out["followup"]).startswith("2026-08-27")


# ==================== Missing / wrong-shaped data ====================


async def test_missing_value_names_the_field_and_transform():
    """
    The raw failure was "float() argument must be a string or a real number,
    not 'NoneType'" — true, and useless to whoever built the step.
    """
    with pytest.raises(StepExecutionError) as excinfo:
        await set_fields(
            {"price": {"source": "{{grand_total}}", "transform": "format_currency",
                       "args": "USD"}},
            trigger={},
        )
    message = str(excinfo.value)
    assert "price" in message
    assert "format_currency" in message
    assert "grand_total" in message
    assert "float()" not in message


async def test_a_default_satisfies_a_missing_value_before_the_transform():
    """A default should be formatted, not bypassed."""
    out, _ = await set_fields(
        {"price": {"source": "{{missing}}", "transform": "format_currency",
                   "args": "USD", "default": "0"}},
        trigger={},
    )
    assert out["price"] == "$0.00"


async def test_aggregations_still_answer_for_an_empty_list():
    """No orders really does total 0 — that is an answer, not a broken reference."""
    out, _ = await set_fields(
        {
            "total": {"source": "{{trigger.orders}}", "transform": "sum", "args": "amount"},
            "n": {"source": "{{trigger.orders}}", "transform": "count"},
        },
        trigger={"orders": []},
    )
    assert out == {"total": 0, "n": 0}


async def test_text_transform_rejects_a_list_instead_of_voicing_a_repr():
    """str([]) is "[]", which a Speak step would read to the caller verbatim."""
    with pytest.raises(StepExecutionError) as excinfo:
        await set_fields(
            {"name": {"source": "{{trigger.orders}}", "transform": "uppercase"}},
            trigger={"orders": [{"sku": "A"}]},
        )
    assert "expected text but got a list" in str(excinfo.value)


async def test_a_bad_transform_argument_names_the_argument():
    with pytest.raises(StepExecutionError) as excinfo:
        await set_fields(
            {"n": {"source": "{{trigger.n}}", "transform": "round", "args": "abc"}},
            trigger={"n": 3.14159},
        )
    assert "argument 'abc'" in str(excinfo.value)


async def test_count_of_blank_text_is_zero_not_one():
    out, _ = await set_fields(
        {"n": {"source": "{{trigger.note}}", "transform": "count"}},
        trigger={"note": "   "},
    )
    assert out["n"] == 0


async def test_error_message_is_not_double_prefixed():
    """The outer handler must not prepend "Transform step failed:" to a message
    that was already written for the builder."""
    with pytest.raises(StepExecutionError) as excinfo:
        await set_fields(
            {"price": {"source": "{{nope}}", "transform": "round", "args": "2"}},
            trigger={},
        )
    assert str(excinfo.value).startswith("Set Fields:")
