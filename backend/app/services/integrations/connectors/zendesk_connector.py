"""
Zendesk Connector.

Creates and updates support tickets from voice interactions.

Two things make Zendesk different from the other REST connectors here:

* **The host is per-tenant** — ``https://<subdomain>.zendesk.com``. That is what
  the seeded row's ``base_url_field`` is for; the real host is stored on the
  connection and resolved by ``resolve_base_url``.
* **Auth is HTTP Basic with a twist** — the username is not the email but
  ``<email>/token``, and the password is the API token. Sending the plain email
  gets a 401 that looks like a bad token. The frontend builds the base64 pair,
  and the seeded ``api_key_format`` wraps it as ``Basic {api_key}``.
"""
import logging
from typing import Any, Dict, List, Optional

from app.services.integrations.connector_base import BaseConnector, ConnectorError

logger = logging.getLogger(__name__)


class ZendeskConnector(BaseConnector):
    """Zendesk Support."""

    async def test_connection(self) -> Dict[str, Any]:
        try:
            response = await self.get("/api/v2/users/me.json")
            user = response.get("user") or {}
            return {
                "success": True,
                "message": "Zendesk connection successful",
                "details": {
                    "user": user.get("name"),
                    "email": user.get("email"),
                    "role": user.get("role"),
                },
            }
        except Exception as exc:  # noqa: BLE001
            return {
                "success": False,
                "message": f"Connection test failed: {exc}",
                "details": {},
            }

    async def create_ticket(
        self,
        subject: str,
        description: str,
        requester_email: Optional[str] = None,
        requester_name: Optional[str] = None,
        priority: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Raise a ticket from a call.

        Naming the requester by email lets Zendesk match or create the end user
        itself, so a caller who already exists keeps their history instead of
        getting a duplicate profile.
        """
        ticket: Dict[str, Any] = {
            "subject": subject,
            "comment": {"body": description},
        }
        if requester_email:
            requester: Dict[str, Any] = {"email": requester_email}
            if requester_name:
                requester["name"] = requester_name
            ticket["requester"] = requester
        if priority:
            allowed = {"urgent", "high", "normal", "low"}
            if priority.lower() not in allowed:
                raise ConnectorError(
                    f"priority must be one of {sorted(allowed)}, got '{priority}'"
                )
            ticket["priority"] = priority.lower()
        if tags:
            ticket["tags"] = tags if isinstance(tags, list) else [tags]

        response = await self.post("/api/v2/tickets.json", json={"ticket": ticket})
        created = response.get("ticket") or {}
        logger.info(f"Zendesk ticket created: {created.get('id')}")
        return {"success": True, "id": created.get("id"), "ticket": created}

    async def add_comment(
        self,
        ticket_id: int,
        comment: str,
        public: bool = True,
    ) -> Dict[str, Any]:
        """Append a comment to an existing ticket."""
        response = await self.put(
            f"/api/v2/tickets/{ticket_id}.json",
            json={"ticket": {"comment": {"body": comment, "public": bool(public)}}},
        )
        return {"success": True, "ticket": response.get("ticket") or {}}

    async def search_tickets(self, query: str, limit: int = 25) -> Dict[str, Any]:
        """Search tickets with Zendesk's search syntax."""
        if not query:
            raise ConnectorError("search_tickets needs a search term")
        response = await self.get(
            "/api/v2/search.json",
            params={"query": f"type:ticket {query}", "per_page": max(1, min(int(limit), 100))},
        )
        results = response.get("results") or []
        return {"success": True, "tickets": results, "count": len(results)}

    async def get_ticket(self, ticket_id: int) -> Dict[str, Any]:
        response = await self.get(f"/api/v2/tickets/{ticket_id}.json")
        return {"success": True, "ticket": response.get("ticket") or {}}
