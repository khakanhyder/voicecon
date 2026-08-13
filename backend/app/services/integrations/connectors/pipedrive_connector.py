"""
Pipedrive Connector.

Authenticates with a personal API token passed as ``?api_token=``, which is why
the seeded row declares ``api_key_location: "query"``. That path is handled by
BaseConnector.get_auth_params — the same mechanism Cal.com uses.

API token rather than OAuth: a token is on the user's own Settings > Personal
preferences > API page, so they can connect immediately. OAuth would require us
to register a Pipedrive marketplace app first, and the tile would be dead until
someone did.
"""
import logging
from typing import Any, Dict, List, Optional

from app.services.integrations.connector_base import BaseConnector, ConnectorError

logger = logging.getLogger(__name__)


class PipedriveConnector(BaseConnector):
    """Pipedrive CRM."""

    async def test_connection(self) -> Dict[str, Any]:
        try:
            response = await self.get("/v1/users/me")
            user = response.get("data") or {}
            return {
                "success": True,
                "message": "Pipedrive connection successful",
                "details": {
                    "user": user.get("name"),
                    "company": user.get("company_name"),
                },
            }
        except Exception as exc:  # noqa: BLE001
            return {
                "success": False,
                "message": f"Connection test failed: {exc}",
                "details": {},
            }

    async def create_person(
        self,
        name: str,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        organization_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Create a person (Pipedrive's word for a contact)."""
        body: Dict[str, Any] = {"name": name}
        # Pipedrive takes these as arrays of {value, primary}, not bare strings;
        # a bare string is accepted and then silently stored blank.
        if email:
            body["email"] = [{"value": email, "primary": True}]
        if phone:
            body["phone"] = [{"value": phone, "primary": True}]
        if organization_id:
            body["org_id"] = organization_id

        response = await self.post("/v1/persons", json=body)
        person = response.get("data") or {}
        logger.info(f"Pipedrive person created: {person.get('id')}")
        return {"success": True, "id": person.get("id"), "person": person}

    async def search_persons(self, query: str, limit: int = 10) -> Dict[str, Any]:
        """Find people by name, email or phone."""
        if not query:
            raise ConnectorError("search_persons needs a search term")
        response = await self.get(
            "/v1/persons/search",
            params={"term": query, "limit": max(1, min(int(limit), 100))},
        )
        items = ((response.get("data") or {}).get("items")) or []
        persons: List[Dict[str, Any]] = [item.get("item", {}) for item in items]
        return {"success": True, "persons": persons, "count": len(persons)}

    async def create_deal(
        self,
        title: str,
        value: Optional[float] = None,
        currency: Optional[str] = None,
        person_id: Optional[int] = None,
        stage_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Create a deal in the pipeline."""
        body: Dict[str, Any] = {"title": title}
        if value is not None:
            body["value"] = value
        if currency:
            body["currency"] = currency
        if person_id:
            body["person_id"] = person_id
        if stage_id:
            body["stage_id"] = stage_id

        response = await self.post("/v1/deals", json=body)
        deal = response.get("data") or {}
        logger.info(f"Pipedrive deal created: {deal.get('id')}")
        return {"success": True, "id": deal.get("id"), "deal": deal}

    async def add_note(
        self,
        content: str,
        person_id: Optional[int] = None,
        deal_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Attach a note — normally the call summary — to a person or deal."""
        if not person_id and not deal_id:
            raise ConnectorError(
                "add_note needs either a person_id or a deal_id to attach to"
            )
        body: Dict[str, Any] = {"content": content}
        if person_id:
            body["person_id"] = person_id
        if deal_id:
            body["deal_id"] = deal_id

        response = await self.post("/v1/notes", json=body)
        return {"success": True, "note": response.get("data") or {}}
