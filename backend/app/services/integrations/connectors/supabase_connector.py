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
            # We hit an arbitrary table endpoint with limit 1 to verify credentials
            auth_data = self.get_auth_data()
            test_table = auth_data.get("test_table", "users")
            res = await self.get(f"/rest/v1/{test_table}", params={"limit": "1"})
            return {
                "success": True,
                "message": "Supabase connection successful",
                "details": {},
            }
        except Exception as e:
            return {"success": False, "message": f"Connection test failed: {e}", "details": {}}

    async def fetch_table(self, table_name: str, limit: int = 10) -> Dict[str, Any]:
        try:
            res = await self.get(f"/rest/v1/{table_name}", params={"limit": str(limit)})
            return {"data": res, "success": True}
        except Exception as e:
            raise ConnectorError(f"Supabase fetch_table failed: {e}")
