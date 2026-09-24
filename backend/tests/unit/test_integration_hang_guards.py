"""
Guards against integration actions that hang instead of failing.

Reported as "the Google Sheets connector hangs" (2026-09-24): append_row on a
fake spreadsheet never returned while Calendar answered in seconds. The request
to Google had already failed; the hang was the bookkeeping UPDATE on the
connection's row, waiting behind another transaction that held it. These tests
pin the fixes: bookkeeping runs on its own session and cannot block, the rate
limiter cannot deadlock on itself, writes are not silently repeated after a
timeout, and every action has an overall time limit.
"""
import asyncio
import time
import uuid

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models.integration import IntegrationConnection, IntegrationConnector
from app.services.integrations import action_runner
from app.services.integrations.http_client import (
    HTTPRequestError,
    IntegrationHTTPClient,
    RateLimiter,
    RetryConfig,
)

pytestmark = pytest.mark.asyncio


# ---- Rate limiter ---------------------------------------------------------------


async def test_rate_limiter_waits_instead_of_deadlocking():
    limiter = RateLimiter(requests_per_minute=1)
    limiter.limits["minute"]["window"] = 0.3  # a 0.3 s "minute"
    await limiter.acquire()
    started = time.time()
    # The old code slept while holding its lock and then re-acquired it: hang.
    await asyncio.wait_for(limiter.acquire(), timeout=3)
    assert 0.2 < time.time() - started < 2


# ---- Retries ------------------------------------------------------------------


def client_with(handler):
    client = IntegrationHTTPClient(
        base_url="https://api.example.com",
        retry_config=RetryConfig(max_retries=3, initial_delay=0.01),
    )
    client._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return client


@pytest.mark.parametrize("method", ["POST", "PATCH"])
async def test_writes_are_not_repeated_after_a_timeout(method):
    calls = []

    def handler(request):
        calls.append(request)
        raise httpx.ReadTimeout("slow", request=request)

    with pytest.raises(HTTPRequestError, match="may or may not have been applied"):
        await client_with(handler).request(method, "/rows", json={"values": [["a"]]})
    assert len(calls) == 1  # a second attempt would append a duplicate row


async def test_writes_are_not_repeated_after_a_server_error():
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(503, text="busy")

    with pytest.raises(HTTPRequestError, match="HTTP 503"):
        await client_with(handler).request("POST", "/rows", json={})
    assert len(calls) == 1


async def test_writes_are_retried_on_429_and_reads_on_503():
    for method, status in (("POST", 429), ("GET", 503)):
        calls = []

        def handler(request, calls=calls, status=status):
            calls.append(request)
            return httpx.Response(status if len(calls) == 1 else 200, json={"ok": True})

        assert await client_with(handler).request(method, "/x") == {"ok": True}
        assert len(calls) == 2


async def test_a_write_that_never_connected_is_retried():
    calls = []

    def handler(request):
        calls.append(request)
        if len(calls) == 1:
            raise httpx.ConnectError("refused", request=request)
        return httpx.Response(200, json={"ok": True})

    assert await client_with(handler).request("POST", "/rows", json={}) == {"ok": True}


# ---- Overall action time limit ------------------------------------------------


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


async def sheets_connection(db):
    connector = IntegrationConnector(id=uuid.uuid4(), name="Google Sheets", slug="google-sheets",
                                     auth_type="oauth2", base_url="https://sheets.googleapis.com")
    connection = IntegrationConnection(id=uuid.uuid4(), user_id=uuid.uuid4(), organization_id=uuid.uuid4(),
                                       connector_id=connector.id, config={}, error_count=0)
    db.add_all([connector, connection])
    await db.commit()
    return connection


async def test_an_action_that_never_returns_is_stopped(db, monkeypatch):
    from app.services.integrations.connectors.google_sheets_connector import GoogleSheetsConnector

    async def never(self, *args, **kwargs):
        await asyncio.sleep(3600)

    monkeypatch.setattr(GoogleSheetsConnector, "append_row", never)
    monkeypatch.setattr(action_runner, "ACTION_TIMEOUT_SECONDS", 0.3)
    connection = await sheets_connection(db)
    started = time.time()
    with pytest.raises(action_runner.IntegrationActionError, match="took longer than .* check the app"):
        await action_runner.run_integration_action(
            db, organization_id=connection.organization_id, connection_id=connection.id,
            action="append_row", parameters={"spreadsheet_id": "S", "range_name": "A1", "values": [["a"]]},
            source=action_runner.SOURCE_WORKFLOW,
        )
    assert time.time() - started < 3


# ---- Bookkeeping ----------------------------------------------------------------


async def test_bookkeeping_is_saved_without_dirtying_the_callers_session(db):
    from app.services.integrations.connectors.google_sheets_connector import GoogleSheetsConnector

    connection = await sheets_connection(db)
    connector = await db.get(IntegrationConnector, connection.connector_id)
    instance = GoogleSheetsConnector(connection=connection, connector=connector, db=db)
    await instance._record_connection_state(error_count=3, last_error="HTTP 404")

    # The caller's copy shows the new values but has nothing pending, so the
    # caller's next commit does not write (and wait on) that row again.
    assert connection.error_count == 3
    assert connection not in db.dirty
    fresh = (await db.execute(
        select(IntegrationConnection.error_count, IntegrationConnection.last_error)
        .where(IntegrationConnection.id == connection.id)
        .execution_options(populate_existing=True)
    )).one()
    assert tuple(fresh) == (3, "HTTP 404")


async def test_bookkeeping_that_cannot_finish_is_skipped(db, monkeypatch):
    from app.services.integrations import connector_base
    from app.services.integrations.connectors.google_sheets_connector import GoogleSheetsConnector

    connection = await sheets_connection(db)
    connector = await db.get(IntegrationConnector, connection.connector_id)
    instance = GoogleSheetsConnector(connection=connection, connector=connector, db=db)
    monkeypatch.setattr(connector_base, "BOOKKEEPING_TIMEOUT", 0.2)

    async def stuck(side):  # stands in for an UPDATE waiting on a locked row
        await asyncio.sleep(3600)

    started = time.time()
    await instance._bookkeeping(stuck, what="record connection use")
    assert time.time() - started < 2


# ---- Connection checks found broken on the live app (2026-09-24) ------------------


async def test_sheets_test_uses_the_sheets_api_not_userinfo(monkeypatch):
    """Sheets connects with only the spreadsheets scope, so userinfo always
    401'd and the Test button failed while real actions worked."""
    from app.services.integrations.connector_base import BaseConnector, ConnectorError
    from app.services.integrations.connectors.google_sheets_connector import GoogleSheetsConnector

    seen = []

    async def fake(self, method, endpoint, **kw):
        seen.append(endpoint)
        raise ConnectorError('Request failed: HTTP 404: {"error": {"status": "NOT_FOUND"}}')

    monkeypatch.setattr(BaseConnector, "make_request", fake)
    connector = IntegrationConnector(name="Google Sheets", slug="google-sheets", auth_type="oauth2",
                                     base_url="https://sheets.googleapis.com")
    instance = GoogleSheetsConnector(connection=IntegrationConnection(config={}), connector=connector, db=None)
    result = await instance.test_connection()
    assert result["success"] is True
    assert seen == ["/v4/spreadsheets/voicecon-connection-check"]

    async def unauthorised(self, method, endpoint, **kw):
        raise ConnectorError("Request failed: HTTP 401: UNAUTHENTICATED")

    monkeypatch.setattr(BaseConnector, "make_request", unauthorised)
    assert (await instance.test_connection())["success"] is False


def test_salesforce_instance_url_is_kept_from_the_token_response():
    from app.services.integrations.integration_manager import _with_instance_url

    assert _with_instance_url({"defaults": {"x": 1}}, {"instance_url": "https://acme.my.salesforce.com/"}) == {
        "defaults": {"x": 1}, "base_url": "https://acme.my.salesforce.com",
    }
    assert _with_instance_url(None, {"access_token": "t"}) == {}


async def test_salesforce_without_a_saved_host_finds_and_saves_it(db, monkeypatch):
    """The connector row's api.salesforce.com is not an API host: every call 404'd."""
    from app.services.integrations.connector_base import BaseConnector
    from app.services.integrations.connectors.salesforce_connector import SalesforceConnector

    calls = []

    async def fake(self, method, endpoint, **kw):
        calls.append((self.http_client.base_url, endpoint))
        if endpoint.endswith("/services/oauth2/userinfo") and endpoint.startswith("https://login."):
            return {"urls": {"custom_domain": "https://acme.my.salesforce.com",
                             "rest": "https://acme.my.salesforce.com/services/data/v{version}/"}}
        return {"records": []}

    monkeypatch.setattr(BaseConnector, "make_request", fake)
    connector = IntegrationConnector(id=uuid.uuid4(), name="Salesforce", slug="salesforce",
                                     auth_type="oauth2", base_url="https://api.salesforce.com")
    connection = IntegrationConnection(id=uuid.uuid4(), user_id=uuid.uuid4(), organization_id=uuid.uuid4(),
                                       connector_id=connector.id, config={"defaults": {}}, error_count=0)
    db.add_all([connector, connection])
    await db.commit()

    instance = SalesforceConnector(connection=connection, connector=connector, db=db)
    await instance.search_leads(query="Acme")
    await instance.search_leads(query="Acme")  # second call: no second lookup

    assert [c[1] for c in calls].count("https://login.salesforce.com/services/oauth2/userinfo") == 1
    assert calls[-1][0] == "https://acme.my.salesforce.com"
    saved = (await db.execute(
        select(IntegrationConnection.config).where(IntegrationConnection.id == connection.id)
        .execution_options(populate_existing=True)
    )).scalar_one()
    assert saved == {"defaults": {}, "base_url": "https://acme.my.salesforce.com"}
