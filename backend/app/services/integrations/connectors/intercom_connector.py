"""
Intercom Connector.

Creates contacts, notes and conversations in Intercom from voice calls.

Uses an Access Token (Intercom's Developer Hub issues one per workspace under
"Authentication"), sent as a bearer token. Intercom's own OAuth exists for
public marketplace apps; for a workspace connecting its own account, the access
token is the documented path and needs nothing registered on our side.
"""
import logging
from typing import Any, Dict, List, Optional

from app.services.integrations.connector_base import BaseConnector, ConnectorError

logger = logging.getLogger(__name__)


class IntercomConnector(BaseConnector):
    """Intercom."""

    #: Intercom versions its API by header. Pinning it means a new default on
    #: their side cannot silently change response shapes under us.
    api_version = "2.11"

    def get_auth_headers(self, access_token: str) -> Dict[str, str]:
        headers = super().get_auth_headers(access_token)
        headers["Intercom-Version"] = self.api_version
        headers["Accept"] = "application/json"
        return headers

    async def test_connection(self) -> Dict[str, Any]:
        try:
            response = await self.get("/me")
            return {
                "success": True,
                "message": "Intercom connection successful",
                "details": {
                    "app": (response.get("app") or {}).get("name"),
                    "email": response.get("email"),
                },
            }
        except Exception as exc:  # noqa: BLE001
            return {
                "success": False,
                "message": f"Connection test failed: {exc}",
                "details": {},
            }

    async def create_contact(
        self,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        name: Optional[str] = None,
        external_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a contact (Intercom calls unidentified ones "leads")."""
        if not any([email, phone, external_id]):
            raise ConnectorError(
                "create_contact needs at least an email, phone or external_id"
            )
        body: Dict[str, Any] = {"role": "user" if external_id else "lead"}
        if email:
            body["email"] = email
        if phone:
            body["phone"] = phone
        if name:
            body["name"] = name
        if external_id:
            body["external_id"] = external_id

        response = await self.post("/contacts", json=body)
        logger.info(f"Intercom contact created: {response.get('id')}")
        return {"success": True, "id": response.get("id"), "contact": response}

    async def search_contacts(self, query: str, limit: int = 10) -> Dict[str, Any]:
        """Find contacts by email, phone or name.

        Intercom's search takes a structured query rather than free text, so the
        one term is fanned out across the three fields a caller could be known
        by — which is the search a voice agent actually wants.
        """
        if not query:
            raise ConnectorError("search_contacts needs a search term")

        body = {
            "query": {
                "operator": "OR",
                "value": [
                    {"field": "email", "operator": "~", "value": query},
                    {"field": "phone", "operator": "~", "value": query},
                    {"field": "name", "operator": "~", "value": query},
                ],
            },
            "pagination": {"per_page": max(1, min(int(limit), 150))},
        }
        response = await self.post("/contacts/search", json=body)
        contacts: List[Dict[str, Any]] = response.get("data") or []
        return {"success": True, "contacts": contacts, "count": len(contacts)}

    async def add_note(self, contact_id: str, note: str) -> Dict[str, Any]:
        """Attach a note — usually the call summary — to a contact."""
        response = await self.post(
            f"/contacts/{contact_id}/notes", json={"body": note}
        )
        return {"success": True, "note": response}

    async def create_conversation(
        self, contact_id: str, message: str
    ) -> Dict[str, Any]:
        """Start a conversation with a contact from the workspace side."""
        response = await self.post(
            "/conversations",
            json={
                "from": {"type": "user", "id": contact_id},
                "body": message,
            },
        )
        logger.info(f"Intercom conversation created: {response.get('id')}")
        return {"success": True, "id": response.get("id"), "conversation": response}
