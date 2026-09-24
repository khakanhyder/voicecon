"""
Monday.com Connector.
Uses OAuth2 Bearer tokens.
"""
import json
import logging
from typing import Any, Dict, List, Optional
from app.services.integrations.connector_base import BaseConnector, ConnectorError

logger = logging.getLogger(__name__)

class MondayConnector(BaseConnector):
    """
    Monday.com Connector.
    Uses GraphQL API, so endpoints hit /v2 with query.
    """
    async def test_connection(self) -> Dict[str, Any]:
        try:
            query = {"query": "query { me { name email } }"}
            res = await self.post("/v2", json=query)
            if "errors" in res:
                return {"success": False, "message": "GraphQL error", "details": res}
            data = res.get("data", {}).get("me", {})
            return {
                "success": True,
                "message": "Monday.com connection successful",
                "details": {"name": data.get("name")},
            }
        except Exception as e:
            return {"success": False, "message": f"Connection test failed: {e}", "details": {}}

    async def list_boards(self, limit: int = 10) -> Dict[str, Any]:
        try:
            query = {"query": f"query {{ boards (limit: {limit}) {{ id name state }} }}"}
            res = await self.post("/v2", json=query)
            return {"boards": res.get("data", {}).get("boards", []), "success": True}
        except Exception as e:
            raise ConnectorError(f"Monday.com list_boards failed: {e}")

    # ------------------------------------------------------------ items
    #
    # Every value travels as a GraphQL variable, never pasted into the query
    # text: item names and column values come from callers and the model.

    async def _gql(self, query: str, variables: Dict[str, Any]) -> Dict[str, Any]:
        try:
            res = await self.post("/v2", json={"query": query, "variables": variables})
        except Exception as e:
            raise ConnectorError(f"Monday.com request failed: {e}")
        if res.get("errors") or res.get("error_message"):
            detail = res.get("error_message") or "; ".join(
                str(err.get("message")) for err in res.get("errors") or []
            )
            raise ConnectorError(f"Monday.com said: {detail}")
        return res.get("data") or {}

    async def _columns(self, board_id: str) -> List[Dict[str, Any]]:
        data = await self._gql(
            "query ($board: [ID!]) { boards(ids: $board) { columns { id title type } } }",
            {"board": [str(board_id)]},
        )
        boards = data.get("boards") or []
        if not boards:
            raise ConnectorError("That board was not found, or this account cannot see it.")
        return boards[0].get("columns") or []

    async def _column_values(self, board_id: str, values: Optional[Dict[str, Any]]) -> str:
        """Plain {"Status": "Done"} as monday's column_values JSON, by column title."""
        if not values:
            return "{}"
        columns = await self._columns(board_id)
        by_title = {c["title"].strip().lower(): c for c in columns}
        by_id = {c["id"]: c for c in columns}
        out: Dict[str, Any] = {}
        for key, value in values.items():
            column = by_title.get(str(key).strip().lower()) or by_id.get(str(key))
            if column is None:
                names = ", ".join(c["title"] for c in columns if c.get("type") != "name")
                raise ConnectorError(f"No column called '{key}'. Columns: {names}.")
            text = "" if value is None else str(value)
            kind = column.get("type")
            if kind == "email":
                out[column["id"]] = {"email": text, "text": text}
            elif kind == "phone":
                out[column["id"]] = {"phone": text}
            elif kind in ("status", "color"):
                out[column["id"]] = {"label": text}
            elif kind == "date":
                out[column["id"]] = {"date": text[:10]}
            elif kind == "checkbox":
                out[column["id"]] = {"checked": "true"} if text.lower() in ("true", "yes", "1", "done") else None
            else:
                out[column["id"]] = text
        return json.dumps(out)

    async def find_items(self, board_id: str, query: str) -> Dict[str, Any]:
        """Items on a board with ``query`` in their name or any column."""
        needle = (query or "").strip().lower()
        if not needle:
            raise ConnectorError("Say what to look for, e.g. the caller's name or phone number.")
        data = await self._gql(
            "query ($board: [ID!]) { boards(ids: $board) { items_page(limit: 200) { items {"
            " id name group { title } column_values { text column { title } } } } } }",
            {"board": [str(board_id)]},
        )
        boards = data.get("boards") or []
        items = ((boards[0].get("items_page") or {}).get("items") if boards else None) or []
        found = []
        for item in items:
            values = {cv["column"]["title"]: cv.get("text") for cv in item.get("column_values") or [] if cv.get("column")}
            if needle in (item.get("name") or "").lower() or any(needle in str(v or "").lower() for v in values.values()):
                found.append({"id": item.get("id"), "name": item.get("name"),
                              "group": (item.get("group") or {}).get("title"), "values": values})
        return {"items": found[:25], "count": len(found)}

    async def get_item(self, item_id: str) -> Dict[str, Any]:
        data = await self._gql(
            "query ($ids: [ID!]) { items(ids: $ids) { id name board { id } column_values { text column { title } } } }",
            {"ids": [str(item_id)]},
        )
        items = data.get("items") or []
        if not items:
            raise ConnectorError("No item with that id.")
        item = items[0]
        return {"id": item.get("id"), "name": item.get("name"), "board_id": (item.get("board") or {}).get("id"),
                "values": {cv["column"]["title"]: cv.get("text") for cv in item.get("column_values") or [] if cv.get("column")}}

    async def create_item(self, board_id: str, item_name: str,
                          values: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Add an item, filling columns by their titles."""
        data = await self._gql(
            "mutation ($board: ID!, $name: String!, $values: JSON) {"
            " create_item(board_id: $board, item_name: $name, column_values: $values) { id name } }",
            {"board": str(board_id), "name": item_name, "values": await self._column_values(board_id, values)},
        )
        item = data.get("create_item") or {}
        return {"id": item.get("id"), "name": item.get("name"), "created": True}

    async def update_item(self, board_id: str, item_id: str, values: Optional[Dict[str, Any]] = None,
                          item_name: Optional[str] = None) -> Dict[str, Any]:
        """Change columns of an item by their titles, or rename it."""
        if not values and not item_name:
            raise ConnectorError('Nothing to change: give new column values, e.g. {"Status": "Done"}, or a new name.')
        column_values = json.loads(await self._column_values(board_id, values))
        if item_name:
            column_values["name"] = item_name
        data = await self._gql(
            "mutation ($board: ID!, $item: ID!, $values: JSON!) {"
            " change_multiple_column_values(board_id: $board, item_id: $item, column_values: $values) { id name } }",
            {"board": str(board_id), "item": str(item_id), "values": json.dumps(column_values)},
        )
        item = data.get("change_multiple_column_values") or {}
        return {"id": item.get("id") or item_id, "name": item.get("name"), "updated": True}

    async def archive_item(self, item_id: str) -> Dict[str, Any]:
        """Archive an item (restorable from the board's archive for 30 days)."""
        data = await self._gql("mutation ($item: ID!) { archive_item(item_id: $item) { id } }", {"item": str(item_id)})
        return {"id": (data.get("archive_item") or {}).get("id") or item_id, "archived": True}

