"""
Turn-taking on a live phone call.

Drives the real VoiceSession with scripted Deepgram messages against a fake
Twilio (which plays audio in real time and echoes marks the way Twilio does),
a fake LLM and a fake text-to-speech voice. What is asserted is what the
caller would experience: how many replies they hear, to which words, and what
the agent remembers afterwards.
"""
import asyncio
import base64
import json
import uuid
from types import SimpleNamespace

import pytest

from app.services.voice import turn_taking
from app.services.voice.llm_service import ConversationContext
from app.services.websocket import voice_session
from app.services.websocket.voice_session import VoiceSession

pytestmark = pytest.mark.asyncio

#: Fake speech runs at ten words a second, so tests stay quick.
BYTES_PER_WORD = 800
#: The end-of-turn waits are scaled down by this for the same reason.
WAIT_SCALE = 0.2


class FakeTwilio:
    """Stands in for the Twilio media stream: buffers audio, plays it in real
    time, echoes each mark when playback reaches it, and on `clear` drops the
    buffer and returns the outstanding marks at once."""

    def __init__(self):
        self.session = None
        self.play_until = 0.0
        self.cleared = 0
        self.marks_sent = []
        self._pending = {}

    async def send_json(self, call_id, message):
        loop = asyncio.get_running_loop()
        event = message["event"]
        if event == "media":
            size = len(base64.b64decode(message["media"]["payload"]))
            self.play_until = max(loop.time(), self.play_until) + size / 8000
        elif event == "mark":
            name = message["mark"]["name"]
            self.marks_sent.append(name)
            self._pending[name] = loop.call_at(self.play_until, self._echo, name)
        elif event == "clear":
            self.cleared += 1
            self.play_until = loop.time()
            for name, handle in list(self._pending.items()):
                handle.cancel()
                self._echo(name)
        return True

    def _echo(self, name):
        self._pending.pop(name, None)
        asyncio.ensure_future(
            self.session.handle_message({"event": "mark", "mark": {"name": name}})
        )


class FakeVoice:
    def __init__(self):
        self.spoken = []

    async def synthesize_stream(self, text, **kwargs):
        self.spoken.append(text)
        audio = b"\xff" * (BYTES_PER_WORD * len(text.split()))
        for i in range(0, len(audio), 1600):
            await asyncio.sleep(0)
            yield audio[i:i + 1600]


class FakeLLM:
    """Replies with `reply(last user message)`, after `delay` seconds."""

    def __init__(self, reply, delay=0.0):
        self.reply = reply
        self.delay = delay
        self.asked = []

    async def chat_stream(self, messages, **kwargs):
        user = [m.content for m in messages if m.role == "user"]
        self.asked.append(user[-1])
        await asyncio.sleep(self.delay)
        out = self.reply(messages)
        if isinstance(out, dict):
            yield out
            return
        for word in out.split(" "):
            yield word + " "


class FakeDB:
    def add(self, obj):
        pass

    async def commit(self):
        pass


class FakeExecutor:
    def __init__(self):
        self.ran = []

    def get_function_definition(self, fn):
        return {"name": fn.name, "description": "", "parameters": {"type": "object", "properties": {}}}

    async def build_tool_definitions(self, tools, db=None):
        return []

    async def execute_function(self, function, parameters, call_id, db):
        self.ran.append(parameters)
        return {"success": True}

    def format_for_llm(self, function, result):
        return "Booked. Reference BK-1."


def make_session(monkeypatch, reply, delay=0.0, **agent_overrides):
    monkeypatch.setattr(
        voice_session, "extra_wait_seconds",
        lambda *a, **k: turn_taking.extra_wait_seconds(*a, **k) * WAIT_SCALE,
    )
    agent = SimpleNamespace(
        id=uuid.uuid4(), name="Ava", organization_id=uuid.uuid4(),
        system_prompt="You are Ava.", first_message="Hello, this is Ava.",
        end_call_phrases=[], stt_model="nova-2", stt_language="en", stt_keywords=[],
        silence_timeout=1000, interrupt_enabled=True, interrupt_sensitivity=0.5,
        max_call_duration=1800, llm_provider="openai", llm_model="m",
        llm_temperature=0.7, llm_max_tokens=200, tts_provider="elevenlabs",
        tts_voice_id="v", tts_speed=1.0,
    )
    for key, value in agent_overrides.items():
        setattr(agent, key, value)

    twilio = FakeTwilio()
    session = VoiceSession(
        call_id="call-1", call=SimpleNamespace(id=uuid.uuid4()), agent=agent,
        connection_manager=twilio, db=FakeDB(),
    )
    twilio.session = session
    session.stream_sid = "MZ1"
    session.llm_service = FakeLLM(reply, delay)
    session.tts_service = FakeVoice()
    session.function_executor = FakeExecutor()
    session.conversation = ConversationContext(system_prompt="You are Ava.")
    session.ended = []

    async def no_kb(query):
        return None

    async def no_costs():
        return None

    async def no_key():
        return None

    async def end_call():
        session.ended.append(asyncio.get_running_loop().time())

    session._get_kb_context = no_kb
    session._update_call_costs = no_costs
    session._tts_api_key = no_key
    session.end_call = end_call
    return session, twilio


def results(text, is_final=False, speech_final=False):
    return {
        "type": "Results", "is_final": is_final, "speech_final": speech_final,
        "channel": {"alternatives": [{"transcript": text}]},
    }


async def caller_says(session, text):
    """A whole utterance: heard, finalised, then followed by a pause."""
    await session._on_deepgram_message(results(text))
    await session._on_deepgram_message(results(text, is_final=True, speech_final=True))


async def settle(session, timeout=5.0):
    """Wait until nothing is in flight and nothing is playing."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        await asyncio.sleep(0.02)
        busy = session._tasks or session._turn_lock.locked() or session._audible()
        if not busy and not session._carry and session._carry_timer is None:
            return
    raise AssertionError("the session never went quiet")


def user_messages(session):
    return [m.content for m in session.conversation.snapshot() if m.role == "user"]


def assistant_messages(session):
    return [m.content for m in session.conversation.snapshot() if m.role == "assistant"]


# ── The reported bug: a pause mid-sentence ───────────────────────────────────


async def test_a_pause_mid_sentence_gets_one_reply_to_the_whole_sentence(monkeypatch):
    session, twilio = make_session(monkeypatch, lambda m: "Tomorrow at three is free.")

    await caller_says(session, "I'd like to book for")
    await asyncio.sleep(0.1)  # thinking, well inside the wait for "…for"
    await caller_says(session, "tomorrow at three.")
    await settle(session)

    # One reply was heard, and it answered the whole sentence.
    assert session.tts_service.spoken == ["Tomorrow at three is free."]
    assert user_messages(session) == ["I'd like to book for tomorrow at three."]
    assert assistant_messages(session) == ["Tomorrow at three is free."]
    assert [e.text for e in session.transcript_entries if e.speaker == "user"] == [
        "I'd like to book for tomorrow at three."
    ]
    assert twilio.cleared == 0


async def test_carrying_on_while_the_agent_is_thinking_discards_the_draft(monkeypatch):
    # A finished-sounding sentence, so no extra wait — but the model is slow,
    # and the caller adds to it before any audio has started.
    session, twilio = make_session(monkeypatch, lambda m: "Of course.", delay=0.3)

    await caller_says(session, "I need an appointment.")
    await asyncio.sleep(0.1)
    await caller_says(session, "It's for my son.")
    await settle(session)

    assert session.tts_service.spoken == ["Of course."]
    assert user_messages(session) == ["I need an appointment. It's for my son."]


async def test_a_finished_sentence_is_answered_without_extra_wait(monkeypatch):
    session, _ = make_session(monkeypatch, lambda m: "We open at nine.")
    loop = asyncio.get_running_loop()
    started = loop.time()

    await caller_says(session, "What time do you open?")
    while not session.tts_service.spoken:
        await asyncio.sleep(0.005)

    assert loop.time() - started < 0.1
    await settle(session)


async def test_a_discarded_draft_is_still_answered_if_nothing_follows(monkeypatch):
    # A cough is heard as a word, discards the draft, and never becomes a
    # final transcript. The caller's sentence must not be lost.
    session, _ = make_session(monkeypatch, lambda m: "Sure.", silence_timeout=300)
    monkeypatch.setattr(voice_session, "CARRY_FLUSH_SECONDS", 0.1)

    await session._on_deepgram_message(results("I'd like to book for", is_final=True, speech_final=True))
    await asyncio.sleep(0.05)
    await session._on_deepgram_message(results("uh"))
    await settle(session)

    assert session.tts_service.spoken == ["Sure."]
    assert user_messages(session) == ["I'd like to book for"]


async def test_a_tool_never_runs_for_a_draft(monkeypatch):
    def reply(messages):
        if any(m.role == "function" for m in messages):
            return "You're booked for Tuesday."
        return {"function_call": {"name": "book", "arguments": json.dumps({"day": "Tuesday"})}}

    session, _ = make_session(monkeypatch, reply)
    session.agent_functions = [SimpleNamespace(name="book")]

    await caller_says(session, "Book me in for")
    await asyncio.sleep(0.1)
    assert session.function_executor.ran == []  # still waiting out the pause
    await caller_says(session, "Tuesday.")
    await settle(session)

    # Booked once, for the whole request.
    assert session.function_executor.ran == [{"day": "Tuesday"}]
    assert session.tts_service.spoken == ["You're booked for Tuesday."]
    assert user_messages(session) == ["Book me in for Tuesday."]


# ── Interruptions ────────────────────────────────────────────────────────────

LONG_REPLY = (
    "We have a few options for you this week. "
    "Tuesday at three is free and so is Wednesday at ten. "
    "Thank you and goodbye."
)


async def test_an_interrupted_reply_is_remembered_only_as_far_as_it_was_heard(monkeypatch):
    session, twilio = make_session(
        monkeypatch, lambda m: LONG_REPLY, end_call_phrases=["goodbye"],
    )

    await caller_says(session, "What do you have this week?")
    await asyncio.sleep(1.2)  # into the second sentence
    await session._on_deepgram_message(results("no wait hold on"))
    await asyncio.sleep(0.1)

    assert twilio.cleared == 1
    remembered = assistant_messages(session)[-1]
    assert remembered.startswith("We have a few options for you this week.")
    assert "goodbye" not in remembered
    # The goodbye was never heard, so the call is not ended on it.
    assert session.ended == []


async def test_the_call_ends_only_after_the_goodbye_has_been_heard(monkeypatch):
    session, twilio = make_session(
        monkeypatch, lambda m: "Thank you for calling and goodbye.", end_call_phrases=["goodbye"],
    )

    await caller_says(session, "That's all, thanks.")
    await settle(session)

    assert len(session.ended) == 1
    assert session.ended[0] >= twilio.play_until - 0.05


async def test_the_agent_stays_interruptible_until_the_last_piece_has_played(monkeypatch):
    session, twilio = make_session(monkeypatch, lambda m: LONG_REPLY)

    await caller_says(session, "What do you have this week?")
    await asyncio.sleep(1.2)  # the first sentence's mark is back; more is playing

    assert len(set(twilio.marks_sent)) == len(twilio.marks_sent) >= 2
    assert session._audible()
    await settle(session)
    assert not session._audible()


async def test_a_listening_noise_over_the_agent_is_not_answered(monkeypatch):
    session, twilio = make_session(monkeypatch, lambda m: LONG_REPLY, interrupt_sensitivity=0.0)

    await caller_says(session, "What do you have this week?")
    await asyncio.sleep(0.6)
    await caller_says(session, "Mm-hm.")
    await settle(session)

    assert twilio.cleared == 0
    assert session.llm_service.asked == ["What do you have this week?"]


async def test_the_agents_own_echo_neither_interrupts_nor_becomes_a_turn(monkeypatch):
    session, twilio = make_session(monkeypatch, lambda m: LONG_REPLY)

    await caller_says(session, "What do you have this week?")
    await asyncio.sleep(0.8)
    # A speakerphone feeds the agent's first sentence back into the line.
    await caller_says(session, "we have a few options for you")
    await settle(session)

    assert twilio.cleared == 0
    assert session.llm_service.asked == ["What do you have this week?"]
    assert session._echo_hits == 1


SPEECH_STARTED = {"type": "SpeechStarted"}


async def test_the_agent_stops_as_soon_as_the_callers_voice_is_heard(monkeypatch):
    session, twilio = make_session(monkeypatch, lambda m: LONG_REPLY)

    await caller_says(session, "What do you have this week?")
    await asyncio.sleep(0.8)
    await session._on_deepgram_message(SPEECH_STARTED)

    # Silent at once — before a single word has been transcribed.
    assert twilio.cleared == 1 and not session._audible()

    await asyncio.sleep(0.2)
    await caller_says(session, "Yes, book it for Tuesday.")
    await settle(session)

    # The rest of the old reply was never played, and the new request was
    # answered knowing only what had been heard.
    remembered = assistant_messages(session)
    assert remembered[0] != LONG_REPLY and LONG_REPLY.startswith(remembered[0].rstrip("…"))
    assert session.llm_service.asked == ["What do you have this week?", "Yes, book it for Tuesday."]


async def test_a_sound_that_is_not_an_interruption_only_pauses_the_agent(monkeypatch):
    monkeypatch.setattr(voice_session, "PAUSE_CONFIRM_SECONDS", 0.2)
    session, twilio = make_session(monkeypatch, lambda m: LONG_REPLY, end_call_phrases=["goodbye"])
    loop = asyncio.get_running_loop()
    started = loop.time()

    await caller_says(session, "What do you have this week?")
    await asyncio.sleep(0.8)
    await session._on_deepgram_message(SPEECH_STARTED)  # a cough: no words follow
    await settle(session)

    # It picked up where it stopped, without synthesizing anything again,
    # and the whole reply was heard: remembered in full, and acted on.
    assert twilio.cleared == 1
    assert len(session.tts_service.spoken) == 3
    assert assistant_messages(session) == [LONG_REPLY]
    assert len(session.ended) == 1
    words = len(LONG_REPLY.split())
    assert loop.time() - started >= words * BYTES_PER_WORD / 8000 + 0.2
    assert session._false_pauses == 1


async def test_a_line_that_keeps_triggering_pauses_stops_being_paused_for(monkeypatch):
    monkeypatch.setattr(voice_session, "PAUSE_CONFIRM_SECONDS", 0.1)
    session, twilio = make_session(monkeypatch, lambda m: LONG_REPLY)

    await caller_says(session, "What do you have this week?")
    for _ in range(4):
        await asyncio.sleep(0.3)
        await session._on_deepgram_message(SPEECH_STARTED)
    await settle(session)

    assert twilio.cleared == 2  # twice, then no more
    assert assistant_messages(session) == [LONG_REPLY]


async def test_mm_hm_pauses_then_resumes_and_is_not_answered(monkeypatch):
    session, twilio = make_session(monkeypatch, lambda m: LONG_REPLY, interrupt_sensitivity=0.0)

    await caller_says(session, "What do you have this week?")
    await asyncio.sleep(0.6)
    await session._on_deepgram_message(SPEECH_STARTED)
    await asyncio.sleep(0.1)
    assert not session._audible()
    await session._on_deepgram_message(results("Mhmm."))
    # Carried on at the first sign it was only a listening noise.
    assert session._audible()
    await session._on_deepgram_message(results("Mhmm.", is_final=True, speech_final=True))
    await settle(session)

    assert assistant_messages(session) == [LONG_REPLY]
    assert session.llm_service.asked == ["What do you have this week?"]
    assert session._false_pauses == 0  # they did say something


async def test_a_short_sentence_while_paused_takes_the_floor(monkeypatch):
    # Three words needed to cut in mid-sentence; "Wait." is one.
    session, twilio = make_session(monkeypatch, lambda m: LONG_REPLY, interrupt_sensitivity=0.0)

    await caller_says(session, "What do you have this week?")
    await asyncio.sleep(0.6)
    await session._on_deepgram_message(SPEECH_STARTED)
    await caller_says(session, "Wait.")
    await asyncio.sleep(0.3)

    # Not resumed: the rest of the reply is dropped and "Wait." answered now,
    # not after the whole reply has played.
    assert session.llm_service.asked == ["What do you have this week?", "Wait."]
    await settle(session)
    assert assistant_messages(session)[0] != LONG_REPLY


async def test_pausing_comes_back_after_a_real_interruption(monkeypatch):
    monkeypatch.setattr(voice_session, "PAUSE_CONFIRM_SECONDS", 0.1)
    session, twilio = make_session(monkeypatch, lambda m: LONG_REPLY)

    await caller_says(session, "What do you have this week?")
    for _ in range(2):  # noise twice: pausing on sound is switched off
        await asyncio.sleep(0.3)
        await session._on_deepgram_message(SPEECH_STARTED)
    await asyncio.sleep(0.3)
    assert session._false_pauses == 2
    await caller_says(session, "Book it for Tuesday please.")  # words still interrupt
    await asyncio.sleep(0.1)

    assert session._false_pauses == 0


async def test_an_interruption_mixed_with_echo_still_interrupts(monkeypatch):
    session, twilio = make_session(monkeypatch, lambda m: LONG_REPLY)

    await caller_says(session, "What do you have this week?")
    await asyncio.sleep(0.8)
    # An echoing line: the caller's words arrive in among the agent's.
    await session._on_deepgram_message(results("options for you this week yes book it for Tuesday"))
    await asyncio.sleep(0.1)

    assert twilio.cleared == 1


async def test_marks_that_come_back_early_do_not_end_the_agents_turn(monkeypatch):
    # A carrier that answers every mark at once, long before the audio ends.
    session, twilio = make_session(
        monkeypatch, lambda m: LONG_REPLY, end_call_phrases=["goodbye"],
    )
    real_send = twilio.send_json

    async def eager_marks(call_id, message):
        await real_send(call_id, message)
        if message["event"] == "mark":
            twilio._pending.pop(message["mark"]["name"]).cancel()
            twilio._echo(message["mark"]["name"])

    twilio.send_json = eager_marks

    await caller_says(session, "What do you have this week?")
    await asyncio.sleep(1.0)
    # Still audible and still interruptible; the call has not been ended
    # on top of the reply.
    assert session._audible() and session.ended == []
    await session._on_deepgram_message(results("no wait hold on"))
    await asyncio.sleep(0.1)

    assert twilio.cleared == 1
    assert session.ended == []


async def test_speech_during_the_greeting_waits_for_it_rather_than_overlapping(monkeypatch):
    session, twilio = make_session(
        monkeypatch, lambda m: "Sure, I can help.",
        first_message="Hello, this is Ava from Pearl Dental, how can I help you today?",
        interrupt_enabled=False,
    )

    session._spawn(session._greet(session.agent.first_message))
    await asyncio.sleep(0.3)
    await caller_says(session, "I want to book.")
    await asyncio.sleep(0.2)
    # The greeting is still playing; the reply has not been started over it.
    assert len(session.tts_service.spoken) == 1
    await settle(session)

    assert session.tts_service.spoken[1] == "Sure, I can help."


async def test_a_caller_who_is_still_talking_counts_as_active(monkeypatch):
    session, _ = make_session(monkeypatch, lambda m: "Okay.")
    session._silence_checkins = 1
    before = session._last_activity

    await asyncio.sleep(0.01)
    await session._on_deepgram_message(results("so what happened was"))

    assert session._last_activity > before
    assert session._silence_checkins == 0


# ── The rules themselves ─────────────────────────────────────────────────────


@pytest.mark.parametrize("text, agent_last, expected", [
    ("What time do you open?", None, 0.0),
    ("Yes.", None, 0.0),
    ("tomorrow", None, 0.0),
    ("I'd like to book for", None, 1.5),
    ("I'd like to book for.", None, 1.5),
    ("My name is John and", None, 1.5),
    ("I was thinking,", None, 1.5),
    ("I'll take that.", None, 0.0),
    ("it's zero three zero zero", None, 0.8),
    ("it's zero three zero zero", "What's the best phone number for you?", 1.5),
    ("j o h n", "Could you spell your name?", 1.5),
    ("I would like to change my booking", None, 0.6),
])
async def test_how_long_to_wait_after_a_pause(text, agent_last, expected):
    assert turn_taking.extra_wait_seconds(text, agent_last) == expected


async def test_echo_needs_most_of_the_words_to_be_the_agents():
    agent = "We have a few options for you this week."
    assert turn_taking.is_echo("we have a few options", agent)
    assert not turn_taking.is_echo("Tuesday please", agent)
    assert not turn_taking.is_echo("options", agent)  # one word is never echo
    # The caller talking over the echo is not echo.
    assert not turn_taking.is_echo("a few options for you yes book it", agent)


async def test_only_listening_noises_are_backchannel():
    assert turn_taking.is_backchannel("Mm-hm.")
    assert turn_taking.is_backchannel("Hello?")
    assert not turn_taking.is_backchannel("Okay.")
    assert not turn_taking.is_backchannel("Yes.")


async def test_sentences_are_spoken_as_they_complete():
    done, rest = turn_taking.pop_sentences("We open at nine every day. And we close")
    assert done == ["We open at nine every day."] and rest == "And we close"
    # Too short to be worth a request of its own: joined to what follows.
    done, rest = turn_taking.pop_sentences("Sure. We open at nine every day. ")
    assert done == ["Sure. We open at nine every day."]
    # An abbreviation's full stop is not the end of the sentence.
    done, rest = turn_taking.pop_sentences("Your appointment is with Dr. Smith")
    assert done == []
    done, rest = turn_taking.pop_sentences("Okay.", final=True)
    assert done == ["Okay."] and rest == ""


# ── The agent's LLM settings reach the model ─────────────────────────────────


async def test_each_call_uses_its_own_agents_temperature_and_max_tokens(monkeypatch):
    # Providers are cached per model. Two agents on one model must still each
    # get their own settings, not those of whichever agent called first.
    from app.services.voice import llm_service as llm_module

    seen = []

    class Provider:
        def __init__(self, **kwargs):
            pass

        async def chat_completion(self, messages, functions=None, **kwargs):
            seen.append((kwargs["temperature"], kwargs["max_tokens"]))
            return SimpleNamespace(content="ok")

        async def chat_completion_stream(self, messages, functions=None, **kwargs):
            seen.append((kwargs["temperature"], kwargs["max_tokens"]))
            yield "ok"

    service = llm_module.LLMService()
    monkeypatch.setattr(service, "PROVIDERS", {"openai": Provider})
    monkeypatch.setattr(service, "_get_api_key", lambda provider: "key")

    await service.chat([], provider="openai", model="m", temperature=0.4, max_tokens=100)
    await service.chat([], provider="openai", model="m", temperature=0.4, max_tokens=900)
    async for _ in service.chat_stream([], provider="openai", model="m", temperature=0.0, max_tokens=250):
        pass

    assert seen == [(0.4, 100), (0.4, 900), (0.0, 250)]


async def test_max_token_limits_the_reply_even_when_the_model_was_given_more_room():
    from app.services.voice.llm_service import cap_stream, trim_to_tokens

    long_reply = "This sentence is here to fill the reply up. " * 40  # ~1,760 characters

    async def stream():
        for word in long_reply.split(" "):
            yield word + " "
        yield {"function_call": {"name": "never_reached"}}

    heard = [c async for c in cap_stream(stream(), 100)]
    assert all(isinstance(c, str) for c in heard)
    assert 350 <= len("".join(heard)) <= 400  # 100 tokens is about 400 characters

    trimmed = trim_to_tokens(long_reply, 100)
    assert len(trimmed) <= 400 and trimmed.endswith(".")
    assert trim_to_tokens("Short.", 100) == "Short."

    # The budget running out on a bare space (a common streamed chunk).
    async def spaced():
        for chunk in ("abcd", " ", "efgh"):
            yield chunk

    assert "".join([c async for c in cap_stream(spaced(), 1)]) == "abcd"

    # A tool call is not text and is never held back.
    async def tool():
        yield {"function_call": {"name": "book"}}

    assert [c async for c in cap_stream(tool(), 100)] == [{"function_call": {"name": "book"}}]


async def test_a_temperature_of_zero_is_sent_as_zero(monkeypatch):
    session, _ = make_session(monkeypatch, lambda m: "Okay.", llm_temperature=0)
    sent = {}
    real = session.llm_service.chat_stream

    def spy(messages, **kwargs):
        sent.update(kwargs)
        return real(messages, **kwargs)

    session.llm_service.chat_stream = spy
    await caller_says(session, "Hello there.")
    await settle(session)

    assert sent["temperature"] == 0.0 and sent["max_tokens"] == 200
