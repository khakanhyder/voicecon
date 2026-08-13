"""
Cal.com Connector.
Uses API Key auth (passed as `apiKey` query param).
"""
import logging
from typing import Dict, Any, List
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
