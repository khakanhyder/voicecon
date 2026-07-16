"""
Airtable Connector.

Integrates with the Airtable REST API. Auth uses a personal access token
(PAT) sent as `Authorization: Bearer <token>`.  The user also supplies a
Base ID that scopes most operations.
"""
import logging
from typing import Dict, Any, Optional, List

from app.services.integrations.connector_base import BaseConnector, ConnectorError

logger = logging.getLogger(__name__)


class AirtableConnector(BaseConnector):
    """
    Airtable connector.

    Actions:
    - test_connection: verify token via /v0/meta/whoami
    - list_bases: list accessible bases
    - list_tables: list tables in a base
    - list_records: list records in a table
    - create_record: create a record in a table
    - update_record: update an existing record
    - search_records: search records by formula
    """

    def _base_id(self) -> str:
        data = self.get_auth_data()
        base_id = data.get("base_id")
        if not base_id:
            raise ConnectorError("Airtable connection is missing base_id")
        return base_id

    async def test_connection(self) -> Dict[str, Any]:
        try:
            res = await self.get("/v0/meta/whoami")
            return {
                "success": True,
                "message": "Airtable connection successful",
                "details": {"id": res.get("id"), "email": res.get("email")},
            }
        except Exception as e:
            logger.error(f"Airtable connection test failed: {e}", exc_info=True)
            return {"success": False, "message": f"Airtable connection test failed: {e}", "details": {}}

    async def list_bases(self) -> Dict[str, Any]:
        """List all accessible bases."""
        try:
            res = await self.get("/v0/meta/bases")
            bases = [{"id": b.get("id"), "name": b.get("name")} for b in res.get("bases", [])]
            return {"bases": bases, "count": len(bases)}
        except Exception as e:
            raise ConnectorError(f"Airtable list_bases failed: {e}")

    async def list_tables(self, base_id: Optional[str] = None) -> Dict[str, Any]:
        """List tables in a base."""
        try:
            bid = base_id or self._base_id()
            res = await self.get(f"/v0/meta/bases/{bid}/tables")
            tables = [{"id": t.get("id"), "name": t.get("name")} for t in res.get("tables", [])]
            return {"tables": tables, "count": len(tables)}
        except Exception as e:
            raise ConnectorError(f"Airtable list_tables failed: {e}")

    async def list_records(self, table_name: str, max_records: int = 100,
                           base_id: Optional[str] = None) -> Dict[str, Any]:
        """List records in a table."""
        try:
            bid = base_id or self._base_id()
            params = {"maxRecords": max_records}
            res = await self.get(f"/v0/{bid}/{table_name}", params=params)
            records = [
                {"id": r.get("id"), "fields": r.get("fields", {})}
                for r in res.get("records", [])
            ]
            return {"records": records, "count": len(records)}
        except Exception as e:
            raise ConnectorError(f"Airtable list_records failed: {e}")

    async def create_record(self, table_name: str, fields: Dict[str, Any],
                            base_id: Optional[str] = None) -> Dict[str, Any]:
        """Create a record in a table."""
        try:
            bid = base_id or self._base_id()
            body = {"records": [{"fields": fields}]}
            res = await self.post(f"/v0/{bid}/{table_name}", json=body)
            created = res.get("records", [{}])[0]
            logger.info(f"Airtable record created: {created.get('id')}")
            return {"id": created.get("id"), "fields": created.get("fields", {})}
        except Exception as e:
            logger.error(f"Airtable create_record failed: {e}", exc_info=True)
            raise ConnectorError(f"Airtable create_record failed: {e}")

    async def update_record(self, table_name: str, record_id: str,
                            fields: Dict[str, Any],
                            base_id: Optional[str] = None) -> Dict[str, Any]:
        """Update an existing record."""
        try:
            bid = base_id or self._base_id()
            body = {"records": [{"id": record_id, "fields": fields}]}
            res = await self.patch(f"/v0/{bid}/{table_name}", json=body)
            updated = res.get("records", [{}])[0]
            return {"id": updated.get("id"), "fields": updated.get("fields", {})}
        except Exception as e:
            raise ConnectorError(f"Airtable update_record failed: {e}")

    async def search_records(self, table_name: str, formula: str,
                             max_records: int = 100,
                             base_id: Optional[str] = None) -> Dict[str, Any]:
        """Search records using an Airtable formula filter."""
        try:
            bid = base_id or self._base_id()
            params = {"filterByFormula": formula, "maxRecords": max_records}
            res = await self.get(f"/v0/{bid}/{table_name}", params=params)
            records = [
                {"id": r.get("id"), "fields": r.get("fields", {})}
                for r in res.get("records", [])
            ]
            return {"records": records, "count": len(records)}
        except Exception as e:
            raise ConnectorError(f"Airtable search_records failed: {e}")
