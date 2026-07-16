"""
Vonage (Nexmo) Connector.
Uses API Key auth.
"""
import logging
import base64
from typing import Dict, Any
from app.services.integrations.connector_base import BaseConnector, ConnectorError

logger = logging.getLogger(__name__)

class VonageConnector(BaseConnector):
    """
    Vonage (Nexmo) Connector.
    Actions:
    - test_connection
    - send_sms
    """
    async def test_connection(self) -> Dict[str, Any]:
        try:
            # Requires api_key and api_secret in query or body usually.
            # Using the account balance endpoint to test credentials.
            auth_data = self.get_auth_data()
            api_key = auth_data.get("api_key", "")
            api_secret = auth_data.get("api_secret", "")
            
            res = await self.get("/v1/account/get-balance", params={"api_key": api_key, "api_secret": api_secret})
            return {
                "success": True,
                "message": "Vonage connection successful",
                "details": {"balance": res.get("value")},
            }
        except Exception as e:
            return {"success": False, "message": f"Connection test failed: {e}", "details": {}}

    async def send_sms(self, to_number: str, from_name: str, text: str) -> Dict[str, Any]:
        try:
            auth_data = self.get_auth_data()
            api_key = auth_data.get("api_key", "")
            api_secret = auth_data.get("api_secret", "")
            
            body = {
                "api_key": api_key,
                "api_secret": api_secret,
                "to": to_number,
                "from": from_name,
                "text": text,
            }
            res = await self.post("/sms/json", json=body)
            return {"response": res, "success": True}
        except Exception as e:
            raise ConnectorError(f"Vonage send_sms failed: {e}")
