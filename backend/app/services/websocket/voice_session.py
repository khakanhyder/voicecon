"""
Voice Session Handler for Twilio Media Streams.

Handles real-time voice processing: STT → LLM → TTS with Twilio WebSocket.
"""
import logging
import asyncio
import json
import base64
from typing import Optional, Dict, Any
from datetime import datetime
from enum import Enum

from app.services.voice.stt_service import get_stt_service
from app.services.voice.tts_service import get_tts_service
from app.services.voice.llm_service import get_llm_service, ConversationContext
from app.services.websocket.connection_manager import ConnectionManager
from app.services.call.transcript_service import get_transcript_service, TranscriptEntry
from app.services.call.analytics_service import get_analytics_service
from app.services.function_executor import get_function_executor
from app.models.agent import Agent, AgentFunction
from app.models.tool import Tool
from app.models.call import Call, CallLog
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class SessionState(str, Enum):
    """Voice session states."""
    INITIALIZING = "initializing"
    READY = "ready"
    LISTENING = "listening"
    PROCESSING = "processing"
    SPEAKING = "speaking"
    ENDED = "ended"
    ERROR = "error"


class VoiceSession:
    """
    Voice session handler for Twilio media streams.

    Processes real-time audio:
    1. Receives audio from Twilio WebSocket (mulaw, 8kHz)
    2. Transcribes with STT (Deepgram)
    3. Generates response with LLM (OpenAI/Anthropic)
    4. Synthesizes speech with TTS (ElevenLabs)
    5. Sends audio back to Twilio

    Handles:
    - Bidirectional audio streaming
    - Conversation state management
    - Audio buffering and format conversion
    - Interruption handling
    - Low-latency processing (<600ms target)
    """

    def __init__(
        self,
        call_id: str,
        call: Call,
        agent: Agent,
        connection_manager: ConnectionManager,
        db: AsyncSession,
    ):
        """
        Initialize voice session.

        Args:
            call_id: Unique call identifier
            call: Call database record
            agent: Agent handling the call
            connection_manager: WebSocket connection manager
            db: Database session
        """
        self.call_id = call_id
        self.call = call
        self.agent = agent
        self.connection_manager = connection_manager
        self.db = db

        # Session state
        self.state = SessionState.INITIALIZING
        self.stream_sid: Optional[str] = None
        self.call_sid: Optional[str] = None

        # Services
        self.stt_service = get_stt_service()
        self.tts_service = get_tts_service()
        self.llm_service = get_llm_service()
        self.transcript_service = get_transcript_service()
        self.analytics_service = get_analytics_service()
        self.function_executor = get_function_executor()

        # Conversation context
        self.conversation: Optional[ConversationContext] = None

        # Agent functions (webhook-based per-agent) + global assigned tools
        self.agent_functions: list[AgentFunction] = []
        self.agent_tools: list[Tool] = []

        # Transcript entries
        self.transcript_entries: list[TranscriptEntry] = []

        # Audio buffering
        self.audio_buffer = bytearray()
        self.buffer_lock = asyncio.Lock()

        # Processing flags
        self.is_processing = False
        self.current_utterance = ""
        self.transcription_complete = asyncio.Event()

        # Metrics
        self.metrics = {
            "audio_chunks_received": 0,
            "audio_chunks_sent": 0,
            "transcriptions": 0,
            "llm_responses": 0,
            "tts_generations": 0,
            "started_at": datetime.utcnow(),
        }

        logger.info(f"Voice session initialized: call_id={call_id}, agent={agent.name}")

    async def start(self) -> None:
        """Start the voice session."""
        try:
            # Load agent webhook functions
            self.agent_functions = await self.function_executor.get_agent_functions(
                agent_id=str(self.agent.id),
                db=self.db,
            )
            # Load globally assigned tools
            self.agent_tools = await self.function_executor.get_agent_assigned_tools(
                agent_id=str(self.agent.id),
                db=self.db,
            )
            logger.info(
                f"Loaded {len(self.agent_functions)} functions + "
                f"{len(self.agent_tools)} tools for agent"
            )

            # Create conversation context
            system_prompt = self.agent.system_prompt or "You are a helpful AI assistant."
            self.conversation = self.llm_service.create_conversation(
                conversation_id=f"call-{self.call_id}",
                system_prompt=system_prompt,
                max_history=20,
            )

            # Send welcome message
            welcome_message = self.agent.first_message or f"Hello! This is {self.agent.name}. How can I help you today?"
            await self._send_welcome_message(welcome_message)

            self.state = SessionState.READY
            logger.info(f"Voice session started: call_id={self.call_id}")

        except Exception as e:
            logger.error(f"Error starting voice session: {e}", exc_info=True)
            self.state = SessionState.ERROR
            raise

    async def handle_message(self, message: dict) -> None:
        """
        Handle incoming WebSocket message from Twilio.

        Twilio sends messages in this format:
        - event: "start" - Stream started
        - event: "media" - Audio data
        - event: "stop" - Stream stopped

        Args:
            message: WebSocket message from Twilio
        """
        try:
            event = message.get("event")

            if event == "start":
                await self._handle_start(message)

            elif event == "media":
                await self._handle_media(message)

            elif event == "stop":
                await self._handle_stop(message)

            elif event == "mark":
                # Mark events indicate audio playback completion
                await self._handle_mark(message)

            else:
                logger.debug(f"Unknown event type: {event}")

        except Exception as e:
            logger.error(f"Error handling message: {e}", exc_info=True)

    async def _handle_start(self, message: dict) -> None:
        """
        Handle stream start event.

        Args:
            message: Start event message
        """
        start_data = message.get("start", {})
        self.stream_sid = start_data.get("streamSid")
        self.call_sid = start_data.get("callSid")

        logger.info(
            f"Stream started: stream_sid={self.stream_sid}, "
            f"call_sid={self.call_sid}, call_id={self.call_id}"
        )

        # Update call record
        if self.call_sid:
            self.call.provider_call_sid = self.call_sid
            await self.db.commit()

    async def _handle_media(self, message: dict) -> None:
        """
        Handle media event (audio data from caller).

        Twilio sends audio as base64-encoded mulaw at 8kHz.

        Args:
            message: Media event message
        """
        media_data = message.get("media", {})
        payload = media_data.get("payload")

        if not payload:
            return

        self.metrics["audio_chunks_received"] += 1

        # Decode audio (base64 mulaw)
        try:
            audio_bytes = base64.b64decode(payload)

            # Add to buffer
            async with self.buffer_lock:
                self.audio_buffer.extend(audio_bytes)

            # Process if we have enough audio (20ms chunks = 160 bytes at 8kHz mulaw)
            if len(self.audio_buffer) >= 160 and not self.is_processing:
                await self._process_audio_chunk()

        except Exception as e:
            logger.error(f"Error processing media: {e}")

    async def _handle_stop(self, message: dict) -> None:
        """
        Handle stream stop event.

        Args:
            message: Stop event message
        """
        logger.info(f"Stream stopped: call_id={self.call_id}")
        self.state = SessionState.ENDED

        # Process any remaining audio
        if len(self.audio_buffer) > 0:
            await self._process_audio_chunk()

    async def _handle_mark(self, message: dict) -> None:
        """
        Handle mark event (audio playback completion).

        Args:
            message: Mark event message
        """
        mark_data = message.get("mark", {})
        mark_name = mark_data.get("name")

        logger.debug(f"Mark event: {mark_name}")

        # Can be used to detect when agent finished speaking
        if mark_name == "speech_end":
            self.state = SessionState.LISTENING

    async def _process_audio_chunk(self) -> None:
        """Process buffered audio for transcription."""
        if self.is_processing:
            return

        self.is_processing = True
        self.state = SessionState.LISTENING

        try:
            # Get audio from buffer
            async with self.buffer_lock:
                audio_data = bytes(self.audio_buffer)
                self.audio_buffer.clear()

            if len(audio_data) < 160:
                return

            # Transcribe audio with STT
            # Note: Deepgram supports mulaw format directly
            transcription = await self._transcribe_audio(audio_data)

            if transcription and transcription.strip():
                logger.info(f"Transcription: {transcription}")
                self.metrics["transcriptions"] += 1

                # Add to current utterance
                self.current_utterance += " " + transcription

                # Check if utterance is complete (simple approach: wait for pause)
                # In production, use VAD (Voice Activity Detection)
                if self._is_utterance_complete(transcription):
                    await self._process_utterance(self.current_utterance.strip())
                    self.current_utterance = ""

        except Exception as e:
            logger.error(f"Error processing audio chunk: {e}", exc_info=True)

        finally:
            self.is_processing = False

    async def _transcribe_audio(self, audio_data: bytes) -> Optional[str]:
        """
        Transcribe audio using STT service.

        Args:
            audio_data: Raw audio bytes (mulaw, 8kHz)

        Returns:
            Transcription text or None
        """
        try:
            # For Deepgram, we can use streaming or batch
            # For low latency, use streaming mode
            provider = self.agent.stt_provider or "deepgram"
            model = self.agent.stt_model or "nova-2"

            # TODO: Implement proper streaming STT
            # For now, use batch transcription
            # result = await self.stt_service.transcribe_stream(
            #     audio_stream=audio_data,
            #     provider=provider,
            #     model=model,
            # )

            # Placeholder: return None for now
            # In production, implement proper streaming
            return None

        except Exception as e:
            logger.error(f"Error transcribing audio: {e}")
            return None

    def _is_utterance_complete(self, transcription: str) -> bool:
        """
        Check if utterance is complete.

        Simple heuristic: check for sentence-ending punctuation.

        Args:
            transcription: Transcription text

        Returns:
            True if utterance appears complete
        """
        if not transcription:
            return False

        # Check for ending punctuation
        endings = ['.', '?', '!']
        return any(transcription.strip().endswith(end) for end in endings)

    async def _process_utterance(self, utterance: str) -> None:
        """
        Process complete user utterance with LLM and respond.

        Args:
            utterance: Complete user utterance
        """
        self.state = SessionState.PROCESSING

        try:
            logger.info(f"Processing utterance: {utterance}")

            # Log user transcript
            await self._log_transcript_entry("user", utterance)

            # Add user message to conversation
            self.conversation.add_message("user", utterance)

            # Generate response with LLM
            response = await self._generate_llm_response()

            if response:
                logger.info(f"LLM response: {response}")
                self.metrics["llm_responses"] += 1

                # Log assistant transcript
                await self._log_transcript_entry("assistant", response)

                # Add assistant response to conversation
                self.conversation.add_message("assistant", response)

                # Update call costs
                await self._update_call_costs()

                # Synthesize and send audio
                await self._speak_response(response)

        except Exception as e:
            logger.error(f"Error processing utterance: {e}", exc_info=True)
            error_msg = "I'm sorry, I didn't quite catch that. Could you repeat?"
            await self._log_transcript_entry("assistant", error_msg)
            await self._speak_response(error_msg)

        finally:
            self.state = SessionState.LISTENING

    async def _generate_llm_response(self) -> Optional[str]:
        """
        Generate response using LLM with function calling support.

        Returns:
            LLM response text
        """
        try:
            provider = self.agent.llm_provider or "openai"
            model = self.agent.llm_model or "gpt-4-turbo-preview"
            temperature = self.agent.llm_temperature or 0.7

            messages = self.conversation.get_messages()

            # Prepare function definitions: webhook functions + global tools
            functions = None
            func_defs = [
                self.function_executor.get_function_definition(f)
                for f in self.agent_functions
            ]
            tool_defs = [
                self.function_executor.get_tool_function_definition(t)
                for t in self.agent_tools
            ]
            all_defs = func_defs + tool_defs
            if all_defs:
                functions = all_defs

            # Generate response (with function calling if available)
            if functions and provider == "openai":
                # Use function calling for OpenAI
                response_text = await self._generate_with_functions(
                    messages, provider, model, temperature, functions
                )
            else:
                # Standard streaming response
                response_chunks = []
                async for chunk in self.llm_service.chat_stream(
                    messages=messages,
                    provider=provider,
                    model=model,
                    temperature=temperature,
                    max_tokens=500,
                ):
                    response_chunks.append(chunk)
                response_text = "".join(response_chunks)

            return response_text

        except Exception as e:
            logger.error(f"Error generating LLM response: {e}")
            return None

    async def _generate_with_functions(
        self,
        messages: list,
        provider: str,
        model: str,
        temperature: float,
        functions: list,
    ) -> str:
        """
        Generate LLM response with function calling support.

        Args:
            messages: Conversation messages
            provider: LLM provider
            model: Model name
            temperature: Temperature
            functions: Function definitions

        Returns:
            Final response text after function execution
        """
        max_function_calls = 5  # Prevent infinite loops
        function_call_count = 0

        while function_call_count < max_function_calls:
            # Call LLM with functions
            response_chunks = []
            function_call = None

            async for chunk in self.llm_service.chat_stream(
                messages=messages,
                provider=provider,
                model=model,
                temperature=temperature,
                max_tokens=500,
                functions=functions,
            ):
                # Check if this is a function call
                if isinstance(chunk, dict) and "function_call" in chunk:
                    function_call = chunk["function_call"]
                else:
                    response_chunks.append(chunk)

            # If no function call, return response
            if not function_call:
                return "".join(response_chunks)

            # Execute function
            function_name = function_call.get("name")
            function_args = json.loads(function_call.get("arguments", "{}"))

            logger.info(f"Executing function: {function_name} with args: {function_args}")

            # Find function by name — check webhook functions first, then global tools
            agent_function = next(
                (f for f in self.agent_functions if f.name == function_name),
                None
            )

            # Also check global tools (name is normalised: spaces→_, lowercased)
            matched_tool = next(
                (t for t in self.agent_tools
                 if t.name.replace(" ", "_").lower()[:64] == function_name),
                None
            )

            if agent_function:
                result = await self.function_executor.execute_function(
                    function=agent_function,
                    parameters=function_args,
                    call_id=self.call_id,
                    db=self.db,
                )
                formatted_result = self.function_executor.format_for_llm(agent_function, result)

            elif matched_tool:
                result = await self.function_executor.execute_global_tool(
                    tool=matched_tool,
                    parameters=function_args,
                    call_id=self.call_id,
                    db=self.db,
                )
                if result.get("success"):
                    formatted_result = f"Tool {matched_tool.name} returned: {json.dumps(result.get('result', {}))}"
                else:
                    formatted_result = f"Tool {matched_tool.name} failed: {result.get('error', 'unknown error')}"

            else:
                return f"I tried to use a capability called {function_name}, but it's not configured."

            # Add function result to conversation
            messages.append({
                "role": "function",
                "name": function_name,
                "content": formatted_result,
            })

            function_call_count += 1

            # Continue loop to let LLM generate final response with function result

        # Max function calls reached
        return "I apologize, but I'm having trouble completing that request."

    async def _speak_response(self, text: str) -> None:
        """
        Synthesize speech and send to caller.

        Args:
            text: Text to speak
        """
        self.state = SessionState.SPEAKING

        try:
            provider = self.agent.tts_provider or "elevenlabs"
            voice_id = self.agent.tts_voice_id or "rachel"

            # Synthesize with streaming for low latency
            audio_chunks = []
            async for audio_chunk in self.tts_service.synthesize_stream(
                text=text,
                provider=provider,
                voice_id=voice_id,
            ):
                audio_chunks.append(audio_chunk)

                # Send to Twilio immediately (stream as we generate)
                await self._send_audio_to_twilio(audio_chunk)

            self.metrics["tts_generations"] += 1

            # Mark end of speech
            await self._send_mark("speech_end")

            logger.info(f"Sent audio response: {len(audio_chunks)} chunks")

        except Exception as e:
            logger.error(f"Error speaking response: {e}", exc_info=True)

        finally:
            self.state = SessionState.LISTENING

    async def _send_audio_to_twilio(self, audio_data: bytes) -> None:
        """
        Send audio to Twilio WebSocket.

        Twilio expects audio as base64-encoded mulaw at 8kHz.

        Args:
            audio_data: Audio bytes (will be converted if needed)
        """
        try:
            # TODO: Convert audio format if needed
            # ElevenLabs returns mp3, need to convert to mulaw

            # For now, assume audio is already in correct format
            payload = base64.b64encode(audio_data).decode('utf-8')

            message = {
                "event": "media",
                "streamSid": self.stream_sid,
                "media": {
                    "payload": payload
                }
            }

            await self.connection_manager.send_json(self.call_id, message)
            self.metrics["audio_chunks_sent"] += 1

        except Exception as e:
            logger.error(f"Error sending audio to Twilio: {e}")

    async def _send_mark(self, name: str) -> None:
        """
        Send mark event to Twilio.

        Args:
            name: Mark name
        """
        message = {
            "event": "mark",
            "streamSid": self.stream_sid,
            "mark": {
                "name": name
            }
        }

        await self.connection_manager.send_json(self.call_id, message)

    async def _send_welcome_message(self, text: str) -> None:
        """
        Send welcome message to caller.

        Args:
            text: Welcome message text
        """
        try:
            logger.info(f"Sending welcome message: {text}")

            # Add to conversation history
            self.conversation.add_message("assistant", text)

            # Synthesize and send
            await self._speak_response(text)

        except Exception as e:
            logger.error(f"Error sending welcome message: {e}")

    async def _update_call_costs(self) -> None:
        """Update call costs in database."""
        try:
            # Get usage stats from services
            stt_stats = await self.stt_service.get_usage_stats(provider=self.agent.stt_provider)
            llm_stats = await self.llm_service.get_usage_stats(provider=self.agent.llm_provider)
            tts_stats = await self.tts_service.get_usage_stats(provider=self.agent.tts_provider)

            # Calculate total costs
            stt_cost = sum(stat.cost for stat in stt_stats)
            llm_cost = sum(stat.cost for stat in llm_stats)
            tts_cost = sum(stat.cost for stat in tts_stats)

            # Update call record
            self.call.cost_stt = stt_cost
            self.call.cost_llm = llm_cost
            self.call.cost_tts = tts_cost
            self.call.cost_total = (
                (self.call.cost_stt or 0) +
                (self.call.cost_llm or 0) +
                (self.call.cost_tts or 0) +
                (self.call.cost_telephony or 0)
            )

            await self.db.commit()

        except Exception as e:
            logger.error(f"Error updating call costs: {e}")

    async def _log_transcript_entry(self, speaker: str, text: str) -> None:
        """
        Log transcript entry.

        Args:
            speaker: Speaker ("user" or "assistant")
            text: Text content
        """
        entry = TranscriptEntry(
            speaker=speaker,
            text=text,
            timestamp=datetime.utcnow(),
        )
        self.transcript_entries.append(entry)

        # Also log to database
        log_type = "stt" if speaker == "user" else "llm"
        call_log = CallLog(
            call_id=self.call.id,
            log_type=log_type,
            severity="info",
            message=f"{speaker}: {text[:100]}...",
            details={
                "speaker": speaker,
                speaker: text if speaker == "user" else None,
                "response": text if speaker == "assistant" else None,
            },
        )

        self.db.add(call_log)
        await self.db.commit()

    async def cleanup(self) -> None:
        """Clean up session resources."""
        try:
            logger.info(f"Cleaning up voice session: call_id={self.call_id}")

            # Save transcript
            if self.transcript_entries:
                await self.transcript_service.save_transcript(
                    call=self.call,
                    transcript=self.transcript_entries,
                    db=self.db,
                )
                logger.info(f"Saved transcript with {len(self.transcript_entries)} entries")

            # Update final costs
            await self._update_call_costs()

            # Update call status
            self.call.status = "completed"
            self.call.ended_at = datetime.utcnow()

            if self.call.answered_at:
                duration = (self.call.ended_at - self.call.answered_at).total_seconds()
                self.call.duration_seconds = int(duration)
                self.call.billable_duration_seconds = int(duration)

            await self.db.commit()

            # Calculate duration
            duration = (datetime.utcnow() - self.metrics["started_at"]).total_seconds()

            logger.info(
                f"Voice session metrics: call_id={self.call_id}, "
                f"duration={duration:.2f}s, "
                f"audio_received={self.metrics['audio_chunks_received']}, "
                f"audio_sent={self.metrics['audio_chunks_sent']}, "
                f"transcriptions={self.metrics['transcriptions']}, "
                f"llm_responses={self.metrics['llm_responses']}, "
                f"tts_generations={self.metrics['tts_generations']}"
            )

            # Delete conversation context
            self.llm_service.delete_conversation(f"call-{self.call_id}")

            self.state = SessionState.ENDED

        except Exception as e:
            logger.error(f"Error cleaning up session: {e}", exc_info=True)
