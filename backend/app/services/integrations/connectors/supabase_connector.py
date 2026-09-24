"""
Supabase Connector.
Uses API Key auth (apikey header and Authorization Bearer).
"""
import logging
import re
from typing import Any, Dict, List, Optional
from app.services.integrations.connector_base import BaseConnector, ConnectorError

logger = logging.getLogger(__name__)

class SupabaseConnector(BaseConnector):
    """
    Supabase Connector.
    Actions:
    - test_connection
    - fetch_table
    """
    def get_auth_headers(self, access_token: str) -> Dict[str, str]:
        # Supabase requires both apikey and Authorization header for REST API.
        return {
            "apikey": access_token,
            "Authorization": f"Bearer {access_token}"
        }

    async def test_connection(self) -> Dict[str, Any]:
        try:
            # The REST root answers with the project's OpenAPI description for
            # any valid key. The previous version probed a table named "users",
            # taken from a `test_table` field no setup form ever collected — so
            # a perfectly good key failed the test on any project that happened
            # not to have that table.
            await self.get("/rest/v1/")
            return {
                "success": True,
                "message": "Supabase connection successful",
                "details": {"project_url": self.http_client.base_url},
            }
        except Exception as e:
            return {"success": False, "message": f"Connection test failed: {e}", "details": {}}

    async def fetch_table(self, table_name: str, limit: int = 10) -> Dict[str, Any]:
        try:
            res = await self.get(f"/rest/v1/{table_name}", params={"limit": str(limit)})
            return {"data": res, "success": True}
        except Exception as e:
            raise ConnectorError(f"Supabase fetch_table failed: {e}")

    # ------------------------------------------------------------ rows

    async def list_tables(self) -> Dict[str, Any]:
        """Tables and views exposed through the REST API (from its OpenAPI root)."""
        try:
            spec = await self.get("/rest/v1/")
        except Exception as e:
            raise ConnectorError(f"Supabase list_tables failed: {e}")
        names = sorted(k for k in (spec.get("definitions") or {}).keys())
        return {"tables": [{"id": n, "name": n} for n in names], "count": len(names)}

    async def find_rows(self, table_name: str, column: str, value: str, limit: int = 10) -> Dict[str, Any]:
        """Rows where ``column`` equals ``value``."""
        rows = await self._select(table_name, column, value, limit=max(1, min(int(limit or 10), 50)))
        return {"rows": rows, "count": len(rows),
                **({} if rows else {"note": f"No row in {table_name} where {column} is '{value}'."})}

    async def get_row(self, table_name: str, column: str, value: str) -> Dict[str, Any]:
        """The single row a change would touch (used for the audit snapshot)."""
        return await self._one(table_name, column, value)

    async def insert_row(self, table_name: str, values: Dict[str, Any]) -> Dict[str, Any]:
        """Add a row."""
        if not isinstance(values, dict) or not values:
            raise ConnectorError('Give the columns to set, e.g. {"name": "Sara", "phone": "+923001234567"}.')
        for column in values:
            _identifier(column)
        try:
            res = await self.post(f"/rest/v1/{_identifier(table_name)}", json=values,
                                  headers={"Prefer": "return=representation"})
        except Exception as e:
            raise ConnectorError(f"Supabase insert failed: {e}")
        row = res[0] if isinstance(res, list) and res else res
        return {"inserted": True, "row": row}

    async def update_row(self, table_name: str, column: str, value: str,
                         values: Dict[str, Any]) -> Dict[str, Any]:
        """Change columns of the one row where ``column`` equals ``value``.

        Exactly one row must match: an update that would silently rewrite many
        rows because the model picked a non-unique column is refused.
        """
        if not isinstance(values, dict) or not values:
            raise ConnectorError('Give the columns to change, e.g. {"status": "cancelled"}.')
        for key in values:
            _identifier(key)
        await self._one(table_name, column, value)
        try:
            res = await self.patch(f"/rest/v1/{_identifier(table_name)}", json=values,
                                   params={_identifier(column): f"eq.{value}"},
                                   headers={"Prefer": "return=representation"})
        except Exception as e:
            raise ConnectorError(f"Supabase update failed: {e}")
        row = res[0] if isinstance(res, list) and res else res
        return {"updated": True, "row": row}

    async def delete_row(self, table_name: str, column: str, value: str) -> Dict[str, Any]:
        """Delete the one row where ``column`` equals ``value``."""
        row = await self._one(table_name, column, value)
        try:
            await self.delete(f"/rest/v1/{_identifier(table_name)}", params={_identifier(column): f"eq.{value}"})
        except Exception as e:
            raise ConnectorError(f"Supabase delete failed: {e}")
        return {"deleted": True, "row": row}

    async def _select(self, table_name: str, column: str, value: Any, limit: int) -> List[Dict[str, Any]]:
        try:
            res = await self.get(
                f"/rest/v1/{_identifier(table_name)}",
                params={_identifier(column): f"eq.{value}", "limit": str(limit)},
            )
        except ConnectorError:
            raise
        except Exception as e:
            raise ConnectorError(f"Supabase lookup failed: {e}")
        return res if isinstance(res, list) else []

    async def _one(self, table_name: str, column: str, value: Any) -> Dict[str, Any]:
        if value in (None, ""):
            raise ConnectorError("Say which row: a column and the value to match, e.g. id and 42.")
        rows = await self._select(table_name, column, value, limit=2)
        if not rows:
            raise ConnectorError(f"No row in {table_name} where {column} is '{value}'.")
        if len(rows) > 1:
            raise ConnectorError(
                f"More than one row in {table_name} has {column} = '{value}'. "
                f"Use a column that is unique for each row, such as id."
            )
        return rows[0]


def _identifier(name: Any) -> str:
    """A table or column name, checked. They go into the URL path and query
    string, where anything else could add PostgREST operators (or=, select=)."""
    text = str(name or "").strip()
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,62}", text) or text.lower() in (
        "select", "order", "limit", "offset", "or", "and", "not", "on_conflict", "columns",
    ):
        raise ConnectorError(f"'{name}' is not a valid table or column name.")
    return text

