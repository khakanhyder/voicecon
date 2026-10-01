"""
"Active calls" on the Analytics page.

An inbound call sat at ``ringing`` for its whole length — Twilio sends an
inbound number no "answered" callback — so the live count stayed at 0 while
someone was talking to the agent. The media stream starting is what marks a
call live now, and these follow a call through its life to check the count at
each point.
"""
import uuid
from datetime import datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.api.v1.endpoints.telephony import advance_call_status
from app.database import Base
from app.models.call import Call
from app.models.user import Organization, OrganizationMember, User
from app.services.analytics.analytics_service import AnalyticsService
from app.services.websocket.voice_session import VoiceSession


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
        direction="inbound",
        from_number="+12896950151",
        to_number="+14155550100",
        **{"status": "ringing", **fields},
    )
    db.add(call)
    await db.commit()
    return call


async def _stream_starts(db, call: Call) -> None:
    """Twilio's media stream sends its ``start`` event: audio is flowing."""
    session = object.__new__(VoiceSession)
    session.call, session.db, session.call_id = call, db, str(call.id)
    session.stream_sid = session.call_sid = None
    session._welcome_sent = True
    session._silence_task = session._max_duration_task = object()

    async def _no_stt():
        return None

    session._start_deepgram = _no_stt
    sid = uuid.uuid4().hex
    await session._handle_start({"start": {"streamSid": f"MZ{sid}", "callSid": f"CA{sid}"}})


async def _active(db, org: Organization) -> int:
    return (await AnalyticsService(db).update_realtime_metrics(org.id)).current_active_calls


@pytest.mark.asyncio
async def test_an_inbound_call_counts_as_active_from_answer_to_hangup(db):
    org = await _organization(db)
    call = await _call(db, org)  # the answer webhook: carrier says "ringing"
    assert await _active(db, org) == 0

    await _stream_starts(db, call)
    assert call.status == "in_progress"
    assert call.answered_at is not None and call.provider_call_sid.startswith("CA")
    assert await _active(db, org) == 1

    # The caller hangs up: the session's cleanup closes the call.
    call.status, call.ended_at = "completed", datetime.utcnow()
    await db.commit()
    assert await _active(db, org) == 0


@pytest.mark.asyncio
async def test_two_calls_at_once_count_as_two_and_other_workspaces_are_not_counted(db):
    org, other = await _organization(db), await _organization(db)
    for _ in range(2):
        await _stream_starts(db, await _call(db, org))
    await _stream_starts(db, await _call(db, other))
    assert await _active(db, org) == 2
    assert await _active(db, other) == 1


@pytest.mark.asyncio
async def test_a_call_stuck_in_progress_does_not_count_forever(db):
    """Its final callback never arrived. Without a cut-off it showed as a live
    call on the dashboard for months."""
    org = await _organization(db)
    await _call(db, org, status="in_progress", created_at=datetime.utcnow() - timedelta(days=3))
    assert await _active(db, org) == 0


@pytest.mark.asyncio
async def test_every_refresh_is_stamped(db):
    org = await _organization(db)
    first = (await AnalyticsService(db).update_realtime_metrics(org.id)).last_updated
    second = (await AnalyticsService(db).update_realtime_metrics(org.id)).last_updated
    # SQLite hands the value back without its timezone; it is UTC either way.
    now = datetime.now(second.tzinfo) if second.tzinfo else datetime.utcnow()
    assert second >= first and (now - second) < timedelta(seconds=5)


class TestCarrierCallbacksCannotMoveACallBackwards:
    def _call(self, status):
        return Call(status=status)

    @pytest.mark.parametrize("late", ["initiated", "ringing"])
    def test_a_late_ringing_does_not_undo_a_live_call(self, late):
        call = self._call("in_progress")
        advance_call_status(call, late)
        assert call.status == "in_progress"

    @pytest.mark.parametrize("late", ["initiated", "ringing", "in_progress"])
    def test_a_finished_call_is_not_reopened(self, late):
        call = self._call("completed")
        advance_call_status(call, late)
        assert call.status == "completed"

    def test_a_call_still_moves_forward(self):
        call = self._call("initiated")
        for status in ("ringing", "in_progress", "completed"):
            advance_call_status(call, status)
            assert call.status == status

    def test_no_status_changes_nothing(self):
        call = self._call("ringing")
        advance_call_status(call, None)
        assert call.status == "ringing"
