"""
Google Sheets Connector.
Uses Google OAuth2 for spreadsheet operations.

Rows are addressed the way a caller would: "the row where Phone is
+923001234567", using the sheet's first row as column headers. Row numbers
shift when a row above is deleted, so update/delete look the row up by that
key at the moment of the change (a row number can still be given, and is then
checked against the key) instead of trusting a number found earlier.
"""
import logging
import re
from typing import Any, Dict, List, Optional
from urllib.parse import quote

from app.services.integrations.connector_base import BaseConnector, ConnectorError

logger = logging.getLogger(__name__)

#: How much of a sheet is read to find a row. Plenty for the contact and booking
#: logs agents keep; a sheet bigger than this should be a database.
READ_RANGE = "A1:ZZ5000"


class GoogleSheetsConnector(BaseConnector):
    """
    Google Sheets Connector.
    Actions:
    - test_connection
    - get_spreadsheet
    - append_row
    - find_rows / get_row
    - update_row / upsert_row / delete_row
    """
    async def test_connection(self) -> Dict[str, Any]:
        """Check the token against the Sheets API itself.

        This used to call Google's userinfo endpoint, which needs the email
        scope. Sheets connects with only the spreadsheets scope, so Google
        answered "Request is missing required authentication credential" and
        the Test button always failed, even while every real Sheets action
        worked. A spreadsheet that does not exist answers 404 to a valid token
        and 401/403 to a bad one, which is exactly the question being asked.
        """
        try:
            await self.get("/v4/spreadsheets/voicecon-connection-check", params={"fields": "spreadsheetId"})
        except Exception as e:
            text = str(e)
            if "HTTP 404" in text:
                return {
                    "success": True,
                    "message": "Google Sheets connection successful",
                    "details": {"api": "sheets.googleapis.com"},
                }
            if "HTTP 403" in text and "SERVICE_DISABLED" in text:
                return {"success": False, "details": {},
                        "message": "The Google Sheets API is not enabled for this app's Google Cloud project."}
            return {"success": False, "message": f"Connection test failed: {e}", "details": {}}
        # A spreadsheet with that id exists and is readable: the token works too.
        return {"success": True, "message": "Google Sheets connection successful", "details": {}}

    async def get_spreadsheet(self, spreadsheet_id: str) -> Dict[str, Any]:
        try:
            res = await self.get(f"/v4/spreadsheets/{spreadsheet_id}")
            return res
        except Exception as e:
            raise ConnectorError(f"Google Sheets get_spreadsheet failed: {e}")

    async def append_row(self, spreadsheet_id: str, range_name: str, values: List[List[Any]]) -> Dict[str, Any]:
        try:
            body = {"values": values}
            res = await self.post(
                f"/v4/spreadsheets/{spreadsheet_id}/values/{range_name}:append",
                params={"valueInputOption": "USER_ENTERED"},
                json=body
            )
            return {"updates": res.get("updates", {}), "success": True}
        except Exception as e:
            raise ConnectorError(f"Google Sheets append_row failed: {e}")

    # ------------------------------------------------------------------ rows

    async def find_rows(
        self,
        spreadsheet_id: str,
        column: str,
        value: str,
        sheet: Optional[str] = None,
        match: str = "exact",
    ) -> Dict[str, Any]:
        """Rows where ``column`` (a header name or a letter) matches ``value``."""
        table = await self._read(spreadsheet_id, sheet)
        rows = self._matching(table, column, value, match)
        return {
            "sheet": table["sheet"],
            "rows": [{"row_number": n, "values": self._as_dict(table["headers"], r)} for n, r in rows[:25]],
            "count": len(rows),
            **({} if rows else {"note": f"No row where {column} is '{value}'."}),
        }

    async def get_row(
        self,
        spreadsheet_id: str,
        sheet: Optional[str] = None,
        row_number: Optional[int] = None,
        column: Optional[str] = None,
        value: Optional[str] = None,
    ) -> Dict[str, Any]:
        """The one row a change would touch (used for the audit snapshot)."""
        table = await self._read(spreadsheet_id, sheet)
        number, row = self._locate(table, row_number, column, value)
        return {"sheet": table["sheet"], "row_number": number, "values": self._as_dict(table["headers"], row)}

    async def update_row(
        self,
        spreadsheet_id: str,
        values: Dict[str, Any],
        sheet: Optional[str] = None,
        row_number: Optional[int] = None,
        column: Optional[str] = None,
        value: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Change some cells of one row, by header name. Other cells are kept."""
        if not isinstance(values, dict) or not values:
            raise ConnectorError('Give the cells to change by column name, e.g. {"Status": "Cancelled"}.')
        table = await self._read(spreadsheet_id, sheet)
        number, row = self._locate(table, row_number, column, value)
        merged = self._merge(table["headers"], row, values)
        await self._write_row(spreadsheet_id, table["sheet"], number, merged)
        return {"updated": True, "row_number": number, "values": self._as_dict(table["headers"], merged)}

    async def upsert_row(
        self,
        spreadsheet_id: str,
        column: str,
        value: str,
        values: Dict[str, Any],
        sheet: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Update the row where ``column`` is ``value``, or add one if none exists."""
        if not isinstance(values, dict) or not values:
            raise ConnectorError('Give the cells to set by column name, e.g. {"Status": "Booked"}.')
        table = await self._read(spreadsheet_id, sheet)
        rows = self._matching(table, column, value, "exact")
        if len(rows) > 1:
            raise ConnectorError(
                f"{len(rows)} rows have {column} = '{value}' (rows {', '.join(str(n) for n, _ in rows[:10])}). "
                f"Say which row number to change."
            )
        wanted = {**values}
        key_header = self._header_for(table["headers"], column)
        wanted.setdefault(key_header, value)
        if rows:
            number, row = rows[0]
            merged = self._merge(table["headers"], row, wanted)
            await self._write_row(spreadsheet_id, table["sheet"], number, merged)
            return {"updated": True, "added": False, "row_number": number,
                    "values": self._as_dict(table["headers"], merged)}
        new_row = self._merge(table["headers"], [], wanted)
        res = await self.post(
            f"/v4/spreadsheets/{spreadsheet_id}/values/{_range(table['sheet'], 'A1')}:append",
            params={"valueInputOption": "USER_ENTERED", "insertDataOption": "INSERT_ROWS"},
            json={"values": [new_row]},
        )
        updated_range = ((res.get("updates") or {}).get("updatedRange")) or ""
        found = re.search(r"![A-Z]+(\d+)", updated_range)
        return {"updated": False, "added": True, "row_number": int(found.group(1)) if found else None,
                "values": self._as_dict(table["headers"], new_row)}

    async def delete_row(
        self,
        spreadsheet_id: str,
        sheet: Optional[str] = None,
        row_number: Optional[int] = None,
        column: Optional[str] = None,
        value: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Remove one row entirely; the rows below move up."""
        table = await self._read(spreadsheet_id, sheet)
        number, row = self._locate(table, row_number, column, value)
        await self.post(
            f"/v4/spreadsheets/{spreadsheet_id}:batchUpdate",
            json={"requests": [{"deleteDimension": {"range": {
                "sheetId": table["sheet_id"], "dimension": "ROWS",
                "startIndex": number - 1, "endIndex": number,
            }}}]},
        )
        return {"deleted": True, "row_number": number, "values": self._as_dict(table["headers"], row)}

    # ------------------------------------------------------------------ helpers

    async def _read(self, spreadsheet_id: str, sheet: Optional[str]) -> Dict[str, Any]:
        """Headers and data rows of one tab (the first tab when none is named)."""
        try:
            meta = await self.get(
                f"/v4/spreadsheets/{spreadsheet_id}",
                params={"fields": "sheets.properties(sheetId,title,index)"},
            )
        except Exception as e:
            raise ConnectorError(f"Could not open that spreadsheet: {e}")
        tabs = [s.get("properties") or {} for s in meta.get("sheets", [])]
        if not tabs:
            raise ConnectorError("That spreadsheet has no sheets.")
        if sheet:
            tab = next((t for t in tabs if (t.get("title") or "").lower() == str(sheet).strip().lower()), None)
            if tab is None:
                names = ", ".join(t.get("title") or "?" for t in tabs)
                raise ConnectorError(f"No sheet called '{sheet}'. Sheets: {names}.")
        else:
            tab = sorted(tabs, key=lambda t: t.get("index", 0))[0]
        title = tab.get("title")
        try:
            res = await self.get(f"/v4/spreadsheets/{spreadsheet_id}/values/{_range(title, READ_RANGE)}")
        except Exception as e:
            raise ConnectorError(f"Could not read sheet '{title}': {e}")
        grid = res.get("values") or []
        if not grid or not any(str(h).strip() for h in grid[0]):
            raise ConnectorError(f"Sheet '{title}' needs column names in its first row.")
        return {"sheet": title, "sheet_id": tab.get("sheetId"), "headers": [str(h) for h in grid[0]], "rows": grid[1:]}

    @staticmethod
    def _header_for(headers: List[str], column: str) -> str:
        wanted = str(column or "").strip()
        for h in headers:
            if h.strip().lower() == wanted.lower():
                return h
        if re.fullmatch(r"[A-Za-z]{1,3}", wanted):
            index = _column_index(wanted)
            if index < len(headers):
                return headers[index]
        raise ConnectorError(f"No column called '{column}'. Columns: {', '.join(h for h in headers if h)}.")

    def _matching(self, table: Dict[str, Any], column: str, value: Any, match: str) -> List[tuple]:
        header = self._header_for(table["headers"], column)
        index = table["headers"].index(header)
        contains = str(match).lower() == "contains"
        found = []
        for offset, row in enumerate(table["rows"]):
            cell = row[index] if index < len(row) else ""
            if (_norm(value) in _norm(cell)) if contains else _same(cell, value):
                found.append((offset + 2, row))  # +1 for 1-based, +1 for the header row
        return found

    def _locate(self, table: Dict[str, Any], row_number: Optional[int], column: Optional[str], value: Any) -> tuple:
        """The single row to change: by key, by number, or by number checked against the key."""
        if row_number not in (None, ""):
            try:
                number = int(row_number)
            except (TypeError, ValueError):
                raise ConnectorError("row_number must be a whole number.")
            if number < 2:
                raise ConnectorError("Row 1 holds the column names and cannot be changed this way.")
            if number - 2 >= len(table["rows"]):
                raise ConnectorError(f"Sheet '{table['sheet']}' has no row {number}.")
            row = table["rows"][number - 2]
            if column and value not in (None, ""):
                header = self._header_for(table["headers"], column)
                index = table["headers"].index(header)
                if not _same(row[index] if index < len(row) else "", value):
                    raise ConnectorError(
                        f"Row {number} no longer has {column} = '{value}' (the sheet changed). Look the row up again."
                    )
            return number, row
        if not column or value in (None, ""):
            raise ConnectorError("Say which row: a column and the value to match (e.g. Phone and the caller's number).")
        rows = self._matching(table, column, value, "exact")
        if not rows:
            raise ConnectorError(f"No row where {column} is '{value}'.")
        if len(rows) > 1:
            raise ConnectorError(
                f"{len(rows)} rows have {column} = '{value}' (rows {', '.join(str(n) for n, _ in rows[:10])}). "
                f"Say which row number to change."
            )
        return rows[0]

    def _merge(self, headers: List[str], row: List[Any], values: Dict[str, Any]) -> List[Any]:
        merged = list(row) + [""] * (len(headers) - len(row))
        for column, value in values.items():
            header = self._header_for(headers, column)
            merged[headers.index(header)] = "" if value is None else value
        return merged[: len(headers)]

    async def _write_row(self, spreadsheet_id: str, sheet: str, number: int, cells: List[Any]) -> None:
        last = _column_letter(len(cells) - 1)
        target = _range(sheet, f"A{number}:{last}{number}")
        try:
            await self.put(
                f"/v4/spreadsheets/{spreadsheet_id}/values/{target}",
                params={"valueInputOption": "USER_ENTERED"},
                json={"values": [cells]},
            )
        except Exception as e:
            raise ConnectorError(f"Google Sheets update failed: {e}")

    @staticmethod
    def _as_dict(headers: List[str], row: List[Any]) -> Dict[str, Any]:
        return {h: (row[i] if i < len(row) else "") for i, h in enumerate(headers) if h}


def _norm(value: Any) -> str:
    """Compare cells the way a person would: trimmed, case-insensitive, and
    phone numbers equal whatever their spacing or punctuation."""
    text = str(value if value is not None else "").strip().lower()
    digits = re.sub(r"\D", "", text)
    if len(digits) >= 7 and re.fullmatch(r"[\d\s()+\-.]+", text):
        return digits
    return text


def _same(cell: Any, value: Any) -> bool:
    """Equal as a person would judge it. Phone numbers match on their last ten
    digits, so "+92 300 1234567" in the sheet matches "0300 1234567" spoken."""
    a, b = _norm(cell), _norm(value)
    if a.isdigit() and b.isdigit() and len(a) >= 7 and len(b) >= 7:
        return a[-10:] == b[-10:] if min(len(a), len(b)) >= 10 else a == b
    return a == b


def _range(sheet: str, cells: str) -> str:
    """An A1 range for a URL path; quotes the sheet name when it needs it."""
    name = sheet if re.fullmatch(r"[A-Za-z0-9_]+", sheet or "") else "'" + str(sheet).replace("'", "''") + "'"
    return quote(f"{name}!{cells}", safe="!:'")


def _column_index(letters: str) -> int:
    index = 0
    for ch in letters.upper():
        index = index * 26 + (ord(ch) - 64)
    return index - 1


def _column_letter(index: int) -> str:
    letters = ""
    index += 1
    while index:
        index, rem = divmod(index - 1, 26)
        letters = chr(65 + rem) + letters
    return letters
