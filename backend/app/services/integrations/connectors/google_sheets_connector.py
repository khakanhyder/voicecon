"""
Google Sheets Connector.
Uses Google OAuth2 for spreadsheet operations.
"""
import logging
from typing import Dict, Any, List
from app.services.integrations.connector_base import BaseConnector, ConnectorError

logger = logging.getLogger(__name__)

class GoogleSheetsConnector(BaseConnector):
    """
    Google Sheets Connector.
    Actions:
    - test_connection
    - get_spreadsheet
    - append_row
    """
    async def test_connection(self) -> Dict[str, Any]:
        try:
            # We must use Google Drive API to verify user profile, or standard Sheets endpoint
            res = await self.get("https://www.googleapis.com/oauth2/v1/userinfo", params={"alt": "json"})
            return {
                "success": True,
                "message": "Google Sheets connection successful",
                "details": {"email": res.get("email")},
            }
        except Exception as e:
            return {"success": False, "message": f"Connection test failed: {e}", "details": {}}

    async def get_spreadsheet(self, spreadsheet_id: str) -> Dict[str, Any]:
        try:
            res = await self.get(f"/v4/spreadsheets/{spreadsheet_id}")
            return res
        except Exception as e:
            raise ConnectorError(f"Google Sheets get_spreadsheet failed: {e}")

    async def append_row(self, spreadsheet_id: str, range_name: str, values: List[List[Any]]) -> Dict[str, Any]:
        try:
            body = {"values": values}
            res = await self.post(
                f"/v4/spreadsheets/{spreadsheet_id}/values/{range_name}:append",
                params={"valueInputOption": "USER_ENTERED"},
                json=body
            )
            return {"updates": res.get("updates", {}), "success": True}
        except Exception as e:
            raise ConnectorError(f"Google Sheets append_row failed: {e}")
