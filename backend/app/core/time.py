"""
One rule for time on the wire: every timestamp the API sends says it is UTC.

Storage is naive UTC — the columns are ``timestamp without time zone`` and the
code writes ``datetime.utcnow()`` into them. That is fine inside Python, but a
naive value serialises as ``"2026-09-30T10:00:00"`` with no zone marker, and a
browser's ``new Date()`` reads such a string as *local* time. Every "x ago" in
the dashboard was therefore off by the viewer's UTC offset: at UTC+5 a call
made two minutes earlier showed as "5h ago".

So the conversion happens at the edge, never in the stored values:

* ``UTCDatetime`` — the annotation for datetime fields on response schemas.
  Validation is unchanged (input stays naive, so it can still be written to a
  naive column); only JSON output gains the ``+00:00``.
* ``install_json_encoder()`` — does the same for plain dicts that FastAPI runs
  through ``jsonable_encoder``.
* ``utc_iso()`` — for hand-built payloads (websocket frames, notification
  payloads, dict endpoints that pre-format their values).

Values that are already aware are converted to UTC, not relabelled.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Annotated, Optional, Union

from pydantic import PlainSerializer

UTC = timezone.utc


def as_utc(value: datetime) -> datetime:
    """An aware UTC datetime. A naive value is taken to already be UTC."""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def utc_iso(value: Optional[Union[datetime, date]]) -> Optional[str]:
    """ISO-8601 with an explicit UTC offset; ``None`` passes through.

    A bare ``date`` (a daily bucket, a billing day) has no time of day and so
    no zone to add — it is returned as ``YYYY-MM-DD``.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return as_utc(value).isoformat()
    return value.isoformat()


def utc_today() -> date:
    """Today's date in UTC — the calendar the stored timestamps are on.

    ``date.today()`` is the *server's* local date, which only agrees with
    ``func.date(<naive UTC column>)`` when the host happens to run in UTC.
    """
    return datetime.now(UTC).date()


#: A datetime field on a response schema. Serialises with an explicit UTC offset.
UTCDatetime = Annotated[
    datetime,
    PlainSerializer(utc_iso, return_type=str, when_used="json-unless-none"),
]


def install_json_encoder() -> None:
    """Make ``jsonable_encoder`` emit UTC offsets for naive datetimes.

    ``jsonable_encoder`` looks up ``ENCODERS_BY_TYPE[type(obj)]`` at call time,
    so replacing the entry covers every dict response.
    """
    from fastapi import encoders

    encoders.ENCODERS_BY_TYPE[datetime] = utc_iso
