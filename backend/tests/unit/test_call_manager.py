"""
Unit tests for CallManager, CallSession and the audio buffer.

`CallSession` writes to `calls` and `call_logs` from inside broad
`try/except` blocks that log and roll back. That means a column-name mismatch
does not crash the call — it silently discards the write, and the damage only
shows up later as an unbilled call or an empty log. Several of the tests below
therefore assert on the *database row* after the fact rather than on a return
value, since a return value would look fine either way.

No STT/LLM/TTS providers are contacted: the session is driven directly.
"""
import uuid
from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from app.models.call import Call, CallLog
from app.services.voice.audio_utils import AudioBuffer, AudioStream
from app.services.voice.call_manager import (
    CallManager,
    CallSession,
    CallState,
    get_call_manager,
)
from app.services.voice.providers.base import AudioChunk


class FakeWebSocket:
    """Records what the session sends, instead of talking to a socket."""

    def __init__(self):
        self.sent_json = []
        self.sent_bytes = []

    async def send_json(self, payload):
        self.sent_json.append(payload)

    async def send_bytes(self, data):
        self.sent_bytes.append(data)

    async def receive(self):
        return {"type": "websocket.disconnect"}

    async def close(self, code=1000):
        self.closed_with = code


def _chunk(data=b"\x00\x01" * 80, sample_rate=8000):
    return AudioChunk(data=data, sample_rate=sample_rate)


async def _make_call_row(db, agent, *, call_id=None, status="initiated"):
    """Insert the `calls` row a live session would already have."""
    call = Call(
        id=call_id or uuid.uuid4(),
        user_id=agent.user_id,
        organization_id=agent.organization_id,
        agent_id=agent.id,
        from_number="+15551234567",
        to_number="+15559876543",
        direction="inbound",
        status=status,
        started_at=datetime.utcnow(),
    )
    db.add(call)
    await db.commit()
    return call


def _session(db, agent, call_id, websocket=None):
    return CallSession(
        call_id=call_id,
        agent_id=agent.id,
        phone_number="+15551234567",
        websocket=websocket or FakeWebSocket(),
        db=db,
    )


@pytest.mark.unit
@pytest.mark.calls
class TestCallSessionSetup:
    async def test_session_starts_in_the_initiated_state(self, db_session, test_agent):
        session = _session(db_session, test_agent, uuid.uuid4())

        assert session.state == CallState.INITIATED
        assert session.agent is None
        assert session.organization_id is None

    async def test_initialize_loads_the_agent_and_its_workspace(
        self, db_session, test_agent
    ):
        """`organization_id` is what usage tracking bills against."""
        call = await _make_call_row(db_session, test_agent)
        session = _session(db_session, test_agent, call.id)

        await session.initialize()

        assert session.agent.id == test_agent.id
        assert session.organization_id == test_agent.organization_id

    async def test_initialize_answers_the_call(self, db_session, test_agent):
        call = await _make_call_row(db_session, test_agent)
        session = _session(db_session, test_agent, call.id)

        await session.initialize()

        assert session.state == CallState.ANSWERED

    async def test_initialize_sends_the_agents_greeting(self, db_session, test_agent):
        call = await _make_call_row(db_session, test_agent)
        websocket = FakeWebSocket()
        session = _session(db_session, test_agent, call.id, websocket)

        await session.initialize()

        greetings = [m for m in websocket.sent_json if m.get("type") == "agent_message"]
        assert greetings and greetings[0]["text"] == test_agent.first_message

    async def test_unknown_agent_is_refused(self, db_session, test_agent):
        """A call for an agent that no longer exists must not open a session."""
        call = await _make_call_row(db_session, test_agent)
        session = CallSession(
            call_id=call.id,
            agent_id=uuid.uuid4(),
            phone_number="+15551234567",
            websocket=FakeWebSocket(),
            db=db_session,
        )

        with pytest.raises(ValueError, match="Agent not found"):
            await session.initialize()


@pytest.mark.unit
@pytest.mark.calls
class TestCallStatePersistence:
    async def test_state_change_is_written_to_the_call_row(
        self, db_session, test_agent
    ):
        call = await _make_call_row(db_session, test_agent)
        session = _session(db_session, test_agent, call.id)

        await session._update_call_state(CallState.IN_PROGRESS)

        await db_session.refresh(call)
        assert call.status == CallState.IN_PROGRESS.value

    async def test_completion_records_end_time_and_duration(
        self, db_session, test_agent
    ):
        """
        Regression: this wrote `end_time`/`duration`, which are not columns on
        `Call`. The AttributeError was swallowed and rolled back, so completed
        calls kept their old status and never stored a duration — and billing,
        which reads that duration, metered nothing.
        """
        call = await _make_call_row(db_session, test_agent)
        session = _session(db_session, test_agent, call.id)
        session.start_time = datetime.utcnow() - timedelta(seconds=90)

        await session._update_call_state(CallState.COMPLETED)

        await db_session.refresh(call)
        assert call.status == CallState.COMPLETED.value
        assert call.ended_at is not None
        assert 85 <= call.duration_seconds <= 95

    async def test_state_change_for_an_unknown_call_is_survivable(
        self, db_session, test_agent
    ):
        """A missing row must not take the live call down with it."""
        session = _session(db_session, test_agent, uuid.uuid4())

        await session._update_call_state(CallState.IN_PROGRESS)

        assert session.state == CallState.IN_PROGRESS


@pytest.mark.unit
@pytest.mark.calls
class TestCallEventLogging:
    async def test_event_is_written_to_the_call_log(self, db_session, test_agent):
        """
        Regression: the log entry was built with `event_type=`/`metadata=`,
        neither of which is a column, so every event raised TypeError and was
        swallowed — `call_logs` stayed empty for every call.
        """
        call = await _make_call_row(db_session, test_agent)
        session = _session(db_session, test_agent, call.id)

        await session._log_event("transcription_final", {"text": "hello there"})

        rows = (
            await db_session.execute(
                select(CallLog).where(CallLog.call_id == call.id)
            )
        ).scalars().all()

        assert len(rows) == 1
        assert rows[0].log_type == "transcription_final"
        assert rows[0].details["text"] == "hello there"

    async def test_error_events_are_recorded_at_error_severity(
        self, db_session, test_agent
    ):
        """Severity is what makes a failing call findable in the log table."""
        call = await _make_call_row(db_session, test_agent)
        session = _session(db_session, test_agent, call.id)

        await session._log_event("llm_error", {"error": "provider timed out"})

        row = (
            await db_session.execute(
                select(CallLog).where(CallLog.call_id == call.id)
            )
        ).scalar_one()

        assert row.severity == "error"
        assert row.message == "provider timed out"


@pytest.mark.unit
@pytest.mark.calls
class TestTranscript:
    async def test_transcript_accumulates_in_order(self, db_session, test_agent):
        call = await _make_call_row(db_session, test_agent)
        session = _session(db_session, test_agent, call.id)

        session.transcript.append("Hello, how can I help you?")
        session.transcript.append("I need help with my order.")

        assert len(session.transcript) == 2
        assert "my order" in session.transcript[1]


@pytest.mark.unit
@pytest.mark.calls
class TestAudioBuffer:
    async def test_chunks_come_back_in_order(self):
        buffer = AudioBuffer(max_size=10)

        await buffer.put(_chunk(b"first" * 32))
        await buffer.put(_chunk(b"second" * 32))

        assert (await buffer.get()).data == b"first" * 32
        assert (await buffer.get()).data == b"second" * 32

    async def test_size_tracks_pending_chunks(self):
        buffer = AudioBuffer(max_size=10)
        assert buffer.is_empty() is True

        await buffer.put(_chunk())

        assert buffer.size() == 1
        assert buffer.is_empty() is False

    async def test_duration_is_derived_from_the_sample_rate(self):
        """16-bit mono: bytes / (sample_rate * 2) seconds."""
        buffer = AudioBuffer(max_size=10)

        await buffer.put(_chunk(data=b"\x00" * 16000, sample_rate=8000))

        assert buffer.duration() == pytest.approx(1.0)

    async def test_buffer_drops_the_oldest_chunk_when_full(self):
        """
        Bounded on purpose: a caller who never drains the buffer must not grow it
        without limit. Dropping the oldest audio is the accepted trade.
        """
        buffer = AudioBuffer(max_size=2)

        for marker in (b"a", b"b", b"c"):
            await buffer.put(_chunk(marker * 32))

        assert buffer.size() == 2
        assert (await buffer.get()).data == b"b" * 32

    async def test_get_all_drains_the_buffer(self):
        buffer = AudioBuffer(max_size=10)
        await buffer.put(_chunk())
        await buffer.put(_chunk())

        assert len(await buffer.get_all()) == 2
        assert buffer.is_empty() is True

    async def test_closed_buffer_refuses_new_audio(self):
        buffer = AudioBuffer(max_size=10)
        await buffer.close()

        assert buffer.is_closed() is True
        with pytest.raises(ValueError):
            await buffer.put(_chunk())

    async def test_get_returns_none_once_closed_and_drained(self):
        """This is the signal that ends the consumer loop — without it it hangs."""
        buffer = AudioBuffer(max_size=10)
        await buffer.put(_chunk())
        await buffer.close()

        assert await buffer.get() is not None
        assert await buffer.get() is None

    async def test_stream_iterates_until_the_buffer_closes(self):
        buffer = AudioBuffer(max_size=10)
        await buffer.put(_chunk(b"x" * 32))
        await buffer.put(_chunk(b"y" * 32))
        await buffer.close()

        received = [chunk.data async for chunk in AudioStream(buffer)]

        assert received == [b"x" * 32, b"y" * 32]


@pytest.mark.unit
@pytest.mark.calls
class TestCallManager:
    async def test_create_call_registers_an_active_session(
        self, db_session, test_agent
    ):
        manager = CallManager()

        session = await manager.create_call(
            agent_id=test_agent.id,
            phone_number="+15551234567",
            websocket=FakeWebSocket(),
            db=db_session,
        )

        assert await manager.get_active_calls_count() == 1
        assert await manager.get_call(session.call_id) is session

    async def test_create_call_writes_a_call_row(self, db_session, test_agent):
        """
        Regression: the row was built with `start_time=`, which is not a column,
        and without the NOT NULL `user_id`/`organization_id` — so the websocket
        call path never produced a call record at all.
        """
        manager = CallManager()

        session = await manager.create_call(
            agent_id=test_agent.id,
            phone_number="+15551234567",
            websocket=FakeWebSocket(),
            db=db_session,
        )

        call = (
            await db_session.execute(select(Call).where(Call.id == session.call_id))
        ).scalar_one()

        assert call.user_id == test_agent.user_id
        assert call.organization_id == test_agent.organization_id
        assert call.agent_id == test_agent.id
        assert call.direction == "inbound"
        assert call.status == CallState.INITIATED.value
        assert call.started_at is not None

    async def test_create_call_refuses_an_unknown_agent(self, db_session):
        manager = CallManager()

        with pytest.raises(ValueError, match="Agent not found"):
            await manager.create_call(
                agent_id=uuid.uuid4(),
                phone_number="+15551234567",
                websocket=FakeWebSocket(),
                db=db_session,
            )

    async def test_each_call_gets_its_own_id(self, db_session, test_agent):
        manager = CallManager()

        first = await manager.create_call(
            agent_id=test_agent.id,
            phone_number="+15551234567",
            websocket=FakeWebSocket(),
            db=db_session,
        )
        second = await manager.create_call(
            agent_id=test_agent.id,
            phone_number="+15559999999",
            websocket=FakeWebSocket(),
            db=db_session,
        )

        assert first.call_id != second.call_id
        assert await manager.get_active_calls_count() == 2

    async def test_unknown_call_id_returns_none(self):
        assert await CallManager().get_call(uuid.uuid4()) is None

    async def test_remove_call_frees_the_slot(self, db_session, test_agent):
        manager = CallManager()
        session = await manager.create_call(
            agent_id=test_agent.id,
            phone_number="+15551234567",
            websocket=FakeWebSocket(),
            db=db_session,
        )

        await manager.remove_call(session.call_id)

        assert await manager.get_active_calls_count() == 0
        assert await manager.get_call(session.call_id) is None

    async def test_removing_an_unknown_call_is_a_no_op(self):
        """Cleanup paths call this twice; the second must not raise."""
        manager = CallManager()

        await manager.remove_call(uuid.uuid4())

        assert await manager.get_active_calls_count() == 0

    async def test_cleanup_all_empties_the_registry(self, db_session, test_agent):
        manager = CallManager()
        await manager.create_call(
            agent_id=test_agent.id,
            phone_number="+15551234567",
            websocket=FakeWebSocket(),
            db=db_session,
        )

        await manager.cleanup_all()

        assert await manager.get_active_calls_count() == 0

    def test_get_call_manager_is_a_singleton(self):
        """One process-wide registry, or a call would be invisible to its owner."""
        assert get_call_manager() is get_call_manager()


@pytest.mark.unit
@pytest.mark.calls
class TestSessionCleanup:
    async def test_cleanup_closes_the_audio_buffer(self, db_session, test_agent):
        call = await _make_call_row(db_session, test_agent)
        session = _session(db_session, test_agent, call.id)

        await session.cleanup()

        assert session.audio_buffer.is_closed() is True

    async def test_cleanup_completes_a_call_still_in_progress(
        self, db_session, test_agent
    ):
        call = await _make_call_row(db_session, test_agent)
        session = _session(db_session, test_agent, call.id)
        session.state = CallState.IN_PROGRESS

        await session.cleanup()

        await db_session.refresh(call)
        assert call.status == CallState.COMPLETED.value

    @pytest.mark.parametrize(
        "terminal", [CallState.COMPLETED, CallState.FAILED, CallState.CANCELLED]
    )
    async def test_cleanup_leaves_an_already_finished_call_alone(
        self, db_session, test_agent, terminal
    ):
        """A failed call must not be rewritten as a successful one on teardown."""
        call = await _make_call_row(db_session, test_agent, status=terminal.value)
        session = _session(db_session, test_agent, call.id)
        session.state = terminal

        await session.cleanup()

        await db_session.refresh(call)
        assert call.status == terminal.value
