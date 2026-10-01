"""
Dates and emails in conversations: the agent is told the real date, and an
address that was spoken reaches the model as an address.
"""
from datetime import datetime, timezone

import pytest

from app.services.voice.conversation_context import (
    current_time_note,
    datetime_note,
    normalize_spoken_emails,
    resolve_timezone,
)
from app.services.voice.guardrails import CONDUCT_RULES, VOICE_RULES


# ---------- today's date ----------
class TestDatetimeNote:
    # Thursday 1 October 2026, 20:30 UTC.
    NOW = datetime(2026, 10, 1, 20, 30, tzinfo=timezone.utc)

    def test_states_the_date_time_and_zone(self):
        note = datetime_note(self.NOW, "UTC")
        assert "Thursday 1 October 2026" in note
        assert "8:30 PM" in note
        assert "timezone UTC" in note

    def test_uses_the_owners_timezone_and_rolls_the_date_over(self):
        """8:30 PM in London is already tomorrow in Karachi — the date must follow."""
        note = datetime_note(self.NOW, "Asia/Karachi")
        assert "Friday 2 October 2026" in note
        assert "1:30 AM" in note
        assert "Friday 2 October (today)" in note

    def test_lists_the_coming_days_with_correct_weekdays(self):
        note = datetime_note(self.NOW, "UTC")
        assert "Thursday 1 October (today)" in note
        assert "Friday 2 October (tomorrow)" in note
        assert "Thursday 8 October" in note   # "next Thursday"
        assert "Wednesday 14 October" in note

    def test_midnight_and_noon_read_as_12(self):
        assert "12:05 AM" in datetime_note(datetime(2026, 10, 1, 0, 5, tzinfo=timezone.utc), "UTC")
        assert "12:00 PM" in datetime_note(datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc), "UTC")

    @pytest.mark.parametrize("bad", [None, "", "Not/AZone"])
    def test_a_missing_or_invalid_timezone_falls_back_to_utc(self, bad):
        assert resolve_timezone(bad).key == "UTC"
        assert "timezone UTC" in datetime_note(self.NOW, bad)

    def test_defaults_to_the_real_clock(self):
        assert str(datetime.now(timezone.utc).year) in datetime_note()


@pytest.mark.asyncio
async def test_the_note_uses_the_agent_owners_profile_timezone():
    class _Result:
        def scalar_one_or_none(self):
            return "Asia/Karachi"

    class _DB:
        async def execute(self, _query):
            return _Result()

    class _Agent:
        user_id = "u1"

    note = await current_time_note(_DB(), _Agent())
    assert "timezone Asia/Karachi" in note


@pytest.mark.asyncio
async def test_a_failed_lookup_never_takes_the_call_down():
    class _DB:
        async def execute(self, _query):
            raise RuntimeError("connection reset")

    class _Agent:
        user_id = "u1"

    assert "timezone UTC" in await current_time_note(_DB(), _Agent())


# ---------- the rules ----------
def test_every_channel_gets_the_date_rules_and_voice_also_gets_the_email_rules():
    assert "CURRENT DATE AND TIME" in CONDUCT_RULES
    assert "full date and time" in CONDUCT_RULES
    assert "read it back one letter at a time" in VOICE_RULES
    assert "never spell out the word one" in VOICE_RULES
    assert "at the rate" in VOICE_RULES
    # The platform rules must stay speakable: this is the pre-existing guard.
    assert "emoji" not in CONDUCT_RULES.lower()


# ---------- spoken emails ----------
@pytest.mark.parametrize(
    "spoken,written",
    [
        ("my email is john dot smith at gmail dot com", "my email is john.smith@gmail.com"),
        ("john dot smith at gmail dot com.", "john.smith@gmail.com."),
        ("yes it's mike dot ross at outlook dot com, thanks", "yes it's mike.ross@outlook.com, thanks"),
        ("it is mike at outlook dot com and my number is 555", "it is mike@outlook.com and my number is 555"),
        ("it's j o h n at g m a i l dot c o m", "it's john@gmail.com"),
        ("sara underscore 99 at yahoo dot co dot uk", "sara_99@yahoo.co.uk"),
        ("john one two three at gmail dot com", "john123@gmail.com"),
        ("info at the rate acme dot com", "info@acme.com"),
        ("jo dash ann at acme dot io", "jo-ann@acme.io"),
        ("my email is smith at gmail.com", "my email is smith@gmail.com"),
        # The exact phrasing a real caller produced: STT split "gmail" in two.
        ("Yes. My email is a l I one two three four a s a d at g mail dot com.", "Yes. My email is ali1234asad@gmail.com."),
        ("a l i 1 2 3 4 a s a d at g mail dot com", "ali1234asad@gmail.com"),
        ("John Dot Smith AT Gmail DOT com", "john.smith@gmail.com"),  # case is noise from speech-to-text
    ],
)
def test_a_spoken_address_becomes_an_address(spoken, written):
    assert normalize_spoken_emails(spoken) == written


@pytest.mark.parametrize(
    "text",
    [
        "send it to john@gmail.com please",   # already written out
        "meet me at five dot",
        "I'll be at the clinic dot com is down",
        "Tuesday at three pm",
        "call me at home dot",
        "hello at world dot zzzz",            # not a real top-level domain
        "I'll see you at the gym dot com",
        "a b at c mail is down",              # a split domain still needs its dot
        "is that at gmail dot com",           # a question, not an address
        "at gmail dot com",                   # nothing before the "at"
        "",
        "no address here",
    ],
)
def test_ordinary_speech_is_left_alone(text):
    assert normalize_spoken_emails(text) == text


def test_none_and_empty_are_safe():
    assert normalize_spoken_emails("") == ""
    assert normalize_spoken_emails(None) is None
