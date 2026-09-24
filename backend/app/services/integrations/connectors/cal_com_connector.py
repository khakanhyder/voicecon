"""
Cal.com Connector.
Uses API Key auth (passed as `apiKey` query param).
"""
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from app.services.integrations.connector_base import BaseConnector, ConnectorError

logger = logging.getLogger(__name__)

class CalComConnector(BaseConnector):
    """
    Cal.com Connector.
    Actions:
    - test_connection
    - list_event_types
    - get_bookings
    """
    # Auth is ``?apiKey=`` — declared as ``api_key_location: "query"`` on the
    # seeded connector row and applied by BaseConnector.get_auth_params. This
    # class used to override get_auth_headers to return {}, which read as
    # "handled elsewhere" but meant no credential was sent at all.

    async def test_connection(self) -> Dict[str, Any]:
        try:
            res = await self.get("/v1/me")
            return {
                "success": True,
                "message": "Cal.com connection successful",
                "details": {"username": res.get("user", {}).get("username")},
            }
        except Exception as e:
            return {"success": False, "message": f"Connection test failed: {e}", "details": {}}

    async def list_event_types(self) -> Dict[str, Any]:
        try:
            res = await self.get("/v1/event-types")
            return {"event_types": res.get("event_types", []), "success": True}
        except Exception as e:
            raise ConnectorError(f"Cal.com list_event_types failed: {e}")

    async def get_bookings(self, status: str = "upcoming") -> Dict[str, Any]:
        try:
            res = await self.get("/v1/bookings", params={"status": status})
            return {"bookings": res.get("bookings", []), "success": True}
        except Exception as e:
            raise ConnectorError(f"Cal.com get_bookings failed: {e}")

    async def find_bookings(self, attendee: str) -> Dict[str, Any]:
        """Upcoming bookings whose attendee email or name matches: the lookup
        before cancelling or rescheduling, so the id is never guessed."""
        needle = (attendee or "").strip().lower()
        if not needle:
            raise ConnectorError("Give the caller's email or name to look up their booking.")
        try:
            res = await self.get("/v1/bookings", params={"status": "upcoming"})
        except Exception as e:
            raise ConnectorError(f"Cal.com find_bookings failed: {e}")
        now = datetime.now(timezone.utc)
        found = []
        for b in res.get("bookings", []):
            people = [a for a in b.get("attendees") or []]
            if not any(needle in (a.get("email") or "").lower() or needle in (a.get("name") or "").lower() for a in people):
                continue
            if (b.get("status") or "").upper() in ("CANCELLED", "REJECTED"):
                continue
            start = _parse(b.get("startTime"))
            if start and start < now:
                continue
            found.append(_booking(b))
        return {"bookings": found[:10], "count": len(found)}

    async def get_booking(self, booking_id: int) -> Dict[str, Any]:
        try:
            res = await self.get(f"/v1/bookings/{booking_id}")
        except Exception as e:
            raise ConnectorError(f"Cal.com get_booking failed: {e}")
        return _booking(res.get("booking", res))

    async def cancel_booking(self, booking_id: int, reason: Optional[str] = None) -> Dict[str, Any]:
        """Cancel a booking; Cal.com emails the attendees."""
        params = {"cancellationReason": reason} if reason else None
        try:
            await self.delete(f"/v1/bookings/{booking_id}/cancel", params=params)
        except Exception as e:
            raise ConnectorError(f"Cal.com cancel_booking failed: {e}")
        return {"id": booking_id, "cancelled": True}

    async def reschedule_booking(self, booking_id: int, start_time: str,
                                 end_time: Optional[str] = None) -> Dict[str, Any]:
        """Move a booking. Without an end time, it keeps its current length."""
        current = await self.get_booking(booking_id)
        if not end_time:
            before_start, before_end, new_start = _parse(current.get("start_time")), _parse(current.get("end_time")), _parse(start_time)
            if not (before_start and before_end and new_start):
                raise ConnectorError("Give the new start time in ISO 8601 format, e.g. 2026-10-02T11:00:00+05:00.")
            end_time = (new_start + (before_end - before_start)).isoformat()
        try:
            res = await self.patch(f"/v1/bookings/{booking_id}", json={"startTime": start_time, "endTime": end_time})
        except Exception as e:
            raise ConnectorError(f"Cal.com reschedule_booking failed: {e}")
        return {**_booking(res.get("booking", res)), "rescheduled": True}


def _parse(value: Any) -> Optional[datetime]:
    try:
        moment = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def _booking(b: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": b.get("id"),
        "title": b.get("title"),
        "start_time": b.get("startTime"),
        "end_time": b.get("endTime"),
        "status": b.get("status"),
        "attendees": [a.get("email") for a in b.get("attendees") or [] if a.get("email")],
    }

