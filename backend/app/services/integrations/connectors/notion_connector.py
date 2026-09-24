"""
Notion Connector.

Integration with the Notion API (OAuth2). Every request must carry a
`Notion-Version` header; auth is a Bearer token handled by BaseConnector.
"""
import logging
from typing import Dict, Any, Optional, List

from app.services.integrations.connector_base import BaseConnector, ConnectorError

logger = logging.getLogger(__name__)

# Pin a stable Notion API version. Bump deliberately when adopting new features.
NOTION_VERSION = "2022-06-28"


class NotionConnector(BaseConnector):
    """
    Notion connector.

    Actions:
    - test_connection: verify the token
    - search: find pages/databases the integration can see
    - create_page: create a page under a parent page (title + text)
    - create_database_item: add a row to a database
    - query_database: list items in a database
    - get_page: fetch a page
    - append_text: append a paragraph to a page/block
    - add_comment: comment on a page
    """

    @property
    def _headers(self) -> Dict[str, str]:
        return {"Notion-Version": NOTION_VERSION}

    @staticmethod
    def _rich_text(text: str) -> List[Dict[str, Any]]:
        return [{"type": "text", "text": {"content": text[:2000]}}]

    async def test_connection(self) -> Dict[str, Any]:
        try:
            me = await self.get("/v1/users/me", headers=self._headers)
            return {
                "success": True,
                "message": "Notion connection successful",
                "details": {"bot_id": me.get("id"), "name": me.get("name")},
            }
        except Exception as e:
            logger.error(f"Notion connection test failed: {e}", exc_info=True)
            return {"success": False, "message": f"Notion connection test failed: {e}", "details": {}}

    async def search(self, query: str = "", object_type: Optional[str] = None,
                     page_size: int = 10) -> Dict[str, Any]:
        """Search pages/databases. object_type: 'page' or 'database' to filter."""
        try:
            body: Dict[str, Any] = {"query": query, "page_size": min(page_size, 100)}
            if object_type in ("page", "database"):
                body["filter"] = {"value": object_type, "property": "object"}
            res = await self.post("/v1/search", json=body, headers=self._headers)
            results = [
                {
                    "id": r.get("id"),
                    "object": r.get("object"),
                    "url": r.get("url"),
                    "title": self._extract_title(r),
                }
                for r in res.get("results", [])
            ]
            return {"results": results, "count": len(results)}
        except Exception as e:
            logger.error(f"Notion search failed: {e}", exc_info=True)
            raise ConnectorError(f"Notion search failed: {e}")

    async def create_page(self, parent_page_id: str, title: str,
                          content: Optional[str] = None) -> Dict[str, Any]:
        """Create a page under a parent page with a title and optional text."""
        try:
            children = []
            if content:
                children.append({
                    "object": "block", "type": "paragraph",
                    "paragraph": {"rich_text": self._rich_text(content)},
                })
            body = {
                "parent": {"type": "page_id", "page_id": parent_page_id},
                "properties": {"title": {"title": self._rich_text(title)}},
                "children": children,
            }
            res = await self.post("/v1/pages", json=body, headers=self._headers)
            logger.info(f"Notion page created: {res.get('id')}")
            return {"id": res.get("id"), "url": res.get("url")}
        except Exception as e:
            logger.error(f"Notion create_page failed: {e}", exc_info=True)
            raise ConnectorError(f"Notion create_page failed: {e}")

    async def create_database_item(self, database_id: str,
                                   properties: Dict[str, Any]) -> Dict[str, Any]:
        """Add a row to a database. `properties` uses Notion's property schema."""
        try:
            body = {"parent": {"type": "database_id", "database_id": database_id},
                    "properties": properties}
            res = await self.post("/v1/pages", json=body, headers=self._headers)
            return {"id": res.get("id"), "url": res.get("url")}
        except Exception as e:
            logger.error(f"Notion create_database_item failed: {e}", exc_info=True)
            raise ConnectorError(f"Notion create_database_item failed: {e}")

    async def query_database(self, database_id: str, page_size: int = 10) -> Dict[str, Any]:
        try:
            res = await self.post(f"/v1/databases/{database_id}/query",
                                  json={"page_size": min(page_size, 100)}, headers=self._headers)
            return {"results": res.get("results", []), "count": len(res.get("results", []))}
        except Exception as e:
            logger.error(f"Notion query_database failed: {e}", exc_info=True)
            raise ConnectorError(f"Notion query_database failed: {e}")

    async def get_page(self, page_id: str) -> Dict[str, Any]:
        try:
            return await self.get(f"/v1/pages/{page_id}", headers=self._headers)
        except Exception as e:
            raise ConnectorError(f"Notion get_page failed: {e}")

    async def append_text(self, block_id: str, text: str) -> Dict[str, Any]:
        """Append a paragraph to a page or block."""
        try:
            body = {"children": [{
                "object": "block", "type": "paragraph",
                "paragraph": {"rich_text": self._rich_text(text)},
            }]}
            res = await self.patch(f"/v1/blocks/{block_id}/children", json=body, headers=self._headers)
            return {"success": True, "block_id": block_id}
        except Exception as e:
            logger.error(f"Notion append_text failed: {e}", exc_info=True)
            raise ConnectorError(f"Notion append_text failed: {e}")

    async def add_comment(self, page_id: str, text: str) -> Dict[str, Any]:
        try:
            body = {"parent": {"page_id": page_id}, "rich_text": self._rich_text(text)}
            res = await self.post("/v1/comments", json=body, headers=self._headers)
            return {"id": res.get("id")}
        except Exception as e:
            raise ConnectorError(f"Notion add_comment failed: {e}")

    # ------------------------------------------------------------ changes

    async def find_database_items(self, database_id: str, query: str) -> Dict[str, Any]:
        """Rows of a database with ``query`` in any text column (title, text,
        email, phone, select). The lookup before updating or archiving one."""
        needle = (query or "").strip().lower()
        if not needle:
            raise ConnectorError("Say what to look for, e.g. the caller's name or email.")
        try:
            res = await self.post(f"/v1/databases/{database_id}/query",
                                  json={"page_size": 100}, headers=self._headers)
        except Exception as e:
            raise ConnectorError(f"Notion find_database_items failed: {e}")
        items = []
        for page in res.get("results", []):
            values = _plain_properties(page)
            if any(needle in str(v).lower() for v in values.values()):
                items.append({"id": page.get("id"), "title": self._extract_title(page),
                              "url": page.get("url"), "values": values})
        return {"items": items[:25], "count": len(items)}

    async def get_page_summary(self, page_id: str) -> Dict[str, Any]:
        """A page with its column values as plain text (used for audit snapshots)."""
        page = await self.get_page(page_id)
        return {
            "id": page.get("id"),
            "title": self._extract_title(page),
            "database_id": (page.get("parent") or {}).get("database_id"),
            "archived": page.get("archived"),
            "values": _plain_properties(page),
        }

    async def update_database_item(self, page_id: str, values: Dict[str, Any]) -> Dict[str, Any]:
        """Change columns of a database row using plain values.

        Each value is converted to the Notion property shape its column needs
        (title, text, number, select, multi-select, status, date, checkbox,
        email, phone, URL), read from the row itself, so the model never has
        to write Notion's JSON.
        """
        if not isinstance(values, dict) or not values:
            raise ConnectorError('Give the columns to change, e.g. {"Status": "Done"}.')
        page = await self.get_page(page_id)
        columns = page.get("properties") or {}
        by_name = {name.lower(): name for name in columns}
        properties: Dict[str, Any] = {}
        for column, value in values.items():
            name = by_name.get(str(column).strip().lower())
            if name is None:
                raise ConnectorError(f"No column called '{column}'. Columns: {', '.join(columns)}.")
            properties[name] = _property_value(columns[name].get("type"), value, name)
        try:
            res = await self.patch(f"/v1/pages/{page_id}", json={"properties": properties}, headers=self._headers)
        except Exception as e:
            raise ConnectorError(f"Notion update failed: {e}")
        return {"id": res.get("id") or page_id, "url": res.get("url"), "updated": True,
                "values": _plain_properties(res) if res.get("properties") else values}

    async def update_page_title(self, page_id: str, title: str) -> Dict[str, Any]:
        """Rename a page (or a database row, via its title column)."""
        page = await self.get_page(page_id)
        title_column = next((n for n, p in (page.get("properties") or {}).items() if p.get("type") == "title"), "title")
        try:
            res = await self.patch(f"/v1/pages/{page_id}",
                                   json={"properties": {title_column: {"title": self._rich_text(title)}}},
                                   headers=self._headers)
        except Exception as e:
            raise ConnectorError(f"Notion rename failed: {e}")
        return {"id": res.get("id") or page_id, "title": title, "updated": True}

    async def archive_page(self, page_id: str) -> Dict[str, Any]:
        """Archive a page or database row (Notion's delete; restorable from Trash)."""
        try:
            await self.patch(f"/v1/pages/{page_id}", json={"archived": True}, headers=self._headers)
        except Exception as e:
            raise ConnectorError(f"Notion archive failed: {e}")
        return {"id": page_id, "archived": True}

    @staticmethod
    def _extract_title(obj: Dict[str, Any]) -> str:
        """Best-effort title extraction from a page/database object."""
        props = obj.get("properties", {})
        for prop in props.values():
            if prop.get("type") == "title":
                parts = prop.get("title", [])
                if parts:
                    return "".join(p.get("plain_text", "") for p in parts)
        title = obj.get("title", [])
        if isinstance(title, list) and title:
            return "".join(p.get("plain_text", "") for p in title)
        return ""


def _plain_properties(page: Dict[str, Any]) -> Dict[str, Any]:
    """A page's column values as plain Python values."""
    out: Dict[str, Any] = {}
    for name, prop in (page.get("properties") or {}).items():
        kind = prop.get("type")
        value = prop.get(kind)
        if kind in ("title", "rich_text"):
            out[name] = "".join(p.get("plain_text") or (p.get("text") or {}).get("content", "") for p in value or [])
        elif kind in ("select", "status"):
            out[name] = (value or {}).get("name")
        elif kind == "multi_select":
            out[name] = [o.get("name") for o in value or []]
        elif kind == "date":
            out[name] = (value or {}).get("start")
        elif kind in ("number", "checkbox", "email", "phone_number", "url"):
            out[name] = value
    return out


def _property_value(kind: str, value: Any, name: str) -> Dict[str, Any]:
    """A plain value in the property shape a Notion column of ``kind`` expects."""
    text = "" if value is None else str(value)
    if kind == "title":
        return {"title": [{"type": "text", "text": {"content": text[:2000]}}]}
    if kind == "rich_text":
        return {"rich_text": [{"type": "text", "text": {"content": text[:2000]}}]}
    if kind == "number":
        try:
            return {"number": None if text == "" else float(value)}
        except (TypeError, ValueError):
            raise ConnectorError(f"'{name}' needs a number.")
    if kind == "select":
        return {"select": {"name": text} if text else None}
    if kind == "status":
        return {"status": {"name": text}}
    if kind == "multi_select":
        names = value if isinstance(value, list) else [v.strip() for v in text.split(",") if v.strip()]
        return {"multi_select": [{"name": str(n)} for n in names]}
    if kind == "date":
        return {"date": {"start": text} if text else None}
    if kind == "checkbox":
        return {"checkbox": value if isinstance(value, bool) else text.strip().lower() in ("true", "yes", "1", "done")}
    if kind in ("email", "phone_number", "url"):
        return {kind: text or None}
    raise ConnectorError(f"The '{name}' column ({kind}) cannot be changed this way.")

