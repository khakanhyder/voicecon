"""
Google Calendar Connector.

Integration with Google Calendar API.
"""
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta

from app.services.integrations.connector_base import BaseConnector, ConnectorError

logger = logging.getLogger(__name__)


class GoogleCalendarConnector(BaseConnector):
    """
    Google Calendar connector.

    Provides methods to interact with Google Calendar API:
    - Create/update/delete events
    - List events
    - Manage calendars
    - Check availability
    - Manage attendees
    """

    async def test_connection(self) -> Dict[str, Any]:
        """
        Test Google Calendar connection by fetching calendar list.

        Returns:
            Test result dictionary
        """
        try:
            # Get calendar list
            response = await self.get("/calendar/v3/users/me/calendarList")

            calendars = response.get("items", [])

            return {
                "success": True,
                "message": "Google Calendar connection successful",
                "details": {
                    "calendar_count": len(calendars),
                    "primary_calendar": next(
                        (cal["id"] for cal in calendars if cal.get("primary")),
                        None
                    ),
                },
            }

        except Exception as e:
            logger.error(f"Google Calendar connection test failed: {e}", exc_info=True)
            return {
                "success": False,
                "message": f"Google Calendar connection test failed: {str(e)}",
                "details": {},
            }

    # ========================================================================
    # Calendar Methods
    # ========================================================================

    async def list_calendars(self) -> List[Dict[str, Any]]:
        """
        List all calendars.

        Returns:
            List of calendars

        Raises:
            ConnectorError: If retrieval fails
        """
        try:
            response = await self.get("/calendar/v3/users/me/calendarList")

            calendars = response.get("items", [])

            return [
                {
                    "id": cal.get("id"),
                    "summary": cal.get("summary"),
                    "description": cal.get("description"),
                    "primary": cal.get("primary", False),
                    "timezone": cal.get("timeZone"),
                    "access_role": cal.get("accessRole"),
                }
                for cal in calendars
            ]

        except Exception as e:
            logger.error(f"Failed to list Google calendars: {e}", exc_info=True)
            raise ConnectorError(f"Failed to list calendars: {str(e)}")

    async def get_primary_calendar_id(self) -> str:
        """
        Get the primary calendar ID.

        Returns:
            Primary calendar ID (usually user's email)

        Raises:
            ConnectorError: If retrieval fails
        """
        try:
            calendars = await self.list_calendars()
            primary = next((cal for cal in calendars if cal.get("primary")), None)

            if not primary:
                raise ConnectorError("No primary calendar found")

            return primary["id"]

        except Exception as e:
            logger.error(f"Failed to get primary calendar: {e}", exc_info=True)
            raise ConnectorError(f"Failed to get primary calendar: {str(e)}")

    # ========================================================================
    # Event Methods
    # ========================================================================

    async def create_event(
        self,
        summary: str,
        start_time: str,
        end_time: str,
        calendar_id: str = "primary",
        description: Optional[str] = None,
        location: Optional[str] = None,
        attendees: Optional[List[str]] = None,
        timezone: str = "UTC",
        send_notifications: bool = True,
    ) -> Dict[str, Any]:
        """
        Create a calendar event.

        Args:
            summary: Event title
            start_time: Start time (ISO 8601 format: 2025-01-15T10:00:00)
            end_time: End time (ISO 8601 format: 2025-01-15T11:00:00)
            calendar_id: Calendar ID (default: "primary")
            description: Event description
            location: Event location
            attendees: List of attendee emails
            timezone: Timezone (default: "UTC")
            send_notifications: Send email notifications to attendees

        Returns:
            Created event data

        Raises:
            ConnectorError: If event creation fails
        """
        try:
            # Build event data
            event_data = {
                "summary": summary,
                "start": {
                    "dateTime": start_time,
                    "timeZone": timezone,
                },
                "end": {
                    "dateTime": end_time,
                    "timeZone": timezone,
                },
            }

            if description:
                event_data["description"] = description
            if location:
                event_data["location"] = location
            if attendees:
                event_data["attendees"] = [{"email": email} for email in attendees]

            # Create event
            params = {"sendUpdates": "all" if send_notifications else "none"}

            response = await self.post(
                f"/calendar/v3/calendars/{calendar_id}/events",
                json=event_data,
                params=params,
            )

            logger.info(f"Google Calendar event created: {response.get('id')}")

            return {
                "id": response.get("id"),
                "summary": response.get("summary"),
                "start": response.get("start"),
                "end": response.get("end"),
                "html_link": response.get("htmlLink"),
                "hangout_link": response.get("hangoutLink"),
                "status": response.get("status"),
            }

        except Exception as e:
            logger.error(f"Failed to create Google Calendar event: {e}", exc_info=True)
            raise ConnectorError(f"Failed to create event: {str(e)}")

    async def update_event(
        self,
        event_id: str,
        calendar_id: str = "primary",
        summary: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        description: Optional[str] = None,
        location: Optional[str] = None,
        attendees: Optional[List[str]] = None,
        timezone: Optional[str] = None,
        send_notifications: bool = True,
    ) -> Dict[str, Any]:
        """
        Update a calendar event, changing only the fields given.

        This is a PATCH, not a PUT. The previous PUT sent only the title and
        times, and Google replaces the whole event on PUT, so a reschedule
        silently dropped the attendees, notes, location and meeting link.

        Moving only the start keeps the event's length: the end moves with it.
        A time without an offset is read in ``timezone``, or else in the zone
        the event already uses, never a blanket UTC.

        Args:
            event_id: Event ID
            calendar_id: Calendar ID (default: "primary")
            summary: New title
            start_time: New start (ISO 8601)
            end_time: New end (ISO 8601); defaults to start + current length
            description: New description
            location: New location
            attendees: Replacement attendee emails
            timezone: IANA zone for offset-less times
            send_notifications: Email attendees about the change

        Returns:
            Updated event data

        Raises:
            ConnectorError: If update fails
        """
        try:
            current = await self.get(
                f"/calendar/v3/calendars/{calendar_id}/events/{event_id}"
            )
            if current.get("status") == "cancelled":
                raise ConnectorError("This appointment has been cancelled, so it cannot be changed.")

            patch: Dict[str, Any] = {}
            if summary is not None:
                patch["summary"] = summary
            if description is not None:
                patch["description"] = description
            if location is not None:
                patch["location"] = location
            if attendees is not None:
                patch["attendees"] = [{"email": email} for email in attendees]

            if start_time or end_time:
                old_start = current.get("start") or {}
                old_end = current.get("end") or {}
                zone = timezone or old_start.get("timeZone") or old_end.get("timeZone")
                if not start_time:
                    start_time = old_start.get("dateTime")
                if not end_time:
                    end_time = _shift_end(start_time, old_start.get("dateTime"), old_end.get("dateTime"))
                if not start_time or not end_time:
                    raise ConnectorError("All-day events cannot be rescheduled to a time slot here.")
                if _parse(end_time) and _parse(start_time) and _parse(end_time) <= _parse(start_time):
                    raise ConnectorError("The new end time must be after the new start time.")
                patch["start"] = {"dateTime": start_time, **({"timeZone": zone} if zone else {})}
                patch["end"] = {"dateTime": end_time, **({"timeZone": zone} if zone else {})}

            if not patch:
                raise ConnectorError("Nothing to change: give a new time, title or notes.")

            params = {"sendUpdates": "all" if send_notifications else "none"}
            response = await self.patch(
                f"/calendar/v3/calendars/{calendar_id}/events/{event_id}",
                json=patch,
                params=params,
            )

            logger.info(f"Google Calendar event updated: {event_id}")

            return {
                "id": response.get("id"),
                "summary": response.get("summary"),
                "start": response.get("start"),
                "end": response.get("end"),
                "html_link": response.get("htmlLink"),
                "status": response.get("status"),
                "updated": True,
            }

        except ConnectorError as e:
            raise ConnectorError(_friendly(str(e), "update"))
        except Exception as e:
            logger.error(f"Failed to update Google Calendar event: {e}", exc_info=True)
            raise ConnectorError(_friendly(f"Failed to update event: {e}", "update"))

    async def delete_event(
        self,
        event_id: str,
        calendar_id: str = "primary",
        send_notifications: bool = True,
    ) -> Dict[str, Any]:
        """
        Delete (cancel) a calendar event.

        Args:
            event_id: Event ID
            calendar_id: Calendar ID (default: "primary")
            send_notifications: Send cancellation notifications

        Returns:
            Deletion result. An event that was already cancelled counts as done,
            so a retried cancel does not read to the caller as a failure.

        Raises:
            ConnectorError: If deletion fails
        """
        try:
            params = {"sendUpdates": "all" if send_notifications else "none"}

            await self.delete(
                f"/calendar/v3/calendars/{calendar_id}/events/{event_id}",
                params=params,
            )

            logger.info(f"Google Calendar event deleted: {event_id}")

            return {
                "id": event_id,
                "success": True,
                "cancelled": True,
            }

        except Exception as e:
            if "HTTP 410" in str(e):
                return {"id": event_id, "success": True, "cancelled": True, "already_cancelled": True}
            logger.error(f"Failed to delete Google Calendar event: {e}", exc_info=True)
            raise ConnectorError(_friendly(f"Failed to delete event: {e}", "cancel"))

    async def get_event(
        self,
        event_id: str,
        calendar_id: str = "primary",
    ) -> Dict[str, Any]:
        """
        Get a calendar event by ID.

        Args:
            event_id: Event ID
            calendar_id: Calendar ID (default: "primary")

        Returns:
            Event data

        Raises:
            ConnectorError: If retrieval fails
        """
        try:
            response = await self.get(
                f"/calendar/v3/calendars/{calendar_id}/events/{event_id}"
            )

            return {
                "id": response.get("id"),
                "summary": response.get("summary"),
                "description": response.get("description"),
                "location": response.get("location"),
                "start": response.get("start"),
                "end": response.get("end"),
                "attendees": response.get("attendees", []),
                "html_link": response.get("htmlLink"),
                "hangout_link": response.get("hangoutLink"),
                "status": response.get("status"),
                "created": response.get("created"),
                "updated": response.get("updated"),
            }

        except Exception as e:
            logger.error(f"Failed to get Google Calendar event: {e}", exc_info=True)
            raise ConnectorError(f"Failed to get event: {str(e)}")

    async def list_events(
        self,
        calendar_id: str = "primary",
        time_min: Optional[str] = None,
        time_max: Optional[str] = None,
        max_results: int = 100,
        order_by: str = "startTime",
        time_zone: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        List calendar events.

        Args:
            calendar_id: Calendar ID (default: "primary")
            time_min: Lower bound (ISO 8601, default: now)
            time_max: Upper bound (ISO 8601)
            max_results: Maximum number of events
            order_by: Order by (startTime or updated)
            time_zone: IANA zone to express event times in (e.g. Asia/Karachi).
                Defaults to the calendar's own zone, which is often not the
                zone the business works in, so an agent reading the times
                would otherwise have to convert them itself.

        Returns:
            List of events

        Raises:
            ConnectorError: If retrieval fails
        """
        try:
            # Default time_min to now
            if not time_min:
                time_min = datetime.utcnow().isoformat() + "Z"

            params = {
                "timeMin": time_min,
                "maxResults": max_results,
                "singleEvents": True,
                "orderBy": order_by,
            }

            if time_max:
                params["timeMax"] = time_max
            if time_zone:
                params["timeZone"] = time_zone

            response = await self.get(
                f"/calendar/v3/calendars/{calendar_id}/events",
                params=params,
            )

            events = response.get("items", [])

            return [
                {
                    "id": event.get("id"),
                    "summary": event.get("summary"),
                    "description": event.get("description"),
                    "location": event.get("location"),
                    "start": event.get("start"),
                    "end": event.get("end"),
                    "attendees": event.get("attendees", []),
                    "html_link": event.get("htmlLink"),
                    "status": event.get("status"),
                }
                for event in events
            ]

        except Exception as e:
            logger.error(f"Failed to list Google Calendar events: {e}", exc_info=True)
            raise ConnectorError(f"Failed to list events: {str(e)}")

    async def find_events(
        self,
        query: str,
        calendar_id: str = "primary",
        time_min: Optional[str] = None,
        time_max: Optional[str] = None,
        time_zone: Optional[str] = None,
        max_results: int = 10,
    ) -> Dict[str, Any]:
        """
        Find upcoming events that mention ``query``: an attendee's email or
        name, or text in the title, notes or location (Google's free-text
        search). This is how an agent gets the event id it needs to reschedule
        or cancel, so it never has to guess one.

        Defaults to the next 90 days, because a caller asking to move an
        appointment means one that has not happened yet.
        """
        query = (query or "").strip()
        if not query:
            raise ConnectorError("Say what to search for, such as the caller's email or phone number.")
        now = datetime.utcnow()
        params: Dict[str, Any] = {
            "q": query,
            "timeMin": time_min or now.isoformat() + "Z",
            "timeMax": time_max or (now + timedelta(days=90)).isoformat() + "Z",
            "maxResults": max(1, min(int(max_results or 10), 25)),
            "singleEvents": True,
            "orderBy": "startTime",
        }
        if time_zone:
            params["timeZone"] = time_zone
        try:
            response = await self.get(
                f"/calendar/v3/calendars/{calendar_id}/events", params=params
            )
        except Exception as e:
            logger.error(f"Failed to search Google Calendar events: {e}", exc_info=True)
            raise ConnectorError(f"Failed to search events: {e}")

        events = [
            {
                "id": ev.get("id"),
                "title": ev.get("summary"),
                "start": (ev.get("start") or {}).get("dateTime") or (ev.get("start") or {}).get("date"),
                "end": (ev.get("end") or {}).get("dateTime") or (ev.get("end") or {}).get("date"),
                "attendees": [a.get("email") for a in ev.get("attendees", []) if a.get("email")],
                "description": ev.get("description"),
                "location": ev.get("location"),
            }
            for ev in response.get("items", [])
            if ev.get("status") != "cancelled"
        ]
        return {
            "count": len(events),
            "events": events,
            **({} if events else {"note": f"No upcoming appointments found for '{query}'."}),
        }

    # ========================================================================
    # Availability Methods
    # ========================================================================

    async def check_availability(
        self,
        start_time: str,
        end_time: str,
        calendar_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Check calendar availability (free/busy).

        Args:
            start_time: Start time (ISO 8601)
            end_time: End time (ISO 8601)
            calendar_ids: List of calendar IDs (default: ["primary"])

        Returns:
            Free/busy information

        Raises:
            ConnectorError: If check fails
        """
        try:
            if not calendar_ids:
                calendar_ids = ["primary"]

            # Build request
            request_data = {
                "timeMin": start_time,
                "timeMax": end_time,
                "items": [{"id": cal_id} for cal_id in calendar_ids],
            }

            response = await self.post(
                "/calendar/v3/freeBusy",
                json=request_data,
            )

            calendars = response.get("calendars", {})

            # Process results
            availability = {}
            for cal_id, cal_data in calendars.items():
                busy_periods = cal_data.get("busy", [])
                availability[cal_id] = {
                    "busy": busy_periods,
                    "is_free": len(busy_periods) == 0,
                }

            return availability

        except Exception as e:
            logger.error(f"Failed to check Google Calendar availability: {e}", exc_info=True)
            raise ConnectorError(f"Failed to check availability: {str(e)}")

    @staticmethod
    def _business_day_window(
        search_start: str,
        search_end: str,
        time_zone: Optional[str],
        day_start: Optional[str],
        day_end: Optional[str],
    ) -> tuple:
        """Turn bare dates plus opening hours into a zoned search window."""
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

        try:
            zone = ZoneInfo(time_zone) if time_zone else ZoneInfo("UTC")
        except (ZoneInfoNotFoundError, ValueError):
            raise ConnectorError(
                f"Unknown time zone '{time_zone}'. Use an IANA name such as Asia/Karachi."
            )

        def _at(value: str, hhmm: str) -> str:
            text = str(value).strip()
            if "T" in text:
                return text
            try:
                hour, minute = (int(x) for x in str(hhmm).split(":")[:2])
                base = datetime.strptime(text[:10], "%Y-%m-%d")
            except ValueError:
                raise ConnectorError(
                    f"Could not read '{text} {hhmm}'. Use a YYYY-MM-DD date and HH:MM times."
                )
            return base.replace(hour=hour, minute=minute, tzinfo=zone).isoformat()

        return _at(search_start, day_start or "00:00"), _at(search_end, day_end or "23:59")

    async def find_available_slots(
        self,
        duration_minutes: int,
        search_start: str,
        search_end: str,
        calendar_id: str = "primary",
        step_minutes: int = 30,
        time_zone: Optional[str] = None,
        day_start: Optional[str] = None,
        day_end: Optional[str] = None,
    ) -> List[Dict[str, str]]:
        """
        Find available time slots.

        Args:
            duration_minutes: Duration of slot in minutes
            search_start: Search start time (ISO 8601)
            search_end: Search end time (ISO 8601)
            calendar_id: Calendar ID (default: "primary")
            step_minutes: Gap between candidate start times (default: 30)
            time_zone: IANA zone of the business, e.g. Asia/Karachi
            day_start: Opening time HH:MM, used when search_start is a bare date
            day_end: Closing time HH:MM; the last slot must end by then

        Slots are returned in the zone of ``search_start``, each with a
        ``time`` label (HH:MM). Slots that have already started are left out:
        nobody can book them, and an agent offering "four o'clock" at five
        past five sounds broken.

        Returns:
            List of available slots with start and end times

        Raises:
            ConnectorError: If search fails
        """
        if time_zone or day_start or day_end:
            search_start, search_end = self._business_day_window(
                search_start, search_end, time_zone, day_start, day_end
            )

        try:
            # Get free/busy info
            availability = await self.check_availability(
                search_start,
                search_end,
                [calendar_id],
            )

            busy_periods = availability.get(calendar_id, {}).get("busy", [])

            # Parse times
            from dateutil import parser as date_parser

            start = date_parser.parse(search_start)
            end = date_parser.parse(search_end)
            duration = timedelta(minutes=duration_minutes)
            step = timedelta(minutes=int(step_minutes or 30))
            zone = start.tzinfo
            now = datetime.now(zone) if zone else datetime.utcnow()

            def _slot(at: datetime) -> Dict[str, str]:
                return {
                    "start": at.isoformat(),
                    "end": (at + duration).isoformat(),
                    "time": at.strftime("%H:%M"),
                }

            def _aligned(at: datetime) -> datetime:
                # After a busy period, resume on the step grid measured from
                # the opening time, so hourly slots stay on the hour.
                if at <= start:
                    return start
                steps = -(-(at - start) // step)  # ceiling division
                return start + steps * step

            # Find free slots
            available_slots = []
            current = start

            for busy in busy_periods:
                busy_start = date_parser.parse(busy["start"])
                busy_end = date_parser.parse(busy["end"])
                if zone:
                    busy_start = busy_start.astimezone(zone)
                    busy_end = busy_end.astimezone(zone)

                # Check if there's a slot before this busy period
                while current + duration <= busy_start:
                    if current >= now:
                        available_slots.append(_slot(current))
                    current += step

                # Move past the busy period
                current = _aligned(max(current, busy_end))

            # Check remaining time after last busy period
            while current + duration <= end:
                if current >= now:
                    available_slots.append(_slot(current))
                current += step

            return available_slots

        except Exception as e:
            logger.error(f"Failed to find available slots: {e}", exc_info=True)
            raise ConnectorError(f"Failed to find available slots: {str(e)}")

    # ========================================================================
    # Quick Add Methods
    # ========================================================================

    async def quick_add_event(
        self,
        text: str,
        calendar_id: str = "primary",
    ) -> Dict[str, Any]:
        """
        Create an event using natural language (Quick Add).

        Args:
            text: Natural language event description
                  (e.g., "Lunch with John tomorrow at 12pm")
            calendar_id: Calendar ID (default: "primary")

        Returns:
            Created event data

        Raises:
            ConnectorError: If creation fails
        """
        try:
            response = await self.post(
                f"/calendar/v3/calendars/{calendar_id}/events/quickAdd",
                params={"text": text},
            )

            logger.info(f"Google Calendar quick add event created: {response.get('id')}")

            return {
                "id": response.get("id"),
                "summary": response.get("summary"),
                "start": response.get("start"),
                "end": response.get("end"),
                "html_link": response.get("htmlLink"),
            }

        except Exception as e:
            logger.error(f"Failed to quick add event: {e}", exc_info=True)
            raise ConnectorError(f"Failed to quick add event: {str(e)}")


def _parse(value: Optional[str]) -> Optional[datetime]:
    """An ISO 8601 timestamp as a datetime, or None if it is not one."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _shift_end(new_start: Optional[str], old_start: Optional[str], old_end: Optional[str]) -> Optional[str]:
    """The end time that keeps the event's current length after moving its start.

    Keeps the new start's own offset (or lack of one), so the pair stays in the
    same frame of reference.
    """
    start, before, after = _parse(new_start), _parse(old_start), _parse(old_end)
    if not (start and before and after):
        return old_end
    end = start + (after - before)
    return end.isoformat()


def _friendly(message: str, verb: str) -> str:
    """Turn Google's status codes into a sentence an agent can repeat."""
    if "HTTP 404" in message:
        return f"No appointment with that id on this calendar, so there was nothing to {verb}. Search for it again."
    if "HTTP 410" in message:
        return "That appointment has already been cancelled."
    if "HTTP 403" in message:
        return f"Google Calendar did not allow this {verb}. The connected account may not have edit access to that calendar."
    return message

