"""
Phase 3 of update/delete in connected apps: Supabase rows (writes only on the
table chosen for the connection), Monday items, Intercom contacts and
conversations, Slack message edit/delete, and SendGrid marketing contacts.
"""
import json

import pytest

from app.services.integrations.action_runner import SOURCE_WORKFLOW, IntegrationActionError
from app.services.integrations.connector_base import ConnectorError

from tests.unit.test_integration_update_delete_phase1 import (  # noqa: F401
    api,
    audit,
    connect,
    db,
    run,
)

pytestmark = pytest.mark.asyncio


# ---- Supabase -------------------------------------------------------------------


async def test_supabase_agent_writes_need_a_chosen_table(db, api):
    connection = await connect(db, "supabase")
    with pytest.raises(IntegrationActionError, match="Choose which table agents may change"):
        await run(db, connection, "update_row", {"table_name": "users", "column": "id", "value": "1", "values": {"role": "admin"}, "confirmed": True})
    assert api.calls == []


async def test_supabase_agent_cannot_name_another_table(db, api):
    api.on("GET", "/rest/v1/bookings", [{"id": 7, "status": "booked"}])
    api.on("PATCH", "/rest/v1/bookings", [{"id": 7, "status": "cancelled"}])
    connection = await connect(db, "supabase", defaults={"table_name": "bookings"})
    await run(db, connection, "update_row", {"table_name": "users", "column": "id", "value": "7", "values": {"status": "cancelled"}, "confirmed": True})
    [(_, path, kw)] = api.sent("PATCH")
    assert path == "/rest/v1/bookings"
    assert kw["params"] == {"id": "eq.7"} and kw["json"] == {"status": "cancelled"}
    [change] = await audit(db)
    assert change.before == {"id": 7, "status": "booked"}


async def test_supabase_update_refuses_when_several_rows_match(db, api):
    api.on("GET", "/rest/v1/bookings", [{"id": 1}, {"id": 2}])
    connection = await connect(db, "supabase", defaults={"table_name": "bookings"})
    with pytest.raises(ConnectorError, match="More than one row"):
        await run(db, connection, "delete_row", {"column": "status", "value": "booked", "confirmed": True}, allow_delete=True)
    assert api.sent("DELETE") == []


@pytest.mark.parametrize("column", ["or", "id)", "select", "id;drop", "a b"])
async def test_supabase_rejects_column_names_that_could_add_operators(db, api, column):
    connection = await connect(db, "supabase", defaults={"table_name": "bookings"})
    with pytest.raises(ConnectorError, match="not a valid table or column name"):
        await run(db, connection, "find_rows", {"column": column, "value": "x"})


async def test_supabase_insert_and_workflow_can_choose_its_table(db, api):
    api.on("POST", "/rest/v1/leads", [{"id": 3, "name": "Sara"}])
    connection = await connect(db, "supabase")
    result = await run(db, connection, "insert_row", {"table_name": "leads", "values": {"name": "Sara"}}, source=SOURCE_WORKFLOW)
    assert result["row"] == {"id": 3, "name": "Sara"}
    [(_, _, kw)] = api.sent("POST")
    assert kw["headers"] == {"Prefer": "return=representation"}


# ---- Monday -----------------------------------------------------------------------


COLUMNS = {"data": {"boards": [{"columns": [
    {"id": "name", "title": "Name", "type": "name"},
    {"id": "status", "title": "Status", "type": "status"},
    {"id": "phone_1", "title": "Phone", "type": "phone"},
    {"id": "date4", "title": "Due", "type": "date"},
]}]}}


def monday(api, item_board="B1"):
    def answer(kw):
        query = kw["json"]["query"]
        if "columns" in query:
            return COLUMNS
        if "items(ids" in query:
            return {"data": {"items": [{"id": "i1", "name": "Sara", "board": {"id": item_board}, "column_values": []}]}}
        if "change_multiple_column_values" in query:
            return {"data": {"change_multiple_column_values": {"id": "i1", "name": "Sara"}}}
        if "archive_item" in query:
            return {"data": {"archive_item": {"id": "i1"}}}
        if "items_page" in query:
            return {"data": {"boards": [{"items_page": {"items": [
                {"id": "i1", "name": "Sara", "column_values": [{"text": "+923001234567", "column": {"title": "Phone"}}]},
                {"id": "i2", "name": "Ali", "column_values": []},
            ]}}]}}
        return {"data": {}}
    api.on("POST", "/v2", answer)
    return api


def gql(api, word):
    return [c[2]["json"] for c in api.sent("POST", "/v2") if word in c[2]["json"]["query"]]


async def test_monday_update_maps_titles_and_sends_values_as_variables(db, api):
    monday(api)
    connection = await connect(db, "monday", defaults={"board_id": "B1"})
    await run(db, connection, "update_item", {"item_id": "i1", "values": {"status": "Done", "Due": "2026-10-02T10:00"}, "confirmed": True})
    [call] = gql(api, "change_multiple_column_values")
    assert call["variables"]["board"] == "B1" and call["variables"]["item"] == "i1"
    assert json.loads(call["variables"]["values"]) == {"status": {"label": "Done"}, "date4": {"date": "2026-10-02"}}
    assert "Done" not in call["query"]  # never pasted into the query text


async def test_monday_item_on_another_board_is_refused(db, api):
    monday(api, item_board="OTHER")
    connection = await connect(db, "monday", defaults={"board_id": "B1"})
    with pytest.raises(IntegrationActionError, match="not on the board"):
        await run(db, connection, "archive_item", {"item_id": "i1", "confirmed": True}, allow_delete=True)
    assert gql(api, "archive_item") == []


async def test_monday_find_and_archive(db, api):
    monday(api)
    connection = await connect(db, "monday", defaults={"board_id": "B1"})
    found = await run(db, connection, "find_items", {"query": "0300"})
    assert found["count"] == 0  # "0300" is not in "+923001234567"
    found = await run(db, connection, "find_items", {"query": "3001234567"})
    assert [i["id"] for i in found["items"]] == ["i1"]
    await run(db, connection, "archive_item", {"item_id": "i1", "confirmed": True}, allow_delete=True)
    assert gql(api, "archive_item")[0]["variables"] == {"item": "i1"}


async def test_monday_unknown_column_lists_the_real_ones(db, api):
    monday(api)
    connection = await connect(db, "monday", defaults={"board_id": "B1"})
    with pytest.raises(ConnectorError, match="Columns: Status, Phone, Due"):
        await run(db, connection, "create_item", {"item_name": "New", "values": {"Email": "x"}})


# ---- Intercom -----------------------------------------------------------------------


async def test_intercom_update_archive_and_close(db, api):
    api.on("PUT", "/contacts/c1", {"id": "c1"})
    api.on("GET", "/me", {"id": 991})
    api.on("POST", "/conversations/search", {"conversations": [{"id": "cv1", "state": "open", "source": {"body": "Order issue"}}]})
    api.on("POST", "/conversations/cv1/parts", {"id": "cv1", "state": "closed"})
    connection = await connect(db, "intercom")
    await run(db, connection, "update_contact", {"contact_id": "c1", "phone": "+15550100", "confirmed": True})
    assert api.sent("PUT")[0][2]["json"] == {"phone": "+15550100"}

    found = await run(db, connection, "find_conversations", {"contact_id": "c1"})
    assert found["conversations"][0]["id"] == "cv1"
    await run(db, connection, "close_conversation", {"conversation_id": "cv1", "note": "Solved on the call", "confirmed": True})
    [(_, _, kw)] = api.sent("POST", "/conversations/cv1/parts")
    assert kw["json"] == {"message_type": "close", "type": "admin", "admin_id": "991", "body": "Solved on the call"}

    with pytest.raises(IntegrationActionError, match="Allow deleting"):
        await run(db, connection, "archive_contact", {"contact_id": "c1", "confirmed": True})
    await run(db, connection, "archive_contact", {"contact_id": "c1", "confirmed": True}, allow_delete=True)
    assert api.sent("POST", "/contacts/c1/archive")


# ---- Slack ------------------------------------------------------------------------


async def test_slack_edit_and_delete_stay_in_the_connections_channel(db, api):
    api.on("POST", "/chat.update", {"ok": True, "channel": "C1", "ts": "1.2"})
    api.on("POST", "/chat.delete", {"ok": True, "channel": "C1", "ts": "1.2"})
    connection = await connect(db, "slack", defaults={"channel": "C1"})
    await run(db, connection, "update_message", {"channel": "C_OTHER", "ts": "1.2", "message": "Fixed typo", "confirmed": True})
    [(_, _, kw)] = api.sent("POST", "/chat.update")
    assert kw["json"] == {"channel": "C1", "ts": "1.2", "text": "Fixed typo"}
    with pytest.raises(IntegrationActionError, match="Allow deleting"):
        await run(db, connection, "delete_message", {"ts": "1.2", "confirmed": True})
    await run(db, connection, "delete_message", {"ts": "1.2", "confirmed": True}, allow_delete=True)
    assert api.sent("POST", "/chat.delete")[0][2]["json"] == {"channel": "C1", "ts": "1.2"}


# ---- SendGrid ---------------------------------------------------------------------


async def test_sendgrid_find_by_email_not_by_query_language(db, api):
    api.on("POST", "/v3/marketing/contacts/search/emails", {"result": {"sara@example.com": {"contact": {"id": "sg1", "email": "sara@example.com", "list_ids": ["L1"]}}}})
    connection = await connect(db, "sendgrid")
    found = await run(db, connection, "find_contact", {"email": "sara@example.com"})
    assert found["id"] == "sg1" and found["list_ids"] == ["L1"]
    assert api.sent("POST")[0][2]["json"] == {"emails": ["sara@example.com"]}


async def test_sendgrid_remove_from_the_connections_list_and_delete(db, api):
    connection = await connect(db, "sendgrid", defaults={"list_id": "L1"})
    await run(db, connection, "remove_contact_from_list", {"list_id": "OTHER", "contact_id": "sg1", "confirmed": True}, allow_delete=True)
    [(_, path, kw)] = api.sent("DELETE")
    assert path == "/v3/marketing/lists/L1/contacts" and kw["params"] == {"contact_ids": "sg1"}
    await run(db, connection, "delete_contact", {"contact_id": "sg1", "confirmed": True}, allow_delete=True)
    assert api.sent("DELETE", "/v3/marketing/contacts")


async def test_sendgrid_add_or_update_puts_them_on_the_list(db, api):
    api.on("PUT", "/v3/marketing/contacts", {"job_id": "j1"})
    connection = await connect(db, "sendgrid", defaults={"list_id": "L1"})
    result = await run(db, connection, "add_contact", {"email": "sara@example.com", "first_name": "Sara"})
    assert result["needs_confirmation"] is True  # may update an existing contact
    await run(db, connection, "add_contact", {"email": "sara@example.com", "first_name": "Sara", "confirmed": True})
    [(_, _, kw)] = api.sent("PUT")
    assert kw["json"] == {"contacts": [{"email": "sara@example.com", "first_name": "Sara"}], "list_ids": ["L1"]}
