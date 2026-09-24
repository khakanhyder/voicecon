"""
Agents and workflows can reschedule and cancel appointments, under rules that
suit a live phone call: deletes are opt-in per tool, updates and deletes need
the caller's confirmation, the calendar is pinned to the connection's choice,
and every change is recorded with the event as it was before.

Google itself is faked at the connector's HTTP helpers (get/patch/delete), so
these run the real registry, adapters, runner and connector logic.
"""
import uuid
from datetime import datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models.integration import IntegrationChange, IntegrationConnection, IntegrationConnector
from app.models.tool import Tool
from app.services.function_executor import FunctionExecutor
from app.services.integrations.action_registry import (
    get_action_schema,
    get_actions_for_connector,
    operation_of,
)
from app.services.integrations.action_runner import (
    SOURCE_AGENT,
    SOURCE_WORKFLOW,
    IntegrationActionError,
    run_integration_action,
)
from app.services.integrations.connector_base import ConnectorError
from app.services.integrations.connectors.google_calendar_connector import GoogleCalendarConnector

ORG = uuid.uuid4()
OTHER_ORG = uuid.uuid4()

EVENT = {
    "id": "evt1",
    "status": "confirmed",
    "summary": "Cleaning - Sara",
    "description": "Phone 0300 1234567",
    "location": "Pearl Dental, F-7",
    "attendees": [{"email": "sara@example.com"}],
    "start": {"dateTime": "2026-10-01T15:00:00+05:00", "timeZone": "Asia/Karachi"},
    "end": {"dateTime": "2026-10-01T15:45:00+05:00", "timeZone": "Asia/Karachi"},
}


class FakeGoogle:
    """Stands in for Google Calendar's REST API and records what was sent."""

    def __init__(self):
        self.calls = []
        self.event = dict(EVENT)
        self.delete_error = None

    def install(self, monkeypatch):
        fake = self

        async def get(self, path, params=None, **kw):
            fake.calls.append(("GET", path, params, None))
            if path.endswith("/events"):
                return {"items": [fake.event, {**fake.event, "id": "gone", "status": "cancelled"}]}
            if path.endswith("/missing"):
                raise ConnectorError("Request failed: HTTP 404: Not Found")
            return fake.event

        async def patch(self, path, json=None, params=None, **kw):
            fake.calls.append(("PATCH", path, params, json))
            return {**fake.event, **json}

        async def delete(self, path, params=None, **kw):
            fake.calls.append(("DELETE", path, params, None))
            if fake.delete_error:
                raise ConnectorError(fake.delete_error)
            return {}

        async def close(self):
            return None

        monkeypatch.setattr(GoogleCalendarConnector, "get", get)
        monkeypatch.setattr(GoogleCalendarConnector, "patch", patch)
        monkeypatch.setattr(GoogleCalendarConnector, "delete", delete)
        monkeypatch.setattr(GoogleCalendarConnector, "close", close, raising=False)
        return self

    def sent(self, method):
        return [c for c in self.calls if c[0] == method]


@pytest.fixture
def google(monkeypatch):
    return FakeGoogle().install(monkeypatch)


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


async def make_connection(db, org=ORG, default_calendar="clinic@group.calendar.google.com"):
    connector = (
        await db.execute(select(IntegrationConnector).where(IntegrationConnector.slug == "google-calendar"))
    ).scalar_one_or_none()
    if connector is None:
        connector = IntegrationConnector(
            id=uuid.uuid4(), name="Google Calendar", slug="google-calendar", auth_type="oauth2",
            base_url="https://www.googleapis.com",
        )
        db.add(connector)
    connection = IntegrationConnection(
        id=uuid.uuid4(), user_id=uuid.uuid4(), organization_id=org, connector_id=connector.id,
        config={"defaults": {"calendar_id": default_calendar}} if default_calendar else {},
    )
    db.add(connection)
    await db.commit()
    return connection


def run(db, connection, action, params, *, source=SOURCE_AGENT, allow_delete=False, org=ORG):
    return run_integration_action(
        db,
        organization_id=org,
        connection_id=connection.id,
        action=action,
        parameters=params,
        source=source,
        tool_config={"allow_destructive": "true" if allow_delete else "false"},
        call_id="call-42",
    )


async def changes(db):
    return (await db.execute(select(IntegrationChange))).scalars().all()


# ---- The registry ------------------------------------------------------------


def test_calendar_actions_are_labelled_by_what_they_do():
    ops = {a["action"]: a["operation"] for a in get_actions_for_connector("google-calendar")}
    assert ops["find_events"] == "read"
    assert ops["create_event"] == "create"
    assert ops["update_event"] == "update"
    assert ops["delete_event"] == "delete"
    flags = {a["action"]: a["destructive"] for a in get_actions_for_connector("google-calendar")}
    assert flags["delete_event"] is True and flags["update_event"] is False


def test_existing_storage_delete_counts_as_destructive():
    assert operation_of(get_action_schema("aws-s3", "delete_object")) == "delete"


# ---- What the agent is shown ---------------------------------------------------


def _tool(action, **cfg):
    return Tool(
        id=uuid.uuid4(), user_id=uuid.uuid4(), organization_id=ORG, name=f"Calendar {action}",
        description="Manage appointments", tool_type="connected_integration", category="integration",
        config={"connector_slug": "google-calendar", "action": action, "connection_id": str(uuid.uuid4()), **cfg},
    )


@pytest.mark.parametrize("action", ["update_event", "delete_event"])
def test_update_and_delete_tools_require_confirmation(action):
    definition = FunctionExecutor().get_tool_function_definition(_tool(action))
    assert definition["parameters"]["properties"]["confirmed"]["type"] == "boolean"
    assert "confirmed" in definition["parameters"]["required"]
    assert "read back" in definition["description"]


def test_older_saved_schema_still_gets_the_confirmation_flag():
    # Tools store their own copy of the parameter list; a tool saved before
    # this rule has no "confirmed" in it.
    saved = {"type": "object", "properties": {"event_id": {"type": "string"}}, "required": ["event_id"]}
    definition = FunctionExecutor().get_tool_function_definition(_tool("delete_event", parameters=saved))
    assert definition["parameters"]["required"] == ["event_id", "confirmed"]


def test_create_tools_are_unchanged():
    definition = FunctionExecutor().get_tool_function_definition(_tool("create_event"))
    assert "confirmed" not in definition["parameters"]["properties"]


# ---- Reschedule ---------------------------------------------------------------


@pytest.mark.asyncio
async def test_reschedule_needs_confirmation_and_changes_nothing_without_it(db, google):
    connection = await make_connection(db)
    result = await run(db, connection, "update_event", {"event_id": "evt1", "start_time": "2026-10-02T11:00:00+05:00"})
    assert result["needs_confirmation"] is True
    assert google.sent("PATCH") == []
    assert await changes(db) == []


@pytest.mark.asyncio
async def test_reschedule_patches_only_the_times_and_keeps_the_length(db, google):
    connection = await make_connection(db)
    result = await run(
        db, connection, "update_event",
        {"event_id": "evt1", "start_time": "2026-10-02T11:00:00+05:00", "confirmed": True},
    )
    assert result["updated"] is True
    [(_, path, params, body)] = google.sent("PATCH")
    # PATCH with only the times: attendees, notes, location and link survive.
    assert set(body) == {"start", "end"}
    assert body["start"] == {"dateTime": "2026-10-02T11:00:00+05:00", "timeZone": "Asia/Karachi"}
    # 45 minutes long before, 45 minutes long after.
    assert body["end"]["dateTime"] == "2026-10-02T11:45:00+05:00"
    assert params == {"sendUpdates": "all"}


@pytest.mark.asyncio
async def test_agent_cannot_point_at_another_calendar(db, google):
    connection = await make_connection(db)
    await run(
        db, connection, "update_event",
        {"event_id": "evt1", "start_time": "2026-10-02T11:00:00+05:00", "calendar_id": "someone-else", "confirmed": True},
    )
    [(_, path, _, _)] = google.sent("PATCH")
    assert "/calendars/clinic@group.calendar.google.com/events/evt1" in path


@pytest.mark.asyncio
async def test_reschedule_is_audited_with_the_event_as_it_was(db, google):
    connection = await make_connection(db)
    await run(
        db, connection, "update_event",
        {"event_id": "evt1", "start_time": "2026-10-02T11:00:00+05:00", "confirmed": True},
    )
    [change] = await changes(db)
    assert (change.operation, change.record_id, change.source, change.call_id, change.success) == (
        "update", "evt1", "agent", "call-42", True,
    )
    assert change.before["start"]["dateTime"] == "2026-10-01T15:00:00+05:00"
    assert "confirmed" not in change.parameters


@pytest.mark.asyncio
async def test_rescheduling_a_cancelled_event_is_refused(db, google):
    google.event = {**EVENT, "status": "cancelled"}
    connection = await make_connection(db)
    with pytest.raises(ConnectorError, match="cancelled"):
        await run(db, connection, "update_event", {"event_id": "evt1", "start_time": "2026-10-02T11:00:00", "confirmed": True})
    [change] = await changes(db)
    assert change.success is False


@pytest.mark.asyncio
async def test_unknown_event_gets_a_sentence_the_agent_can_use(db, google):
    connection = await make_connection(db)
    with pytest.raises(ConnectorError, match="No appointment with that id"):
        await run(db, connection, "update_event", {"event_id": "missing", "title": "x", "confirmed": True})


@pytest.mark.asyncio
async def test_end_before_start_is_refused(db, google):
    connection = await make_connection(db)
    with pytest.raises(ConnectorError, match="after the new start"):
        await run(
            db, connection, "update_event",
            {"event_id": "evt1", "start_time": "2026-10-02T11:00:00+05:00", "end_time": "2026-10-02T10:00:00+05:00", "confirmed": True},
        )


# ---- Cancel -------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cancel_is_refused_unless_the_tool_allows_deleting(db, google):
    connection = await make_connection(db)
    with pytest.raises(IntegrationActionError, match="Allow deleting"):
        await run(db, connection, "delete_event", {"event_id": "evt1", "confirmed": True})
    assert google.sent("DELETE") == []


@pytest.mark.asyncio
async def test_cancel_needs_confirmation_even_when_allowed(db, google):
    connection = await make_connection(db)
    result = await run(db, connection, "delete_event", {"event_id": "evt1"}, allow_delete=True)
    assert result["needs_confirmation"] is True
    assert google.sent("DELETE") == []


@pytest.mark.asyncio
async def test_confirmed_cancel_deletes_and_is_audited(db, google):
    connection = await make_connection(db)
    result = await run(db, connection, "delete_event", {"event_id": "evt1", "confirmed": "true"}, allow_delete=True)
    assert result["cancelled"] is True
    [(_, path, params, _)] = google.sent("DELETE")
    assert path.endswith("/events/evt1") and params == {"sendUpdates": "all"}
    [change] = await changes(db)
    assert change.operation == "delete" and change.before["summary"] == "Cleaning - Sara"


@pytest.mark.asyncio
async def test_cancelling_twice_is_not_an_error(db, google):
    google.delete_error = "Request failed: HTTP 410: Resource has been deleted"
    connection = await make_connection(db)
    result = await run(db, connection, "delete_event", {"event_id": "evt1", "confirmed": True}, allow_delete=True)
    assert result["already_cancelled"] is True


# ---- Find ---------------------------------------------------------------------


@pytest.mark.asyncio
async def test_find_searches_upcoming_events_and_hides_cancelled_ones(db, google):
    connection = await make_connection(db)
    result = await run(db, connection, "find_events", {"query": "sara@example.com", "time_zone": "Asia/Karachi"})
    [(_, path, params, _)] = google.sent("GET")
    assert params["q"] == "sara@example.com" and params["singleEvents"] is True
    assert params["timeZone"] == "Asia/Karachi"
    window = datetime.fromisoformat(params["timeMax"].rstrip("Z")) - datetime.fromisoformat(params["timeMin"].rstrip("Z"))
    assert window >= timedelta(days=89)
    assert [e["id"] for e in result["events"]] == ["evt1"]
    assert result["events"][0]["attendees"] == ["sara@example.com"]
    assert await changes(db) == []  # reads are not audited


# ---- Guards shared with workflows ---------------------------------------------


@pytest.mark.asyncio
async def test_unlisted_connector_methods_cannot_be_called(db, google):
    # get_primary_calendar_id exists on the connector but is not an action.
    connection = await make_connection(db)
    with pytest.raises(IntegrationActionError, match="not available"):
        await run(db, connection, "get_primary_calendar_id", {})


@pytest.mark.asyncio
async def test_another_workspaces_connection_is_not_found(db, google):
    connection = await make_connection(db, org=OTHER_ORG)
    with pytest.raises(IntegrationActionError, match="not found"):
        await run(db, connection, "find_events", {"query": "x"})


@pytest.mark.asyncio
async def test_workflow_steps_run_updates_without_the_agent_rules_but_are_audited(db, google):
    # A workflow step is designed by a person, not improvised mid-call.
    connection = await make_connection(db)
    await run(db, connection, "delete_event", {"event_id": "evt1"}, source=SOURCE_WORKFLOW)
    assert len(google.sent("DELETE")) == 1
    [change] = await changes(db)
    assert change.source == "workflow"


@pytest.mark.asyncio
async def test_workflow_steps_still_let_their_author_choose_the_calendar(db, google):
    connection = await make_connection(db)
    await run(db, connection, "find_events", {"query": "x", "calendar_id": "chosen"}, source=SOURCE_WORKFLOW)
    [(_, path, _, _)] = google.sent("GET")
    assert "/calendars/chosen/events" in path


# ---- End to end through the agent's tool executor ----------------------------


@pytest.mark.asyncio
async def test_agent_tool_call_end_to_end(db, google):
    connection = await make_connection(db)
    tool = _tool("delete_event", connection_id=str(connection.id), allow_destructive="true")
    db.add(tool)
    await db.commit()

    executor = FunctionExecutor()
    first = await executor.execute_global_tool(tool, {"event_id": "evt1"}, call_id="call-7", db=db)
    assert first["result"]["needs_confirmation"] is True

    second = await executor.execute_global_tool(tool, {"event_id": "evt1", "confirmed": True}, call_id="call-7", db=db)
    assert second["success"] is True and second["result"]["cancelled"] is True
    [change] = await changes(db)
    assert change.tool_id == tool.id and change.call_id == "call-7"


@pytest.mark.asyncio
async def test_agent_tool_without_delete_permission_reports_why(db, google):
    connection = await make_connection(db)
    tool = _tool("delete_event", connection_id=str(connection.id))
    db.add(tool)
    await db.commit()
    out = await FunctionExecutor().execute_global_tool(tool, {"event_id": "evt1", "confirmed": True}, db=db)
    assert out["success"] is False and "Allow deleting" in out["error"]


# ---- Saving a tool -------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "action, allow, error",
    [
        ("delete_event", None, True),
        ("delete_event", "false", True),
        ("delete_event", "true", False),
        ("update_event", None, False),  # updates are guarded by confirmation, not opt-in
        ("find_events", None, False),
    ],
)
async def test_saving_a_delete_tool_requires_allow_deleting(db, action, allow, error):
    from app.services.tools.validation import check_tool_references

    connection = await make_connection(db)
    config = {"connection_id": str(connection.id), "action": action}
    if allow is not None:
        config["allow_destructive"] = allow
    connection.is_active = True
    await db.commit()
    errors = await check_tool_references("connected_integration", config, ORG, db)
    assert ("allow_destructive" in errors) is error
