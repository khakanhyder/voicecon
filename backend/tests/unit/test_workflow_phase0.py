"""
Regression tests for the workflow Phase 0 stabilization fixes.

Each test here pins a specific defect that existed before the fix, so a
regression fails loudly rather than silently reintroducing a security hole.

Runs on an in-memory SQLite database (the models use SQLAlchemy's generic Uuid
and JSON types) so it needs no external Postgres.
"""
import asyncio
import uuid
from datetime import datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models.integration import Workflow, WorkflowExecution
from app.schemas.workflow import TriggerType
from app.services.workflows.scheduler import WorkflowScheduler
from app.services.workflows.trigger_handlers import (
    TriggerError,
    TriggerManager,
    TriggerValidator,
    WebhookTriggerHandler,
)
from app.services.workflows.workflow_engine import reap_stranded_executions


pytestmark = pytest.mark.asyncio


# ==================== Fixtures ====================


@pytest_asyncio.fixture
async def db() -> AsyncSession:
    """In-memory SQLite session with the full schema created."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    await engine.dispose()


async def _make_workflow(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    trigger_type: str,
    trigger_config: dict | None = None,
    is_active: bool = True,
    last_executed_at: datetime | None = None,
) -> Workflow:
    """Insert a workflow with a single no-op step."""
    workflow = Workflow(
        user_id=uuid.uuid4(),
        organization_id=organization_id,
        name="test workflow",
        trigger_type=trigger_type,
        trigger_config=trigger_config or {},
        workflow_steps={"steps": [{"id": "s1", "type": "end", "config": {}}]},
        is_active=is_active,
        last_executed_at=last_executed_at,
    )
    db.add(workflow)
    await db.commit()
    await db.refresh(workflow)
    return workflow


# ==================== Cross-tenant trigger isolation ====================


async def test_process_event_requires_organization_id(db):
    """process_event must refuse to run unscoped.

    It previously had no organization parameter at all and selected every
    active workflow of the trigger type across all tenants.
    """
    manager = TriggerManager(db)

    with pytest.raises(TriggerError, match="organization_id is required"):
        await manager.process_event(
            TriggerType.CALL_COMPLETED,
            {"status": "completed"},
            organization_id=None,
        )


async def test_process_event_ignores_other_organizations(db, monkeypatch):
    """A tenant's event must never select another tenant's workflows."""
    org_a, org_b = uuid.uuid4(), uuid.uuid4()

    mine = await _make_workflow(db, organization_id=org_a, trigger_type="call_completed")
    theirs = await _make_workflow(db, organization_id=org_b, trigger_type="call_completed")

    triggered: list[str] = []

    async def fake_trigger_all(self, event_type, event_data, workflows):
        triggered.extend(str(w.id) for w in workflows)
        return []

    monkeypatch.setattr(TriggerManager, "_trigger_all", fake_trigger_all)

    manager = TriggerManager(db)
    await manager.process_event(
        TriggerType.CALL_COMPLETED,
        {"status": "completed"},
        organization_id=org_a,
    )

    assert triggered == [str(mine.id)]
    assert str(theirs.id) not in triggered


async def test_process_event_excludes_inactive_and_deleted(db, monkeypatch):
    """Inactive and soft-deleted workflows must not be candidates."""
    org = uuid.uuid4()

    active = await _make_workflow(db, organization_id=org, trigger_type="call_completed")
    await _make_workflow(
        db, organization_id=org, trigger_type="call_completed", is_active=False
    )
    deleted = await _make_workflow(db, organization_id=org, trigger_type="call_completed")
    deleted.deleted_at = datetime.utcnow()
    await db.commit()

    seen: list[str] = []

    async def fake_trigger_all(self, event_type, event_data, workflows):
        seen.extend(str(w.id) for w in workflows)
        return []

    monkeypatch.setattr(TriggerManager, "_trigger_all", fake_trigger_all)

    await TriggerManager(db).process_event(
        TriggerType.CALL_COMPLETED, {}, organization_id=org
    )

    assert seen == [str(active.id)]


# ==================== Webhook fails closed ====================


async def test_webhook_without_configured_key_never_triggers(db):
    """A keyless webhook workflow used to match ANY key on a public endpoint."""
    handler = WebhookTriggerHandler(db)

    assert await handler.should_trigger({}, {"webhook_key": "anything"}) is False
    assert await handler.should_trigger({"webhook_key": ""}, {"webhook_key": ""}) is False
    assert await handler.should_trigger({}, {}) is False


async def test_webhook_key_must_match(db):
    """A configured key must compare equal to the supplied one."""
    handler = WebhookTriggerHandler(db)
    config = {"webhook_key": "k" * 32}

    assert await handler.should_trigger(config, {"webhook_key": "k" * 32}) is True
    assert await handler.should_trigger(config, {"webhook_key": "wrong"}) is False
    assert await handler.should_trigger(config, {}) is False
    # Non-string keys must not blow up compare_digest
    assert await handler.should_trigger(config, {"webhook_key": 12345}) is False


async def test_webhook_ip_allowlist_still_enforced(db):
    """The IP allowlist must keep working alongside the key check."""
    handler = WebhookTriggerHandler(db)
    config = {"webhook_key": "k" * 32, "allowed_ips": ["10.0.0.1"]}

    assert await handler.should_trigger(
        config, {"webhook_key": "k" * 32, "source_ip": "10.0.0.1"}
    ) is True
    assert await handler.should_trigger(
        config, {"webhook_key": "k" * 32, "source_ip": "10.0.0.9"}
    ) is False


async def test_process_webhook_returns_empty_for_blank_key(db):
    assert await TriggerManager(db).process_webhook("", {}) == []


# ==================== Trigger validation ====================


async def test_validator_rejects_bad_cron():
    with pytest.raises(TriggerError, match="Invalid cron expression"):
        TriggerValidator.validate_trigger_config(
            TriggerType.SCHEDULE,
            {"schedule_type": "cron", "cron_expression": "not a cron"},
        )


async def test_validator_rejects_short_webhook_key():
    with pytest.raises(TriggerError, match="at least 16 characters"):
        TriggerValidator.validate_trigger_config(
            TriggerType.WEBHOOK, {"webhook_key": "short"}
        )


async def test_validator_accepts_valid_schedule():
    TriggerValidator.validate_trigger_config(
        TriggerType.SCHEDULE,
        {"schedule_type": "cron", "cron_expression": "*/5 * * * *"},
    )


async def test_prepare_trigger_config_generates_webhook_key():
    """Webhook workflows need a key: matching now fails closed without one."""
    from app.api.v1.endpoints.workflows import _prepare_trigger_config

    config = _prepare_trigger_config(TriggerType.WEBHOOK, {})

    assert len(config["webhook_key"]) >= 16
    # An explicitly supplied key is preserved
    supplied = _prepare_trigger_config(TriggerType.WEBHOOK, {"webhook_key": "z" * 20})
    assert supplied["webhook_key"] == "z" * 20


async def test_prepare_trigger_config_raises_http_400_on_invalid():
    from fastapi import HTTPException
    from app.api.v1.endpoints.workflows import _prepare_trigger_config

    with pytest.raises(HTTPException) as exc:
        _prepare_trigger_config(
            TriggerType.SCHEDULE, {"schedule_type": "cron", "cron_expression": "bad"}
        )

    assert exc.value.status_code == 400


# ==================== Scheduler: no duplicate firing ====================


async def test_claim_is_won_only_once(db):
    """Two concurrent polls seeing the same due workflow must not both fire it."""
    org = uuid.uuid4()
    workflow = await _make_workflow(
        db,
        organization_id=org,
        trigger_type="schedule",
        trigger_config={"schedule_type": "interval", "interval_seconds": 60},
    )

    scheduler = WorkflowScheduler()
    now = datetime.utcnow()

    first = await scheduler._claim(db, workflow, now)
    # Second poll still holds the stale pre-claim value it read earlier
    second = await scheduler._claim(db, workflow, now + timedelta(seconds=1))

    assert first is True
    assert second is False


async def test_claim_deactivates_one_time_schedule(db):
    """A one-time schedule is disabled in the same UPDATE that claims it."""
    org = uuid.uuid4()
    workflow = await _make_workflow(
        db,
        organization_id=org,
        trigger_type="schedule",
        trigger_config={"schedule_type": "one_time"},
    )

    scheduler = WorkflowScheduler()
    claimed = await scheduler._claim(db, workflow, datetime.utcnow(), deactivate=True)

    assert claimed is True

    # The claim deliberately does not synchronize the session, so re-read from
    # the database rather than trusting the identity-mapped instance.
    await db.refresh(workflow)
    assert workflow.is_active is False
    assert workflow.last_executed_at is not None


async def test_claim_fails_on_inactive_workflow(db):
    """An already-deactivated workflow cannot be claimed."""
    org = uuid.uuid4()
    workflow = await _make_workflow(
        db,
        organization_id=org,
        trigger_type="schedule",
        trigger_config={"schedule_type": "interval", "interval_seconds": 60},
        is_active=False,
    )

    scheduler = WorkflowScheduler()
    assert await scheduler._claim(db, workflow, datetime.utcnow()) is False


async def test_one_time_schedule_handles_tz_aware_iso_string(db):
    """A 'Z'-suffixed scheduled_at parses to an aware datetime.

    Comparing that against naive utcnow() previously raised TypeError.
    """
    org = uuid.uuid4()
    past = (datetime.utcnow() - timedelta(hours=1)).isoformat() + "Z"
    workflow = await _make_workflow(
        db,
        organization_id=org,
        trigger_type="schedule",
        trigger_config={"schedule_type": "one_time", "scheduled_at": past},
    )

    scheduler = WorkflowScheduler()
    # Must not raise, and the time has passed so it is due
    assert await scheduler._check_one_time_schedule(workflow, datetime.utcnow()) is True


# ==================== Scheduler: task lifecycle ====================


async def test_spawn_trigger_keeps_strong_reference(monkeypatch):
    """In-flight dispatches must be strongly referenced or asyncio may GC them."""
    scheduler = WorkflowScheduler()
    started = asyncio.Event()
    release = asyncio.Event()

    async def fake_trigger(workflow_id, schedule_type=None):
        started.set()
        await release.wait()

    monkeypatch.setattr(scheduler, "_trigger_workflow", fake_trigger)

    scheduler._spawn_trigger("wf-1", "cron")
    await started.wait()

    assert len(scheduler._trigger_tasks) == 1

    release.set()
    await asyncio.gather(*scheduler._trigger_tasks, return_exceptions=True)
    # done_callback discards the finished task
    assert len(scheduler._trigger_tasks) == 0


async def test_stop_cancels_inflight_tasks(monkeypatch):
    """stop() must cancel dispatches rather than leaking them."""
    scheduler = WorkflowScheduler()
    started = asyncio.Event()

    async def never_finishes(workflow_id, schedule_type=None):
        started.set()
        await asyncio.sleep(3600)

    monkeypatch.setattr(scheduler, "_trigger_workflow", never_finishes)

    scheduler._spawn_trigger("wf-1", "cron")
    await started.wait()

    await scheduler.stop()

    assert len(scheduler._trigger_tasks) == 0


async def test_trigger_workflow_does_not_take_a_session():
    """It must open its own session; the poll loop's session is already closed.

    Guards against reintroducing `_trigger_workflow(workflow, db)`.
    """
    import inspect

    params = inspect.signature(WorkflowScheduler._trigger_workflow).parameters
    assert "db" not in params
    assert "workflow_id" in params


# ==================== Stranded execution reaper ====================


async def test_reaper_marks_running_executions_failed(db):
    org = uuid.uuid4()
    workflow = await _make_workflow(db, organization_id=org, trigger_type="manual")

    running = WorkflowExecution(
        workflow_id=workflow.id,
        status="running",
        started_at=datetime.utcnow() - timedelta(hours=2),
    )
    completed = WorkflowExecution(
        workflow_id=workflow.id,
        status="completed",
        started_at=datetime.utcnow() - timedelta(hours=2),
    )
    db.add_all([running, completed])
    await db.commit()

    reaped = await reap_stranded_executions(db)

    assert reaped == 1

    rows = (await db.execute(select(WorkflowExecution))).scalars().all()
    by_id = {r.id: r for r in rows}
    assert by_id[running.id].status == "failed"
    assert by_id[running.id].completed_at is not None
    assert "interrupted" in by_id[running.id].error_message
    # An already-finished run is untouched
    assert by_id[completed.id].status == "completed"


async def test_reaper_age_threshold_spares_fresh_runs(db):
    """The periodic sweep must not kill runs that are still legitimately alive."""
    org = uuid.uuid4()
    workflow = await _make_workflow(db, organization_id=org, trigger_type="manual")

    fresh = WorkflowExecution(
        workflow_id=workflow.id, status="running", started_at=datetime.utcnow()
    )
    stale = WorkflowExecution(
        workflow_id=workflow.id,
        status="running",
        started_at=datetime.utcnow() - timedelta(hours=3),
    )
    db.add_all([fresh, stale])
    await db.commit()

    reaped = await reap_stranded_executions(db, older_than_seconds=3600)

    assert reaped == 1

    rows = {r.id: r for r in (await db.execute(select(WorkflowExecution))).scalars().all()}
    assert rows[fresh.id].status == "running"
    assert rows[stale.id].status == "failed"


async def test_reaper_is_noop_when_nothing_stranded(db):
    assert await reap_stranded_executions(db) == 0
