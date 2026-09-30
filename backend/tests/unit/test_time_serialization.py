"""Every timestamp the API sends must say it is UTC.

A naive "2026-09-30T10:00:00" is read by browsers as *local* time, which put
every "x ago" in the dashboard off by the viewer's UTC offset.
"""
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel

import app.main  # noqa: F401  (installs the jsonable_encoder hook)
from app.core.time import UTCDatetime, as_utc, utc_iso, utc_today

NAIVE = datetime(2026, 9, 30, 10, 0, 0, 123456)


def test_utc_iso_marks_naive_values_as_utc():
    assert utc_iso(NAIVE) == "2026-09-30T10:00:00.123456+00:00"


def test_utc_iso_converts_aware_values_instead_of_relabelling():
    pkt = timezone(timedelta(hours=5))
    assert utc_iso(datetime(2026, 9, 30, 15, 0, tzinfo=pkt)) == "2026-09-30T10:00:00+00:00"


def test_utc_iso_leaves_dates_and_none_alone():
    assert utc_iso(date(2026, 9, 30)) == "2026-09-30"
    assert utc_iso(None) is None


def test_as_utc_and_utc_today():
    assert as_utc(NAIVE).tzinfo is timezone.utc
    assert utc_today() == datetime.now(timezone.utc).date()


class _Out(BaseModel):
    at: UTCDatetime
    maybe: Optional[UTCDatetime] = None


def test_schema_json_output_carries_offset_but_value_stays_naive():
    out = _Out(at=NAIVE)
    # Validation does not touch the value, so it can still go into a naive column.
    assert out.at.tzinfo is None
    assert out.model_dump(mode="json") == {"at": "2026-09-30T10:00:00.123456+00:00", "maybe": None}


def test_both_response_paths_through_fastapi():
    api = FastAPI()

    @api.get("/model", response_model=_Out)
    def model():
        return _Out(at=NAIVE)

    @api.get("/dict")
    def plain():
        return {"at": NAIVE, "nested": [{"at": NAIVE}], "day": date(2026, 9, 30)}

    client = TestClient(api)
    assert client.get("/model").json()["at"] == "2026-09-30T10:00:00.123456+00:00"
    body = client.get("/dict").json()
    assert body["at"] == "2026-09-30T10:00:00.123456+00:00"
    assert body["nested"][0]["at"] == "2026-09-30T10:00:00.123456+00:00"
    assert body["day"] == "2026-09-30"
