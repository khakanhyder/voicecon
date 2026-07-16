"""
Monday.com Connector.
Uses OAuth2 Bearer tokens.
"""
import logging
from typing import Dict, Any
from app.services.integrations.connector_base import BaseConnector, ConnectorError

logger = logging.getLogger(__name__)

class MondayConnector(BaseConnector):
    """
    Monday.com Connector.
    Uses GraphQL API, so endpoints hit /v2 with query.
    """
    async def test_connection(self) -> Dict[str, Any]:
        try:
            query = {"query": "query { me { name email } }"}
            res = await self.post("/v2", json=query)
            if "errors" in res:
                return {"success": False, "message": "GraphQL error", "details": res}
            data = res.get("data", {}).get("me", {})
            return {
                "success": True,
                "message": "Monday.com connection successful",
                "details": {"name": data.get("name")},
            }
        except Exception as e:
            return {"success": False, "message": f"Connection test failed: {e}", "details": {}}

    async def list_boards(self, limit: int = 10) -> Dict[str, Any]:
        try:
            query = {"query": f"query {{ boards (limit: {limit}) {{ id name state }} }}"}
            res = await self.post("/v2", json=query)
            return {"boards": res.get("data", {}).get("boards", []), "success": True}
        except Exception as e:
            raise ConnectorError(f"Monday.com list_boards failed: {e}")
