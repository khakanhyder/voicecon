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
    def get_auth_headers(self, access_token: str) -> Dict[str, str]:
        # Cal.com allows apiKey as query parameter, but we can also use Authorization Bearer
        # according to standard fallback or configure it via seed_data auth_config.
        # But let's return it as query parameter by overriding make_request, or
        # using the database auth_config format if handled correctly in base.
        return {}  # Handled by auth_config template in base class or query params

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
