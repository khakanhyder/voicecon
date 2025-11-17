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
        timezone: str = "UTC",
        send_notifications: bool = True,
    ) -> Dict[str, Any]:
        """
        Update a calendar event.

        Args:
            event_id: Event ID
            calendar_id: Calendar ID (default: "primary")
            summary: Event title
            start_time: Start time (ISO 8601)
            end_time: End time (ISO 8601)
            description: Event description
            location: Event location
            attendees: List of attendee emails
            timezone: Timezone
            send_notifications: Send email notifications

        Returns:
            Updated event data

        Raises:
            ConnectorError: If update fails
        """
        try:
            # Get current event
            current_event = await self.get(
                f"/calendar/v3/calendars/{calendar_id}/events/{event_id}"
            )

            # Build update data
            event_data = {
                "summary": summary or current_event.get("summary"),
                "start": current_event.get("start"),
                "end": current_event.get("end"),
            }

            # Update times if provided
            if start_time:
                event_data["start"] = {
                    "dateTime": start_time,
                    "timeZone": timezone,
                }
            if end_time:
                event_data["end"] = {
                    "dateTime": end_time,
                    "timeZone": timezone,
                }

            # Update other fields
            if description is not None:
                event_data["description"] = description
            if location is not None:
                event_data["location"] = location
            if attendees is not None:
                event_data["attendees"] = [{"email": email} for email in attendees]

            # Update event
            params = {"sendUpdates": "all" if send_notifications else "none"}

            response = await self.put(
                f"/calendar/v3/calendars/{calendar_id}/events/{event_id}",
                json=event_data,
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
            }

        except Exception as e:
            logger.error(f"Failed to update Google Calendar event: {e}", exc_info=True)
            raise ConnectorError(f"Failed to update event: {str(e)}")

    async def delete_event(
        self,
        event_id: str,
        calendar_id: str = "primary",
        send_notifications: bool = True,
    ) -> Dict[str, Any]:
        """
        Delete a calendar event.

        Args:
            event_id: Event ID
            calendar_id: Calendar ID (default: "primary")
            send_notifications: Send cancellation notifications

        Returns:
            Deletion result

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
            }

        except Exception as e:
            logger.error(f"Failed to delete Google Calendar event: {e}", exc_info=True)
            raise ConnectorError(f"Failed to delete event: {str(e)}")

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
    ) -> List[Dict[str, Any]]:
        """
        List calendar events.

        Args:
            calendar_id: Calendar ID (default: "primary")
            time_min: Lower bound (ISO 8601, default: now)
            time_max: Upper bound (ISO 8601)
            max_results: Maximum number of events
            order_by: Order by (startTime or updated)

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

    async def find_available_slots(
        self,
        duration_minutes: int,
        search_start: str,
        search_end: str,
        calendar_id: str = "primary",
    ) -> List[Dict[str, str]]:
        """
        Find available time slots.

        Args:
            duration_minutes: Duration of slot in minutes
            search_start: Search start time (ISO 8601)
            search_end: Search end time (ISO 8601)
            calendar_id: Calendar ID (default: "primary")

        Returns:
            List of available slots with start and end times

        Raises:
            ConnectorError: If search fails
        """
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

            # Find free slots
            available_slots = []
            current = start

            for busy in busy_periods:
                busy_start = date_parser.parse(busy["start"])
                busy_end = date_parser.parse(busy["end"])

                # Check if there's a slot before this busy period
                while current + duration <= busy_start:
                    available_slots.append({
                        "start": current.isoformat(),
                        "end": (current + duration).isoformat(),
                    })
                    current += timedelta(minutes=30)  # 30-minute increments

                # Move past the busy period
                current = max(current, busy_end)

            # Check remaining time after last busy period
            while current + duration <= end:
                available_slots.append({
                    "start": current.isoformat(),
                    "end": (current + duration).isoformat(),
                })
                current += timedelta(minutes=30)

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
