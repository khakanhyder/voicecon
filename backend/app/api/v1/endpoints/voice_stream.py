"""
Voice Stream WebSocket Endpoint.

Handles Twilio Media Stream WebSocket connections for real-time voice processing.
"""
import logging
import json
from typing import Dict
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.call import Call
from app.models.agent import Agent
from app.services.websocket.connection_manager import get_connection_manager
from app.services.websocket.voice_session import VoiceSession

logger = logging.getLogger(__name__)

router = APIRouter()

# Active voice sessions
_active_sessions: Dict[str, VoiceSession] = {}


@router.websocket("/stream/{call_id}")
async def voice_stream_websocket(
    websocket: WebSocket,
    call_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    WebSocket endpoint for Twilio Media Streams.

    This endpoint receives:
    - Stream start events
    - Audio data from caller (mulaw, 8kHz, base64)
    - Stream stop events

    And sends:
    - Audio data to caller (mulaw, 8kHz, base64)
    - Mark events for synchronization

    Flow:
    1. Twilio connects via WebSocket
    2. Sends "start" event with stream metadata
    3. Streams audio as "media" events
    4. Receives audio responses
    5. Sends "stop" event on call end

    Args:
        websocket: WebSocket connection from Twilio
        call_id: Call identifier (UUID)
        db: Database session
    """
    connection_manager = get_connection_manager()
    voice_session: VoiceSession = None

    try:
        # Connect WebSocket
        await connection_manager.connect(call_id, websocket)

        logger.info(f"Twilio media stream connected: call_id={call_id}")

        # Get call from database
        result = await db.execute(
            select(Call).where(Call.id == call_id)
        )
        call = result.scalar_one_or_none()

        if not call:
            logger.error(f"Call not found: {call_id}")
            await websocket.close(code=4004, reason="Call not found")
            return

        # Get agent
        agent_result = await db.execute(
            select(Agent).where(Agent.id == call.agent_id)
        )
        agent = agent_result.scalar_one_or_none()

        if not agent:
            logger.error(f"Agent not found: {call.agent_id}")
            await websocket.close(code=4004, reason="Agent not found")
            return

        # Create voice session
        voice_session = VoiceSession(
            call_id=call_id,
            call=call,
            agent=agent,
            connection_manager=connection_manager,
            db=db,
        )

        # Store in active sessions
        _active_sessions[call_id] = voice_session

        # Start session
        await voice_session.start()

        logger.info(f"Voice session started: call_id={call_id}, agent={agent.name}")

        # Main message loop
        while True:
            # Receive message from Twilio
            message_text = await websocket.receive_text()

            try:
                message = json.loads(message_text)

                # Handle message
                await voice_session.handle_message(message)

            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON from Twilio: {e}")
            except Exception as e:
                logger.error(f"Error handling message: {e}", exc_info=True)

    except WebSocketDisconnect:
        logger.info(f"Twilio media stream disconnected: call_id={call_id}")

    except Exception as e:
        logger.error(f"Error in voice stream WebSocket: {e}", exc_info=True)

    finally:
        # Cleanup
        if voice_session:
            try:
                await voice_session.cleanup()
            except Exception as e:
                logger.error(f"Error cleaning up voice session: {e}")

            # Remove from active sessions
            if call_id in _active_sessions:
                del _active_sessions[call_id]

        # Disconnect WebSocket
        await connection_manager.disconnect(call_id)

        logger.info(f"Voice stream cleanup complete: call_id={call_id}")


@router.get("/sessions/active")
async def get_active_sessions():
    """
    Get active voice sessions.

    Returns:
        List of active session info
    """
    return {
        "active_sessions": len(_active_sessions),
        "sessions": [
            {
                "call_id": call_id,
                "state": session.state,
                "stream_sid": session.stream_sid,
                "call_sid": session.call_sid,
                "agent": session.agent.name,
                "metrics": session.metrics,
            }
            for call_id, session in _active_sessions.items()
        ]
    }


@router.get("/sessions/{call_id}")
async def get_session_info(call_id: str):
    """
    Get info for a specific session.

    Args:
        call_id: Call identifier

    Returns:
        Session info
    """
    session = _active_sessions.get(call_id)

    if not session:
        return {"error": "Session not found"}, 404

    return {
        "call_id": call_id,
        "state": session.state,
        "stream_sid": session.stream_sid,
        "call_sid": session.call_sid,
        "agent": {
            "id": str(session.agent.id),
            "name": session.agent.name,
        },
        "conversation": {
            "message_count": session.conversation.get_message_count() if session.conversation else 0,
        },
        "metrics": session.metrics,
    }
