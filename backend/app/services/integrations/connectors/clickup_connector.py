"""
ClickUp Connector.

Integration with the ClickUp API v2 (OAuth2). ClickUp's Authorization header is
the raw access token WITHOUT a "Bearer " prefix, so get_auth_headers is overridden.
"""
import logging
from typing import Dict, Any, Optional, List

from app.services.integrations.connector_base import BaseConnector, ConnectorError

logger = logging.getLogger(__name__)


class ClickUpConnector(BaseConnector):
    """
    ClickUp connector.

    Actions:
    - test_connection: verify the token (authorized user)
    - get_workspaces: list workspaces (teams) the user can access
    - get_spaces: list spaces in a workspace
    - get_lists: list task lists in a space (folderless)
    - create_task: create a task in a list
    - get_task / update_task / list_tasks
    - add_comment: comment on a task
    """

    def get_auth_headers(self, access_token: str) -> Dict[str, str]:
        # ClickUp expects the raw token, not "Bearer <token>".
        return {"Authorization": access_token}

    async def test_connection(self) -> Dict[str, Any]:
        try:
            res = await self.get("/user")
            user = res.get("user", {})
            return {
                "success": True,
                "message": "ClickUp connection successful",
                "details": {"user_id": user.get("id"), "username": user.get("username")},
            }
        except Exception as e:
            logger.error(f"ClickUp connection test failed: {e}", exc_info=True)
            return {"success": False, "message": f"ClickUp connection test failed: {e}", "details": {}}

    async def get_workspaces(self) -> Dict[str, Any]:
        """List workspaces (ClickUp calls them 'teams')."""
        try:
            res = await self.get("/team")
            teams = [{"id": t.get("id"), "name": t.get("name")} for t in res.get("teams", [])]
            return {"workspaces": teams, "count": len(teams)}
        except Exception as e:
            raise ConnectorError(f"ClickUp get_workspaces failed: {e}")

    async def get_spaces(self, workspace_id: str) -> Dict[str, Any]:
        try:
            res = await self.get(f"/team/{workspace_id}/space")
            spaces = [{"id": s.get("id"), "name": s.get("name")} for s in res.get("spaces", [])]
            return {"spaces": spaces, "count": len(spaces)}
        except Exception as e:
            raise ConnectorError(f"ClickUp get_spaces failed: {e}")

    async def get_lists(self, space_id: str) -> Dict[str, Any]:
        """List folderless task lists in a space."""
        try:
            res = await self.get(f"/space/{space_id}/list")
            lists = [{"id": l.get("id"), "name": l.get("name")} for l in res.get("lists", [])]
            return {"lists": lists, "count": len(lists)}
        except Exception as e:
            raise ConnectorError(f"ClickUp get_lists failed: {e}")

    async def create_task(self, list_id: str, name: str,
                          description: Optional[str] = None,
                          status: Optional[str] = None,
                          assignees: Optional[List[int]] = None,
                          priority: Optional[int] = None,
                          due_date: Optional[int] = None) -> Dict[str, Any]:
        """Create a task in a list. due_date is a Unix timestamp in ms."""
        try:
            body: Dict[str, Any] = {"name": name}
            if description:
                body["description"] = description
            if status:
                body["status"] = status
            if assignees:
                body["assignees"] = assignees
            if priority is not None:
                body["priority"] = priority
            if due_date is not None:
                body["due_date"] = due_date
            res = await self.post(f"/list/{list_id}/task", json=body)
            logger.info(f"ClickUp task created: {res.get('id')}")
            return {"id": res.get("id"), "name": res.get("name"), "url": res.get("url")}
        except Exception as e:
            logger.error(f"ClickUp create_task failed: {e}", exc_info=True)
            raise ConnectorError(f"ClickUp create_task failed: {e}")

    async def get_task(self, task_id: str) -> Dict[str, Any]:
        try:
            return await self.get(f"/task/{task_id}")
        except Exception as e:
            raise ConnectorError(f"ClickUp get_task failed: {e}")

    async def update_task(
        self,
        task_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        status: Optional[str] = None,
        priority: Optional[Any] = None,
        due_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Update a task's name, description, status, priority or due date.

        Explicit arguments rather than ``**fields``: the values come from an
        agent, and a catch-all let it set anything ClickUp accepts (assignees,
        archived, parent...) by naming it. ``priority`` takes 1-4 or a word
        (urgent/high/normal/low); ``due_date`` takes an ISO date or datetime.
        """
        body: Dict[str, Any] = {}
        if name is not None:
            body["name"] = name
        if description is not None:
            body["description"] = description
        if status is not None:
            body["status"] = status
        if priority not in (None, ""):
            body["priority"] = _clickup_priority(priority)
        if due_date:
            body["due_date"] = _epoch_ms(due_date)
            body["due_date_time"] = "T" in str(due_date)
        if not body:
            raise ConnectorError("Nothing to change: give a new name, description, status, priority or due date.")
        try:
            res = await self.put(f"/task/{task_id}", json=body)
            return {
                "id": res.get("id"),
                "name": res.get("name"),
                "status": (res.get("status") or {}).get("status"),
                "url": res.get("url"),
                "updated": True,
            }
        except Exception as e:
            raise ConnectorError(f"ClickUp update_task failed: {e}")

    async def delete_task(self, task_id: str) -> Dict[str, Any]:
        """Delete a task (ClickUp keeps it in Trash for 30 days)."""
        try:
            await self.delete(f"/task/{task_id}")
        except Exception as e:
            raise ConnectorError(f"ClickUp delete_task failed: {e}")
        return {"id": task_id, "deleted": True}

    async def find_tasks(self, list_id: str, query: Optional[str] = None) -> Dict[str, Any]:
        """Tasks in a list whose name or description contains ``query``.

        The lookup an agent uses before updating a task, so it acts on an id it
        found rather than one it guessed.
        """
        try:
            res = await self.get(f"/list/{list_id}/task", params={"page": 0, "include_closed": "true"})
        except Exception as e:
            raise ConnectorError(f"ClickUp find_tasks failed: {e}")
        needle = (query or "").strip().lower()
        tasks = [
            {
                "id": t.get("id"),
                "name": t.get("name"),
                "status": (t.get("status") or {}).get("status"),
                "due_date": _iso_from_ms(t.get("due_date")),
                "url": t.get("url"),
            }
            for t in res.get("tasks", [])
            if not needle
            or needle in (t.get("name") or "").lower()
            or needle in (t.get("description") or t.get("text_content") or "").lower()
        ]
        return {"tasks": tasks[:25], "count": len(tasks)}

    async def list_tasks(self, list_id: str, page: int = 0) -> Dict[str, Any]:
        try:
            res = await self.get(f"/list/{list_id}/task", params={"page": page})
            tasks = [{"id": t.get("id"), "name": t.get("name"),
                      "status": (t.get("status") or {}).get("status")}
                     for t in res.get("tasks", [])]
            return {"tasks": tasks, "count": len(tasks)}
        except Exception as e:
            raise ConnectorError(f"ClickUp list_tasks failed: {e}")

    async def add_comment(self, task_id: str, comment_text: str) -> Dict[str, Any]:
        try:
            res = await self.post(f"/task/{task_id}/comment", json={"comment_text": comment_text})
            return {"id": res.get("id"), "success": True}
        except Exception as e:
            raise ConnectorError(f"ClickUp add_comment failed: {e}")


_PRIORITIES = {"urgent": 1, "high": 2, "normal": 3, "low": 4}


def _clickup_priority(value: Any) -> int:
    """ClickUp priority 1 (urgent) to 4 (low), from a number or a word."""
    word = str(value).strip().lower()
    if word in _PRIORITIES:
        return _PRIORITIES[word]
    try:
        number = int(float(word))
    except ValueError:
        raise ConnectorError("Priority must be urgent, high, normal or low (or 1-4).")
    if not 1 <= number <= 4:
        raise ConnectorError("Priority must be urgent, high, normal or low (or 1-4).")
    return number


def _epoch_ms(value: str) -> int:
    """ClickUp dates are Unix milliseconds. Accepts YYYY-MM-DD or ISO 8601."""
    from datetime import datetime, timezone

    text = str(value).strip().replace("Z", "+00:00")
    try:
        moment = datetime.fromisoformat(text)
    except ValueError:
        raise ConnectorError(f"'{value}' is not a date. Use YYYY-MM-DD or an ISO 8601 time.")
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return int(moment.timestamp() * 1000)


def _iso_from_ms(value: Any) -> Optional[str]:
    from datetime import datetime, timezone

    try:
        return datetime.fromtimestamp(int(value) / 1000, tz=timezone.utc).isoformat()
    except (TypeError, ValueError):
        return None

