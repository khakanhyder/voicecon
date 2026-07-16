"""
Calendly Connector.

Integrates with the Calendly REST API. Auth uses an OAuth2 Bearer token
sent as `Authorization: Bearer <token>`.
"""
import logging
from typing import Dict, Any, Optional, List

from app.services.integrations.connector_base import BaseConnector, ConnectorError

logger = logging.getLogger(__name__)


class CalendlyConnector(BaseConnector):
    """
    Calendly connector.

    Actions:
    - test_connection: verify token via /users/me
    - get_user: get current user info
    - list_event_types: list user's event types
    - list_scheduled_events: list scheduled events
    - get_event_details: get details of a specific event
    - create_webhook: create a webhook subscription
    """

    async def test_connection(self) -> Dict[str, Any]:
        try:
            res = await self.get("/users/me")
            resource = res.get("resource", {})
            return {
                "success": True,
                "message": "Calendly connection successful",
                "details": {"name": resource.get("name"), "email": resource.get("email")},
            }
        except Exception as e:
            logger.error(f"Calendly connection test failed: {e}", exc_info=True)
            return {"success": False, "message": f"Calendly connection test failed: {e}", "details": {}}

    async def get_user(self) -> Dict[str, Any]:
        """Get the current authenticated user's details."""
        try:
            res = await self.get("/users/me")
            return res.get("resource", {})
        except Exception as e:
            raise ConnectorError(f"Calendly get_user failed: {e}")

    async def list_event_types(self) -> Dict[str, Any]:
        """List event types for the current user."""
        try:
            user = await self.get_user()
            user_uri = user.get("uri")
            if not user_uri:
                raise ConnectorError("Could not retrieve user URI")

            res = await self.get("/event_types", params={"user": user_uri})
            collection = res.get("collection", [])
            event_types = [
                {
                    "uri": e.get("uri"),
                    "name": e.get("name"),
                    "type": e.get("type"),
                    "active": e.get("active"),
                    "scheduling_url": e.get("scheduling_url"),
                    "duration": e.get("duration"),
                }
                for e in collection
            ]
            return {"event_types": event_types, "count": len(event_types)}
        except Exception as e:
            raise ConnectorError(f"Calendly list_event_types failed: {e}")

    async def list_scheduled_events(self, status: str = "active", count: int = 20) -> Dict[str, Any]:
        """List scheduled events."""
        try:
            user = await self.get_user()
            user_uri = user.get("uri")
            if not user_uri:
                raise ConnectorError("Could not retrieve user URI")

            params = {
                "user": user_uri,
                "status": status,
                "count": count,
                "sort": "start_time:desc"
            }
            res = await self.get("/scheduled_events", params=params)
            collection = res.get("collection", [])
            events = [
                {
                    "uri": e.get("uri"),
                    "name": e.get("name"),
                    "status": e.get("status"),
                    "start_time": e.get("start_time"),
                    "end_time": e.get("end_time"),
                    "location": e.get("location", {}).get("location"),
                }
                for e in collection
            ]
            return {"events": events, "count": len(events)}
        except Exception as e:
            raise ConnectorError(f"Calendly list_scheduled_events failed: {e}")

    async def get_event_details(self, event_uuid: str) -> Dict[str, Any]:
        """Get details of a specific scheduled event."""
        try:
            res = await self.get(f"/scheduled_events/{event_uuid}")
            return res.get("resource", {})
        except Exception as e:
            raise ConnectorError(f"Calendly get_event_details failed: {e}")

    async def create_webhook(self, url: str, events: List[str]) -> Dict[str, Any]:
        """Create a webhook subscription."""
        try:
            user = await self.get_user()
            user_uri = user.get("uri")
            org_uri = user.get("current_organization")
            
            if not org_uri:
                raise ConnectorError("Could not retrieve organization URI")

            body = {
                "url": url,
                "events": events,
                "organization": org_uri,
                "scope": "organization"
            }
            res = await self.post("/webhook_subscriptions", json=body)
            return {"id": res.get("resource", {}).get("uri"), "success": True}
        except Exception as e:
            raise ConnectorError(f"Calendly create_webhook failed: {e}")
