"""
list_events can express event times in the business's own time zone.

Google answers in the calendar's zone by default. The Pearl Dental demo
calendar is set to US Eastern, so an 11:00 Islamabad booking came back as
02:00-04:00 and the agent had to convert it before offering free slots.
"""
import pytest

from app.services.integrations.action_registry import (
    adapt_parameters,
    drop_unsupported_arguments,
)
from app.services.integrations.connectors.google_calendar_connector import (
    GoogleCalendarConnector,
)


class _Recorder(GoogleCalendarConnector):
    def __init__(self):
        self.calls = []

    async def get(self, path, params=None, **kwargs):
        self.calls.append((path, params))
        return {"items": []}


@pytest.mark.asyncio
async def test_time_zone_is_sent_to_google():
    connector = _Recorder()
    await connector.list_events(time_min="2026-09-19T00:00:00Z", time_zone="Asia/Karachi")
    _, params = connector.calls[0]
    assert params["timeZone"] == "Asia/Karachi"


@pytest.mark.asyncio
async def test_time_zone_is_optional():
    connector = _Recorder()
    await connector.list_events(time_min="2026-09-19T00:00:00Z")
    _, params = connector.calls[0]
    assert "timeZone" not in params


def test_workflow_parameter_reaches_the_method():
    # The exact path a workflow action step takes: schema names are adapted,
    # then anything the method does not declare is dropped.
    params = adapt_parameters(
        "google-calendar",
        "list_events",
        {"start_date": "2026-09-19", "time_zone": "Asia/Karachi"},
    )
    params = drop_unsupported_arguments(_Recorder().list_events, params)
    assert params["time_zone"] == "Asia/Karachi"
    assert params["time_min"] == "2026-09-19T00:00:00Z"


def test_list_events_reads_the_connections_default_calendar():
    """Bookings and availability must look at the same calendar.

    create_event declared calendar_id, so the connection's default calendar
    filled it in; list_events did not, so it read "primary" and a slot that
    had just been booked still looked free.
    """
    from app.services.integrations.action_registry import get_action_schema
    from app.services.integrations.resource_registry import apply_connection_defaults

    config = {"defaults": {"calendar_id": "clinic@group.calendar.google.com"}}
    for action in ("create_event", "list_events"):
        schema = get_action_schema("google-calendar", action)
        accepted = set(schema["parameters"]["properties"])
        filled = apply_connection_defaults({}, config, accepted_keys=accepted)
        assert filled.get("calendar_id") == "clinic@group.calendar.google.com", action
