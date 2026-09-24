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

    # ------------------------------------------------------------ changes

    async def get_person(self, person_id: int) -> Dict[str, Any]:
        response = await self.get(f"/v1/persons/{person_id}")
        p = response.get("data") or {}
        return {"id": p.get("id"), "name": p.get("name"),
                "email": _primary(p.get("email")), "phone": _primary(p.get("phone"))}

    async def update_person(self, person_id: int, name: Optional[str] = None,
                            email: Optional[str] = None, phone: Optional[str] = None) -> Dict[str, Any]:
        """Change a person's name, email or phone (the new value becomes primary)."""
        body: Dict[str, Any] = {}
        if name:
            body["name"] = name
        if email:
            body["email"] = [{"value": email, "primary": True}]
        if phone:
            body["phone"] = [{"value": phone, "primary": True}]
        if not body:
            raise ConnectorError("Nothing to change: give a new name, email or phone.")
        response = await self.put(f"/v1/persons/{person_id}", json=body)
        return {"success": True, "id": (response.get("data") or {}).get("id") or person_id, "updated": True}

    async def delete_person(self, person_id: int) -> Dict[str, Any]:
        """Delete a person (Pipedrive keeps deleted items restorable for 30 days)."""
        await self.delete(f"/v1/persons/{person_id}")
        return {"success": True, "id": person_id, "deleted": True}

    async def search_deals(self, query: str, limit: int = 10) -> Dict[str, Any]:
        """Find deals by title, or by the person or organisation on them."""
        if not query:
            raise ConnectorError("search_deals needs a search term")
        response = await self.get("/v1/deals/search", params={"term": query, "limit": max(1, min(int(limit), 50))})
        items = ((response.get("data") or {}).get("items")) or []
        deals = [
            {
                "id": d.get("id"),
                "title": d.get("title"),
                "value": d.get("value"),
                "status": d.get("status"),
                "stage": (d.get("stage") or {}).get("name"),
                "person": (d.get("person") or {}).get("name"),
            }
            for d in (item.get("item", {}) for item in items)
        ]
        return {"success": True, "deals": deals, "count": len(deals)}

    async def get_deal(self, deal_id: int) -> Dict[str, Any]:
        response = await self.get(f"/v1/deals/{deal_id}")
        d = response.get("data") or {}
        return {"id": d.get("id"), "title": d.get("title"), "value": d.get("value"),
                "status": d.get("status"), "stage_id": d.get("stage_id"), "pipeline_id": d.get("pipeline_id")}

    async def update_deal(self, deal_id: int, title: Optional[str] = None, value: Optional[float] = None,
                          stage: Optional[str] = None, status: Optional[str] = None,
                          lost_reason: Optional[str] = None) -> Dict[str, Any]:
        """Change a deal's title or value, move it to a stage (by name or id),
        or mark it won/lost."""
        body: Dict[str, Any] = {}
        if title:
            body["title"] = title
        if value is not None:
            body["value"] = value
        if stage not in (None, ""):
            body["stage_id"] = await self._stage_id(deal_id, stage)
        if status:
            if status.lower() not in ("open", "won", "lost"):
                raise ConnectorError("status must be open, won or lost")
            body["status"] = status.lower()
            if status.lower() == "lost" and lost_reason:
                body["lost_reason"] = lost_reason
        if not body:
            raise ConnectorError("Nothing to change: give a new title, value, stage or status.")
        response = await self.put(f"/v1/deals/{deal_id}", json=body)
        d = response.get("data") or {}
        return {"success": True, "id": d.get("id") or deal_id, "status": d.get("status"),
                "stage_id": d.get("stage_id"), "updated": True}

    async def delete_deal(self, deal_id: int) -> Dict[str, Any]:
        """Delete a deal (restorable for 30 days in Pipedrive)."""
        await self.delete(f"/v1/deals/{deal_id}")
        return {"success": True, "id": deal_id, "deleted": True}

    async def _stage_id(self, deal_id: int, stage: Any) -> int:
        """A stage id from an id or a stage name in the deal's own pipeline."""
        if str(stage).strip().isdigit():
            return int(stage)
        deal = await self.get_deal(deal_id)
        response = await self.get("/v1/stages", params={"pipeline_id": deal.get("pipeline_id")})
        stages = response.get("data") or []
        wanted = str(stage).strip().lower()
        for s in stages:
            if (s.get("name") or "").strip().lower() == wanted:
                return s.get("id")
        names = ", ".join(s.get("name") or "?" for s in stages)
        raise ConnectorError(f"No stage called '{stage}' in this deal's pipeline. Stages: {names}.")


def _primary(values: Any) -> Optional[str]:
    """The primary value of Pipedrive's [{value, primary}] list."""
    if isinstance(values, list) and values:
        chosen = next((v for v in values if v.get("primary")), values[0])
        return chosen.get("value")
    return values if isinstance(values, str) else None

