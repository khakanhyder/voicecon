"""
Voice Session Handler for Twilio Media Streams.

Handles real-time voice processing: STT → LLM → TTS with Twilio WebSocket.
"""
import logging
import asyncio
import json
import base64
import audioop
from typing import Optional, Dict, Any
from datetime import datetime
from enum import Enum

import aiohttp

from app.core.config import settings
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

        # Deepgram streaming STT (persistent connection for the call)
        self._dg_http: Optional[aiohttp.ClientSession] = None
        self._dg_ws = None
        self._dg_recv_task: Optional[asyncio.Task] = None
        self._dg_ready = False
        self._utterance_parts: list[str] = []
        self._turn_lock = asyncio.Lock()
        self._welcome_sent = False

        # A telephony action (transfer/hang_up/dtmf/voicemail) that must run
        # AFTER the agent has spoken its confirmation, since executing it ends
        # or replaces the live media stream.
        self._pending_telephony: Optional[Dict[str, Any]] = None

        # Set while a workflow `ask` step is waiting on the caller's next
        # utterance; the transcript handler resolves it instead of running a
        # normal LLM turn. None means normal conversation.
        self._awaiting_reply: Optional[asyncio.Future] = None

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

            # Note: the welcome message and Deepgram STT stream are started from
            # _handle_start, once Twilio has sent the "start" event and we know
            # the stream_sid — sending media before that has no valid target.

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

        # Open the Deepgram STT stream now that the media stream is live, then
        # greet the caller. Both are deferred here (not in start()) because they
        # need a live stream_sid to be useful.
        await self._start_deepgram()

        if not self._welcome_sent:
            self._welcome_sent = True
            welcome_message = (
                self.agent.first_message
                or f"Hello! This is {self.agent.name}. How can I help you today?"
            )
            await self._send_welcome_message(welcome_message)

    async def _handle_media(self, message: dict) -> None:
        """
        Handle media event (audio data from caller).

        Twilio sends audio as base64-encoded mulaw at 8kHz. We decode it and
        forward the raw mulaw bytes straight to Deepgram, which accepts mulaw
        natively — no local transcription/format work needed on the way in.

        Args:
            message: Media event message
        """
        media_data = message.get("media", {})
        payload = media_data.get("payload")

        if not payload:
            return

        self.metrics["audio_chunks_received"] += 1

        try:
            audio_bytes = base64.b64decode(payload)
            if self._dg_ws is not None and not self._dg_ws.closed:
                await self._dg_ws.send_bytes(audio_bytes)
        except Exception as e:
            logger.error(f"Error forwarding media to Deepgram: {e}")

    async def _start_deepgram(self) -> None:
        """
        Open a persistent Deepgram streaming-STT connection for this call.

        Twilio inbound media is mulaw at 8kHz, which Deepgram accepts natively,
        so we point Deepgram at that encoding and forward bytes as they arrive.
        A background task reads transcripts and drives the conversation turn.
        """
        if self._dg_ws is not None:
            return  # already started

        api_key = getattr(settings, "DEEPGRAM_API_KEY", None)
        if not api_key:
            logger.error("DEEPGRAM_API_KEY not configured — cannot transcribe call audio")
            return

        model = self.agent.stt_model or "nova-2"
        language = self.agent.stt_language or "en"
        dg_url = (
            "wss://api.deepgram.com/v1/listen"
            f"?model={model}"
            f"&language={language}"
            "&encoding=mulaw"
            "&sample_rate=8000"
            "&channels=1"
            "&interim_results=true"
            "&punctuate=true"
            "&endpointing=300"
            "&utterance_end_ms=1000"
        )

        try:
            self._dg_http = aiohttp.ClientSession()
            self._dg_ws = await self._dg_http.ws_connect(
                dg_url,
                headers={"Authorization": f"Token {api_key}"},
            )
            self._dg_ready = True
            self._dg_recv_task = asyncio.create_task(self._deepgram_receiver())
            logger.info(f"Deepgram STT stream opened: call_id={self.call_id}")
        except Exception as e:
            logger.error(f"Failed to open Deepgram stream: {e}", exc_info=True)
            self._dg_ready = False
            if self._dg_http is not None:
                await self._dg_http.close()
                self._dg_http = None
            self._dg_ws = None

    async def _deepgram_receiver(self) -> None:
        """
        Read transcripts from Deepgram and trigger a conversation turn when the
        caller finishes an utterance. Interim results accumulate; a final result
        with speech_final (or an UtteranceEnd) closes the turn.
        """
        try:
            async for msg in self._dg_ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    data = json.loads(msg.data)
                    msg_type = data.get("type")

                    if msg_type == "Results":
                        alts = data.get("channel", {}).get("alternatives", [{}])
                        transcript = alts[0].get("transcript", "") if alts else ""
                        is_final = data.get("is_final", False)
                        speech_final = data.get("speech_final", False)

                        if transcript and is_final:
                            self._utterance_parts.append(transcript)
                            self.metrics["transcriptions"] += 1

                        if speech_final and self._utterance_parts:
                            utterance = " ".join(self._utterance_parts).strip()
                            self._utterance_parts = []
                            if utterance:
                                asyncio.create_task(self._handle_caller_utterance(utterance))

                    elif msg_type == "UtteranceEnd":
                        if self._utterance_parts:
                            utterance = " ".join(self._utterance_parts).strip()
                            self._utterance_parts = []
                            if utterance:
                                asyncio.create_task(self._handle_caller_utterance(utterance))

                elif msg.type in (aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.ERROR):
                    break

        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"Deepgram receiver error: {e}", exc_info=True)

    async def _handle_caller_utterance(self, utterance: str) -> None:
        """
        Process one complete caller utterance, serialised so overlapping final
        transcripts can't start two LLM turns at once.
        """
        # If a workflow `ask` step is waiting on the caller, this utterance is
        # its answer — hand it over instead of starting a normal LLM turn.
        fut = getattr(self, "_awaiting_reply", None)
        if fut is not None and not fut.done():
            self._awaiting_reply = None
            fut.set_result(utterance)
            await self._log_transcript_entry("user", utterance)
            return

        if self._turn_lock.locked():
            # A turn is already in flight; fold this utterance into the next one
            # rather than interleaving two responses.
            self._utterance_parts.insert(0, utterance)
            return
        async with self._turn_lock:
            await self._process_utterance(utterance)

    async def _handle_stop(self, message: dict) -> None:
        """
        Handle stream stop event.

        Args:
            message: Stop event message
        """
        logger.info(f"Stream stopped: call_id={self.call_id}")
        self.state = SessionState.ENDED
        await self._close_deepgram()

    async def _close_deepgram(self) -> None:
        """Tear down the Deepgram stream and its receiver task."""
        if self._dg_recv_task is not None:
            self._dg_recv_task.cancel()
            try:
                await self._dg_recv_task
            except (asyncio.CancelledError, Exception):
                pass
            self._dg_recv_task = None
        if self._dg_ws is not None:
            try:
                await self._dg_ws.close()
            except Exception:
                pass
            self._dg_ws = None
        if self._dg_http is not None:
            try:
                await self._dg_http.close()
            except Exception:
                pass
            self._dg_http = None
        self._dg_ready = False

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

                # Now that the confirmation has been spoken, run any deferred
                # call-control action (transfer/hang_up/dtmf/voicemail).
                await self._run_pending_telephony()

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
                inner = result.get("result", {}) if result.get("success") else {}
                if isinstance(inner, dict) and inner.get("requires_telephony"):
                    # Telephony action — execute against the live call rather than
                    # just handing the intent back to the LLM as text.
                    formatted_result = await self._handle_telephony_tool(inner)
                elif result.get("success"):
                    formatted_result = f"Tool {matched_tool.name} returned: {json.dumps(inner)}"
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

    # ── Telephony actions ────────────────────────────────────────────────────

    def _caller_number(self) -> Optional[str]:
        """The caller's number, accounting for call direction."""
        if getattr(self.call, "direction", "inbound") == "outbound":
            return self.call.to_number
        return self.call.from_number

    def _agent_number(self) -> Optional[str]:
        """Our Twilio number for this call, accounting for direction."""
        if getattr(self.call, "direction", "inbound") == "outbound":
            return self.call.from_number
        return self.call.to_number

    def _resolve_number(self, value: Optional[str]) -> Optional[str]:
        """Substitute number templates like {{caller_number}}."""
        if not value:
            return value
        v = value.strip()
        if "{{caller_number}}" in v:
            v = v.replace("{{caller_number}}", self._caller_number() or "")
        if v in ("caller", "caller_number"):
            v = self._caller_number() or ""
        return v.strip() or None

    async def _handle_telephony_tool(self, inner: Dict[str, Any]) -> str:
        """
        Route a telephony tool result to a real action.

        SMS is sent immediately (it does not affect the live call). Call-control
        actions (transfer/hang_up/dtmf/voicemail) are deferred until after the
        agent speaks its confirmation, because executing them ends or replaces
        the media stream — see _run_pending_telephony.
        """
        action = inner.get("action")
        cfg = inner.get("config", {}) or {}
        params = inner.get("parameters", {}) or {}

        if action == "send_sms":
            to_number = self._resolve_number(params.get("to") or cfg.get("to")) or self._caller_number()
            body = params.get("message") or cfg.get("message") or ""
            if not to_number:
                return "Could not send the text: no recipient number available."
            if not body:
                return "Could not send the text: no message content provided."
            try:
                svc = self._get_twilio()
                res = await svc.send_sms(
                    to_number=to_number, body=body, from_number=self._agent_number()
                )
            except Exception as e:
                logger.error(f"send_sms failed: {e}")
                return f"The text message could not be sent ({e})."
            if res.get("success"):
                return f"Text message sent to {to_number}. Confirm this to the caller."
            return f"The text message failed to send: {res.get('error', 'unknown error')}."

        if action in ("transfer_call", "hang_up", "dtmf", "leave_voicemail"):
            # Defer until the confirmation has been spoken.
            self._pending_telephony = {"action": action, "config": cfg, "parameters": params}
            hints = {
                "transfer_call": "You are about to transfer the caller. Tell them you're connecting them now, in one short sentence.",
                "hang_up": "You are about to end the call. Say a brief, polite goodbye.",
                "dtmf": "You are about to send the requested tones. Acknowledge briefly.",
                "leave_voicemail": "You are about to leave the message. Acknowledge briefly.",
            }
            return hints.get(action, "Acknowledge the request briefly.")

        return f"Telephony action '{action}' is not supported."

    def _get_twilio(self):
        """Lazily get the Twilio service (raises if creds are unconfigured)."""
        from app.services.telephony.twilio_service import get_twilio_service
        return get_twilio_service()

    async def _run_pending_telephony(self) -> None:
        """Execute a deferred call-control action after the agent has spoken."""
        pending = self._pending_telephony
        if not pending:
            return
        self._pending_telephony = None

        action = pending["action"]
        cfg = pending.get("config", {})
        params = pending.get("parameters", {})

        if not self.call_sid:
            logger.error(f"Cannot run telephony action '{action}': no live call_sid")
            return

        try:
            svc = self._get_twilio()
            if action == "transfer_call":
                dest = self._resolve_number(params.get("destination") or cfg.get("destination"))
                if not dest:
                    logger.error("transfer_call: no destination configured")
                    return
                await svc.transfer_call(self.call_sid, dest)
            elif action == "hang_up":
                await svc.hang_up(self.call_sid)
            elif action == "dtmf":
                digits = params.get("digits") or cfg.get("digits") or ""
                if digits:
                    await svc.send_dtmf(self.call_sid, digits)
            elif action == "leave_voicemail":
                message = params.get("message") or cfg.get("message") or ""
                if message:
                    await svc.leave_voicemail(self.call_sid, message)
            logger.info(f"Executed telephony action '{action}' on call {self.call_sid}")
        except Exception as e:
            logger.error(f"Failed to execute telephony action '{action}': {e}", exc_info=True)

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

            # Request Twilio-native audio (8kHz mulaw) straight from the provider
            # so no local decoding/resampling is needed. ElevenLabs supports
            # "ulaw_8000"; other providers fall back through _to_twilio_mulaw.
            tts_kwargs = {"text": text, "provider": provider, "voice_id": voice_id}
            if provider == "elevenlabs":
                tts_kwargs["output_format"] = "ulaw_8000"

            # Reframe the provider's byte stream into 20ms (160-byte) mulaw frames,
            # which is what Twilio expects for smooth playback.
            frame = bytearray()
            chunk_count = 0
            async for audio_chunk in self.tts_service.synthesize_stream(**tts_kwargs):
                mulaw = self._to_twilio_mulaw(audio_chunk, provider)
                if not mulaw:
                    continue
                frame.extend(mulaw)
                while len(frame) >= 160:
                    await self._send_audio_to_twilio(bytes(frame[:160]))
                    del frame[:160]
                    chunk_count += 1

            if frame:
                await self._send_audio_to_twilio(bytes(frame))
                chunk_count += 1

            self.metrics["tts_generations"] += 1

            # Mark end of speech
            await self._send_mark("speech_end")

            logger.info(f"Sent audio response: {chunk_count} frames")

        except Exception as e:
            logger.error(f"Error speaking response: {e}", exc_info=True)

        finally:
            self.state = SessionState.LISTENING

    def _to_twilio_mulaw(self, audio_data: bytes, provider: str) -> bytes:
        """
        Ensure audio is 8kHz mulaw for Twilio.

        For ElevenLabs we request "ulaw_8000", so the bytes are already correct
        and pass through untouched. For any provider that returns 16-bit PCM we
        convert with audioop (used as a safety net). MP3 is not decodable here,
        so a non-mulaw provider without PCM output should be configured to emit
        ulaw/PCM upstream.
        """
        if not audio_data:
            return b""
        if provider == "elevenlabs":
            return audio_data  # already ulaw_8000
        # Best-effort PCM (linear16) -> mulaw fallback for other providers.
        try:
            pcm8k, _ = audioop.ratecv(audio_data, 2, 1, 16000, 8000, None)
            return audioop.lin2ulaw(pcm8k, 2)
        except Exception:
            # Unknown/undecodable format (e.g. MP3): pass through rather than crash.
            return audio_data

    async def _send_audio_to_twilio(self, audio_data: bytes) -> None:
        """
        Send one frame of 8kHz mulaw audio to Twilio as a base64 media event.

        Args:
            audio_data: mulaw 8kHz audio bytes (already Twilio-ready)
        """
        try:
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

            # Close the Deepgram STT stream first so no more turns are triggered.
            await self._close_deepgram()

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

            # Fire any workflows the user hooked to "call completed". Never let a
            # workflow problem surface as a call teardown failure.
            await self._fire_call_completed_workflows(duration)

        except Exception as e:
            logger.error(f"Error cleaning up session: {e}", exc_info=True)

    # ── Workflow-driven conversation API ─────────────────────────────────────
    # These back the VoiceChannel in services/workflows/channels.py, letting a
    # workflow drive a live call. They're thin wrappers over the session's own
    # machinery so a flow speaks/listens exactly like a normal turn does.

    async def speak(self, text: str) -> None:
        """Speak a line to the caller (used by workflow `speak` steps)."""
        await self._speak_response(text)

    async def wait_for_user_reply(self, timeout: int = 10) -> Optional[str]:
        """
        Wait for the caller's next complete utterance.

        Returns None on timeout so a workflow `ask` step can move on rather than
        hanging the call forever.
        """
        loop = asyncio.get_running_loop()
        fut: asyncio.Future = loop.create_future()
        self._awaiting_reply = fut
        try:
            return await asyncio.wait_for(fut, timeout=timeout)
        except asyncio.TimeoutError:
            logger.info(f"No caller reply within {timeout}s")
            return None
        finally:
            if getattr(self, "_awaiting_reply", None) is fut:
                self._awaiting_reply = None

    async def transfer_call(self, destination: str, transfer_type: str = "blind") -> None:
        """Transfer the live call (used by workflow `transfer` steps)."""
        svc = self._get_twilio()
        await svc.transfer_call(self.call_sid, destination)

    async def end_call(self) -> None:
        """Hang up the live call (used by workflow `end` steps)."""
        svc = self._get_twilio()
        await svc.hang_up(self.call_sid)

    async def _fire_call_completed_workflows(self, duration: float) -> None:
        """
        Dispatch the `call_completed` event to the workflow engine.

        Post-call workflows (push the transcript to a CRM, send a follow-up SMS,
        …) hang off this. Runs on its own DB session and swallows its own errors:
        the call is already over, and a broken workflow must not break teardown.
        """
        try:
            from app.database import AsyncSessionLocal
            from app.services.workflows.trigger_handlers import get_trigger_manager

            event_data = {
                "call_id": str(self.call.id),
                "agent_id": str(self.call.agent_id) if self.call.agent_id else None,
                "status": self.call.status,
                "duration": int(duration),
                "phone_number": getattr(self.call, "from_number", None) or "",
                "to_number": getattr(self.call, "to_number", None) or "",
                "direction": getattr(self.call, "direction", None),
                "transcript": self.transcript_entries,
                "ended_at": self.call.ended_at.isoformat() if self.call.ended_at else None,
            }

            async with AsyncSessionLocal() as db:
                manager = get_trigger_manager(db)
                executions = await manager.process_event("call_completed", event_data)

            if executions:
                logger.info(
                    f"call_completed triggered {len(executions)} workflow(s) "
                    f"for call {self.call_id}"
                )
        except Exception as e:
            logger.error(
                f"Failed to dispatch call_completed workflows for call "
                f"{self.call_id}: {e}",
                exc_info=True,
            )
