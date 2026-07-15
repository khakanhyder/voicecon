"""
WhatsApp Connector (Meta WhatsApp Business Cloud API).

Bring-your-own-credentials model: each customer supplies their own WhatsApp
Business **access token** (stored as the connection's api_key) and their
**phone_number_id** (stored as an additional field). This lets every customer
use their own WhatsApp Business number without the platform owner needing Meta
Embedded Signup / Tech-Provider approval.

Requests go to graph.facebook.com/<version>/<phone_number_id>/messages with a
Bearer token.
"""
import logging
from typing import Dict, Any, Optional, List

from app.services.integrations.connector_base import BaseConnector, ConnectorError

logger = logging.getLogger(__name__)


class WhatsAppConnector(BaseConnector):
    """
    WhatsApp Business Cloud API connector.

    Actions:
    - test_connection: verify token + phone number id
    - send_message: send a free-form text message (within the 24h window)
    - send_template: send an approved message template (for first contact)
    """

    def get_auth_headers(self, access_token: str) -> Dict[str, str]:
        """
        Meta Graph API authenticates with a Bearer token. The connection is
        stored as an ``api_key`` type (the customer's WhatsApp access token), so
        override the default ``X-API-Key`` header the base class would send —
        Meta ignores that and reports "An access token is required".
        """
        return {"Authorization": f"Bearer {access_token}"}

    def _phone_number_id(self) -> str:
        data = self.get_auth_data()
        phone_id = data.get("phone_number_id")
        if not phone_id:
            raise ConnectorError("WhatsApp connection is missing phone_number_id")
        return phone_id

    async def test_connection(self) -> Dict[str, Any]:
        try:
            phone_id = self._phone_number_id()
            # Fetch the phone number's display info to validate token + id.
            info = await self.get(f"/{phone_id}", params={"fields": "display_phone_number,verified_name"})
            return {
                "success": True,
                "message": "WhatsApp connection successful",
                "details": {
                    "phone_number": info.get("display_phone_number"),
                    "verified_name": info.get("verified_name"),
                },
            }
        except Exception as e:
            logger.error(f"WhatsApp connection test failed: {e}", exc_info=True)
            return {"success": False, "message": f"WhatsApp connection test failed: {e}", "details": {}}

    async def send_message(self, to: str, message: str) -> Dict[str, Any]:
        """
        Send a free-form text message. Only works inside the 24-hour customer
        service window (after the recipient messaged the business); otherwise use
        send_template.

        Args:
            to: recipient phone number in E.164 without '+' (e.g. 15551234567)
            message: text body
        """
        try:
            phone_id = self._phone_number_id()
            body = {
                "messaging_product": "whatsapp",
                "to": to.lstrip("+"),
                "type": "text",
                "text": {"body": message[:4096]},
            }
            res = await self.post(f"/{phone_id}/messages", json=body)
            msg_id = (res.get("messages") or [{}])[0].get("id")
            logger.info(f"WhatsApp message sent: {msg_id}")
            return {"success": True, "message_id": msg_id, "to": to}
        except Exception as e:
            logger.error(f"WhatsApp send_message failed: {e}", exc_info=True)
            raise ConnectorError(f"WhatsApp send_message failed: {e}")

    async def send_template(self, to: str, template_name: str,
                            language_code: str = "en_US",
                            body_params: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Send an approved message template — required for the first message to a
        user (outside the 24h window).

        Args:
            to: recipient phone number (E.164 without '+')
            template_name: the approved template's name
            language_code: e.g. 'en_US'
            body_params: values for the template's {{1}}, {{2}} … placeholders
        """
        try:
            phone_id = self._phone_number_id()
            template: Dict[str, Any] = {"name": template_name, "language": {"code": language_code}}
            if body_params:
                template["components"] = [{
                    "type": "body",
                    "parameters": [{"type": "text", "text": p} for p in body_params],
                }]
            body = {
                "messaging_product": "whatsapp",
                "to": to.lstrip("+"),
                "type": "template",
                "template": template,
            }
            res = await self.post(f"/{phone_id}/messages", json=body)
            msg_id = (res.get("messages") or [{}])[0].get("id")
            logger.info(f"WhatsApp template sent: {msg_id}")
            return {"success": True, "message_id": msg_id, "to": to}
        except Exception as e:
            logger.error(f"WhatsApp send_template failed: {e}", exc_info=True)
            raise ConnectorError(f"WhatsApp send_template failed: {e}")
