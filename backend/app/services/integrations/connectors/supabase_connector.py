"""
Supabase Connector.
Uses API Key auth (apikey header and Authorization Bearer).
"""
import logging
from typing import Dict, Any
from app.services.integrations.connector_base import BaseConnector, ConnectorError

logger = logging.getLogger(__name__)

class SupabaseConnector(BaseConnector):
    """
    Supabase Connector.
    Actions:
    - test_connection
    - fetch_table
    """
    def get_auth_headers(self, access_token: str) -> Dict[str, str]:
        # Supabase requires both apikey and Authorization header for REST API.
        return {
            "apikey": access_token,
            "Authorization": f"Bearer {access_token}"
        }

    async def test_connection(self) -> Dict[str, Any]:
        try:
            # The REST root answers with the project's OpenAPI description for
            # any valid key. The previous version probed a table named "users",
            # taken from a `test_table` field no setup form ever collected — so
            # a perfectly good key failed the test on any project that happened
            # not to have that table.
            await self.get("/rest/v1/")
            return {
                "success": True,
                "message": "Supabase connection successful",
                "details": {"project_url": self.http_client.base_url},
            }
        except Exception as e:
            return {"success": False, "message": f"Connection test failed: {e}", "details": {}}

    async def fetch_table(self, table_name: str, limit: int = 10) -> Dict[str, Any]:
        try:
            res = await self.get(f"/rest/v1/{table_name}", params={"limit": str(limit)})
            return {"data": res, "success": True}
        except Exception as e:
            raise ConnectorError(f"Supabase fetch_table failed: {e}")
