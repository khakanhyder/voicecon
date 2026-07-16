"""
Twilio Connector.

Integrates with the Twilio REST API (2010-04-01).  Auth uses HTTP Basic
where the username is the Account SID and the password is the Auth Token.
The user supplies these as a Base64-encoded "SID:Token" string in the
api_key field and their Twilio phone number in additional auth data.
"""
import os
import base64
import logging
from typing import Dict, Any, Optional, List

from app.services.integrations.connector_base import BaseConnector, ConnectorError

logger = logging.getLogger(__name__)


class TwilioConnector(BaseConnector):
    """
    Twilio connector.

    Actions:
    - test_connection: verify credentials via the Account endpoint
    - send_sms: send an SMS message
    - list_messages: list recent messages
    - list_calls: list recent calls
    - lookup_number: look up a phone number
    """

    def get_auth_headers(self, access_token: str) -> Dict[str, str]:
        """
        Twilio uses HTTP Basic auth.  The access_token is stored as the
        Base64-encoded 'AccountSID:AuthToken' pair.
        """
        return {"Authorization": f"Basic {access_token}"}

    def _account_sid(self) -> str:
        """Extract Account SID from the stored auth data."""
        data = self.get_auth_data()
        sid = data.get("account_sid")
        if sid:
            return sid
        # Fallback: decode from the Base64 credential
        try:
            token = self.credential_manager.decrypt(self.connection.api_key_encrypted)
            decoded = base64.b64decode(token).decode()
            return decoded.split(":")[0]
        except Exception:
            raise ConnectorError("Twilio Account SID not found")

    def _twilio_phone(self) -> Optional[str]:
        data = self.get_auth_data()
        return data.get("phone_number")

    async def test_connection(self) -> Dict[str, Any]:
        try:
            sid = self._account_sid()
            res = await self.get(f"/2010-04-01/Accounts/{sid}.json")
            return {
                "success": True,
                "message": "Twilio connection successful",
                "details": {
                    "account_sid": res.get("sid"),
                    "friendly_name": res.get("friendly_name"),
                    "status": res.get("status"),
                },
            }
        except Exception as e:
            logger.error(f"Twilio connection test failed: {e}", exc_info=True)
            return {"success": False, "message": f"Twilio connection test failed: {e}", "details": {}}

    async def send_sms(self, to: str, message: str,
                       from_number: Optional[str] = None) -> Dict[str, Any]:
        """Send an SMS message."""
        try:
            sid = self._account_sid()
            sender = from_number or self._twilio_phone()
            if not sender:
                raise ConnectorError("No 'from' phone number configured")

            data = {"To": to, "From": sender, "Body": message[:1600]}
            res = await self.post(
                f"/2010-04-01/Accounts/{sid}/Messages.json",
                data=data,
            )
            logger.info(f"Twilio SMS sent: {res.get('sid')}")
            return {
                "sid": res.get("sid"),
                "to": res.get("to"),
                "from": res.get("from"),
                "status": res.get("status"),
                "success": True,
            }
        except Exception as e:
            logger.error(f"Twilio send_sms failed: {e}", exc_info=True)
            raise ConnectorError(f"Twilio send_sms failed: {e}")

    async def list_messages(self, limit: int = 20) -> Dict[str, Any]:
        """List recent SMS messages."""
        try:
            sid = self._account_sid()
            res = await self.get(
                f"/2010-04-01/Accounts/{sid}/Messages.json",
                params={"PageSize": limit},
            )
            messages = [
                {
                    "sid": m.get("sid"),
                    "to": m.get("to"),
                    "from": m.get("from"),
                    "body": m.get("body", "")[:200],
                    "status": m.get("status"),
                    "date_sent": m.get("date_sent"),
                }
                for m in res.get("messages", [])
            ]
            return {"messages": messages, "count": len(messages)}
        except Exception as e:
            raise ConnectorError(f"Twilio list_messages failed: {e}")

    async def list_calls(self, limit: int = 20) -> Dict[str, Any]:
        """List recent calls."""
        try:
            sid = self._account_sid()
            res = await self.get(
                f"/2010-04-01/Accounts/{sid}/Calls.json",
                params={"PageSize": limit},
            )
            calls = [
                {
                    "sid": c.get("sid"),
                    "to": c.get("to"),
                    "from": c.get("from"),
                    "status": c.get("status"),
                    "duration": c.get("duration"),
                    "date_created": c.get("date_created"),
                }
                for c in res.get("calls", [])
            ]
            return {"calls": calls, "count": len(calls)}
        except Exception as e:
            raise ConnectorError(f"Twilio list_calls failed: {e}")

    async def lookup_number(self, phone_number: str) -> Dict[str, Any]:
        """Look up information about a phone number (requires Lookup API)."""
        try:
            res = await self.get(
                f"/v2/PhoneNumbers/{phone_number}",
                params={"Fields": "caller_name,line_type_intelligence"},
            )
            return {
                "phone_number": res.get("phone_number"),
                "country_code": res.get("country_code"),
                "caller_name": res.get("caller_name", {}).get("caller_name"),
                "carrier": res.get("carrier", {}).get("name"),
            }
        except Exception as e:
            raise ConnectorError(f"Twilio lookup_number failed: {e}")
