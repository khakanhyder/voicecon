"""
Phase 2 of update/delete in connected apps: Google Sheets rows, GoHighLevel
appointments and opportunities, Cal.com and Calendly bookings, Notion database
rows, Zendesk tickets, Pipedrive people and deals, and delete/archive for
ClickUp, Trello and Airtable.

Same approach as phase 1: the real runner, with each provider's HTTP API faked
at the connector's request helpers.
"""
import pytest

from app.services.integrations.action_runner import SOURCE_WORKFLOW, IntegrationActionError
from app.services.integrations.connector_base import ConnectorError

# Shared fake API, database and helpers.
from tests.unit.test_integration_update_delete_phase1 import (  # noqa: F401
    api,
    audit,
    connect,
    db,
    run,
)

pytestmark = pytest.mark.asyncio

SS = "SS1"
META = {"sheets": [
    {"properties": {"sheetId": 0, "title": "Bookings", "index": 0}},
    {"properties": {"sheetId": 77, "title": "Old leads", "index": 1}},
]}
GRID = {"values": [
    ["Name", "Phone", "Status"],
    ["Sara", "+92 300 1234567", "Booked"],
    ["Ali", "0321-7654321", "Booked"],
    ["Dup", "555", "x"],
    ["Dup2", "555", "y"],
]}


def sheet(api, grid=GRID, tab="Bookings"):
    api.on("GET", f"/v4/spreadsheets/{SS}", META)
    api.on("GET", f"/v4/spreadsheets/{SS}/values/{tab}!A1:ZZ5000", grid)
    api.on("GET", f"/v4/spreadsheets/{SS}/values/'Old%20leads'!A1:ZZ5000", grid)
    return api


# ---- Google Sheets --------------------------------------------------------------


async def test_find_rows_matches_phone_numbers_however_written(db, api):
    sheet(api)
    connection = await connect(db, "google-sheets", defaults={"spreadsheet_id": SS})
    result = await run(db, connection, "find_rows", {"column": "phone", "value": "0300 1234567"})
    assert result["rows"] == [{"row_number": 2, "values": {"Name": "Sara", "Phone": "+92 300 1234567", "Status": "Booked"}}]


async def test_update_row_changes_only_the_named_cells(db, api):
    sheet(api)
    connection = await connect(db, "google-sheets", defaults={"spreadsheet_id": SS})
    result = await run(db, connection, "update_row", {
        "column": "Phone", "value": "03217654321", "values": {"status": "Cancelled"}, "confirmed": True,
    })
    assert result["row_number"] == 3
    [(_, path, kw)] = api.sent("PUT")
    assert path == f"/v4/spreadsheets/{SS}/values/Bookings!A3:C3"
    assert kw["json"] == {"values": [["Ali", "0321-7654321", "Cancelled"]]}
    [change] = await audit(db)
    assert change.before["values"]["Status"] == "Booked"


async def test_update_row_refuses_when_several_rows_match(db, api):
    sheet(api)
    connection = await connect(db, "google-sheets", defaults={"spreadsheet_id": SS})
    with pytest.raises(ConnectorError, match="2 rows have Phone = '555' \\(rows 4, 5\\)"):
        await run(db, connection, "update_row", {"column": "Phone", "value": "555", "values": {"Status": "z"}, "confirmed": True})
    assert api.sent("PUT") == []


async def test_row_number_is_checked_against_the_key(db, api):
    sheet(api)
    connection = await connect(db, "google-sheets", defaults={"spreadsheet_id": SS})
    # Row 4 is "Dup", not Sara: the sheet changed since the lookup.
    with pytest.raises(ConnectorError, match="no longer has"):
        await run(db, connection, "update_row", {"row_number": 4, "column": "Name", "value": "Sara", "values": {"Status": "z"}, "confirmed": True})
    await run(db, connection, "update_row", {"row_number": 5, "column": "Phone", "value": "555", "values": {"Status": "z"}, "confirmed": True})
    assert api.sent("PUT")[0][1].endswith("A5:C5")


async def test_unknown_column_lists_the_real_ones(db, api):
    sheet(api)
    connection = await connect(db, "google-sheets", defaults={"spreadsheet_id": SS})
    with pytest.raises(ConnectorError, match="Columns: Name, Phone, Status"):
        await run(db, connection, "update_row", {"column": "Phone", "value": "03217654321", "values": {"Email": "x"}, "confirmed": True})


async def test_upsert_updates_an_existing_row_or_adds_one(db, api):
    sheet(api)
    api.on("POST", f"/v4/spreadsheets/{SS}/values/Bookings!A1:append", {"updates": {"updatedRange": "Bookings!A6:C6"}})
    connection = await connect(db, "google-sheets", defaults={"spreadsheet_id": SS})
    existing = await run(db, connection, "upsert_row", {"column": "Phone", "value": "03001234567", "values": {"Status": "Paid"}, "confirmed": True})
    assert existing["updated"] and existing["row_number"] == 2
    added = await run(db, connection, "upsert_row", {"column": "Phone", "value": "0999", "values": {"Name": "New"}, "confirmed": True})
    assert added["added"] and added["row_number"] == 6
    [(_, _, kw)] = api.sent("POST")
    assert kw["json"] == {"values": [["New", "0999", ""]]}


async def test_delete_row_removes_that_row_from_the_right_tab(db, api):
    sheet(api, tab="Bookings")
    connection = await connect(db, "google-sheets", defaults={"spreadsheet_id": SS})
    await run(db, connection, "delete_row", {"sheet": "old leads", "column": "Name", "value": "ali", "confirmed": True}, allow_delete=True)
    [(_, path, kw)] = api.sent("POST")
    assert path == f"/v4/spreadsheets/{SS}:batchUpdate"
    assert kw["json"]["requests"][0]["deleteDimension"]["range"] == {"sheetId": 77, "dimension": "ROWS", "startIndex": 2, "endIndex": 3}


async def test_header_row_cannot_be_deleted(db, api):
    sheet(api)
    connection = await connect(db, "google-sheets", defaults={"spreadsheet_id": SS})
    with pytest.raises(ConnectorError, match="column names"):
        await run(db, connection, "delete_row", {"row_number": 1, "column": "Name", "value": "Name", "confirmed": True}, allow_delete=True)


async def test_agent_is_pinned_to_the_connections_spreadsheet(db, api):
    sheet(api)
    connection = await connect(db, "google-sheets", defaults={"spreadsheet_id": SS})
    await run(db, connection, "find_rows", {"spreadsheet_id": "SOMEONE_ELSES", "column": "Name", "value": "Sara"})
    assert all("SOMEONE_ELSES" not in c[1] for c in api.calls)


# ---- GoHighLevel ----------------------------------------------------------------


async def test_ghl_reschedule_and_cancel_appointment(db, api):
    api.on("GET", "/v1/contacts/g1/appointments", {"events": [{"id": "ap1", "title": "Cleaning", "startTime": "2026-10-01T10:00:00Z"}]})
    api.on("GET", "/v1/appointments/ap1", {"appointment": {"id": "ap1", "startTime": "2026-10-01T10:00:00Z", "status": "confirmed"}})
    api.on("PUT", "/v1/appointments/ap1", {"id": "ap1", "startTime": "2026-10-02T11:00:00Z"})
    connection = await connect(db, "gohighlevel")
    found = await run(db, connection, "find_appointments", {"contact_id": "g1"})
    assert found["appointments"][0]["id"] == "ap1"

    await run(db, connection, "reschedule_appointment", {"appointment_id": "ap1", "start_time": "2026-10-02T11:00:00Z", "time_zone": "Asia/Karachi", "confirmed": True})
    [(_, _, kw)] = api.sent("PUT", "/v1/appointments/ap1")
    assert kw["json"] == {"selectedSlot": "2026-10-02T11:00:00Z", "selectedTimezone": "Asia/Karachi"}

    with pytest.raises(IntegrationActionError, match="Allow deleting"):
        await run(db, connection, "cancel_appointment", {"appointment_id": "ap1", "confirmed": True})
    await run(db, connection, "cancel_appointment", {"appointment_id": "ap1", "confirmed": True}, allow_delete=True)
    [(_, _, kw)] = api.sent("PUT", "/v1/appointments/ap1/status")
    assert kw["json"] == {"status": "cancelled"}
    changes = await audit(db)
    assert [c.action for c in changes] == ["reschedule_appointment", "cancel_appointment"]
    assert changes[0].before["start_time"] == "2026-10-01T10:00:00Z"


async def test_ghl_update_opportunity_keeps_what_it_does_not_change(db, api):
    api.on("GET", "/v1/pipelines/P1/opportunities/o1", {"id": "o1", "name": "Quote", "status": "open", "pipelineStageId": "s1", "monetaryValue": 900, "contact": {"id": "g1"}})
    api.on("GET", "/v1/pipelines/", {"pipelines": [{"id": "P1", "stages": [{"id": "s1", "name": "New Lead"}, {"id": "s2", "name": "Booked"}]}]})
    connection = await connect(db, "gohighlevel", defaults={"pipeline_id": "P1"})
    await run(db, connection, "update_opportunity", {"opportunity_id": "o1", "stage": "booked", "confirmed": True})
    [(_, path, kw)] = api.sent("PUT")
    assert path == "/v1/pipelines/P1/opportunities/o1"
    assert kw["json"] == {"title": "Quote", "status": "open", "stageId": "s2", "contactId": "g1", "monetaryValue": 900}


# ---- Cal.com ------------------------------------------------------------------------


BOOKINGS = {"bookings": [
    {"id": 11, "title": "Consult", "startTime": "2099-01-05T10:00:00Z", "endTime": "2099-01-05T10:30:00Z", "status": "ACCEPTED", "attendees": [{"email": "sara@example.com", "name": "Sara"}]},
    {"id": 12, "title": "Past", "startTime": "2000-01-05T10:00:00Z", "endTime": "2000-01-05T10:30:00Z", "status": "ACCEPTED", "attendees": [{"email": "sara@example.com"}]},
    {"id": 13, "title": "Other", "startTime": "2099-01-06T10:00:00Z", "status": "ACCEPTED", "attendees": [{"email": "ali@example.com"}]},
]}


async def test_calcom_find_reschedule_cancel(db, api):
    api.on("GET", "/v1/bookings", BOOKINGS)
    api.on("GET", "/v1/bookings/11", {"booking": BOOKINGS["bookings"][0]})
    api.on("PATCH", "/v1/bookings/11", {"booking": {**BOOKINGS["bookings"][0], "startTime": "2099-01-07T09:00:00+00:00"}})
    connection = await connect(db, "cal-com")
    found = await run(db, connection, "find_bookings", {"attendee": "SARA@example.com"})
    assert [b["id"] for b in found["bookings"]] == [11]

    await run(db, connection, "reschedule_booking", {"booking_id": 11, "start_time": "2099-01-07T09:00:00+00:00", "confirmed": True})
    [(_, _, kw)] = api.sent("PATCH")
    assert kw["json"] == {"startTime": "2099-01-07T09:00:00+00:00", "endTime": "2099-01-07T09:30:00+00:00"}

    await run(db, connection, "cancel_booking", {"booking_id": 11, "reason": "Caller asked", "confirmed": True}, allow_delete=True)
    [(_, path, kw)] = api.sent("DELETE")
    assert path == "/v1/bookings/11/cancel" and kw["params"] == {"cancellationReason": "Caller asked"}


# ---- Calendly ---------------------------------------------------------------------


async def test_calendly_find_gives_reschedule_links_and_cancel_works(db, api):
    api.on("GET", "/users/me", {"resource": {"uri": "https://api.calendly.com/users/U1"}})
    api.on("GET", "/scheduled_events", {"collection": [{"uri": "https://api.calendly.com/scheduled_events/EV1", "name": "Intro", "start_time": "2099-01-01T10:00:00Z"}]})
    api.on("GET", "/scheduled_events/EV1/invitees", {"collection": [{"reschedule_url": "https://calendly.com/reschedulings/x", "cancel_url": "https://calendly.com/cancellations/x"}]})
    api.on("GET", "/scheduled_events/EV1", {"resource": {"name": "Intro", "status": "active"}})
    connection = await connect(db, "calendly")
    found = await run(db, connection, "find_events", {"invitee_email": "sara@example.com"})
    event = found["events"][0]
    assert event["event_uuid"] == "EV1" and event["reschedule_url"].startswith("https://calendly.com/reschedulings")
    params = api.sent("GET", "/scheduled_events")[0][2]["params"]
    assert params["invitee_email"] == "sara@example.com" and params["status"] == "active"

    await run(db, connection, "cancel_event", {"event_uuid": "EV1", "confirmed": True}, allow_delete=True)
    [(_, path, kw)] = api.sent("POST")
    assert path == "/scheduled_events/EV1/cancellation" and kw["json"] == {"reason": "Cancelled by phone"}


# ---- Notion -------------------------------------------------------------------------


PAGE = {
    "id": "aaaaaaaa-1111-2222-3333-444444444444",
    "parent": {"type": "database_id", "database_id": "dbdbdbdb-0000-0000-0000-000000000001"},
    "properties": {
        "Name": {"type": "title", "title": [{"plain_text": "Sara"}]},
        "Status": {"type": "status", "status": {"name": "Open"}},
        "Amount": {"type": "number", "number": 10},
        "Due": {"type": "date", "date": None},
        "Paid": {"type": "checkbox", "checkbox": False},
        "Tags": {"type": "multi_select", "multi_select": []},
    },
}
PAGE_PATH = f"/v1/pages/{PAGE['id']}"


async def test_notion_update_converts_plain_values_to_notion_properties(db, api):
    api.on("GET", PAGE_PATH, PAGE)
    connection = await connect(db, "notion", defaults={"database_id": "dbdbdbdb000000000000000000000001"})
    await run(db, connection, "update_database_item", {
        "page_id": PAGE["id"],
        "values": {"status": "Done", "Amount": "25.5", "Due": "2026-10-02", "paid": "yes", "Tags": "vip, callback"},
        "confirmed": True,
    })
    [(_, _, kw)] = api.sent("PATCH")
    assert kw["json"] == {"properties": {
        "Status": {"status": {"name": "Done"}},
        "Amount": {"number": 25.5},
        "Due": {"date": {"start": "2026-10-02"}},
        "Paid": {"checkbox": True},
        "Tags": {"multi_select": [{"name": "vip"}, {"name": "callback"}]},
    }}
    [change] = await audit(db)
    assert change.before["values"]["Status"] == "Open"


async def test_notion_row_in_another_database_is_refused(db, api):
    api.on("GET", PAGE_PATH, {**PAGE, "parent": {"database_id": "someone-elses"}})
    connection = await connect(db, "notion", defaults={"database_id": "dbdbdbdb000000000000000000000001"})
    with pytest.raises(IntegrationActionError, match="not on the database"):
        await run(db, connection, "archive_page", {"page_id": PAGE["id"], "confirmed": True}, allow_delete=True)
    assert api.sent("PATCH") == []


async def test_notion_archive(db, api):
    api.on("GET", PAGE_PATH, PAGE)
    connection = await connect(db, "notion", defaults={"database_id": "dbdbdbdb-0000-0000-0000-000000000001"})
    await run(db, connection, "archive_page", {"page_id": PAGE["id"], "confirmed": True}, allow_delete=True)
    [(_, _, kw)] = api.sent("PATCH")
    assert kw["json"] == {"archived": True}


async def test_notion_find_rows_by_any_text(db, api):
    api.on("POST", "/v1/databases/DB1/query", {"results": [PAGE, {**PAGE, "id": "p2", "properties": {"Name": {"type": "title", "title": [{"plain_text": "Ali"}]}}}]})
    connection = await connect(db, "notion", defaults={"database_id": "DB1"})
    found = await run(db, connection, "find_database_items", {"query": "sara"})
    assert [i["id"] for i in found["items"]] == [PAGE["id"]]


# ---- Zendesk ------------------------------------------------------------------------


async def test_zendesk_update_ticket(db, api):
    api.on("PUT", "/api/v2/tickets/42.json", {"ticket": {"id": 42, "status": "solved"}})
    connection = await connect(db, "zendesk")
    await run(db, connection, "update_ticket", {"ticket_id": 42, "status": "Solved", "add_tags": ["phone"], "comment": "Resolved on the call", "confirmed": True})
    [(_, _, kw)] = api.sent("PUT")
    assert kw["json"] == {"ticket": {"status": "solved", "additional_tags": ["phone"], "comment": {"body": "Resolved on the call", "public": False}}}
    with pytest.raises(ConnectorError, match="status must be one of"):
        await run(db, connection, "update_ticket", {"ticket_id": 42, "status": "closed", "confirmed": True})


# ---- Pipedrive ----------------------------------------------------------------------


async def test_pipedrive_update_deal_by_stage_name_and_delete(db, api):
    api.on("GET", "/v1/deals/5", {"data": {"id": 5, "title": "Acme", "pipeline_id": 1, "stage_id": 1}})
    api.on("GET", "/v1/stages", {"data": [{"id": 1, "name": "Lead In"}, {"id": 3, "name": "Proposal Made"}]})
    api.on("PUT", "/v1/deals/5", {"data": {"id": 5, "stage_id": 3, "status": "open"}})
    connection = await connect(db, "pipedrive")
    await run(db, connection, "update_deal", {"deal_id": 5, "stage": "proposal made", "value": 1200, "confirmed": True})
    [(_, _, kw)] = api.sent("PUT")
    assert kw["json"] == {"value": 1200, "stage_id": 3}
    with pytest.raises(IntegrationActionError, match="Allow deleting"):
        await run(db, connection, "delete_deal", {"deal_id": 5, "confirmed": True})
    await run(db, connection, "delete_deal", {"deal_id": 5, "confirmed": True}, allow_delete=True)
    assert api.sent("DELETE", "/v1/deals/5")


async def test_pipedrive_update_person_makes_new_email_primary(db, api):
    api.on("PUT", "/v1/persons/9", {"data": {"id": 9}})
    connection = await connect(db, "pipedrive")
    await run(db, connection, "update_person", {"person_id": 9, "email": "new@example.com", "confirmed": True})
    [(_, _, kw)] = api.sent("PUT")
    assert kw["json"] == {"email": [{"value": "new@example.com", "primary": True}]}


# ---- Delete / archive for ClickUp, Trello, Airtable ------------------------------


async def test_clickup_delete_stays_on_the_pinned_list(db, api):
    api.on("GET", "/task/t1", {"id": "t1", "list": {"id": "L1"}})
    api.on("GET", "/task/t2", {"id": "t2", "list": {"id": "OTHER"}})
    connection = await connect(db, "clickup", defaults={"list_id": "L1"})
    await run(db, connection, "delete_task", {"task_id": "t1", "confirmed": True}, allow_delete=True)
    with pytest.raises(IntegrationActionError, match="not on the list"):
        await run(db, connection, "delete_task", {"task_id": "t2", "confirmed": True}, allow_delete=True)
    assert [c[1] for c in api.sent("DELETE")] == ["/task/t1"]


async def test_trello_archive_closes_the_card(db, api):
    api.on("GET", "/cards/k1", {"id": "k1", "idBoard": "B1"})
    connection = await connect(db, "trello", defaults={"board_id": "B1"})
    await run(db, connection, "archive_card", {"card_id": "k1", "confirmed": True}, allow_delete=True)
    [(_, path, kw)] = api.sent("PUT")
    assert path == "/cards/k1" and kw["params"] == {"closed": "true"}


async def test_airtable_delete_record(db, api):
    connection = await connect(db, "airtable")
    await run(db, connection, "delete_record", {"table_name": "Leads", "record_id": "rec1", "confirmed": True}, allow_delete=True)
    assert api.sent("DELETE", "/v0/appB/Leads/rec1")


async def test_workflow_steps_can_use_the_new_actions_without_agent_rules(db, api):
    sheet(api)
    connection = await connect(db, "google-sheets", defaults={"spreadsheet_id": SS})
    await run(db, connection, "delete_row", {"column": "Name", "value": "Sara"}, source=SOURCE_WORKFLOW)
    assert api.sent("POST")
    [change] = await audit(db)
    assert change.source == "workflow"
