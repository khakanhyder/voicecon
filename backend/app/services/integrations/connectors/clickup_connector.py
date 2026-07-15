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

    async def update_task(self, task_id: str, **fields) -> Dict[str, Any]:
        """Update a task. Accepts name, description, status, priority, due_date, etc."""
        try:
            body = {k: v for k, v in fields.items() if v is not None}
            res = await self.put(f"/task/{task_id}", json=body)
            return {"id": res.get("id"), "name": res.get("name")}
        except Exception as e:
            raise ConnectorError(f"ClickUp update_task failed: {e}")

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
