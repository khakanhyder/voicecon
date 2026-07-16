"""
Google Drive Connector.
Uses Google OAuth2 for file operations.
"""
import logging
from typing import Dict, Any
from app.services.integrations.connector_base import BaseConnector, ConnectorError

logger = logging.getLogger(__name__)

class GoogleDriveConnector(BaseConnector):
    """
    Google Drive Connector.
    Actions:
    - test_connection
    - list_files
    """
    async def test_connection(self) -> Dict[str, Any]:
        try:
            res = await self.get("https://www.googleapis.com/drive/v3/about", params={"fields": "user"})
            return {
                "success": True,
                "message": "Google Drive connection successful",
                "details": {"user": res.get("user", {}).get("displayName")},
            }
        except Exception as e:
            return {"success": False, "message": f"Connection test failed: {e}", "details": {}}

    async def list_files(self, query: str = "", limit: int = 10) -> Dict[str, Any]:
        try:
            params = {"pageSize": limit, "fields": "files(id, name, mimeType)"}
            if query:
                params["q"] = query
            res = await self.get("/drive/v3/files", params=params)
            return {"files": res.get("files", []), "success": True}
        except Exception as e:
            raise ConnectorError(f"Google Drive list_files failed: {e}")
