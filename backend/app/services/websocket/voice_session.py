"""
Voice Session Handler for Twilio Media Streams.

Handles real-time voice processing: STT → LLM → TTS with Twilio WebSocket.
"""
import logging
import asyncio
import json
import base64
import audioop
from collections import deque
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum

import aiohttp

from app.core.config import settings
from app.services.voice.stt_service import get_stt_service
from app.services.voice.tts_service import get_tts_service
from app.services.voice.voice_library import resolve_tts_api_key
from app.services.voice.guardrails import VOICE_RULES, strip_for_speech
from app.services.voice.conversation_context import current_time_note, normalize_spoken_emails
from app.services.voice.turn_taking import (
    extra_wait_seconds,
    is_backchannel,
    is_echo,
    pop_sentences,
    speech_units,
    word_count,
)
from app.services.voice import languages
from app.services.voice.llm_service import get_llm_service, ConversationContext, cap_stream
from app.services.voice.providers.base import ChatMessage
from app.services.workflows.channels import VoiceChannel
from app.services.websocket.connection_manager import ConnectionManager
from app.services.call.transcript_service import get_transcript_service, TranscriptEntry
from app.services.call.analytics_service import get_analytics_service
from app.services.function_executor import get_function_executor, sanitize_function_name
from app.models.agent import Agent, AgentFunction
from app.models.tool import Tool
from app.models.call import Call, CallLog
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.time import utc_iso

logger = logging.getLogger(__name__)

#: Seconds of total silence before the agent asks "Are you still there?";
#: a second unanswered stretch ends the call.
SILENCE_CHECK_IN_SECONDS = 15.0

#: How long after the agent stops being audible its own words can still come
#: back as speakerphone echo (line delay plus transcription lag).
ECHO_TAIL_SECONDS = 1.0

#: How far back in the agent's speech an echo is looked for, in words.
ECHO_WINDOW_WORDS = 30

#: After a draft reply is discarded, how long past the caller's usual pause to
#: wait for the rest of their sentence before answering what there is.
CARRY_FLUSH_SECONDS = 2.5

#: After pausing for a sound from the caller, how long to wait for words
#: before deciding it was not an interruption and carrying on.
PAUSE_CONFIRM_SECONDS = 1.2

#: Pauses that turn out to be nothing (line noise, echo) before the agent
#: stops pausing on sound alone for the rest of the call.
MAX_FALSE_PAUSES = 2

#: Slack on top of the estimated playback time before giving up on Twilio's
#: "finished playing" mark.
PLAYBACK_GRACE_SECONDS = 1.5

#: Spoken when the model returns nothing, so the caller is not left in silence.
#: The English wording; a call says it in the agent's language (see
#: ``VoiceSession._line``).
NO_REPLY_MESSAGE = languages.phrase("no_reply", "en")


class SessionState(str, Enum):
    """Voice session states."""
    INITIALIZING = "initializing"
    READY = "ready"
    LISTENING = "listening"
    PROCESSING = "processing"
    SPEAKING = "speaking"
    ENDED = "ended"
    ERROR = "error"


@dataclass
class _Segment:
    """
    One piece of agent speech: its audio, and where the caller is in it.

    The audio is kept so that playback can be paused when the caller makes a
    sound and picked up from the same point if it was not an interruption.
    `base` is the byte offset playback last (re)started from, `start` the
    loop time it did so (None while stopped), `sent` how far the carrier has
    been given.
    """
    text: str
    audio: bytearray = field(default_factory=bytearray)
    sent: int = 0
    base: int = 0
    start: Optional[float] = None
    stopped_at: float = 0.0
    #: Cut off for good by an interruption; never resumed.
    dropped: bool = False

    def played_bytes(self, now: float) -> int:
        if self.start is None:
            return self.base
        elapsed = int(max(now - self.start, 0.0) * 8000)
        return self.base + min(elapsed, self.sent - self.base)

    def end(self) -> float:
        """Loop time at which what has been sent finishes (or was stopped)."""
        if self.start is None:
            return self.stopped_at
        return self.start + (self.sent - self.base) / 8000

    def played_words(self, now: float, slack: int = 0) -> List[str]:
        # Pieces of roughly equal length to say, in any script: splitting on
        # spaces made a whole Chinese or Japanese sentence one "word".
        words = speech_units(self.text)
        if not self.audio:
            return []
        played = self.played_bytes(now)
        if played >= len(self.audio):
            return words
        return words[: int(len(words) * played / len(self.audio)) + slack]


@dataclass
class _Turn:
    """
    One reply to the caller, from end of speech to end of playback.

    A turn is a draft until it is `committed` — the moment it first speaks or
    runs a tool. Until then the caller carrying on talking simply discards it,
    and their words are answered together as one turn.
    """
    gen: int
    text: str
    #: Loop time before which the turn may think but not act.
    hold_until: float
    committed: bool = False
    reply_started: bool = False
    interrupted: bool = False
    tools_ran: bool = False
    #: LLM text not yet cut into sentences.
    buffer: str = ""
    #: Every sentence of the reply, spoken or not.
    reply: List[str] = field(default_factory=list)
    segments: List[_Segment] = field(default_factory=list)
    #: What the caller actually heard, set when they interrupt.
    heard: Optional[str] = None


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
        self._tts_key: Optional[str] = None
        self._tts_key_resolved = False
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

        # Silence watchdog: nothing on a real call used to notice a caller
        # who stopped talking — the line stayed open until Twilio's own
        # max_call_duration limit. Tracks the last time the caller (or the
        # agent) said anything, so a background task can check in and, if
        # that goes unanswered too, hang up (M10).
        self._last_activity = datetime.utcnow()
        self._silence_task: Optional[asyncio.Task] = None
        self._silence_checkins = 0

        # Ends the call at the agent's max_call_duration (nothing did before;
        # only the browser test enforced it).
        self._max_duration_task: Optional[asyncio.Task] = None

        # Pay As You Go: ends the call when the credit reserved for it runs
        # out and no more can be reserved. Does nothing on other plans.
        self._balance_task: Optional[asyncio.Task] = None

        # Barge-in. Audio is streamed to Twilio faster than real time, so it
        # keeps playing from Twilio's buffer after _speak_response returns:
        # `_playing` stays true until Twilio has echoed back the mark that
        # follows every piece of speech still in that buffer.
        # `_interrupted` stops the frame loop when the caller talks over it.
        self._playing = False
        self._interrupted = False
        self._mark_seq = 0
        self._pending_marks: set[str] = set()
        # Loop time at which everything sent so far will have been played.
        self._playback_cursor = 0.0
        # What the agent said most recently, to recognise its own echo.
        self._recent_speech: deque[_Segment] = deque(maxlen=6)
        # One writer to the carrier at a time: a resume must not interleave
        # with a sentence still being synthesized.
        self._audio_lock = asyncio.Lock()
        # Paused: the caller made a sound over the agent. Audio is kept, not
        # sent, until it proves to be an interruption (dropped) or not
        # (resumed from where it stopped).
        self._held = False
        self._held_timer: Optional[asyncio.Task] = None
        self._held_heard_words = False
        self._false_pauses = 0
        self._echo_hits = 0
        # The agent's last full line, which decides how patiently to wait
        # for the answer (a phone number takes longer than a yes).
        self._last_agent_text = ""

        # Utterances that finished while a turn was in flight, answered as one
        # turn as soon as it ends.
        self._pending_utterances: list[str] = []

        # The turn being answered. Bumping `_turn_gen` discards it while it
        # is still a draft; its words wait in `_carry` to be answered
        # together with whatever the caller says next.
        self._turn: Optional[_Turn] = None
        self._turn_gen = 0
        self._carry = ""
        self._carry_timer: Optional[asyncio.Task] = None
        # Loop time the caller last stopped speaking.
        self._last_eos = 0.0
        self._tasks: set[asyncio.Task] = set()

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
            system_prompt = (self.agent.system_prompt or "You are a helpful AI assistant.") + VOICE_RULES
            # The agent is otherwise never told today's date.
            system_prompt += await current_time_note(self.db, self.agent)
            # The agent's language. It reached speech recognition only, so an
            # agent set to Spanish was never told to answer in Spanish.
            system_prompt += languages.language_instruction(self._language)
            end_call_phrases = list(self.agent.end_call_phrases or [])
            if end_call_phrases:
                phrases_str = ", ".join(f'"{p}"' for p in end_call_phrases)
                system_prompt += (
                    f"\n\nWhen the caller wants to end the conversation or says goodbye, "
                    f"respond warmly and use one of these exact phrases to end: {phrases_str}."
                )
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

        # Update call record. The media stream starting *is* the call being
        # answered: audio is flowing and the agent is about to speak. Carriers
        # do not reliably say so — Twilio sends an inbound number no "answered"
        # callback at all, only the final one — so an inbound call sat at
        # "ringing" for its whole length and never counted as an active call.
        if self.call_sid:
            self.call.provider_call_sid = self.call_sid
        now = datetime.utcnow()
        if self.call.status in (None, "initiated", "ringing"):
            self.call.status = "in_progress"
        if not self.call.started_at:
            self.call.started_at = self.call.created_at or now
        if not self.call.answered_at:
            self.call.answered_at = now
        await self.db.commit()

        # Open the Deepgram STT stream now that the media stream is live, then
        # greet the caller. Both are deferred here (not in start()) because they
        # need a live stream_sid to be useful.
        await self._start_deepgram()

        if not self._welcome_sent:
            self._welcome_sent = True
            # The customer's own greeting as written; the editor's untouched
            # default, or none at all, in the agent's language.
            welcome_message = languages.spoken_greeting(
                self.agent.first_message, self._language, self.agent.name
            )
            # As a task: awaited here it held up this receive loop, so nothing
            # the caller said during the greeting reached Deepgram until the
            # greeting had been sent.
            self._spawn(self._greet(welcome_message))

        self._last_activity = datetime.utcnow()
        if self._silence_task is None:
            self._silence_task = asyncio.create_task(self._silence_watchdog())
        if self._max_duration_task is None:
            self._max_duration_task = asyncio.create_task(self._max_duration_guard())
        if getattr(self, "_balance_task", None) is None:
            self._balance_task = asyncio.create_task(self._balance_guard())

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

        from app.services.voice.stt_service import deepgram_keyword_params, deepgram_turn_params

        language = languages.canonical(self._language)
        # A model the provider does not offer in this language is refused at
        # connect, and the call then runs with no transcription at all.
        model = languages.resolve_stt_model(self.agent.stt_model, language)
        dg_url = (
            "wss://api.deepgram.com/v1/listen"
            f"?model={model}"
            f"&language={language}"
            "&encoding=mulaw"
            "&sample_rate=8000"
            "&channels=1"
            "&interim_results=true"
            "&punctuate=true"
            # SpeechStarted: the caller's voice is reported a fraction of a
            # second in, long before the first words are transcribed.
            "&vad_events=true"
            # The agent's Silence Timeout: how long the caller must pause
            # before their turn ends. Was a fixed 300ms that ignored it.
            f"{deepgram_turn_params(self.agent.silence_timeout)}"
            f"{deepgram_keyword_params(model, self.agent.stt_keywords)}"
        )

        try:
            self._dg_http = aiohttp.ClientSession()
            self._dg_ws = await self._dg_http.ws_connect(
                dg_url,
                headers={"Authorization": f"Token {api_key}"},
            )
            self._dg_ready = True
            self._dg_recv_task = asyncio.create_task(self._deepgram_receiver())
            logger.info(
                f"Deepgram STT stream opened: call_id={self.call_id}, "
                f"model={model}, language={language}"
            )
        except Exception as e:
            logger.error(
                f"Failed to open Deepgram stream (model={model}, language={language}): {e}",
                exc_info=True,
            )
            self._dg_ready = False
            if self._dg_http is not None:
                await self._dg_http.close()
                self._dg_http = None
            self._dg_ws = None

    async def _deepgram_receiver(self) -> None:
        """Read Deepgram's messages for the length of the call."""
        try:
            async for msg in self._dg_ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    await self._on_deepgram_message(json.loads(msg.data))
                elif msg.type in (aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.ERROR):
                    break

        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"Deepgram receiver error: {e}", exc_info=True)

    async def _on_deepgram_message(self, data: dict) -> None:
        """
        Act on one transcript message. Final results accumulate; speech_final
        (or an UtteranceEnd) closes the caller's turn. Every result with words
        in it, interim included, counts as the caller speaking.
        """
        msg_type = data.get("type")

        if msg_type == "Results":
            alts = data.get("channel", {}).get("alternatives", [{}])
            transcript = alts[0].get("transcript", "") if alts else ""
            is_final = data.get("is_final", False)
            speech_final = data.get("speech_final", False)

            if transcript and self._is_own_echo(transcript):
                # The agent's voice coming back down the line: not the
                # caller, so it neither interrupts nor becomes a turn.
                logger.info(f"Treated as the agent's own echo: {transcript!r}: call_id={self.call_id}")
                if is_final:
                    self._echo_hits += 1
            elif transcript:
                await self._on_caller_speech(transcript)
                if is_final:
                    self._utterance_parts.append(transcript)
                    self.metrics["transcriptions"] += 1

            if speech_final:
                self._end_of_speech()

        elif msg_type == "UtteranceEnd":
            self._end_of_speech()

        elif msg_type == "SpeechStarted":
            await self._on_speech_started()

    def _spawn(self, coro) -> asyncio.Task:
        """Run a coroutine in the background, keeping a reference so it is
        not garbage-collected mid-flight and its failure is logged."""
        task = asyncio.create_task(coro)
        self._tasks.add(task)

        def _done(t: asyncio.Task) -> None:
            self._tasks.discard(t)
            if not t.cancelled() and t.exception() is not None:
                logger.error(f"Voice session task failed: {t.exception()}", exc_info=t.exception())

        task.add_done_callback(_done)
        return task

    def _audible(self) -> bool:
        """Whether the caller can hear the agent right now.

        Judged first by how much audio has been sent: 8,000 bytes is one
        second, whatever the carrier does with marks. A mark still
        outstanding extends that a little, for audio delayed on the way."""
        now = asyncio.get_running_loop().time()
        if now < self._playback_cursor:
            return True
        return self._playing and now < self._playback_cursor + PLAYBACK_GRACE_SECONDS

    def _is_own_echo(self, transcript: str) -> bool:
        """The agent's own words picked up by the caller's microphone (a
        speakerphone), rather than the caller speaking. Only what has just
        been played can echo — not words the agent has yet to say."""
        now = asyncio.get_running_loop().time()
        played: List[str] = []
        for seg in self._recent_speech:
            if seg.end() + ECHO_TAIL_SECONDS <= now:
                continue
            # A few words of slack: the timeline is an estimate.
            played.extend(seg.played_words(now, slack=3))
        return bool(played) and is_echo(transcript, " ".join(played[-ECHO_WINDOW_WORDS:]))

    async def _on_speech_started(self) -> None:
        """
        Deepgram heard a voice begin — a fraction of a second in, well before
        any words. If the agent is talking, stop talking at once and listen.

        Whether it was an interruption is decided by the words that follow:
        enough of them and the rest of the reply is dropped; a cough, an
        "mm-hm" or nothing at all and the agent carries on from where it
        stopped. Waiting for the words before stopping left the agent
        talking over the caller for one to two seconds.
        """
        if not self.agent.interrupt_enabled or self._held:
            return
        if self._false_pauses >= MAX_FALSE_PAUSES or not self._audible():
            return
        await self._stop_audio(drop=False)
        self._held_heard_words = False
        self._restart_held_timer()
        logger.info(f"Caller made a sound; agent paused: call_id={self.call_id}")

    def _restart_held_timer(self) -> None:
        if self._held_timer is not None:
            self._held_timer.cancel()

        async def _expire() -> None:
            await asyncio.sleep(PAUSE_CONFIRM_SECONDS)
            self._held_timer = None
            await self._resume_playback()

        self._held_timer = asyncio.create_task(_expire())

    async def _stop_audio(self, drop: bool) -> None:
        """
        Silence the agent now: note how far each piece of speech had played,
        and have the carrier discard what it has buffered.

        Args:
            drop: The rest is abandoned (an interruption). Otherwise it is
                held, to be resumed by _resume_playback.
        """
        async with self._audio_lock:
            now = asyncio.get_running_loop().time()
            for seg in self._recent_speech:
                if seg.dropped:
                    continue
                played = seg.played_bytes(now) // 160 * 160
                if played >= len(seg.audio) and seg.start is not None and seg.end() <= now:
                    continue  # already heard in full
                seg.base = seg.sent = played
                seg.start = None
                seg.stopped_at = now
                seg.dropped = drop
            self._held = not drop
            self._playing = False
            self._pending_marks.clear()
            self._playback_cursor = now
            if self.stream_sid:
                try:
                    await self.connection_manager.send_json(
                        self.call_id, {"event": "clear", "streamSid": self.stream_sid}
                    )
                except Exception as e:
                    logger.error(f"Failed to clear carrier audio: {e}")

    async def _resume_playback(self) -> None:
        """Carry on from where the agent paused: the sound was not an
        interruption."""
        if self._held_timer is not None and self._held_timer is not asyncio.current_task():
            self._held_timer.cancel()
        self._held_timer = None
        async with self._audio_lock:
            if not self._held:
                return
            self._held = False
            if not self._held_heard_words:
                # Nothing was said: noise or echo. A line that keeps doing
                # this would make the agent stutter, so stop pausing on it.
                self._false_pauses += 1
            loop = asyncio.get_running_loop()
            resent = 0
            for seg in self._recent_speech:
                if seg.dropped or seg.sent >= len(seg.audio):
                    continue
                seg.start = max(loop.time(), self._playback_cursor)
                rest = bytes(seg.audio[seg.sent:])
                for i in range(0, len(rest), 1600):
                    await self._send_audio_to_twilio(rest[i:i + 1600])
                seg.sent = len(seg.audio)
                resent += len(rest)
                self._playback_cursor = seg.end()
            if resent:
                self._mark_seq += 1
                mark = f"speech-{self._mark_seq}"
                self._pending_marks.add(mark)
                self._playing = True
                await self._send_mark(mark)
        logger.info(
            f"Not an interruption; agent resumed ({resent / 8000:.1f}s left): call_id={self.call_id}"
        )

    async def _on_caller_speech(self, transcript: str) -> None:
        """
        The caller is talking (any transcript with words, interim included).

        If the reply in flight is still a draft, drop it: they had only
        paused, and the rest of the sentence belongs to the same turn. If the
        agent is already audible, this is an interruption instead.
        """
        self._last_activity = datetime.utcnow()
        self._silence_checkins = 0

        turn = self._turn
        if turn is not None and not turn.committed and turn.gen == self._turn_gen:
            self._turn_gen += 1
            self._carry = turn.text
            logger.info(f"Caller carried on speaking; reply discarded: call_id={self.call_id}")
        elif self._should_barge_in(transcript):
            await self._barge_in()
        elif self._held:
            self._held_heard_words = True
            if is_backchannel(" ".join(self._utterance_parts + [transcript])):
                # "Mm-hm": they are listening, not interrupting. Carry on.
                await self._resume_playback()
            else:
                # Words, but not yet enough to count: keep listening.
                self._restart_held_timer()
        elif self._audible():
            # Heard over the agent but not acted on. Logged because "the
            # agent would not stop" is otherwise impossible to diagnose.
            heard = " ".join(self._utterance_parts + [transcript])
            logger.info(
                f"Caller spoke over the agent without interrupting: {heard!r} "
                f"({word_count(heard)} words, {self._interrupt_min_words()} needed, "
                f"interruptions {'on' if self.agent.interrupt_enabled else 'OFF'}): "
                f"call_id={self.call_id}"
            )

        if self._carry:
            self._restart_carry_timer()

    def _restart_carry_timer(self) -> None:
        """Answer a discarded turn's words even if nothing follows them — the
        sound that discarded it may have been a cough Deepgram never turns
        into a final transcript."""
        if self._carry_timer is not None:
            self._carry_timer.cancel()
        wait = max(int(self.agent.silence_timeout or 1000), 300) / 1000 + CARRY_FLUSH_SECONDS

        async def _flush() -> None:
            await asyncio.sleep(wait)
            self._carry_timer = None
            self._end_of_speech()

        self._carry_timer = asyncio.create_task(_flush())

    def _end_of_speech(self) -> None:
        """The caller has stopped: hand everything they said to a turn."""
        if self._held:
            # They finished without saying enough to interrupt.
            self._spawn(self._resume_playback())
        utterance = " ".join([self._carry] + self._utterance_parts).strip()
        if not utterance:
            return
        self._carry = ""
        self._utterance_parts = []
        if self._carry_timer is not None and self._carry_timer is not asyncio.current_task():
            self._carry_timer.cancel()
        self._carry_timer = None
        self._last_eos = asyncio.get_running_loop().time()
        self._spawn(self._handle_caller_utterance(utterance))

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

        # "Mm-hm" while the agent is talking is listening, not a turn;
        # answering it made the agent stop and start over.
        if (self._audible() or self._held) and is_backchannel(utterance):
            logger.info(f"Ignored a listening noise over the agent: {utterance!r}")
            return

        # Whoever holds the lock (a turn, the greeting, a check-in) finishes
        # first; then everything said meanwhile is answered as one turn,
        # rather than interleaving two responses.
        self._pending_utterances.append(utterance)
        async with self._turn_lock:
            while self._pending_utterances and self.state != SessionState.ENDED:
                queued = " ".join(self._pending_utterances).strip()
                self._pending_utterances = []
                if queued:
                    await self._process_utterance(queued)

    def _should_barge_in(self, transcript: str) -> bool:
        """The caller is talking over audible agent speech, with interruptions
        on and enough words said to clear the agent's Interrupt Sensitivity."""
        if not self.agent.interrupt_enabled or self._interrupted:
            return False
        if not (self._audible() or self._held or self.state == SessionState.SPEAKING):
            return False
        heard = " ".join(self._utterance_parts + [transcript])
        return word_count(heard) >= self._interrupt_min_words()

    def _interrupt_min_words(self) -> int:
        """1 word at full sensitivity, 3 at zero — so a cough or an "mm-hm"
        doesn't cut the agent off. Same rule as the browser test panel. One
        more word is needed on a line that has been echoing the agent back."""
        raw = self.agent.interrupt_sensitivity
        sensitivity = float(raw) if raw is not None else 0.5
        words = max(1, round(3 - 2 * sensitivity))
        return words + 1 if self._echo_hits >= 2 else words

    @staticmethod
    def _heard_text(segments: List[_Segment], now: float) -> str:
        """The part of a reply that had been played by `now`."""
        parts = []
        for seg in segments:
            words = seg.played_words(now)
            if len(words) == len(speech_units(seg.text)) and seg.audio:
                parts.append(seg.text)
                continue
            if words:
                parts.append("".join(words).strip() + "…")
            break
        return " ".join(parts)

    async def _barge_in(self) -> None:
        """The caller is interrupting: drop the rest of what the agent was
        saying — already paused if their voice was heard starting, otherwise
        stopped here."""
        now = asyncio.get_running_loop().time()
        turn = self._turn
        if turn is not None and turn.reply_started and not turn.interrupted:
            turn.interrupted = True
            turn.heard = self._heard_text(turn.segments, now)
        self._interrupted = True
        if self._held_timer is not None:
            self._held_timer.cancel()
            self._held_timer = None
        await self._stop_audio(drop=True)
        logger.info(f"Caller barged in: call_id={self.call_id}")

    async def _wait_playback(self) -> None:
        """
        Wait until the caller has heard everything sent so far, or cut it off.

        Audio is sent faster than it plays, so "sent" is not "heard". Whatever
        must follow the words — a hang-up, a transfer, the next turn — waits
        here, or it lands on top of them.
        """
        loop = asyncio.get_running_loop()
        while self.state != SessionState.ENDED:
            now = loop.time()
            if self._held:
                # Paused for the caller: the rest may yet be played.
                await asyncio.sleep(0.05)
                continue
            # Done once the audio sent has had time to play and its marks are
            # back — or are overdue. Not on the marks alone: one that comes
            # back early must not end the wait while the agent is audible.
            if now >= self._playback_cursor and (
                not self._pending_marks
                or now >= self._playback_cursor + PLAYBACK_GRACE_SECONDS
            ):
                break
            await asyncio.sleep(0.05)
        self._pending_marks.clear()
        self._playing = False
        self._last_activity = datetime.utcnow()

    async def _greet(self, text: str) -> None:
        """Speak the opening line as a turn of its own, so a reply cannot
        start on top of it."""
        async with self._turn_lock:
            await self._send_welcome_message(text)
            await self._wait_playback()

    async def _handle_stop(self, message: dict) -> None:
        """
        Handle stream stop event.

        Args:
            message: Stop event message
        """
        logger.info(f"Stream stopped: call_id={self.call_id}")
        self.state = SessionState.ENDED
        await self._close_deepgram()
        await self._stop_call_timers()

    async def _stop_call_timers(self) -> None:
        # Discard any reply still being drafted.
        self._turn_gen += 1
        for attr in (
            "_silence_task",
            "_max_duration_task",
            "_balance_task",
            "_carry_timer",
            "_held_timer",
        ):
            task = getattr(self, attr, None)
            if task is not None and task is not asyncio.current_task():
                task.cancel()
                try:
                    await task
                except (asyncio.CancelledError, Exception):
                    pass
            setattr(self, attr, None)

    async def _max_duration_guard(self) -> None:
        """End the call politely once it reaches the agent's Max Call Duration."""
        try:
            limit = max(int(self.agent.max_call_duration or 1800), 60)
            await asyncio.sleep(limit)
            if self.state == SessionState.ENDED:
                return
            logger.info(f"Max call duration ({limit}s) reached: call_id={self.call_id}")
            await self._end_politely(self._line("time_limit"))
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"Max call duration guard error: {e}", exc_info=True)

    async def _end_politely(self, goodbye: str, *, patience: float = 10) -> None:
        """Say a closing line and hang up.

        Lets an in-flight turn finish its sentence rather than talking over
        it; if it is stuck for longer than ``patience`` seconds, cuts it off.
        """
        try:
            await asyncio.wait_for(self._turn_lock.acquire(), timeout=patience)
            acquired = True
        except asyncio.TimeoutError:
            acquired = False
            await self._barge_in()
        try:
            await self._speak_response(goodbye)
            await self._wait_playback()
            await self.end_call()
        finally:
            if acquired:
                self._turn_lock.release()

    async def _balance_guard(self) -> None:
        """End the call when the Pay As You Go credit reserved for it runs out.

        The call starts with credit for some minutes reserved (see
        ``billing/call_credit``). Shortly before those are used up it asks for
        more; while the wallet has unreserved credit the call simply carries
        on. When there is none left the agent says goodbye and hangs up, a few
        seconds early so the goodbye fits inside the minutes already paid for.

        A call on a subscription or a trial has nothing reserved and this
        returns at once.
        """
        try:
            from app.services.billing import call_credit
            from app.services.billing.wallet import call_hold

            allowed = int(call_hold(self.call).get("max_seconds") or 0)
            if allowed <= 0:
                return
            # Past this the max-duration guard ends the call anyway.
            cap = call_credit.max_call_seconds(self.agent)
            loop = asyncio.get_running_loop()
            started = loop.time()

            while self.state != SessionState.ENDED:
                wait = allowed - call_credit.END_MARGIN_SECONDS - (loop.time() - started)
                if wait > 0:
                    await asyncio.sleep(wait)
                if self.state == SessionState.ENDED or allowed >= cap:
                    return
                extended = await call_credit.extend(self.call.id, max_seconds=cap)
                if extended > allowed:
                    allowed = extended
                    continue
                logger.info(f"Reserved credit used up: call_id={self.call_id}")
                # The caller is the business's customer: they are not told why.
                # Less patience than the time-limit goodbye, because every
                # second past the margin is a minute that was not paid for.
                await self._end_politely(self._line("must_end"), patience=4)
                return
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"Balance guard error: {e}", exc_info=True)

    async def _silence_watchdog(self) -> None:
        """
        Check in on a caller who has gone quiet, and hang up if a second
        check-in also gets no reply. Not the agent's `silence_timeout` — that
        is the sub-second-to-few-second pause that ends a turn (see
        deepgram_turn_params); this is how long a caller may say nothing at
        all, matching MIN_CHECK_IN_MS in CallTestPanel.tsx.
        """
        try:
            interval = SILENCE_CHECK_IN_SECONDS

            while self.state != SessionState.ENDED:
                await asyncio.sleep(interval)
                if self.state == SessionState.ENDED:
                    break
                # A turn is in flight (caller or agent talking) — not silence.
                # The caller counts as talking from their first word, not
                # only once they finish: a long answer used to be cut into
                # with "Are you still there?".
                if (
                    self._audible()
                    or self._turn_lock.locked()
                    or self._utterance_parts
                    or self._carry
                    or self.state in (SessionState.PROCESSING, SessionState.SPEAKING)
                ):
                    continue

                idle_seconds = (datetime.utcnow() - self._last_activity).total_seconds()
                if idle_seconds < interval:
                    continue

                # Under the turn lock, like every other line the agent speaks:
                # a reply starting at the same moment would otherwise be mixed
                # into this one frame by frame.
                async with self._turn_lock:
                    if self._silence_checkins == 0:
                        self._silence_checkins = 1
                        await self._speak_response(self._line("still_there"))
                        await self._wait_playback()
                        continue

                    # Second consecutive silent check-in: nobody's on the line.
                    await self._speak_response(self._line("silence_goodbye"))
                    await self._wait_playback()
                    await self.end_call()
                    break

        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"Silence watchdog error: {e}", exc_info=True)

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

        left = self._playback_cursor - asyncio.get_running_loop().time()
        logger.info(
            f"Playback mark {mark_name} returned, about {max(left, 0):.1f}s of audio "
            f"still to play: call_id={self.call_id}"
        )

        # Each piece of speech is followed by its own mark. The agent stops
        # being audible when the last one outstanding comes back — one shared
        # name let the greeting's mark end a reply that was still playing.
        # Marks for audio a barge-in cleared are no longer pending: ignored.
        if mark_name in self._pending_marks:
            self._pending_marks.discard(mark_name)
            if not self._pending_marks:
                self._playing = False
                self._last_activity = datetime.utcnow()

    async def _process_utterance(self, utterance: str) -> None:
        """
        Answer one complete caller utterance: think, speak, then act.

        The reply is drafted straight away but stays a draft until its hold
        expires (see extra_wait_seconds). If the caller carries on speaking
        before then, the draft is discarded without a trace and their words
        come back merged into the next utterance.

        Args:
            utterance: Complete user utterance
        """
        self._turn_gen += 1
        turn = _Turn(
            gen=self._turn_gen,
            text=utterance,
            hold_until=self._last_eos + extra_wait_seconds(
                utterance, self._last_agent_text, self._language or "en"
            ),
        )
        self._turn = turn
        self.state = SessionState.PROCESSING
        self._last_activity = datetime.utcnow()
        self._silence_checkins = 0
        history = self.conversation.snapshot()
        user_entry = None

        try:
            logger.info(f"Processing utterance: {utterance}")

            # Log user transcript
            user_entry = await self._log_transcript_entry("user", utterance)

            # Pull anything relevant from the agent's knowledge base(s) and give
            # it to the model as context for THIS turn, so answers are grounded
            # in the customer's own documents rather than the model's guesses.
            kb_context = await self._get_kb_context(utterance)
            if kb_context:
                self.conversation.add_message(
                    "system",
                    "Use the following information from the company knowledge base to "
                    "answer the caller's next question. If it doesn't contain the answer, "
                    "say you don't have that information rather than guessing.\n\n"
                    f"{kb_context}",
                )

            # Add user message to conversation
            self.conversation.add_message("user", normalize_spoken_emails(utterance))

            # Generate the response, speaking each sentence as it is written
            response = await self._generate_llm_response(turn)

            # A fixed line handed back whole rather than streamed.
            if not self._stale(turn) and not turn.reply and (response or "").strip():
                await self._voice(turn, response, final=True)

            if not turn.reply and not self._stale(turn):
                # The model failed or returned nothing. Say so rather than
                # leaving the caller in silence until the idle check-in.
                logger.warning(f"No reply generated for utterance: call_id={self.call_id}")
                if await self._commit(turn):
                    no_reply = self._line("no_reply")
                    await self._log_transcript_entry("assistant", no_reply)
                    await self._speak_response(no_reply)
                    await self._wait_playback()
                    return

            if self._stale(turn):
                # The caller had not finished. Forget this turn happened.
                self.conversation.restore(history)
                if user_entry in self.transcript_entries:
                    self.transcript_entries.remove(user_entry)
                return

            self.metrics["llm_responses"] += 1

            # Update call costs
            await self._update_call_costs()

            # Everything below belongs after the words, not on top of them.
            await self._wait_playback()
            await self._record_reply(turn)

            if turn.interrupted:
                # The caller cut the reply off, so they did not agree to
                # whatever it was announcing.
                self._pending_telephony = None
                return

            # Now that the confirmation has been heard, run any deferred
            # call-control action (transfer/hang_up/dtmf/voicemail).
            await self._run_pending_telephony()

            # The agent used one of the configured end-call phrases —
            # mirrors the browser test console's phrase match (see
            # agents.py's /respond endpoint), which real calls never had.
            reply = " ".join(turn.reply)
            end_call_phrases = self.agent.end_call_phrases or []
            if end_call_phrases and any(p.lower() in reply.lower() for p in end_call_phrases):
                await self.end_call()

        except Exception as e:
            logger.error(f"Error processing utterance: {e}", exc_info=True)
            error_msg = self._line("no_reply")
            await self._log_transcript_entry("assistant", error_msg)
            await self._speak_response(error_msg)
            await self._wait_playback()

        finally:
            if self._turn is turn:
                self._turn = None
            if self.state != SessionState.ENDED:
                self.state = SessionState.LISTENING

    def _stale(self, turn: _Turn) -> bool:
        """A draft the caller talked past, or one the call ended under."""
        if self.state == SessionState.ENDED:
            return True
        return not turn.committed and turn.gen != self._turn_gen

    async def _commit(self, turn: _Turn) -> bool:
        """
        Make the turn real, once its hold has run out. Returns False if the
        caller resumed first — the turn must then do nothing audible and run
        no tool.
        """
        if turn.committed:
            return True
        loop = asyncio.get_running_loop()
        while True:
            if self._stale(turn):
                return False
            remaining = turn.hold_until - loop.time()
            if remaining <= 0:
                break
            await asyncio.sleep(min(remaining, 0.05))
        turn.committed = True
        return True

    async def _voice(self, turn: _Turn, chunk: str, final: bool = False) -> bool:
        """
        Feed streamed LLM text to the caller, sentence by sentence.

        Returns False when generation should stop: the turn was discarded, or
        the caller interrupted. After a tool has run the text is still
        collected (unspoken) so the conversation remembers what the tool did.
        """
        if self._stale(turn):
            return False
        turn.buffer += chunk
        sentences, turn.buffer = pop_sentences(turn.buffer, final)
        for sentence in sentences:
            sentence = strip_for_speech(sentence)
            if not sentence:
                continue
            if not await self._commit(turn):
                return False
            turn.reply_started = True
            turn.reply.append(sentence)
            if not turn.interrupted:
                await self._speak_response(sentence, turn=turn)
        return turn.tools_ran or not turn.interrupted

    async def _record_reply(self, turn: _Turn) -> None:
        """
        Put the finished reply into the conversation and the transcript — as
        the caller heard it. A reply they cut off is recorded only up to that
        point, or the model goes on as if it had been heard in full.
        """
        full = " ".join(turn.reply).strip()
        if not turn.interrupted:
            self.conversation.add_message("assistant", full)
            await self._log_transcript_entry("assistant", full)
            self._last_agent_text = full
            return

        heard = (turn.heard or "").strip()
        if turn.tools_ran:
            # What the tool did (a booking, a lookup) must not be forgotten,
            # so the whole reply stays, with a note on how much got through.
            self.conversation.add_message("assistant", full)
            note = (
                f'The caller interrupted and only heard this much of your last reply: "{heard}".'
                if heard else
                "The caller interrupted before hearing any of your last reply."
            )
            if self._pending_telephony:
                note += " The transfer or hang-up you announced has not happened."
            self.conversation.add_message("system", note)
        elif heard:
            self.conversation.add_message("assistant", heard)
        if heard:
            await self._log_transcript_entry("assistant", heard)
        self._last_agent_text = heard or full

    async def _get_kb_context(self, query: str) -> Optional[str]:
        """
        Retrieve relevant knowledge-base passages for the caller's question.

        Searches every knowledge base attached to this agent (auto_inject only).
        Returns None when the agent has no knowledge base or nothing matches, so
        a call is never blocked or slowed by a KB problem.
        """
        try:
            from sqlalchemy import select
            from app.models.knowledge_base import AgentKnowledgeBase
            from app.services.knowledge_base.rag_service import search_knowledge_base_db
            from app.core.config import settings as _settings

            if not self.agent or not self.db:
                return None

            links = (
                await self.db.execute(
                    select(AgentKnowledgeBase)
                    .where(
                        AgentKnowledgeBase.agent_id == self.agent.id,
                        AgentKnowledgeBase.is_active == True,  # noqa: E712
                        AgentKnowledgeBase.auto_inject == True,  # noqa: E712
                    )
                    .order_by(AgentKnowledgeBase.priority.desc())
                )
            ).scalars().all()

            if not links:
                return None

            passages = []
            for link in links:
                hits = await search_knowledge_base_db(
                    db=self.db,
                    knowledge_base_id=str(link.knowledge_base_id),
                    query=query,
                    api_key=_settings.OPENAI_API_KEY,
                    top_k=link.max_results or 3,
                    min_similarity=link.min_similarity or 0.2,
                )
                for h in hits:
                    title = h.get("document_title") or "document"
                    passages.append(f"[{title}] {h['content']}")

            if not passages:
                logger.info("KB search found nothing relevant for this utterance")
                return None

            logger.info(f"Injecting {len(passages)} knowledge-base passage(s) into the turn")
            return "\n\n".join(passages[:5])

        except Exception as e:
            # Never let a KB failure break the conversation.
            logger.error(f"Knowledge base lookup failed: {e}", exc_info=True)
            return None

    async def _generate_llm_response(self, turn: Optional[_Turn] = None) -> Optional[str]:
        """
        Generate response using LLM with function calling support.

        Args:
            turn: The live turn. When given, each sentence is spoken as soon
                as it is written instead of after the whole reply.

        Returns:
            LLM response text
        """
        try:
            provider = self.agent.llm_provider or "openai"
            # None lets llm_service pick the provider's own default — an
            # OpenAI name here failed outright for an agent on Claude.
            model = self.agent.llm_model or None
            # float(), not the raw column value: llm_temperature is Numeric, so
            # SQLAlchemy hands back a Decimal, which the provider SDKs cannot
            # JSON-encode into the request body — every turn failed with
            # "Object of type Decimal is not JSON serializable".
            # `is None`, not `or`: a temperature of 0 is a setting, and was
            # being read as "unset" and replaced with 0.7.
            raw_temperature = self.agent.llm_temperature
            temperature = float(raw_temperature) if raw_temperature is not None else 0.7
            # The agent's Max Token setting; was a hardcoded 500.
            max_tokens = int(self.agent.llm_max_tokens or 400)

            messages = self.conversation.get_messages()

            # Prepare function definitions: webhook functions + global tools
            functions = None
            func_defs = [
                self.function_executor.get_function_definition(f)
                for f in self.agent_functions
            ]
            # Async: workflow-backed tools derive their parameter schema from
            # the workflow's declared inputs, which needs a database read.
            tool_defs = await self.function_executor.build_tool_definitions(
                self.agent_tools, db=self.db
            )
            all_defs = func_defs + tool_defs
            if all_defs:
                functions = all_defs

            # Generate response (with function calling if available)
            if functions:
                # Tool calling works on every provider (OpenAI and Anthropic
                # both stream a function_call dict). This used to be
                # OpenAI-only, so an agent on Claude could not use any of
                # its tools during a real phone call.
                response_text = await self._generate_with_functions(
                    messages, provider, model, temperature, functions, max_tokens,
                    turn=turn,
                )
            else:
                # Standard streaming response
                response_chunks = []
                stream = cap_stream(self.llm_service.chat_stream(
                    messages=messages,
                    provider=provider,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                ), max_tokens)
                try:
                    async for chunk in stream:
                        response_chunks.append(chunk)
                        if turn is not None and not await self._voice(turn, chunk):
                            break
                finally:
                    await self._close_stream(stream)
                response_text = "".join(response_chunks)
                if turn is not None:
                    await self._voice(turn, "", final=True)

            return response_text

        except Exception as e:
            logger.error(f"Error generating LLM response: {e}")
            return None

    @staticmethod
    async def _close_stream(stream) -> None:
        """Close an LLM stream that was left early, so its HTTP response is
        released now rather than whenever the generator is collected."""
        aclose = getattr(stream, "aclose", None)
        if aclose is not None:
            try:
                await aclose()
            except Exception:
                pass

    async def _generate_with_functions(
        self,
        messages: list,
        provider: str,
        model: str,
        temperature: float,
        functions: list,
        max_tokens: int = 400,
        turn: Optional[_Turn] = None,
    ) -> str:
        """
        Generate LLM response with function calling support.

        Args:
            messages: Conversation messages
            provider: LLM provider
            model: Model name
            temperature: Temperature
            functions: Function definitions
            turn: The live turn, if the reply is to be spoken as it streams

        Returns:
            Final response text after function execution
        """
        max_function_calls = 5  # Prevent infinite loops
        function_call_count = 0

        while function_call_count < max_function_calls:
            # Call LLM with functions
            response_chunks = []
            function_call = None

            stopped = False
            stream = cap_stream(self.llm_service.chat_stream(
                messages=messages,
                provider=provider,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                functions=functions,
            ), max_tokens)
            try:
                async for chunk in stream:
                    # Check if this is a function call
                    if isinstance(chunk, dict) and "function_call" in chunk:
                        function_call = chunk["function_call"]
                    else:
                        response_chunks.append(chunk)
                        if turn is not None and not await self._voice(turn, chunk):
                            stopped = True
                            break
            finally:
                await self._close_stream(stream)

            said = "".join(response_chunks)
            if stopped:
                return said
            # Speak whatever is left: the end of the answer, or a lead-in
            # ("Let me check that for you") ahead of a tool.
            if turn is not None and not await self._voice(turn, "", final=True):
                return said

            # If no function call, return response
            if not function_call:
                return said

            # A tool acts on the world, so it never runs for a draft: wait out
            # the hold, and stop here if the caller carried on speaking.
            if turn is not None:
                if not await self._commit(turn):
                    return said
                turn.tools_ran = True

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
                 if sanitize_function_name(t.name) == function_name),
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
                # A workflow can take seconds. Say something first so the
                # caller isn't sitting in silence while it runs — unless the
                # model has just said its own lead-in.
                if matched_tool.tool_type == "workflow" and not (turn is not None and said.strip()):
                    await self._speak_filler(matched_tool)

                result = await self.function_executor.execute_global_tool(
                    tool=matched_tool,
                    parameters=function_args,
                    call_id=self.call_id,
                    db=self.db,
                    # Live channel, so speak/ask steps inside the workflow
                    # reach the caller instead of being simulated.
                    channel=VoiceChannel(self),
                    # AI steps in the workflow answer with this agent's model.
                    llm={"provider": provider, "model": model},
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
                # The tool's name means nothing to a caller; it goes to the log.
                logger.warning(
                    f"Model called a tool that is not set up: {function_name}: call_id={self.call_id}"
                )
                return await self._fixed_line(turn, self._line("tool_trouble"))

            # Record the exchange as ChatMessage objects. `messages` is a
            # List[ChatMessage] — appending raw dicts here raised AttributeError
            # on the next turn, when _format_messages read msg.function_call.
            #
            # The assistant's request must be appended before its result, or
            # OpenAI receives an orphan tool message with no matching call.
            messages.append(
                ChatMessage(
                    role="assistant",
                    # A lead-in the caller heard stays on the record, so the
                    # model does not say it again with the answer.
                    content=(said.strip() or None) if turn is not None else None,
                    function_call={
                        "name": function_name,
                        "arguments": function_call.get("arguments", "{}"),
                    },
                )
            )
            messages.append(
                ChatMessage(
                    role="function",
                    name=function_name,
                    content=formatted_result,
                )
            )

            function_call_count += 1

            # Continue loop to let LLM generate final response with function result

        # Max function calls reached
        return await self._fixed_line(turn, self._line("tool_trouble"))

    @property
    def _language(self) -> Optional[str]:
        """The agent's language (the Language setting on its Transcriber tab)."""
        return getattr(getattr(self, "agent", None), "stt_language", None)

    def _line(self, key: str) -> str:
        """One of the platform's own lines, in the agent's language."""
        return languages.phrase(key, self._language)

    async def _fixed_line(self, turn: Optional[_Turn], text: str) -> str:
        """A line the session writes itself rather than the model: spoken
        like any other part of a live turn's reply."""
        if turn is not None:
            await self._voice(turn, text, final=True)
        return text

    async def _speak_filler(self, tool) -> None:
        """
        Say a short holding line before a slow tool runs.

        A workflow that books an appointment can take several seconds. Without
        this the caller hears dead air and usually starts talking again, which
        derails the turn.

        Args:
            tool: The tool about to run; its config may override the wording
        """
        filler = languages.spoken_filler(
            (tool.config or {}).get("filler_message"), self._language
        )

        try:
            await self.speak(filler)
        except Exception as e:
            # A failed filler must never block the tool it precedes.
            logger.warning(f"Could not speak filler line: {e}")

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

    async def _tts_api_key(self) -> Optional[str]:
        """The workspace's own provider key when the agent speaks with one of
        its custom voices, else None. Looked up once per call, on a session
        of its own: the call's session may be mid-query when speech starts."""
        if not self._tts_key_resolved:
            from app.database import AsyncSessionLocal

            async with AsyncSessionLocal() as db:
                self._tts_key = await resolve_tts_api_key(
                    db,
                    self.agent.organization_id,
                    self.agent.tts_provider or "elevenlabs",
                    self.agent.tts_voice_id,
                )
            self._tts_key_resolved = True
        return self._tts_key

    async def _speak_response(self, text: str, turn: Optional[_Turn] = None) -> None:
        """
        Synthesize speech and send to caller.

        Args:
            text: Text to speak
            turn: The turn this is part of the reply to, if any — so an
                interruption can tell how much of the reply was heard
        """
        self.state = SessionState.SPEAKING
        self._interrupted = False
        text = strip_for_speech(text)

        segment = _Segment(text=text)
        self._recent_speech.append(segment)
        if turn is not None:
            turn.segments.append(segment)
        # Registered before any audio goes out, so an earlier mark coming
        # back cannot mark the agent silent while this is being sent.
        loop = asyncio.get_running_loop()
        self._mark_seq += 1
        mark = f"speech-{self._mark_seq}"
        self._pending_marks.add(mark)

        async def send_frame(data: bytes) -> None:
            async with self._audio_lock:
                segment.audio.extend(data)
                if self._held or segment.dropped:
                    return  # kept for a resume, or abandoned
                if segment.start is None:
                    # After whatever is still queued at the carrier.
                    segment.start = max(loop.time(), self._playback_cursor)
                await self._send_audio_to_twilio(data)
                segment.sent += len(data)
                self._playback_cursor = segment.end()

        try:
            provider = self.agent.tts_provider or "elevenlabs"
            voice_id = self.agent.tts_voice_id or "rachel"

            # Request Twilio-native audio (8kHz mulaw) straight from the provider
            # so no local decoding/resampling is needed. ElevenLabs supports
            # "ulaw_8000"; other providers fall back through _to_twilio_mulaw.
            tts_kwargs = {
                "text": text,
                "provider": provider,
                "voice_id": voice_id,
                "api_key": await self._tts_api_key(),
                # The agent's Speech Speed — only browser tests honoured it.
                "speed": float(self.agent.tts_speed or 1.0),
            }
            if provider == "elevenlabs":
                tts_kwargs["output_format"] = "ulaw_8000"
            # Pin the voice to the agent's language, so a short sentence or a
            # number is not read in English.
            language_code = languages.tts_language_code(self._language)
            if language_code:
                tts_kwargs["language_code"] = language_code

            # Reframe the provider's byte stream into 20ms (160-byte) mulaw frames,
            # which is what Twilio expects for smooth playback.
            frame = bytearray()
            chunk_count = 0
            self._playing = True
            async for audio_chunk in self.tts_service.synthesize_stream(**tts_kwargs):
                if self._interrupted:
                    break
                mulaw = self._to_twilio_mulaw(audio_chunk, provider)
                if not mulaw:
                    continue
                frame.extend(mulaw)
                while len(frame) >= 160 and not self._interrupted:
                    await send_frame(bytes(frame[:160]))
                    del frame[:160]
                    chunk_count += 1

            self.metrics["tts_generations"] += 1

            if self._interrupted:
                logger.info(f"Speech cut off by the caller after {chunk_count} frames")
                return

            if frame:
                await send_frame(bytes(frame))
                chunk_count += 1

            # Mark end of speech; Twilio echoes it back when playback reaches
            # it, which is when the agent actually stops being audible.
            if chunk_count and not self._held and not segment.dropped:
                await self._send_mark(mark)
                mark = None

            logger.info(f"Sent audio response: {chunk_count} frames")

        except Exception as e:
            logger.error(f"Error speaking response: {e}", exc_info=True)

        finally:
            # No mark went out (cut off, or synthesis failed), so none will
            # come back for it.
            if mark is not None:
                self._pending_marks.discard(mark)
                if not self._pending_marks:
                    self._playing = False
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
            self._last_agent_text = text

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

    async def _log_transcript_entry(self, speaker: str, text: str) -> TranscriptEntry:
        """
        Log transcript entry.

        Args:
            speaker: Speaker ("user" or "assistant")
            text: Text content

        Returns:
            The entry added to the call's transcript
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
        return entry

    async def cleanup(self) -> None:
        """Clean up session resources."""
        try:
            logger.info(f"Cleaning up voice session: call_id={self.call_id}")

            # Close the Deepgram STT stream first so no more turns are triggered.
            self.state = SessionState.ENDED
            await self._close_deepgram()
            await self._stop_call_timers()

            # Save transcript
            if self.transcript_entries:
                await self.transcript_service.save_transcript(
                    call=self.call,
                    transcript=self.transcript_entries,
                    db=self.db,
                )
                logger.info(f"Saved transcript with {len(self.transcript_entries)} entries")

                # Analyze transcript and persist sentiment + topics so the
                # analytics dashboard has accurate per-call data.
                try:
                    analysis = await self.transcript_service.analyze_transcript(
                        self.transcript_entries
                    )
                    if analysis.key_topics:
                        self.call.topics = analysis.key_topics
                except Exception as e:
                    logger.warning(f"Transcript analysis failed for call {self.call_id}: {e}")

                # Generate an AI conversation summary (with heuristic fallback)
                # and derive sentiment from it.
                try:
                    from app.services.call.summary_service import get_summary_service

                    summary_result = await get_summary_service().summarize(
                        self.transcript_entries,
                        provider=getattr(self.agent, "llm_provider", None) or "openai",
                        model=getattr(self.agent, "llm_model", None),
                    )
                    if summary_result:
                        self.call.summary = summary_result.summary
                        self.call.sentiment_score = summary_result.sentiment_score
                        self.call.sentiment_label = summary_result.sentiment_label
                except Exception as e:
                    logger.warning(f"Summary generation failed for call {self.call_id}: {e}")

                await self.db.commit()

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
                "ended_at": utc_iso(self.call.ended_at),
            }

            organization_id = getattr(self.call, "organization_id", None)
            if organization_id is None:
                logger.warning(
                    f"Call {self.call_id} has no organization_id; "
                    f"skipping call_completed workflow dispatch"
                )
                return

            async with AsyncSessionLocal() as db:
                manager = get_trigger_manager(db)
                executions = await manager.process_event(
                    "call_completed",
                    event_data,
                    organization_id=organization_id,
                )

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
