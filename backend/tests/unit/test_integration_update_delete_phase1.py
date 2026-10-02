"""
Phase 1 of update/delete in connected apps: ClickUp, Trello, Airtable,
HubSpot, GoHighLevel and Stripe.

Each test goes through the real runner (the path agent tools and workflow steps
share), with the provider's HTTP API faked at the connector's request helpers,
and checks exactly what would be sent to the provider.
"""
import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models.integration import IntegrationChange, IntegrationConnection, IntegrationConnector
from app.services.integrations.action_runner import (
    SOURCE_AGENT,
    SOURCE_WORKFLOW,
    IntegrationActionError,
    run_integration_action,
)
from app.services.integrations.connector_base import BaseConnector, ConnectorError
from app.services.integrations.connectors.gohighlevel_connector import GoHighLevelConnector
from app.services.integrations.connectors.trello_connector import TrelloConnector

ORG = uuid.uuid4()


class FakeAPI:
    """Routes (method, path) to canned answers and records every request."""

    def __init__(self):
        self.calls = []
        self.routes = {}

    def on(self, method, path, answer):
        self.routes[(method, path)] = answer
        return self

    def install(self, monkeypatch):
        fake = self

        def handler(method):
            async def call(self, path, **kw):
                fake.calls.append((method, path, kw))
                answer = fake.routes.get((method, path), {})
                if isinstance(answer, Exception):
                    raise answer
                return answer(kw) if callable(answer) else answer
            return call

        for method in ("get", "post", "put", "patch", "delete"):
            monkeypatch.setattr(BaseConnector, method, handler(method.upper()))

        async def close(self):
            return None

        async def trello_auth(self, extra=None):
            return dict(extra or {})

        monkeypatch.setattr(BaseConnector, "close", close, raising=False)
        monkeypatch.setattr(TrelloConnector, "_auth_params", trello_auth)
        monkeypatch.setattr(GoHighLevelConnector, "_location_id", lambda self: "loc1")
        # Airtable keeps its base id in the connection's encrypted auth data.
        monkeypatch.setattr(BaseConnector, "get_auth_data", lambda self: {"base_id": "appB"})
        return self

    def sent(self, method, path=None):
        return [c for c in self.calls if c[0] == method and (path is None or c[1] == path)]


@pytest.fixture
def api(monkeypatch):
    return FakeAPI().install(monkeypatch)


@pytest_asyncio.fixture
async def db() -> AsyncSession:
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


async def connect(db, slug, defaults=None, config=None):
    connector = IntegrationConnector(id=uuid.uuid4(), name=slug, slug=slug, auth_type="api_key", base_url="https://api")
    db.add(connector)
    connection = IntegrationConnection(
        id=uuid.uuid4(), user_id=uuid.uuid4(), organization_id=ORG, connector_id=connector.id,
        config={**(config or {}), **({"defaults": defaults} if defaults else {})},
    )
    db.add(connection)
    await db.commit()
    return connection


def run(db, connection, action, params, *, source=SOURCE_AGENT, allow_delete=False):
    return run_integration_action(
        db, organization_id=ORG, connection_id=connection.id, action=action, parameters=params,
        source=source, tool_config={"allow_destructive": "true" if allow_delete else "false"}, call_id="c1",
    )


async def audit(db):
    return (await db.execute(select(IntegrationChange))).scalars().all()


# ---- Every new change action is guarded ---------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "slug, action, params",
    [
        ("clickup", "update_task", {"task_id": "t1", "name": "x"}),
        ("trello", "update_card", {"card_id": "k1", "name": "x"}),
        ("airtable", "update_record", {"table_name": "Leads", "record_id": "rec1", "fields": {"a": 1}}),
        ("hubspot", "update_contact", {"contact_id": "1", "phone": "1"}),
        ("hubspot", "update_deal", {"deal_id": "1", "stage": "closedwon"}),
        ("gohighlevel", "update_contact", {"contact_id": "g1", "phone": "1"}),
        ("stripe", "update_customer", {"customer_id": "cus_1", "name": "x"}),
    ],
)
async def test_updates_need_the_callers_confirmation(db, api, slug, action, params):
    connection = await connect(db, slug)
    result = await run(db, connection, action, params)
    assert result["needs_confirmation"] is True
    assert [c for c in api.calls if c[0] != "GET"] == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "slug, action, params",
    [
        ("hubspot", "delete_contact", {"contact_id": "1"}),
        ("stripe", "cancel_subscription", {"subscription_id": "sub_1"}),
        ("stripe", "cancel_payment_intent", {"intent_id": "pi_1"}),
    ],
)
async def test_deletes_and_cancellations_are_opt_in(db, api, slug, action, params):
    connection = await connect(db, slug)
    with pytest.raises(IntegrationActionError, match="Allow deleting"):
        await run(db, connection, action, {**params, "confirmed": True})
    assert [c for c in api.calls if c[0] != "GET"] == []


# ---- ClickUp ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_clickup_update_sends_only_the_allowed_fields(db, api):
    api.on("GET", "/task/t1", {"id": "t1", "name": "Old", "list": {"id": "L1"}})
    api.on("PUT", "/task/t1", {"id": "t1", "name": "New", "status": {"status": "complete"}})
    connection = await connect(db, "clickup", defaults={"list_id": "L1"})
    result = await run(db, connection, "update_task", {
        "task_id": "t1", "name": "New", "status": "complete", "priority": "high", "due_date": "2026-10-02",
        "assignees": {"add": [999]}, "archived": True,  # an LLM being creative
        "confirmed": True,
    })
    assert result["updated"] is True
    [(_, _, kw)] = api.sent("PUT")
    assert kw["json"] == {"name": "New", "status": "complete", "priority": 2,
                          "due_date": 1790899200000, "due_date_time": False}
    [change] = await audit(db)
    assert change.before["name"] == "Old" and change.record_id == "t1"


@pytest.mark.asyncio
async def test_clickup_task_on_another_list_is_refused(db, api):
    api.on("GET", "/task/t9", {"id": "t9", "list": {"id": "SOMEONE_ELSES"}})
    connection = await connect(db, "clickup", defaults={"list_id": "L1"})
    with pytest.raises(IntegrationActionError, match="not on the list"):
        await run(db, connection, "update_task", {"task_id": "t9", "name": "x", "list_id": "SOMEONE_ELSES", "confirmed": True})
    assert api.sent("PUT") == []


@pytest.mark.asyncio
async def test_clickup_find_tasks_filters_by_text(db, api):
    api.on("GET", "/list/L1/task", {"tasks": [
        {"id": "a", "name": "Call back Sara", "status": {"status": "open"}},
        {"id": "b", "name": "Invoice", "description": "for sara@example.com"},
        {"id": "c", "name": "Unrelated"},
    ]})
    connection = await connect(db, "clickup", defaults={"list_id": "L1"})
    result = await run(db, connection, "find_tasks", {"query": "sara"})
    assert [t["id"] for t in result["tasks"]] == ["a", "b"]


# ---- Trello -------------------------------------------------------------------


@pytest.mark.asyncio
async def test_trello_update_maps_fields_and_cannot_archive(db, api):
    api.on("GET", "/cards/k1", {"id": "k1", "name": "Old", "idBoard": "B1", "idList": "L1"})
    api.on("PUT", "/cards/k1", {"id": "k1", "name": "New", "idList": "L2"})
    connection = await connect(db, "trello", defaults={"board_id": "B1", "list_id": "L1"})
    await run(db, connection, "update_card", {
        "card_id": "k1", "name": "New", "description": "Moved", "move_to_list_id": "L2",
        "closed": True, "confirmed": True,
    })
    [(_, _, kw)] = api.sent("PUT")
    assert kw["params"] == {"name": "New", "desc": "Moved", "idList": "L2"}


@pytest.mark.asyncio
async def test_trello_card_on_another_board_is_refused(db, api):
    api.on("GET", "/cards/k2", {"id": "k2", "idBoard": "OTHER"})
    connection = await connect(db, "trello", defaults={"board_id": "B1"})
    with pytest.raises(IntegrationActionError, match="not on the board"):
        # Naming the other board does not help: the board is pinned.
        await run(db, connection, "update_card", {"card_id": "k2", "name": "x", "board_id": "OTHER", "confirmed": True})
    assert api.sent("PUT") == []


@pytest.mark.asyncio
async def test_trello_find_cards_searches_the_pinned_board(db, api):
    api.on("GET", "/boards/B1/cards", [{"id": "k1", "name": "Sara - quote"}, {"id": "k2", "name": "Other"}])
    connection = await connect(db, "trello", defaults={"board_id": "B1"})
    result = await run(db, connection, "find_cards", {"query": "sara", "board_id": "ELSEWHERE"})
    assert [c["id"] for c in result["cards"]] == ["k1"]
    assert api.sent("GET", "/boards/ELSEWHERE/cards") == []


# ---- Airtable -----------------------------------------------------------------


@pytest.mark.asyncio
async def test_airtable_find_escapes_the_search_value(db, api):
    connection = await connect(db, "airtable")
    api.on("GET", "/v0/appB/Leads", {"records": [{"id": "rec1", "fields": {"Name": "O'Brien"}}]})
    result = await run(db, connection, "find_records", {"table_name": "Leads", "field": "Name", "value": "O'Brien"})
    [(_, _, kw)] = api.sent("GET")
    assert kw["params"]["filterByFormula"] == "LOWER({Name}&'') = LOWER('O\\'Brien')"
    assert result["records"][0]["id"] == "rec1"


@pytest.mark.asyncio
async def test_airtable_update_patches_the_record_and_keeps_a_before_copy(db, api):
    connection = await connect(db, "airtable")
    api.on("GET", "/v0/appB/Leads/rec1", {"id": "rec1", "fields": {"Status": "New"}})
    api.on("PATCH", "/v0/appB/Leads", {"records": [{"id": "rec1", "fields": {"Status": "Booked"}}]})
    await run(db, connection, "update_record", {"table_name": "Leads", "record_id": "rec1", "fields": {"Status": "Booked"}, "confirmed": True})
    [(_, _, kw)] = api.sent("PATCH")
    assert kw["json"] == {"records": [{"id": "rec1", "fields": {"Status": "Booked"}}]}
    [change] = await audit(db)
    assert change.before["fields"] == {"Status": "New"}


# ---- HubSpot ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_hubspot_update_contact_maps_names_to_hubspot_properties(db, api):
    api.on("PATCH", "/crm/v3/objects/contacts/7", {"id": "7"})
    connection = await connect(db, "hubspot")
    await run(db, connection, "update_contact", {"contact_id": "7", "email": "a@b.co", "first_name": "Sara", "confirmed": True})
    [(_, _, kw)] = api.sent("PATCH")
    assert kw["json"] == {"properties": {"email": "a@b.co", "firstname": "Sara"}}


@pytest.mark.asyncio
async def test_hubspot_update_deal_and_find_deals(db, api):
    api.on("POST", "/crm/v3/objects/deals/search", {"total": 1, "results": [{"id": "9", "properties": {"dealname": "Acme"}}]})
    api.on("PATCH", "/crm/v3/objects/deals/9", {"id": "9"})
    connection = await connect(db, "hubspot")
    found = await run(db, connection, "search_deals", {"query": "Acme"})
    assert found["deals"] == [{"id": "9", "dealname": "Acme"}]
    await run(db, connection, "update_deal", {"deal_id": "9", "stage": "closedwon", "amount": 500, "confirmed": True})
    [(_, _, kw)] = api.sent("PATCH")
    assert kw["json"] == {"properties": {"dealstage": "closedwon", "amount": 500}}


@pytest.mark.asyncio
async def test_hubspot_update_deal_with_nothing_to_change_is_explained(db, api):
    connection = await connect(db, "hubspot")
    with pytest.raises(ConnectorError, match="Nothing to change"):
        await run(db, connection, "update_deal", {"deal_id": "9", "confirmed": True})
    assert api.sent("PATCH") == []


@pytest.mark.asyncio
async def test_hubspot_delete_contact_when_allowed(db, api):
    api.on("GET", "/crm/v3/objects/contacts/7", {"id": "7", "properties": {"email": "a@b.co"}})
    connection = await connect(db, "hubspot")
    result = await run(db, connection, "delete_contact", {"contact_id": "7", "confirmed": True}, allow_delete=True)
    assert result["success"] is True
    assert api.sent("DELETE", "/crm/v3/objects/contacts/7")
    [change] = await audit(db)
    assert change.operation == "delete" and change.before["properties"]["email"] == "a@b.co"


# ---- GoHighLevel --------------------------------------------------------------


@pytest.mark.asyncio
async def test_ghl_update_contact_uses_camel_case_and_drops_unknown_fields(db, api):
    api.on("PUT", "/v1/contacts/g1", {"contact": {"id": "g1"}})
    connection = await connect(db, "gohighlevel")
    await run(db, connection, "update_contact", {"contact_id": "g1", "first_name": "Sara", "phone": "555", "tags": ["vip"], "dnd": True, "confirmed": True})
    [(_, _, kw)] = api.sent("PUT")
    assert kw["json"] == {"firstName": "Sara", "phone": "555"}


PIPELINES = {"pipelines": [{"id": "P1", "name": "Sales", "stages": [{"id": "s1", "name": "New Lead"}, {"id": "s2", "name": "Booked"}]}]}


@pytest.mark.asyncio
@pytest.mark.parametrize("stage, expected", [(None, "s1"), ("booked", "s2"), ("s2", "s2")])
async def test_ghl_opportunity_stage_by_name_or_first(db, api, stage, expected):
    api.on("GET", "/v1/pipelines/", PIPELINES)
    api.on("POST", "/v1/pipelines/opportunities", {"id": "o1", "title": "Quote"})
    connection = await connect(db, "gohighlevel", defaults={"pipeline_id": "P1"})
    params = {"title": "Quote", "contact_id": "g1", **({"stage": stage} if stage else {})}
    await run(db, connection, "create_opportunity", params, source=SOURCE_WORKFLOW)
    [(_, _, kw)] = api.sent("POST")
    assert kw["json"]["pipelineStageId"] == expected and kw["json"]["pipelineId"] == "P1"


@pytest.mark.asyncio
async def test_ghl_unknown_stage_lists_the_real_ones(db, api):
    api.on("GET", "/v1/pipelines/", PIPELINES)
    connection = await connect(db, "gohighlevel", defaults={"pipeline_id": "P1"})
    with pytest.raises(ConnectorError, match="Stages: New Lead, Booked"):
        await run(db, connection, "create_opportunity", {"title": "Quote", "stage": "Won"})


# ---- Stripe -------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stripe_find_customer_and_list_subscriptions(db, api):
    api.on("GET", "/v1/customers", {"data": [{"id": "cus_1", "email": "a@b.co", "name": "Sara"}]})
    api.on("GET", "/v1/subscriptions", {"data": [{"id": "sub_1", "status": "active", "items": {"data": [{"price": {"id": "price_1", "unit_amount": 900, "recurring": {"interval": "month"}}}]}}]})
    connection = await connect(db, "stripe")
    found = await run(db, connection, "find_customers", {"email": "a@b.co"})
    assert found["customers"][0]["id"] == "cus_1"
    subs = await run(db, connection, "list_subscriptions", {"customer_id": "cus_1"})
    assert subs["subscriptions"][0]["plans"][0] == {"price": "price_1", "product": None, "amount": 900, "interval": "month"}


@pytest.mark.asyncio
async def test_stripe_cancel_defaults_to_the_end_of_the_paid_period(db, api):
    api.on("GET", "/v1/subscriptions/sub_1", {"id": "sub_1", "status": "active"})
    api.on("POST", "/v1/subscriptions/sub_1", {"id": "sub_1", "status": "active", "cancel_at_period_end": True})
    connection = await connect(db, "stripe")
    result = await run(db, connection, "cancel_subscription", {"subscription_id": "sub_1", "confirmed": True}, allow_delete=True)
    assert result["cancel_at_period_end"] is True
    [(_, _, kw)] = api.sent("POST")
    assert kw["data"] == {"cancel_at_period_end": "true"}
    assert api.sent("DELETE") == []
    [change] = await audit(db)
    assert change.before["status"] == "active"


@pytest.mark.asyncio
async def test_stripe_cancel_immediately_when_asked(db, api):
    api.on("DELETE", "/v1/subscriptions/sub_1", {"id": "sub_1", "status": "canceled"})
    connection = await connect(db, "stripe")
    await run(db, connection, "cancel_subscription", {"subscription_id": "sub_1", "immediately": True, "confirmed": True}, allow_delete=True)
    assert api.sent("DELETE", "/v1/subscriptions/sub_1")


# Stripe takes form bodies with nested values in brackets. They used to go out
# as a Python dict's repr, which Stripe rejects as "Invalid object", so no
# payment intent was ever created.


def test_stripe_bodies_go_out_in_brackets_on_the_wire():
    import httpx

    from app.services.integrations.connectors.stripe_connector import _form

    body = httpx.Request("POST", "https://api.stripe.com/v1/x", data=_form({
        "amount": 4500,
        "automatic_payment_methods": {"enabled": True},
        "items": [{"price": "price_1", "quantity": 1}],
        "metadata": {"call": "c1"},
        "description": None,
    })).content.decode()
    assert body == (
        "amount=4500&automatic_payment_methods%5Benabled%5D=true"
        "&items%5B0%5D%5Bprice%5D=price_1&items%5B0%5D%5Bquantity%5D=1&metadata%5Bcall%5D=c1"
    )


@pytest.mark.asyncio
async def test_stripe_payment_intent_is_accepted_and_not_reported_as_paid(db, api):
    api.on("POST", "/v1/payment_intents", {"id": "pi_1", "amount": 4500, "currency": "usd", "status": "requires_payment_method"})
    connection = await connect(db, "stripe")
    result = await run(db, connection, "create_payment_intent", {"amount": 4500, "customer": "cus_1"})
    [(_, _, kw)] = api.sent("POST")
    assert kw["data"] == {"amount": 4500, "currency": "usd", "customer": "cus_1",
                          "automatic_payment_methods[enabled]": "true"}
    assert "No money has been taken" in result["message"]


@pytest.mark.asyncio
async def test_stripe_subscription_items_are_sent_as_a_list(db, api):
    api.on("POST", "/v1/subscriptions", {"id": "sub_1", "status": "active"})
    connection = await connect(db, "stripe")
    await run(db, connection, "create_subscription", {"customer": "cus_1", "items": [{"price": "price_1"}]})
    [(_, _, kw)] = api.sent("POST")
    assert kw["data"] == {"customer": "cus_1", "items[0][price]": "price_1"}


@pytest.mark.asyncio
async def test_stripe_payment_link_takes_one_payment_and_returns_the_url(db, api):
    api.on("POST", "/v1/prices", {"id": "price_9"})
    api.on("POST", "/v1/payment_links", {"id": "plink_1", "url": "https://buy.stripe.com/test_abc"})
    connection = await connect(db, "stripe")
    result = await run(db, connection, "create_payment_link", {
        "amount": 4500, "description": "Studio deposit", "email": "sara+1@example.com",
    })
    price, link = api.sent("POST")
    assert price[2]["data"] == {"unit_amount": 4500, "currency": "usd", "product_data[name]": "Studio deposit"}
    assert link[2]["data"] == {"line_items[0][price]": "price_9", "line_items[0][quantity]": 1,
                               "restrictions[completed_sessions][limit]": 1}
    assert result["url"] == "https://buy.stripe.com/test_abc?prefilled_email=sara%2B1%40example.com"
    assert result["amount"] == 4500


@pytest.mark.asyncio
async def test_stripe_invoice_is_emailed_to_a_new_customer(db, api):
    api.on("GET", "/v1/customers", {"data": []})
    api.on("POST", "/v1/customers", {"id": "cus_new", "email": "sara@example.com"})
    api.on("POST", "/v1/invoices", {"id": "in_1", "status": "draft"})
    api.on("POST", "/v1/invoices/in_1/send", {
        "id": "in_1", "number": "A-0001", "status": "open", "amount_due": 4500, "currency": "usd",
        "customer_email": "sara@example.com", "hosted_invoice_url": "https://invoice.stripe.com/i/1",
    })
    connection = await connect(db, "stripe")
    result = await run(db, connection, "send_invoice", {
        "amount": 4500, "description": "Studio deposit", "email": "sara@example.com", "name": "Sara",
    })
    assert [c[1] for c in api.sent("POST")] == [
        "/v1/customers", "/v1/invoices", "/v1/invoiceitems", "/v1/invoices/in_1/finalize", "/v1/invoices/in_1/send",
    ]
    invoice = api.sent("POST", "/v1/invoices")[0][2]["data"]
    assert invoice["customer"] == "cus_new" and invoice["collection_method"] == "send_invoice"
    assert invoice["days_until_due"] == 7 and invoice["pending_invoice_items_behavior"] == "exclude"
    assert api.sent("POST", "/v1/invoiceitems")[0][2]["data"] == {
        "customer": "cus_new", "invoice": "in_1", "amount": 4500, "currency": "usd", "description": "Studio deposit",
    }
    assert result["status"] == "open" and result["sent_to"] == "sara@example.com"
    assert result["hosted_invoice_url"] == "https://invoice.stripe.com/i/1"


@pytest.mark.asyncio
async def test_stripe_invoice_reuses_the_customer_with_that_email(db, api):
    api.on("GET", "/v1/customers", {"data": [{"id": "cus_1", "email": "sara@example.com"}]})
    api.on("POST", "/v1/invoices", {"id": "in_1"})
    api.on("POST", "/v1/invoices/in_1/send", {"id": "in_1", "status": "open"})
    connection = await connect(db, "stripe")
    result = await run(db, connection, "send_invoice", {"amount": 4500, "description": "Deposit", "email": "sara@example.com"})
    assert api.sent("POST", "/v1/customers") == []
    assert result["customer"] == "cus_1"


@pytest.mark.asyncio
async def test_stripe_invoice_that_fails_leaves_no_draft_and_gives_stripes_reason(db, api):
    api.on("POST", "/v1/invoices", {"id": "in_1"})
    api.on("POST", "/v1/invoiceitems", ConnectorError(
        'Request failed: HTTP 400: {"error": {"message": "Amount must be at least $0.50 usd", "type": "invalid_request_error"}}'
    ))
    connection = await connect(db, "stripe")
    with pytest.raises(ConnectorError) as failure:
        await run(db, connection, "send_invoice", {"amount": 10, "description": "Deposit", "customer_id": "cus_1"})
    assert str(failure.value) == "Failed to send invoice: Amount must be at least $0.50 usd"
    assert api.sent("DELETE", "/v1/invoices/in_1")
    assert api.sent("POST", "/v1/invoices/in_1/send") == []


@pytest.mark.asyncio
@pytest.mark.parametrize("action, params", [
    ("send_invoice", {"amount": 45.5, "description": "Deposit", "email": "a@b.co"}),
    ("send_invoice", {"amount": 4500, "description": "Deposit"}),
    ("create_payment_link", {"amount": 0, "description": "Deposit"}),
])
async def test_stripe_payment_requests_are_checked_before_anything_is_sent(db, api, action, params):
    connection = await connect(db, "stripe")
    with pytest.raises((ConnectorError, IntegrationActionError)):
        await run(db, connection, action, params)
    assert api.calls == []
