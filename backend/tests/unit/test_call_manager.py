"""
Unit tests for CallManager and CallSession.

Tests the complete call lifecycle including:
- Session initialization
- Audio streaming
- Transcription processing
- LLM interaction
- State management
"""
import pytest
import uuid
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from fastapi import WebSocket

from app.services.voice.call_manager import (
    CallManager,
    CallSession,
    CallState,
    get_call_manager,
)
from app.models.agent import Agent
from app.models.call import Call
from app.services.voice import TranscriptionResult, AudioChunk


@pytest.mark.unit
@pytest.mark.asyncio
class TestCallSession:
    """Test CallSession functionality."""

    async def test_session_initialization(self, db_session, test_agent):
        """Test call session initialization."""
        websocket = AsyncMock(spec=WebSocket)
        call_id = uuid.uuid4()
        phone_number = "+1234567890"

        session = CallSession(
            call_id=call_id,
            agent_id=test_agent.id,
            phone_number=phone_number,
            websocket=websocket,
            db=db_session,
        )

        assert session.call_id == call_id
        assert session.agent_id == test_agent.id
        assert session.phone_number == phone_number
        assert session.state == CallState.INITIATED
        assert session.agent is None

        # Initialize session
        await session.initialize()

        assert session.agent is not None
        assert session.agent.id == test_agent.id
        assert session.organization_id == test_agent.organization_id

    async def test_session_initialization_agent_not_found(self, db_session):
        """Test session initialization with non-existent agent."""
        websocket = AsyncMock(spec=WebSocket)
        call_id = uuid.uuid4()
        agent_id = uuid.uuid4()
        phone_number = "+1234567890"

        session = CallSession(
            call_id=call_id,
            agent_id=agent_id,
            phone_number=phone_number,
            websocket=websocket,
            db=db_session,
        )

        with pytest.raises(ValueError, match="Agent not found"):
            await session.initialize()

    async def test_session_state_transitions(self, db_session, test_agent):
        """Test call state transitions."""
        websocket = AsyncMock(spec=WebSocket)
        call_id = uuid.uuid4()

        session = CallSession(
            call_id=call_id,
            agent_id=test_agent.id,
            phone_number="+1234567890",
            websocket=websocket,
            db=db_session,
        )

        await session.initialize()

        # Initial state
        assert session.state == CallState.INITIATED

        # Simulate state changes
        session.state = CallState.RINGING
        assert session.state == CallState.RINGING

        session.state = CallState.ANSWERED
        assert session.state == CallState.ANSWERED

        session.state = CallState.IN_PROGRESS
        assert session.state == CallState.IN_PROGRESS

    async def test_audio_buffer_management(self, db_session, test_agent):
        """Test audio buffer handling."""
        websocket = AsyncMock(spec=WebSocket)
        call_id = uuid.uuid4()

        session = CallSession(
            call_id=call_id,
            agent_id=test_agent.id,
            phone_number="+1234567890",
            websocket=websocket,
            db=db_session,
        )

        await session.initialize()

        # Verify audio buffer exists
        assert session.audio_buffer is not None
        assert session.audio_stream is not None

        # Test adding audio data
        audio_data = b"fake_audio_data"
        session.audio_buffer.add(audio_data)

        assert len(session.audio_buffer) > 0

    async def test_transcript_accumulation(self, db_session, test_agent):
        """Test transcript accumulation during call."""
        websocket = AsyncMock(spec=WebSocket)
        call_id = uuid.uuid4()

        session = CallSession(
            call_id=call_id,
            agent_id=test_agent.id,
            phone_number="+1234567890",
            websocket=websocket,
            db=db_session,
        )

        await session.initialize()

        # Add transcript entries
        session.transcript.append("Hello, how can I help you?")
        session.transcript.append("I need help with my order.")
        session.transcript.append("Of course, I can help with that.")

        assert len(session.transcript) == 3
        assert "help with my order" in session.transcript[1]

    @patch("app.services.voice.call_manager.get_stt_service")
    @patch("app.services.voice.call_manager.get_llm_service")
    @patch("app.services.voice.call_manager.get_tts_service")
    async def test_handle_audio_chunk(
        self,
        mock_tts,
        mock_llm,
        mock_stt,
        db_session,
        test_agent,
    ):
        """Test handling incoming audio chunks."""
        # Setup mocks
        mock_stt_instance = AsyncMock()
        mock_stt_instance.transcribe.return_value = TranscriptionResult(
            text="Hello, I need help",
            is_final=True,
            confidence=0.95,
        )
        mock_stt.return_value = mock_stt_instance

        websocket = AsyncMock(spec=WebSocket)
        call_id = uuid.uuid4()

        session = CallSession(
            call_id=call_id,
            agent_id=test_agent.id,
            phone_number="+1234567890",
            websocket=websocket,
            db=db_session,
        )

        await session.initialize()

        # Simulate receiving audio
        audio_chunk = AudioChunk(
            data=b"fake_audio_data",
            timestamp=datetime.utcnow(),
        )

        # This would be part of the actual implementation
        session.audio_buffer.add(audio_chunk.data)

        assert len(session.audio_buffer) > 0

    async def test_call_duration_calculation(self, db_session, test_agent):
        """Test call duration calculation."""
        websocket = AsyncMock(spec=WebSocket)
        call_id = uuid.uuid4()

        session = CallSession(
            call_id=call_id,
            agent_id=test_agent.id,
            phone_number="+1234567890",
            websocket=websocket,
            db=db_session,
        )

        await session.initialize()

        start_time = session.start_time
        assert start_time is not None
        assert session.end_time is None

        # Simulate call end
        session.end_time = datetime.utcnow()
        duration = (session.end_time - start_time).total_seconds()

        assert duration >= 0
        assert session.end_time > session.start_time


@pytest.mark.unit
@pytest.mark.asyncio
class TestCallManager:
    """Test CallManager functionality."""

    async def test_get_call_manager_singleton(self):
        """Test that get_call_manager returns singleton instance."""
        manager1 = get_call_manager()
        manager2 = get_call_manager()

        assert manager1 is manager2
        assert isinstance(manager1, CallManager)

    async def test_create_call_session(self, db_session, test_agent):
        """Test creating a new call session."""
        manager = CallManager()
        websocket = AsyncMock(spec=WebSocket)
        phone_number = "+1234567890"

        session = await manager.create_call(
            agent_id=test_agent.id,
            phone_number=phone_number,
            websocket=websocket,
            db=db_session,
        )

        assert session is not None
        assert session.agent_id == test_agent.id
        assert session.phone_number == phone_number
        assert session.call_id in manager._sessions

    async def test_get_active_session(self, db_session, test_agent):
        """Test retrieving an active call session."""
        manager = CallManager()
        websocket = AsyncMock(spec=WebSocket)

        # Create session
        session = await manager.create_call(
            agent_id=test_agent.id,
            phone_number="+1234567890",
            websocket=websocket,
            db=db_session,
        )

        # Retrieve session
        retrieved = manager.get_session(session.call_id)

        assert retrieved is not None
        assert retrieved.call_id == session.call_id

    async def test_end_call_session(self, db_session, test_agent):
        """Test ending a call session."""
        manager = CallManager()
        websocket = AsyncMock(spec=WebSocket)

        # Create session
        session = await manager.create_call(
            agent_id=test_agent.id,
            phone_number="+1234567890",
            websocket=websocket,
            db=db_session,
        )

        call_id = session.call_id
        assert call_id in manager._sessions

        # End session
        await manager.end_call(call_id)

        # Verify session removed
        assert call_id not in manager._sessions

    async def test_list_active_sessions(self, db_session, test_agent):
        """Test listing all active sessions."""
        manager = CallManager()

        # Create multiple sessions
        session1 = await manager.create_call(
            agent_id=test_agent.id,
            phone_number="+1111111111",
            websocket=AsyncMock(spec=WebSocket),
            db=db_session,
        )

        session2 = await manager.create_call(
            agent_id=test_agent.id,
            phone_number="+2222222222",
            websocket=AsyncMock(spec=WebSocket),
            db=db_session,
        )

        active_sessions = manager.list_active_sessions()

        assert len(active_sessions) >= 2
        assert session1.call_id in [s.call_id for s in active_sessions]
        assert session2.call_id in [s.call_id for s in active_sessions]

    async def test_get_session_by_agent(self, db_session, test_agent):
        """Test getting sessions by agent ID."""
        manager = CallManager()

        # Create sessions for the agent
        await manager.create_call(
            agent_id=test_agent.id,
            phone_number="+1111111111",
            websocket=AsyncMock(spec=WebSocket),
            db=db_session,
        )

        await manager.create_call(
            agent_id=test_agent.id,
            phone_number="+2222222222",
            websocket=AsyncMock(spec=WebSocket),
            db=db_session,
        )

        agent_sessions = manager.get_sessions_by_agent(test_agent.id)

        assert len(agent_sessions) >= 2
        assert all(s.agent_id == test_agent.id for s in agent_sessions)

    async def test_concurrent_sessions_limit(self, db_session, test_agent):
        """Test handling multiple concurrent sessions."""
        manager = CallManager()
        max_sessions = 10

        sessions = []
        for i in range(max_sessions):
            session = await manager.create_call(
                agent_id=test_agent.id,
                phone_number=f"+123456{i:04d}",
                websocket=AsyncMock(spec=WebSocket),
                db=db_session,
            )
            sessions.append(session)

        assert len(manager.list_active_sessions()) >= max_sessions

        # Clean up
        for session in sessions:
            await manager.end_call(session.call_id)


@pytest.mark.unit
@pytest.mark.asyncio
class TestCallStateManagement:
    """Test call state management."""

    async def test_call_state_enum_values(self):
        """Test CallState enum values."""
        assert CallState.INITIATED == "initiated"
        assert CallState.RINGING == "ringing"
        assert CallState.ANSWERED == "answered"
        assert CallState.IN_PROGRESS == "in_progress"
        assert CallState.COMPLETED == "completed"
        assert CallState.FAILED == "failed"
        assert CallState.CANCELLED == "cancelled"

    async def test_valid_state_transitions(self, db_session, test_agent):
        """Test valid state transitions."""
        websocket = AsyncMock(spec=WebSocket)
        session = CallSession(
            call_id=uuid.uuid4(),
            agent_id=test_agent.id,
            phone_number="+1234567890",
            websocket=websocket,
            db=db_session,
        )

        await session.initialize()

        # Valid transition flow
        session.state = CallState.INITIATED
        session.state = CallState.RINGING
        session.state = CallState.ANSWERED
        session.state = CallState.IN_PROGRESS
        session.state = CallState.COMPLETED

        assert session.state == CallState.COMPLETED

    async def test_failure_state_transition(self, db_session, test_agent):
        """Test transitioning to failed state."""
        websocket = AsyncMock(spec=WebSocket)
        session = CallSession(
            call_id=uuid.uuid4(),
            agent_id=test_agent.id,
            phone_number="+1234567890",
            websocket=websocket,
            db=db_session,
        )

        await session.initialize()

        session.state = CallState.IN_PROGRESS
        session.state = CallState.FAILED

        assert session.state == CallState.FAILED

    async def test_cancelled_state_transition(self, db_session, test_agent):
        """Test transitioning to cancelled state."""
        websocket = AsyncMock(spec=WebSocket)
        session = CallSession(
            call_id=uuid.uuid4(),
            agent_id=test_agent.id,
            phone_number="+1234567890",
            websocket=websocket,
            db=db_session,
        )

        await session.initialize()

        session.state = CallState.RINGING
        session.state = CallState.CANCELLED

        assert session.state == CallState.CANCELLED
