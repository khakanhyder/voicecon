"""
GoHighLevel Connector.

Integrates with the GoHighLevel REST API v1. Auth uses a Bearer token
(the user's sub-account or agency-level API key).  Most endpoints are
scoped to a Location ID, stored in additional auth data.
"""
import logging
from typing import Dict, Any, Optional, List

from app.services.integrations.connector_base import BaseConnector, ConnectorError

logger = logging.getLogger(__name__)


class GoHighLevelConnector(BaseConnector):
    """
    GoHighLevel connector.

    Actions:
    - test_connection: verify token via /v1/contacts/
    - create_contact: create a contact
    - search_contacts: search contacts by query
    - get_contact: get a single contact
    - update_contact: update a contact
    - list_pipelines: list pipelines
    - create_opportunity: create a pipeline opportunity
    - list_calendars: list calendars
    - book_appointment: book a calendar appointment
    """

    def _location_id(self) -> str:
        data = self.get_auth_data()
        loc = data.get("location_id")
        if not loc:
            raise ConnectorError("GoHighLevel connection is missing location_id")
        return loc

    async def test_connection(self) -> Dict[str, Any]:
        try:
            res = await self.get("/v1/contacts/", params={"limit": 1})
            return {
                "success": True,
                "message": "GoHighLevel connection successful",
                "details": {"contacts_found": len(res.get("contacts", []))},
            }
        except Exception as e:
            logger.error(f"GoHighLevel connection test failed: {e}", exc_info=True)
            return {"success": False, "message": f"GoHighLevel connection test failed: {e}", "details": {}}

    async def create_contact(self, first_name: Optional[str] = None,
                             last_name: Optional[str] = None,
                             email: Optional[str] = None,
                             phone: Optional[str] = None,
                             company_name: Optional[str] = None,
                             **extra) -> Dict[str, Any]:
        """Create a new contact in GoHighLevel."""
        try:
            body: Dict[str, Any] = {"locationId": self._location_id()}
            if first_name: body["firstName"] = first_name
            if last_name: body["lastName"] = last_name
            if email: body["email"] = email
            if phone: body["phone"] = phone
            if company_name: body["companyName"] = company_name
            body.update({k: v for k, v in extra.items() if v is not None})

            res = await self.post("/v1/contacts/", json=body)
            contact = res.get("contact", res)
            logger.info(f"GHL contact created: {contact.get('id')}")
            return {
                "id": contact.get("id"),
                "first_name": contact.get("firstName"),
                "last_name": contact.get("lastName"),
                "email": contact.get("email"),
                "phone": contact.get("phone"),
            }
        except Exception as e:
            logger.error(f"GHL create_contact failed: {e}", exc_info=True)
            raise ConnectorError(f"GoHighLevel create_contact failed: {e}")

    async def search_contacts(self, query: str, limit: int = 20) -> Dict[str, Any]:
        """Search contacts by name, email, or phone."""
        try:
            params = {"query": query, "limit": limit, "locationId": self._location_id()}
            res = await self.get("/v1/contacts/", params=params)
            contacts = [
                {
                    "id": c.get("id"),
                    "name": f"{c.get('firstName', '')} {c.get('lastName', '')}".strip(),
                    "email": c.get("email"),
                    "phone": c.get("phone"),
                }
                for c in res.get("contacts", [])
            ]
            return {"contacts": contacts, "count": len(contacts)}
        except Exception as e:
            raise ConnectorError(f"GoHighLevel search_contacts failed: {e}")

    async def get_contact(self, contact_id: str) -> Dict[str, Any]:
        """Get a single contact by ID."""
        try:
            res = await self.get(f"/v1/contacts/{contact_id}")
            c = res.get("contact", res)
            return {
                "id": c.get("id"),
                "first_name": c.get("firstName"),
                "last_name": c.get("lastName"),
                "email": c.get("email"),
                "phone": c.get("phone"),
                "company": c.get("companyName"),
            }
        except Exception as e:
            raise ConnectorError(f"GoHighLevel get_contact failed: {e}")

    async def update_contact(self, contact_id: str, **fields) -> Dict[str, Any]:
        """Update a contact."""
        try:
            body = {k: v for k, v in fields.items() if v is not None}
            res = await self.put(f"/v1/contacts/{contact_id}", json=body)
            c = res.get("contact", res)
            return {"id": c.get("id"), "updated": True}
        except Exception as e:
            raise ConnectorError(f"GoHighLevel update_contact failed: {e}")

    async def list_pipelines(self) -> Dict[str, Any]:
        """List all pipelines."""
        try:
            res = await self.get("/v1/pipelines/", params={"locationId": self._location_id()})
            pipelines = [
                {"id": p.get("id"), "name": p.get("name")}
                for p in res.get("pipelines", [])
            ]
            return {"pipelines": pipelines, "count": len(pipelines)}
        except Exception as e:
            raise ConnectorError(f"GoHighLevel list_pipelines failed: {e}")

    async def create_opportunity(self, pipeline_id: str, stage_id: str,
                                 title: str, contact_id: Optional[str] = None,
                                 monetary_value: Optional[float] = None,
                                 **extra) -> Dict[str, Any]:
        """Create a pipeline opportunity."""
        try:
            body: Dict[str, Any] = {
                "pipelineId": pipeline_id,
                "pipelineStageId": stage_id,
                "title": title,
                "locationId": self._location_id(),
            }
            if contact_id: body["contactId"] = contact_id
            if monetary_value is not None: body["monetaryValue"] = monetary_value
            body.update({k: v for k, v in extra.items() if v is not None})

            res = await self.post("/v1/pipelines/opportunities", json=body)
            return {"id": res.get("id"), "title": res.get("title"), "success": True}
        except Exception as e:
            raise ConnectorError(f"GoHighLevel create_opportunity failed: {e}")

    async def list_calendars(self) -> Dict[str, Any]:
        """List all calendars."""
        try:
            res = await self.get("/v1/calendars/", params={"locationId": self._location_id()})
            calendars = [
                {"id": c.get("id"), "name": c.get("name")}
                for c in res.get("calendars", [])
            ]
            return {"calendars": calendars, "count": len(calendars)}
        except Exception as e:
            raise ConnectorError(f"GoHighLevel list_calendars failed: {e}")

    async def book_appointment(self, calendar_id: str, contact_id: str,
                               start_time: str, end_time: str,
                               title: Optional[str] = None, **extra) -> Dict[str, Any]:
        """Book a calendar appointment."""
        try:
            body: Dict[str, Any] = {
                "calendarId": calendar_id,
                "contactId": contact_id,
                "startTime": start_time,
                "endTime": end_time,
                "locationId": self._location_id(),
            }
            if title: body["title"] = title
            body.update({k: v for k, v in extra.items() if v is not None})

            res = await self.post("/v1/appointments/", json=body)
            return {"id": res.get("id"), "success": True}
        except Exception as e:
            raise ConnectorError(f"GoHighLevel book_appointment failed: {e}")
