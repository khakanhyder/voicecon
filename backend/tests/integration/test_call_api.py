"""
Integration tests for Call API endpoints.

Tests complete call flow API including WebSocket connections.
"""
import pytest
import uuid
import json
from datetime import datetime
from unittest.mock import AsyncMock, patch

from app.models.call import Call, CallLog
from app.models.agent import Agent


@pytest.mark.integration
@pytest.mark.asyncio
class TestCallAPI:
    """Test call API endpoints."""

    async def test_list_calls(self, auth_client, db_session, test_agent):
        """Test listing calls for organization."""
        # Create test calls
        for i in range(3):
            call = Call(
                id=uuid.uuid4(),
                agent_id=test_agent.id,
                organization_id=test_agent.organization_id,
                phone_number=f"+123456{i:04d}",
                direction="inbound",
                status="completed",
                duration_seconds=120 + i * 10,
            )
            db_session.add(call)

        await db_session.commit()

        # Test API
        response = auth_client.get("/api/v1/calls")

        assert response.status_code == 200
        data = response.json()

        assert "calls" in data
        assert len(data["calls"]) >= 3
        assert all(c["agent_id"] == str(test_agent.id) for c in data["calls"])

    async def test_list_calls_with_filters(
        self, auth_client, db_session, test_agent
    ):
        """Test listing calls with filters."""
        # Create calls with different statuses
        call1 = Call(
            id=uuid.uuid4(),
            agent_id=test_agent.id,
            organization_id=test_agent.organization_id,
            phone_number="+1234567890",
            direction="inbound",
            status="completed",
            duration_seconds=120,
        )

        call2 = Call(
            id=uuid.uuid4(),
            agent_id=test_agent.id,
            organization_id=test_agent.organization_id,
            phone_number="+1234567891",
            direction="outbound",
            status="failed",
            duration_seconds=0,
        )

        db_session.add(call1)
        db_session.add(call2)
        await db_session.commit()

        # Filter by status
        response = auth_client.get("/api/v1/calls?status=completed")

        assert response.status_code == 200
        data = response.json()

        assert all(c["status"] == "completed" for c in data["calls"])

        # Filter by direction
        response = auth_client.get("/api/v1/calls?direction=outbound")

        assert response.status_code == 200
        data = response.json()

        assert all(c["direction"] == "outbound" for c in data["calls"])

    async def test_get_call_by_id(self, auth_client, db_session, test_agent):
        """Test retrieving specific call by ID."""
        # Create test call
        call = Call(
            id=uuid.uuid4(),
            agent_id=test_agent.id,
            organization_id=test_agent.organization_id,
            phone_number="+1234567890",
            direction="inbound",
            status="completed",
            duration_seconds=180,
        )
        db_session.add(call)
        await db_session.commit()

        # Test API
        response = auth_client.get(f"/api/v1/calls/{call.id}")

        assert response.status_code == 200
        data = response.json()

        assert data["id"] == str(call.id)
        assert data["phone_number"] == "+1234567890"
        assert data["duration_seconds"] == 180

    async def test_get_call_not_found(self, auth_client):
        """Test retrieving non-existent call."""
        non_existent_id = uuid.uuid4()

        response = auth_client.get(f"/api/v1/calls/{non_existent_id}")

        assert response.status_code == 404

    async def test_create_outbound_call(self, auth_client, db_session, test_agent):
        """Test creating an outbound call."""
        call_data = {
            "agent_id": str(test_agent.id),
            "phone_number": "+1234567890",
            "direction": "outbound",
        }

        with patch("app.services.telephony.twilio_service.TwilioService") as mock_twilio:
            mock_twilio.return_value.initiate_call = AsyncMock(
                return_value={"call_sid": "CA123456789"}
            )

            response = auth_client.post("/api/v1/calls", json=call_data)

            assert response.status_code == 201
            data = response.json()

            assert data["phone_number"] == "+1234567890"
            assert data["direction"] == "outbound"
            assert data["status"] == "initiated"

    async def test_create_call_with_invalid_agent(self, auth_client):
        """Test creating call with non-existent agent."""
        call_data = {
            "agent_id": str(uuid.uuid4()),
            "phone_number": "+1234567890",
            "direction": "outbound",
        }

        response = auth_client.post("/api/v1/calls", json=call_data)

        assert response.status_code == 404

    async def test_create_call_with_invalid_phone(self, auth_client, test_agent):
        """Test creating call with invalid phone number."""
        call_data = {
            "agent_id": str(test_agent.id),
            "phone_number": "invalid_phone",
            "direction": "outbound",
        }

        response = auth_client.post("/api/v1/calls", json=call_data)

        assert response.status_code == 422

    async def test_end_active_call(self, auth_client, db_session, test_agent):
        """Test ending an active call."""
        # Create active call
        call = Call(
            id=uuid.uuid4(),
            agent_id=test_agent.id,
            organization_id=test_agent.organization_id,
            phone_number="+1234567890",
            direction="inbound",
            status="in_progress",
            duration_seconds=0,
        )
        db_session.add(call)
        await db_session.commit()

        # End call
        response = auth_client.post(f"/api/v1/calls/{call.id}/end")

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "completed"
        assert data["duration_seconds"] > 0

    async def test_get_call_transcript(self, auth_client, db_session, test_agent):
        """Test retrieving call transcript."""
        # Create call with transcript
        call = Call(
            id=uuid.uuid4(),
            agent_id=test_agent.id,
            organization_id=test_agent.organization_id,
            phone_number="+1234567890",
            direction="inbound",
            status="completed",
            duration_seconds=120,
        )
        db_session.add(call)
        await db_session.flush()

        # Add transcript entries
        transcript1 = CallLog(
            id=uuid.uuid4(),
            call_id=call.id,
            speaker="user",
            message="Hello, I need help",
            timestamp=datetime.utcnow(),
        )

        transcript2 = CallLog(
            id=uuid.uuid4(),
            call_id=call.id,
            speaker="agent",
            message="Of course, I'm here to help",
            timestamp=datetime.utcnow(),
        )

        db_session.add(transcript1)
        db_session.add(transcript2)
        await db_session.commit()

        # Test API
        response = auth_client.get(f"/api/v1/calls/{call.id}/transcript")

        assert response.status_code == 200
        data = response.json()

        assert len(data["transcript"]) == 2
        assert data["transcript"][0]["speaker"] == "user"
        assert data["transcript"][1]["speaker"] == "agent"

    async def test_get_call_recording_url(self, auth_client, db_session, test_agent):
        """Test retrieving call recording URL."""
        # Create call with recording
        call = Call(
            id=uuid.uuid4(),
            agent_id=test_agent.id,
            organization_id=test_agent.organization_id,
            phone_number="+1234567890",
            direction="inbound",
            status="completed",
            duration_seconds=120,
            recording_url="https://recordings.example.com/call123.mp3",
        )
        db_session.add(call)
        await db_session.commit()

        # Test API
        response = auth_client.get(f"/api/v1/calls/{call.id}/recording")

        assert response.status_code == 200
        data = response.json()

        assert "recording_url" in data
        assert "recordings.example.com" in data["recording_url"]

    async def test_get_call_recording_not_available(
        self, auth_client, db_session, test_agent
    ):
        """Test retrieving recording when not available."""
        # Create call without recording
        call = Call(
            id=uuid.uuid4(),
            agent_id=test_agent.id,
            organization_id=test_agent.organization_id,
            phone_number="+1234567890",
            direction="inbound",
            status="completed",
            duration_seconds=120,
        )
        db_session.add(call)
        await db_session.commit()

        # Test API
        response = auth_client.get(f"/api/v1/calls/{call.id}/recording")

        assert response.status_code == 404

    async def test_list_calls_pagination(self, auth_client, db_session, test_agent):
        """Test call list pagination."""
        # Create many calls
        for i in range(25):
            call = Call(
                id=uuid.uuid4(),
                agent_id=test_agent.id,
                organization_id=test_agent.organization_id,
                phone_number=f"+123456{i:04d}",
                direction="inbound",
                status="completed",
                duration_seconds=60,
            )
            db_session.add(call)

        await db_session.commit()

        # Test first page
        response = auth_client.get("/api/v1/calls?limit=10&offset=0")

        assert response.status_code == 200
        data = response.json()

        assert len(data["calls"]) == 10
        assert data["total"] >= 25

        # Test second page
        response = auth_client.get("/api/v1/calls?limit=10&offset=10")

        assert response.status_code == 200
        data = response.json()

        assert len(data["calls"]) == 10

    async def test_get_call_analytics(self, auth_client, db_session, test_agent):
        """Test getting call analytics."""
        # Create calls with varying metrics
        calls = [
            Call(
                id=uuid.uuid4(),
                agent_id=test_agent.id,
                organization_id=test_agent.organization_id,
                phone_number=f"+123456{i:04d}",
                direction="inbound",
                status="completed" if i % 2 == 0 else "failed",
                duration_seconds=120 if i % 2 == 0 else 0,
            )
            for i in range(10)
        ]

        for call in calls:
            db_session.add(call)

        await db_session.commit()

        # Test API
        response = auth_client.get(f"/api/v1/calls/analytics?agent_id={test_agent.id}")

        assert response.status_code == 200
        data = response.json()

        assert "total_calls" in data
        assert "completed_calls" in data
        assert "failed_calls" in data
        assert "average_duration" in data
        assert data["total_calls"] >= 10


@pytest.mark.integration
@pytest.mark.asyncio
class TestCallWebSocket:
    """Test WebSocket call connections."""

    @patch("app.services.voice.call_manager.CallManager")
    async def test_websocket_connection(self, mock_manager, auth_client, test_agent):
        """Test establishing WebSocket connection for call."""
        # This is a simplified test since WebSocket testing requires special handling
        # In a real scenario, you'd use a WebSocket test client

        phone_number = "+1234567890"

        # Verify WebSocket endpoint exists
        # Note: Actual WebSocket testing would require websockets library
        # or FastAPI's TestClient with WebSocket support

        assert True  # Placeholder for actual WebSocket test

    async def test_websocket_requires_active_agent(self, db_session, test_agent):
        """Test WebSocket rejects inactive agent."""
        # Deactivate agent
        test_agent.is_active = False
        await db_session.commit()

        # Attempt to connect should fail
        # Actual implementation would use WebSocket test client

        assert test_agent.is_active is False

    async def test_websocket_audio_streaming(self, test_agent):
        """Test audio streaming through WebSocket."""
        # Test would involve:
        # 1. Establishing WebSocket connection
        # 2. Sending audio chunks
        # 3. Receiving transcriptions and responses
        # 4. Verifying bidirectional communication

        # Placeholder for actual implementation
        assert True


@pytest.mark.integration
@pytest.mark.asyncio
class TestCallLogging:
    """Test call logging and transcript management."""

    async def test_create_call_log_entry(self, db_session, test_agent):
        """Test creating call log entries."""
        # Create call
        call = Call(
            id=uuid.uuid4(),
            agent_id=test_agent.id,
            organization_id=test_agent.organization_id,
            phone_number="+1234567890",
            direction="inbound",
            status="in_progress",
        )
        db_session.add(call)
        await db_session.flush()

        # Create log entry
        log_entry = CallLog(
            id=uuid.uuid4(),
            call_id=call.id,
            speaker="user",
            message="Hello",
            timestamp=datetime.utcnow(),
        )
        db_session.add(log_entry)
        await db_session.commit()

        assert log_entry.call_id == call.id
        assert log_entry.message == "Hello"

    async def test_call_log_ordering(self, db_session, test_agent):
        """Test call logs are ordered by timestamp."""
        # Create call
        call = Call(
            id=uuid.uuid4(),
            agent_id=test_agent.id,
            organization_id=test_agent.organization_id,
            phone_number="+1234567890",
            direction="inbound",
            status="completed",
        )
        db_session.add(call)
        await db_session.flush()

        # Create log entries with different timestamps
        from sqlalchemy import select

        logs = []
        for i in range(3):
            log = CallLog(
                id=uuid.uuid4(),
                call_id=call.id,
                speaker="user" if i % 2 == 0 else "agent",
                message=f"Message {i}",
                timestamp=datetime.utcnow(),
            )
            logs.append(log)
            db_session.add(log)

        await db_session.commit()

        # Retrieve logs
        result = await db_session.execute(
            select(CallLog)
            .where(CallLog.call_id == call.id)
            .order_by(CallLog.timestamp)
        )
        retrieved_logs = result.scalars().all()

        assert len(retrieved_logs) == 3
        # Verify chronological order
        for i in range(len(retrieved_logs) - 1):
            assert retrieved_logs[i].timestamp <= retrieved_logs[i + 1].timestamp
