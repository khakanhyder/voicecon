"""
find_available_slots must offer times a business can actually be booked at.

Given only a date, it searched the whole UTC day in 30 minute steps and kept
slots that had already passed, so a clinic in Islamabad was offered 03:00 and,
late in the afternoon, times earlier the same day.
"""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.services.integrations.action_registry import adapt_parameters
from app.services.integrations.connectors.google_calendar_connector import (
    GoogleCalendarConnector,
)

KARACHI = ZoneInfo("Asia/Karachi")


class _FreeBusy(GoogleCalendarConnector):
    def __init__(self, busy):
        self.busy = busy

    async def check_availability(self, time_min, time_max, calendar_ids=None, **_):
        return {calendar_ids[0]: {"busy": self.busy}}


def _future_day() -> str:
    return (datetime.now(KARACHI) + timedelta(days=7)).strftime("%Y-%m-%d")


@pytest.mark.asyncio
async def test_opening_hours_are_local_to_the_business():
    params = adapt_parameters(
        "google-calendar",
        "find_available_slots",
        {"date": "2026-09-19", "duration_minutes": 60, "time_zone": "Asia/Karachi",
         "day_start": "09:00", "day_end": "17:00"},
    )
    seen = {}

    class _Spy(_FreeBusy):
        async def check_availability(self, time_min, time_max, calendar_ids=None, **_):
            seen["window"] = (time_min, time_max)
            return {calendar_ids[0]: {"busy": []}}

    await _Spy([]).find_available_slots(**params)
    assert seen["window"] == ("2026-09-19T09:00:00+05:00", "2026-09-19T17:00:00+05:00")


@pytest.mark.asyncio
async def test_a_mistyped_time_zone_is_reported_clearly():
    from app.services.integrations.connector_base import ConnectorError

    with pytest.raises(ConnectorError, match="Unknown time zone 'Asia/Karachy'"):
        await _FreeBusy([]).find_available_slots(
            duration_minutes=60, search_start="2026-09-19", search_end="2026-09-19",
            time_zone="Asia/Karachy", day_start="09:00", day_end="17:00",
        )


def test_a_bare_date_keeps_the_old_whole_day_window():
    result = adapt_parameters("google-calendar", "find_available_slots", {"date": "2026-08-13"})
    assert result["search_start"] == "2026-08-13T00:00:00Z"


@pytest.mark.asyncio
async def test_hourly_slots_skip_a_booking_given_in_utc():
    day = _future_day()
    # 10:00-11:00 Karachi, reported by Google in UTC as freebusy does.
    busy = [{"start": f"{day}T05:00:00Z", "end": f"{day}T06:00:00Z"}]
    slots = await _FreeBusy(busy).find_available_slots(
        duration_minutes=60,
        search_start=f"{day}T09:00:00+05:00",
        search_end=f"{day}T17:00:00+05:00",
        step_minutes=60,
    )
    assert [s["time"] for s in slots] == ["09:00", "11:00", "12:00", "13:00", "14:00", "15:00", "16:00"]
    assert slots[1]["start"] == f"{day}T11:00:00+05:00"


@pytest.mark.asyncio
async def test_a_half_hour_booking_blocks_the_hour_it_overlaps():
    day = _future_day()
    busy = [{"start": f"{day}T09:30:00+05:00", "end": f"{day}T10:15:00+05:00"}]
    slots = await _FreeBusy(busy).find_available_slots(
        duration_minutes=60,
        search_start=f"{day}T09:00:00+05:00",
        search_end=f"{day}T13:00:00+05:00",
        step_minutes=60,
    )
    assert [s["time"] for s in slots] == ["11:00", "12:00"]


@pytest.mark.asyncio
async def test_slots_that_have_already_started_are_not_offered():
    today = datetime.now(KARACHI).strftime("%Y-%m-%d")
    slots = await _FreeBusy([]).find_available_slots(
        duration_minutes=60,
        search_start=f"{today}T00:00:00+05:00",
        search_end=f"{today}T23:59:00+05:00",
        step_minutes=60,
    )
    now = datetime.now(KARACHI)
    assert all(datetime.fromisoformat(s["start"]) >= now for s in slots)
