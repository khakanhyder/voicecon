"""
The call log as a CSV file — what "Export CSV" on the Calls page downloads.

The columns follow the table on that page, so the file reads like the screen
it came from. Two things differ on purpose:

* Start time is a real timestamp, not "10m ago", in the timezone the browser
  asked for (stored values are naive UTC — see ``app.core.time``).
* Duration and cost are plain numbers, so a spreadsheet can sum them.
"""
from __future__ import annotations

import csv
import io
import re
from datetime import datetime
from typing import Any, Iterable, Mapping, Optional
from zoneinfo import ZoneInfo

from app.core.time import UTC, as_utc

HEADERS = (
    "Call ID",
    "Assistant",
    "Direction",
    "Assistant Phone Number",
    "Customer Phone Number",
    "Status",
    "End Reason",
    "Success Evaluation",
    "Start Time",
    "Duration (seconds)",
    "Cost (USD)",
)

#: A spreadsheet runs a cell that starts with one of these as a formula. Agent
#: names are typed by workspace members and a caller id can be anything, so
#: such cells are quoted with a leading apostrophe.
_FORMULA_LEAD = ("=", "+", "-", "@", "\t", "\r")
#: ...except an ordinary phone number, which is the one "+…" value every row has.
_PHONE = re.compile(r"^\+\d[\d\s().-]*$")


def resolve_timezone(name: Optional[str]) -> tuple[Any, str]:
    """The zone to print times in and its label. Unknown or missing → UTC."""
    if name:
        try:
            return ZoneInfo(name), name
        except Exception:
            # A name this server's tz database doesn't know, or junk input.
            pass
    return UTC, "UTC"


def _cell(value: Any) -> str:
    if value is None:
        return ""
    text = str(value)
    if text.startswith(_FORMULA_LEAD) and not _PHONE.match(text):
        return f"'{text}"
    return text


def _label(value: Optional[str]) -> str:
    """``customer_hung_up`` → ``Customer hung up``, as the page shows it."""
    return (value or "").replace("_", " ").strip().capitalize()


def _parties(direction: str, from_number: str, to_number: str) -> tuple[str, str]:
    """(assistant's number, customer's number) for a call."""
    if direction == "outbound":
        return from_number, to_number
    if direction == "inbound":
        return to_number, from_number
    return "Web Test", "Web Test"


def _row(call: Mapping[str, Any], tz: Any) -> list[str]:
    assistant_phone, customer_phone = _parties(
        call["direction"], call["from_number"], call["to_number"]
    )
    metadata = call.get("call_metadata") or {}
    started: Optional[datetime] = call.get("started_at") or call.get("created_at")
    cost = call.get("cost_total")
    duration = call.get("duration_seconds")
    return [
        _cell(call["id"]),
        _cell(call.get("agent_name") or call.get("agent_id") or "Unknown"),
        _cell(_label(call["direction"])),
        _cell(assistant_phone),
        _cell(customer_phone),
        _cell(_label(call["status"])),
        _cell(_label(metadata.get("disconnection_reason") or call["status"])),
        _cell(_label(call.get("sentiment_label"))),
        as_utc(started).astimezone(tz).strftime("%Y-%m-%d %H:%M:%S") if started else "",
        "" if duration is None else str(duration),
        "" if cost is None else f"{cost:.4f}",
    ]


def build_calls_csv(calls: Iterable[Mapping[str, Any]], timezone_name: Optional[str] = None) -> bytes:
    """CSV bytes for ``calls`` (mappings of the columns the export selects).

    Encoded with a UTF-8 BOM: without it Excel reads the file as the system
    code page and mangles any non-ASCII agent name.
    """
    tz, tz_label = resolve_timezone(timezone_name)
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\r\n")
    writer.writerow(
        f"{h} ({tz_label})" if h == "Start Time" else h for h in HEADERS
    )
    for call in calls:
        writer.writerow(_row(call, tz))
    return out.getvalue().encode("utf-8-sig")
