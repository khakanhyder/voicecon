"""
"Export CSV" on the Calls page.

The button used to do nothing. It now downloads the workspace's call log from
``GET /calls/export``; these check the file against the calls behind it.
"""
import csv
import io
import uuid
from datetime import datetime
from decimal import Decimal

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.dependencies import get_current_org_id, get_current_user
from app.database import Base, get_db
from app.main import app
from app.models.agent import Agent
from app.models.call import Call
from app.models.user import Organization, OrganizationMember, User
from app.services.call.call_export import build_calls_csv


@pytest_asyncio.fixture
async def db():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with async_sessionmaker(engine, expire_on_commit=False)() as session:
        yield session
    await engine.dispose()


async def _organization(db) -> Organization:
    user = User(email=f"o-{uuid.uuid4().hex[:8]}@acme.test", hashed_password="x", is_active=True)
    db.add(user)
    await db.flush()
    org = Organization(name="Acme", slug=f"acme-{uuid.uuid4().hex[:8]}", owner_id=user.id)
    db.add(org)
    await db.flush()
    db.add(OrganizationMember(organization_id=org.id, user_id=user.id, role="owner"))
    await db.commit()
    return org


async def _call(db, org: Organization, **fields) -> Call:
    call = Call(
        user_id=org.owner_id,
        organization_id=org.id,
        **{
            "direction": "inbound",
            "from_number": "+12896950151",
            "to_number": "+13412172798",
            "status": "completed",
            **fields,
        },
    )
    db.add(call)
    await db.commit()
    return call


@pytest_asyncio.fixture
async def export(db):
    """Download the export as a workspace, parsed into header + row dicts."""

    async def _export(org: Organization, **params):
        user = await db.get(User, org.owner_id)

        async def _db():
            yield db

        app.dependency_overrides[get_db] = _db
        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_current_org_id] = lambda: org.id
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                res = await client.get("/api/v1/calls/export", params=params)
        finally:
            app.dependency_overrides.clear()
        assert res.status_code == 200, res.text
        rows = list(csv.DictReader(io.StringIO(res.content.decode("utf-8-sig"))))
        return res, rows

    return _export


@pytest.mark.asyncio
async def test_export_downloads_the_call_log_as_the_page_shows_it(db, export):
    org = await _organization(db)
    agent = Agent(user_id=org.owner_id, organization_id=org.id, name="Diamant Versatile")
    db.add(agent)
    await db.flush()
    call = await _call(
        db, org,
        agent_id=agent.id,
        started_at=datetime(2026, 10, 2, 9, 30, 0),
        duration_seconds=186,
        cost_total=Decimal("0.0261"),
        sentiment_label="neutral",
        call_metadata={"disconnection_reason": "customer_hung_up"},
    )

    res, rows = await export(org, tz="Asia/Karachi")

    assert res.headers["content-type"].startswith("text/csv")
    assert res.headers["content-disposition"].startswith('attachment; filename="calls-')
    assert res.headers["content-disposition"].endswith('.csv"')
    assert rows == [{
        "Call ID": str(call.id),
        "Assistant": "Diamant Versatile",
        "Direction": "Inbound",
        # Inbound: the customer dialled (from), the assistant answered (to).
        "Assistant Phone Number": "+13412172798",
        "Customer Phone Number": "+12896950151",
        "Status": "Completed",
        "End Reason": "Customer hung up",
        "Success Evaluation": "Neutral",
        # Stored as naive UTC; 09:30 UTC is 14:30 in Karachi.
        "Start Time (Asia/Karachi)": "2026-10-02 14:30:00",
        "Duration (seconds)": "186",
        "Cost (USD)": "0.0261",
    }]


@pytest.mark.asyncio
async def test_export_holds_every_call_not_just_the_first_page(db, export):
    org = await _organization(db)
    db.add_all(
        Call(
            user_id=org.owner_id, organization_id=org.id, direction="inbound",
            from_number="+12896950151", to_number="+13412172798", status="completed",
            started_at=datetime(2026, 10, 1, 0, 0, i % 60),
        )
        for i in range(130)
    )
    await db.commit()

    _, rows = await export(org)

    assert len(rows) == 130  # the list endpoint the table uses stops at 100


@pytest.mark.asyncio
async def test_export_applies_the_pages_filters(db, export):
    org = await _organization(db)
    await _call(db, org, status="completed", from_number="+12896950151")
    await _call(db, org, status="failed", from_number="+12896950151")
    await _call(db, org, status="completed", direction="outbound",
                from_number="+13412172798", to_number="+447700900123")

    _, failed = await export(org, status="failed")
    _, british = await export(org, search="4477")
    _, both = await export(org, status="completed", search="289695")
    _, nothing = await export(org, search="000000")

    assert [r["Status"] for r in failed] == ["Failed"]
    assert [r["Customer Phone Number"] for r in british] == ["+447700900123"]
    assert [(r["Status"], r["Customer Phone Number"]) for r in both] == [("Completed", "+12896950151")]
    assert nothing == []


@pytest.mark.asyncio
async def test_export_never_includes_another_workspaces_calls(db, export):
    mine, theirs = await _organization(db), await _organization(db)
    await _call(db, mine, from_number="+12896950151")
    await _call(db, theirs, from_number="+19998887777")

    _, rows = await export(mine)

    assert [r["Customer Phone Number"] for r in rows] == ["+12896950151"]


@pytest.mark.asyncio
async def test_export_orders_newest_first_and_names_a_missing_agent(db, export):
    org = await _organization(db)
    await _call(db, org, started_at=datetime(2026, 10, 1, 8, 0), from_number="+11111111111")
    await _call(db, org, started_at=datetime(2026, 10, 2, 8, 0), from_number="+12222222222")
    await _call(db, org, direction="test", from_number="web", to_number="web",
                started_at=datetime(2026, 9, 30, 8, 0))

    _, rows = await export(org)

    assert [r["Customer Phone Number"] for r in rows] == ["+12222222222", "+11111111111", "Web Test"]
    assert {r["Assistant"] for r in rows} == {"Unknown"}
    assert rows[0]["Start Time (UTC)"] == "2026-10-02 08:00:00"
    assert rows[0]["Duration (seconds)"] == "" and rows[0]["Cost (USD)"] == ""


def _only_row(call: dict, tz=None) -> dict:
    base = {
        "id": uuid.uuid4(), "agent_id": None, "agent_name": "Ava", "direction": "inbound",
        "from_number": "+12896950151", "to_number": "+13412172798", "status": "completed",
        "call_metadata": {}, "sentiment_label": None,
        "started_at": datetime(2026, 10, 2, 9, 30), "created_at": datetime(2026, 10, 2, 9, 29),
        "duration_seconds": 5, "cost_total": Decimal("0.0100"),
    }
    text = build_calls_csv([{**base, **call}], tz).decode("utf-8-sig")
    return next(csv.DictReader(io.StringIO(text)))


def test_a_formula_in_a_name_is_not_run_by_the_spreadsheet():
    row = _only_row({"agent_name": '=HYPERLINK("http://evil.test","Ava")', "from_number": "=1+1"})

    assert row["Assistant"].startswith("'=")
    assert row["Customer Phone Number"] == "'=1+1"
    # An ordinary number keeps its "+" untouched.
    assert row["Assistant Phone Number"] == "+13412172798"


def test_commas_quotes_and_accents_survive_the_round_trip():
    row = _only_row({"agent_name": 'Zoë "Front Desk", Clinic'})

    assert row["Assistant"] == 'Zoë "Front Desk", Clinic'


def test_an_unknown_timezone_falls_back_to_utc():
    row = _only_row({}, tz="Not/AZone")

    assert row["Start Time (UTC)"] == "2026-10-02 09:30:00"
