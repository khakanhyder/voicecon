"""
Telnyx Connector.
Uses API Key auth as Bearer token.
"""
import logging
from typing import Dict, Any
from app.services.integrations.connector_base import BaseConnector, ConnectorError

logger = logging.getLogger(__name__)

class TelnyxConnector(BaseConnector):
    """
    Telnyx Connector.
    Actions:
    - test_connection
    - send_message
    """
    async def test_connection(self) -> Dict[str, Any]:
        try:
            res = await self.get("/v2/phone_numbers", params={"page[size]": 1})
            return {
                "success": True,
                "message": "Telnyx connection successful",
                "details": {"meta": res.get("meta")},
            }
        except Exception as e:
            return {"success": False, "message": f"Connection test failed: {e}", "details": {}}

    async def send_message(self, to_number: str, from_number: str, text: str) -> Dict[str, Any]:
        try:
            body = {
                "to": to_number,
                "from": from_number,
                "text": text,
            }
            res = await self.post("/v2/messages", json=body)
            return {"message": res.get("data", {}), "success": True}
        except Exception as e:
            raise ConnectorError(f"Telnyx send_message failed: {e}")
