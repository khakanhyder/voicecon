"""
Call Manager - Handles WebSocket connections for real-time voice calls.

Manages the complete call lifecycle:
- Audio streaming from telephony provider (Twilio)
- Real-time transcription via STT service
- LLM conversation management
- TTS synthesis and audio response
- Call state management
"""
import asyncio
import logging
import uuid
from typing import Optional, Dict, Callable, Any
from datetime import datetime
from enum import Enum

from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.voice.stt_service import get_stt_service
from app.services.voice.tts_service import get_tts_service
from app.services.voice.llm_service import get_llm_service
from app.services.voice.providers.base import ChatMessage, AudioChunk, TranscriptionResult
from app.services.voice.audio_utils import AudioBuffer, AudioStream
from app.models.call import Call, CallLog
from app.models.agent import Agent
from app.services.billing.usage_tracker import UsageTracker
from sqlalchemy import select

logger = logging.getLogger(__name__)


class CallState(str, Enum):
    """Call state enumeration."""
    INITIATED = "initiated"
    RINGING = "ringing"
    ANSWERED = "answered"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class CallSession:
    """
    Represents an active call session.

    Manages audio streaming, transcription, and call state.
    """

    def __init__(
        self,
        call_id: uuid.UUID,
        agent_id: uuid.UUID,
        phone_number: str,
        websocket: WebSocket,
        db: AsyncSession,
    ):
        self.call_id = call_id
        self.agent_id = agent_id
        self.phone_number = phone_number
        self.websocket = websocket
        self.db = db

        # Call state
        self.state = CallState.INITIATED
        self.start_time = datetime.utcnow()
        self.end_time: Optional[datetime] = None

        # Audio management
        self.audio_buffer = AudioBuffer(max_size=1000)
        self.audio_stream = AudioStream(self.audio_buffer)

        # Transcription
        self.transcript: list[str] = []
        self.current_sentence = ""

        # Agent configuration
        self.agent: Optional[Agent] = None
        self.organization_id: Optional[uuid.UUID] = None

        # Tasks
        self._tasks: list[asyncio.Task] = []

    async def initialize(self) -> None:
        """Initialize the call session."""
        logger.info(f"Initializing call session: {self.call_id}")

        # Load agent configuration
        result = await self.db.execute(
            select(Agent).where(Agent.id == self.agent_id)
        )
        self.agent = result.scalar_one_or_none()

        if not self.agent:
            raise ValueError(f"Agent not found: {self.agent_id}")

        # Store organization_id for usage tracking
        self.organization_id = self.agent.organization_id

        # Update call state
        await self._update_call_state(CallState.ANSWERED)

        # Send welcome message if configured
        if self.agent.first_message:
            await self._send_message({
                "type": "agent_message",
                "text": self.agent.first_message,
                "timestamp": datetime.utcnow().isoformat(),
            })

            # Synthesize welcome message to audio
            await self._synthesize_and_send_audio(self.agent.first_message)

    async def start(self) -> None:
        """Start the call session."""
        logger.info(f"Starting call session: {self.call_id}")

        try:
            await self._update_call_state(CallState.IN_PROGRESS)

            # Start transcription task
            transcription_task = asyncio.create_task(self._handle_transcription())
            self._tasks.append(transcription_task)

            # Start audio receiving task
            audio_task = asyncio.create_task(self._receive_audio())
            self._tasks.append(audio_task)

            # Wait for tasks to complete
            await asyncio.gather(*self._tasks, return_exceptions=True)

        except Exception as e:
            logger.error(f"Error in call session {self.call_id}: {e}")
            await self._update_call_state(CallState.FAILED)
            raise
        finally:
            await self.cleanup()

    async def _receive_audio(self) -> None:
        """Receive audio chunks from WebSocket."""
        try:
            while True:
                # Receive audio data from WebSocket
                message = await self.websocket.receive()

                if message["type"] == "websocket.disconnect":
                    logger.info(f"WebSocket disconnected for call: {self.call_id}")
                    break

                # Handle different message types
                if message["type"] == "websocket.receive":
                    if "bytes" in message:
                        # Binary audio data
                        audio_data = message["bytes"]

                        # Create audio chunk (assuming 16kHz, mono)
                        chunk = AudioChunk(
                            data=audio_data,
                            sample_rate=16000,
                            channels=1,
                        )

                        # Add to buffer for transcription
                        await self.audio_buffer.put(chunk)

                        # Log audio received
                        await self._log_event("audio_received", {
                            "size": len(audio_data),
                        })

                    elif "text" in message:
                        # Control messages
                        await self._handle_control_message(message["text"])

        except WebSocketDisconnect:
            logger.info(f"WebSocket disconnected for call: {self.call_id}")
        except Exception as e:
            logger.error(f"Error receiving audio for call {self.call_id}: {e}")
            raise
        finally:
            await self.audio_buffer.close()

    async def _handle_transcription(self) -> None:
        """Handle real-time transcription."""
        try:
            stt = get_stt_service()

            # Get provider from agent configuration
            provider = self.agent.stt_provider or "deepgram"
            language = self.agent.stt_language or "en"
            model = self.agent.stt_model

            logger.info(
                f"Starting transcription for call {self.call_id}: "
                f"provider={provider}, language={language}, model={model}"
            )

            # Stream transcription
            async for result in stt.transcribe_stream(
                self.audio_stream,
                provider=provider,
                language=language,
                model=model,
                interim_results=True,
            ):
                await self._handle_transcription_result(result)

        except Exception as e:
            logger.error(f"Error in transcription for call {self.call_id}: {e}")
            await self._log_event("transcription_error", {"error": str(e)})

    async def _handle_transcription_result(self, result: TranscriptionResult) -> None:
        """Handle transcription result."""
        try:
            if result.is_final:
                # Final transcription - add to transcript
                self.transcript.append(result.text)
                self.current_sentence = ""

                # Send to client
                await self._send_message({
                    "type": "transcription",
                    "text": result.text,
                    "is_final": True,
                    "confidence": result.confidence,
                    "timestamp": result.timestamp.isoformat(),
                })

                # Log final transcription
                await self._log_event("transcription_final", {
                    "text": result.text,
                    "confidence": result.confidence,
                })

                # Process with LLM (placeholder for now)
                # TODO: Integrate LLM service
                await self._process_with_llm(result.text)

            else:
                # Interim result - update current sentence
                self.current_sentence = result.text

                # Send interim update
                await self._send_message({
                    "type": "transcription",
                    "text": result.text,
                    "is_final": False,
                    "timestamp": result.timestamp.isoformat(),
                })

        except Exception as e:
            logger.error(f"Error handling transcription result: {e}")

    async def _process_with_llm(self, user_message: str) -> None:
        """
        Process user message with LLM and generate response.
        """
        try:
            llm = get_llm_service()

            # Get or create conversation context
            conversation_id = f"call-{self.call_id}"
            context = llm.get_conversation(conversation_id)

            if not context:
                # Create new conversation with agent's system prompt
                system_prompt = self.agent.system_prompt or "You are a helpful AI assistant."
                context = llm.create_conversation(
                    conversation_id=conversation_id,
                    system_prompt=system_prompt,
                    max_history=20,
                )

            # Add user message to context
            context.add_message("user", user_message)

            # Get LLM configuration from agent
            provider = self.agent.llm_provider or "openai"
            model = self.agent.llm_model or None  # Use default
            temperature = self.agent.llm_temperature or 0.7

            logger.info(
                f"Processing with LLM for call {self.call_id}: "
                f"provider={provider}, model={model}, message_len={len(user_message)}"
            )

            # Generate response with streaming
            full_response = ""

            async for chunk in llm.chat_stream(
                messages=context.get_messages(),
                provider=provider,
                model=model,
                temperature=temperature,
                max_tokens=500,  # Limit for voice responses
            ):
                full_response += chunk

            # Add assistant response to context
            context.add_message("assistant", full_response)

            # Send text response to client
            await self._send_message({
                "type": "agent_response",
                "text": full_response,
                "timestamp": datetime.utcnow().isoformat(),
            })

            # Log LLM interaction
            await self._log_event("llm_response", {
                "user_message": user_message,
                "assistant_response": full_response,
                "provider": provider,
                "model": model,
                "conversation_turns": context.get_message_count(),
            })

            # Convert to speech with TTS service
            await self._synthesize_and_send_audio(full_response)

        except Exception as e:
            logger.error(f"Error processing with LLM for call {self.call_id}: {e}")
            await self._log_event("llm_error", {"error": str(e)})

            # Fallback response
            fallback = "I apologize, I'm having trouble processing that. Could you please try again?"
            await self._send_message({
                "type": "agent_response",
                "text": fallback,
                "timestamp": datetime.utcnow().isoformat(),
            })
            await self._synthesize_and_send_audio(fallback)

    async def _synthesize_and_send_audio(self, text: str) -> None:
        """
        Synthesize text to speech and send audio to client.

        Args:
            text: Text to convert to speech
        """
        try:
            tts = get_tts_service()

            # Get TTS provider from agent configuration
            provider = self.agent.tts_provider or "elevenlabs"
            voice_id = self.agent.tts_voice
            model = self.agent.tts_model

            logger.info(
                f"Synthesizing audio for call {self.call_id}: "
                f"provider={provider}, voice={voice_id}, text_length={len(text)}"
            )

            # Stream audio chunks to client for low latency
            async for audio_chunk in tts.synthesize_stream(
                text=text,
                provider=provider,
                voice_id=voice_id,
                model=model,
            ):
                # Send audio chunk to WebSocket
                await self.websocket.send_bytes(audio_chunk)

            # Log TTS event
            await self._log_event("tts_synthesis", {
                "text": text,
                "provider": provider,
                "voice_id": voice_id,
                "character_count": len(text),
            })

        except Exception as e:
            logger.error(f"Error synthesizing audio for call {self.call_id}: {e}")
            await self._log_event("tts_error", {"error": str(e)})

    async def _handle_control_message(self, message: str) -> None:
        """Handle control messages from client."""
        import json

        try:
            data = json.loads(message)
            msg_type = data.get("type")

            if msg_type == "end_call":
                logger.info(f"End call requested for: {self.call_id}")
                await self._update_call_state(CallState.COMPLETED)
                await self.cleanup()

            elif msg_type == "ping":
                await self._send_message({"type": "pong"})

            else:
                logger.warning(f"Unknown control message type: {msg_type}")

        except json.JSONDecodeError:
            logger.error(f"Invalid JSON in control message: {message}")

    async def _send_message(self, message: Dict[str, Any]) -> None:
        """Send message to WebSocket client."""
        import json

        try:
            await self.websocket.send_json(message)
        except Exception as e:
            logger.error(f"Error sending message: {e}")

    async def _update_call_state(self, state: CallState) -> None:
        """Update call state in database."""
        self.state = state

        try:
            # Update call record
            result = await self.db.execute(
                select(Call).where(Call.id == self.call_id)
            )
            call = result.scalar_one_or_none()

            if call:
                call.status = state.value

                if state == CallState.COMPLETED:
                    self.end_time = datetime.utcnow()
                    call.end_time = self.end_time
                    call.duration = int((self.end_time - self.start_time).total_seconds())

                await self.db.commit()

                logger.info(f"Updated call {self.call_id} state to: {state}")

        except Exception as e:
            logger.error(f"Error updating call state: {e}")
            await self.db.rollback()

    async def _log_event(self, event_type: str, metadata: Dict[str, Any]) -> None:
        """Log call event."""
        try:
            log_entry = CallLog(
                call_id=self.call_id,
                timestamp=datetime.utcnow(),
                event_type=event_type,
                metadata=metadata,
            )
            self.db.add(log_entry)
            await self.db.commit()

        except Exception as e:
            logger.error(f"Error logging event: {e}")
            await self.db.rollback()

    async def cleanup(self) -> None:
        """Clean up call session resources."""
        logger.info(f"Cleaning up call session: {self.call_id}")

        # Cancel all tasks
        for task in self._tasks:
            if not task.done():
                task.cancel()

        # Close audio buffer
        await self.audio_buffer.close()

        # Update final call state if not already done
        if self.state not in [CallState.COMPLETED, CallState.FAILED, CallState.CANCELLED]:
            await self._update_call_state(CallState.COMPLETED)

        # Save final transcript
        if self.transcript:
            await self._log_event("call_transcript", {
                "transcript": self.transcript,
                "total_sentences": len(self.transcript),
            })

        # Record usage for billing (only if call was completed successfully)
        if self.state == CallState.COMPLETED and self.organization_id:
            try:
                await UsageTracker.record_call_usage(
                    db=self.db,
                    call_id=self.call_id,
                    organization_id=self.organization_id,
                )
            except Exception as e:
                logger.error(f"Error recording usage for call {self.call_id}: {e}")


class CallManager:
    """
    Manages multiple concurrent call sessions.

    Handles WebSocket connections and routes them to appropriate call sessions.
    """

    def __init__(self):
        self._active_calls: Dict[uuid.UUID, CallSession] = {}
        self._lock = asyncio.Lock()

    async def create_call(
        self,
        agent_id: uuid.UUID,
        phone_number: str,
        websocket: WebSocket,
        db: AsyncSession,
    ) -> CallSession:
        """
        Create a new call session.

        Args:
            agent_id: ID of the agent handling the call
            phone_number: Caller's phone number
            websocket: WebSocket connection
            db: Database session

        Returns:
            CallSession instance
        """
        call_id = uuid.uuid4()

        # Create call record in database
        call = Call(
            id=call_id,
            agent_id=agent_id,
            from_number=phone_number,
            to_number="system",  # Updated by telephony provider
            direction="inbound",
            status=CallState.INITIATED.value,
            start_time=datetime.utcnow(),
        )
        db.add(call)
        await db.commit()

        # Create call session
        session = CallSession(
            call_id=call_id,
            agent_id=agent_id,
            phone_number=phone_number,
            websocket=websocket,
            db=db,
        )

        async with self._lock:
            self._active_calls[call_id] = session

        logger.info(f"Created call session: {call_id} for agent: {agent_id}")

        return session

    async def get_call(self, call_id: uuid.UUID) -> Optional[CallSession]:
        """Get active call session by ID."""
        async with self._lock:
            return self._active_calls.get(call_id)

    async def remove_call(self, call_id: uuid.UUID) -> None:
        """Remove call session."""
        async with self._lock:
            if call_id in self._active_calls:
                del self._active_calls[call_id]
                logger.info(f"Removed call session: {call_id}")

    async def get_active_calls_count(self) -> int:
        """Get count of active calls."""
        async with self._lock:
            return len(self._active_calls)

    async def cleanup_all(self) -> None:
        """Clean up all active calls."""
        async with self._lock:
            for call_session in self._active_calls.values():
                await call_session.cleanup()
            self._active_calls.clear()


# Global call manager instance
_call_manager: Optional[CallManager] = None


def get_call_manager() -> CallManager:
    """
    Get global call manager instance (singleton).

    Returns:
        CallManager instance
    """
    global _call_manager
    if _call_manager is None:
        _call_manager = CallManager()
    return _call_manager
