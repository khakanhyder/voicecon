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

    async def update_contact(self, contact_id: str,
                             first_name: Optional[str] = None,
                             last_name: Optional[str] = None,
                             email: Optional[str] = None,
                             phone: Optional[str] = None,
                             company_name: Optional[str] = None) -> Dict[str, Any]:
        """Update a contact."""
        # Explicit fields, not **fields: the values come from an agent, and a
        # catch-all let it set tags, DND flags or custom fields by naming them.
        body = {
            key: value
            for key, value in (
                ("firstName", first_name), ("lastName", last_name), ("email", email),
                ("phone", phone), ("companyName", company_name),
            )
            if value not in (None, "")
        }
        if not body:
            raise ConnectorError("Nothing to change: give a new name, email, phone or company.")
        try:
            res = await self.put(f"/v1/contacts/{contact_id}", json=body)
            c = res.get("contact", res)
            return {"id": c.get("id") or contact_id, "updated": True}
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

    async def create_opportunity(self, pipeline_id: str, title: str,
                                 stage_id: Optional[str] = None,
                                 contact_id: Optional[str] = None,
                                 monetary_value: Optional[float] = None,
                                 **extra) -> Dict[str, Any]:
        """Create a pipeline opportunity."""
        try:
            stage_id = await self._resolve_stage(pipeline_id, stage_id)
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

    async def _resolve_stage(self, pipeline_id: str, stage: Optional[str]) -> str:
        """A stage id from an id, a stage name, or nothing (the first stage).

        An agent knows "New lead", not a GoHighLevel stage id.
        """
        res = await self.get("/v1/pipelines/", params={"locationId": self._location_id()})
        pipeline = next((p for p in res.get("pipelines", []) if p.get("id") == pipeline_id), None)
        stages = (pipeline or {}).get("stages") or []
        if not stage:
            if not stages:
                raise ConnectorError("That pipeline has no stages to put the opportunity in.")
            return stages[0].get("id")
        wanted = str(stage).strip().lower()
        for s in stages:
            if s.get("id") == stage or (s.get("name") or "").strip().lower() == wanted:
                return s.get("id")
        if not stages:
            return stage  # Could not list stages; let GoHighLevel judge the id.
        names = ", ".join(s.get("name") or "?" for s in stages)
        raise ConnectorError(f"No stage called '{stage}' in that pipeline. Stages: {names}.")

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

    # ------------------------------------------------------------ changes

    async def delete_contact(self, contact_id: str) -> Dict[str, Any]:
        """Delete a contact."""
        try:
            await self.delete(f"/v1/contacts/{contact_id}")
            return {"id": contact_id, "deleted": True}
        except Exception as e:
            raise ConnectorError(f"GoHighLevel delete_contact failed: {e}")

    async def find_appointments(self, contact_id: str) -> Dict[str, Any]:
        """A contact's appointments: the lookup before rescheduling or cancelling."""
        try:
            res = await self.get(f"/v1/contacts/{contact_id}/appointments")
        except Exception as e:
            raise ConnectorError(f"GoHighLevel find_appointments failed: {e}")
        items = res.get("events") or res.get("appointments") or []
        appointments = [
            {
                "id": a.get("id"),
                "title": a.get("title"),
                "calendar_id": a.get("calendarId"),
                "start_time": a.get("startTime"),
                "end_time": a.get("endTime"),
                "status": a.get("appointmentStatus") or a.get("status"),
            }
            for a in items
        ]
        return {"appointments": appointments, "count": len(appointments)}

    async def get_appointment(self, appointment_id: str) -> Dict[str, Any]:
        try:
            res = await self.get(f"/v1/appointments/{appointment_id}")
        except Exception as e:
            raise ConnectorError(f"GoHighLevel get_appointment failed: {e}")
        a = res.get("appointment", res)
        return {
            "id": a.get("id") or appointment_id,
            "title": a.get("title"),
            "calendar_id": a.get("calendarId"),
            "contact_id": a.get("contactId"),
            "start_time": a.get("startTime"),
            "end_time": a.get("endTime"),
            "status": a.get("appointmentStatus") or a.get("status"),
        }

    async def reschedule_appointment(self, appointment_id: str, start_time: str,
                                     time_zone: Optional[str] = None) -> Dict[str, Any]:
        """Move an appointment to a new slot (GoHighLevel keeps its length)."""
        body: Dict[str, Any] = {"selectedSlot": start_time}
        if time_zone:
            body["selectedTimezone"] = time_zone
        try:
            res = await self.put(f"/v1/appointments/{appointment_id}", json=body)
        except Exception as e:
            raise ConnectorError(f"GoHighLevel reschedule_appointment failed: {e}")
        a = res.get("appointment", res) if isinstance(res, dict) else {}
        return {"id": a.get("id") or appointment_id, "start_time": a.get("startTime") or start_time, "rescheduled": True}

    async def cancel_appointment(self, appointment_id: str) -> Dict[str, Any]:
        """Mark an appointment cancelled. It stays on the calendar's history,
        which is what a front desk expects, rather than disappearing."""
        try:
            await self.put(f"/v1/appointments/{appointment_id}/status", json={"status": "cancelled"})
        except Exception as e:
            raise ConnectorError(f"GoHighLevel cancel_appointment failed: {e}")
        return {"id": appointment_id, "cancelled": True}

    async def find_opportunities(self, pipeline_id: str, query: str) -> Dict[str, Any]:
        """Opportunities in a pipeline matching a name, email or phone."""
        try:
            res = await self.get(f"/v1/pipelines/{pipeline_id}/opportunities", params={"query": query, "limit": 20})
        except Exception as e:
            raise ConnectorError(f"GoHighLevel find_opportunities failed: {e}")
        opps = [
            {
                "id": o.get("id"),
                "title": o.get("name") or o.get("title"),
                "status": o.get("status"),
                "stage_id": o.get("pipelineStageId"),
                "monetary_value": o.get("monetaryValue"),
                "contact": (o.get("contact") or {}).get("name"),
            }
            for o in res.get("opportunities", [])
        ]
        return {"opportunities": opps, "count": len(opps)}

    async def get_opportunity(self, pipeline_id: str, opportunity_id: str) -> Dict[str, Any]:
        try:
            o = await self.get(f"/v1/pipelines/{pipeline_id}/opportunities/{opportunity_id}")
        except Exception as e:
            raise ConnectorError(f"GoHighLevel get_opportunity failed: {e}")
        o = o.get("opportunity", o)
        return {
            "id": o.get("id") or opportunity_id,
            "title": o.get("name") or o.get("title"),
            "status": o.get("status"),
            "stage_id": o.get("pipelineStageId"),
            "monetary_value": o.get("monetaryValue"),
            "contact_id": (o.get("contact") or {}).get("id") or o.get("contactId"),
            "pipeline_id": o.get("pipelineId") or pipeline_id,
        }

    async def update_opportunity(self, pipeline_id: str, opportunity_id: str,
                                 stage: Optional[str] = None,
                                 status: Optional[str] = None,
                                 title: Optional[str] = None,
                                 monetary_value: Optional[float] = None) -> Dict[str, Any]:
        """Move an opportunity to another stage, mark it won/lost, or change its
        title or value. GoHighLevel's update needs the whole record, so the
        current one is read and only the given fields are replaced."""
        if status is not None and str(status).lower() not in ("open", "won", "lost", "abandoned"):
            raise ConnectorError("Status must be open, won, lost or abandoned.")
        if stage is None and status is None and title is None and monetary_value is None:
            raise ConnectorError("Nothing to change: give a new stage, status, title or value.")
        current = await self.get_opportunity(pipeline_id, opportunity_id)
        body: Dict[str, Any] = {
            "title": title or current.get("title"),
            "status": (status or current.get("status") or "open").lower(),
            "stageId": await self._resolve_stage(pipeline_id, stage) if stage else current.get("stage_id"),
        }
        if current.get("contact_id"):
            body["contactId"] = current["contact_id"]
        value = monetary_value if monetary_value is not None else current.get("monetary_value")
        if value is not None:
            body["monetaryValue"] = value
        try:
            await self.put(f"/v1/pipelines/{pipeline_id}/opportunities/{opportunity_id}", json=body)
        except Exception as e:
            raise ConnectorError(f"GoHighLevel update_opportunity failed: {e}")
        return {"id": opportunity_id, "updated": True, "stage_id": body["stageId"], "status": body["status"]}

