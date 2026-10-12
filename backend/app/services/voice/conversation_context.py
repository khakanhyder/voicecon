"""
What an agent has to be told, or told correctly, to handle dates and emails.

Two problems, both of which a prompt alone cannot solve:

* **The model does not know what day it is.** "Next Friday", "tomorrow at 3"
  and "do you have anything this week" cannot be answered without it, and an
  agent that guesses will offer slots in the past. So every conversation starts
  with the real date and time in the agent owner's timezone, plus a short
  calendar of the coming days — models are bad at weekday arithmetic, and a
  list they can read off removes the arithmetic.

* **Speech-to-text writes emails the way they are said.** A caller who says
  "john dot smith at gmail dot com" arrives as those words, and the model has
  to guess the address from them. `normalize_spoken_emails` turns it into
  ``john.smith@gmail.com`` before the model sees it, so the guess is a rule
  that can be tested instead of a habit of the model. The agent is still told
  to read the address back and wait for a yes: the rules improve the guess,
  they cannot prove it.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tlds import TLDS

logger = logging.getLogger(__name__)

#: How many days ahead the agent gets a ready-made calendar for.
CALENDAR_DAYS = 14


# ─────────────────────────────────────────────────────────────────────────────
# Today's date
# ─────────────────────────────────────────────────────────────────────────────
def resolve_timezone(name: Optional[str]) -> ZoneInfo:
    """The named zone, or UTC when it is blank or not a real zone."""
    if name:
        try:
            return ZoneInfo(name)
        except (ZoneInfoNotFoundError, ValueError):
            logger.warning("Unknown timezone %r on an agent owner; using UTC", name)
    return ZoneInfo("UTC")


def _day(d: datetime) -> str:
    # No %-d: it is not portable. Strip the leading zero by hand.
    return f"{d.strftime('%A')} {d.day} {d.strftime('%B')}"


def datetime_note(now_utc: Optional[datetime] = None, tz_name: Optional[str] = None) -> str:
    """
    The "it is now …" block appended to an agent's system prompt.

    `now_utc` exists so tests can pin the clock; production passes nothing.
    """
    tz = resolve_timezone(tz_name)
    now = (now_utc or datetime.now(timezone.utc)).astimezone(tz)
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)

    days = []
    for offset in range(CALENDAR_DAYS):
        d = today + timedelta(days=offset)
        label = _day(d)
        if offset == 0:
            label += " (today)"
        elif offset == 1:
            label += " (tomorrow)"
        days.append(label)

    clock = f"{now.hour % 12 or 12}:{now.minute:02d} {'AM' if now.hour < 12 else 'PM'}"
    return (
        "\n\nCURRENT DATE AND TIME (use this, never guess it):\n"
        f"- Right now it is {_day(now)} {now.year}, {clock}, timezone {tz.key}.\n"
        f"- The next {CALENDAR_DAYS} days: " + "; ".join(days) + ".\n"
        "- Work out \"tomorrow\", \"next Friday\", \"this weekend\" and similar from "
        "the list above. Never offer, accept or book a time that has already "
        "passed today."
    )


async def current_time_note(db: AsyncSession, agent) -> str:
    """
    `datetime_note` in the timezone of whoever owns the agent.

    The owner's profile timezone is the best signal available — a business's
    callers and its opening hours live there — and it falls back to UTC when
    unset. A lookup failure must never take a call down, so it degrades to UTC.
    """
    tz_name = None
    try:
        from app.models.user import User

        tz_name = (
            await db.execute(select(User.timezone).where(User.id == agent.user_id))
        ).scalar_one_or_none()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not load the agent owner's timezone: %s", exc)
    return datetime_note(tz_name=tz_name)


# ─────────────────────────────────────────────────────────────────────────────
# Spoken email addresses
# ─────────────────────────────────────────────────────────────────────────────
_CONNECTORS = {
    "dot": ".", "period": ".", "point": ".",
    "underscore": "_", "dash": "-", "hyphen": "-", "plus": "+",
}
_DOT_WORDS = ("dot", "period", "point")
_DIGIT_WORDS = {
    "zero": "0", "oh": "0", "one": "1", "two": "2", "three": "3", "four": "4",
    "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9",
}
#: Everything a caller says, or speech-to-text hears, for "@". "at the rate
#: (of)" is how many callers say it; "at the red", "at the of rate", "at rate"
#: and "add the rate" are how speech-to-text mishears it. A match only counts
#: when a real domain follows, so "at the right time" is never touched.
_AT_PHRASE = re.compile(
    r"\b(?:at|add|ad|et)\s+(?:(?:the|da|de|d|a)\s+)?(?:of\s+)?"
    r"(?:rate|rates|rated|red|rat|right|raid|read|ret|reat)(?:\s+of)?\b"
    r"|\bat\s+(?:sign|symbol)\b"
    r"|\s+@\s*|@\s+",  # "@" that speech-to-text wrote with spaces round it
    re.IGNORECASE,
)
#: "full stop" is how many callers say the dot in a name ("sajid full stop ali").
_DOT_PHRASE = re.compile(r"\bfull\s+stop\b", re.IGNORECASE)
#: Mail providers callers name without the dot ("gmail com") or that
#: speech-to-text splits in two ("hot mail").
_PROVIDERS = {
    "gmail", "googlemail", "yahoo", "ymail", "hotmail", "outlook", "live", "msn",
    "icloud", "aol", "protonmail", "proton", "zoho", "gmx", "yandex",
}
#: Endings safe to join to a label across sentence punctuation ("Gmail. Com.").
#: Kept short on purpose: "in" or "me" there is far more often the next sentence.
_SPOKEN_TLDS = {
    "com", "net", "org", "co", "io", "ai", "edu", "gov", "pk", "uk", "us", "ca",
    "au", "de", "info", "biz",
}
_TRAILING_PUNCT = ".,;:!?"
#: Words that stand before an address in ordinary speech ("my email is ...",
#: "yes it's ...") and are never part of it. The local part is read backwards
#: from the "at" and stops at the first of these.
_NOT_A_LOCAL_PART = {
    "is", "that", "this", "it", "its", "it's", "the", "a", "an", "me", "my", "you",
    "your", "we", "they", "he", "she", "and", "or", "to", "of", "on", "in", "for",
    "so", "if", "then", "there", "here", "who", "what", "was", "are", "am", "be",
    "from", "with", "email", "e-mail", "mail", "address", "id", "emailed", "mailed",
    "i'm", "im", "yes", "yeah", "yep", "sure", "okay", "ok", "um", "uh", "hmm",
    "well", "please", "just", "actually", "no", "not", "sorry", "but", "also",
    "use", "try", "send", "reach", "contact", "write", "note", "down", "name",
    "called", "spelled", "spell", "like", "correct", "right", "by", "via", "at",
    "maybe", "perhaps", "probably", "think", "guess", "mean", "meant", "now",
    "again", "instead", "rather", "change", "update", "new", "old", "other",
    "another", "let", "let's", "lets", "give", "take", "have", "has", "had", "got",
    "need", "want", "wanna", "gonna", "can", "could", "will", "would", "should",
    "do", "does", "did", "be", "been", "being", "say", "said", "type", "typed",
    "put", "make", "go", "should've", "work", "personal", "business", "office",
    "official", "gmail", "hotmail", "outlook", "yahoo", "account", "one's",
}
#: At most this many plain words make up a local part ("sajid ali khan at …").
_MAX_LOCAL_WORDS = 3
_LOCAL_WORD = re.compile(r"[a-z0-9][a-z0-9._+-]*")
_EMAIL = re.compile(r"[a-z0-9][a-z0-9._%+-]*@[a-z0-9-]+(?:\.[a-z0-9-]+)*\.[a-z]{2,}")
#: Stand-ins for the phrases above while a sentence is being read. A phrase
#: that does not end up inside an address is put back exactly as it was said.
_MARK = ""


def _strip(token: str) -> str:
    return token.strip(_TRAILING_PUNCT + "\"'()")


def _kind(token: str) -> str:
    """AT, CONNECTOR, DIGIT, CHAR (one letter/digit), or WORD."""
    if token.startswith(_MARK):
        return "AT" if token.endswith("@") else "CONNECTOR"
    low = _strip(token).lower()
    if low == "at":
        return "AT"
    if low in _CONNECTORS:
        return "CONNECTOR"
    if low in _DIGIT_WORDS or (low.isdigit() and low.isascii()):
        return "DIGIT"
    if len(low) == 1 and low.isalnum():
        return "CHAR"
    return "WORD"


def _render(token: str) -> str:
    if token.startswith(_MARK):
        return "."
    low = _strip(token).lower()
    if low in _CONNECTORS:
        return _CONNECTORS[low]
    if low in _DIGIT_WORDS:
        return _DIGIT_WORDS[low]
    return _strip(token)


def _domain(tokens: list[str], start: int) -> Optional[tuple[str, int]]:
    """
    Read a domain starting at `start`, ending in a real top-level domain.

    A label is either one spoken word ("gmail") or a run of spelled letters
    ("g m a i l"); labels are separated by "dot". Reading stops at the first
    label not followed by "dot", so the words after an address ("... dot com
    and my number is ...") are never swallowed into it. Returns
    (domain, index just past it).
    """
    labels: list[str] = []
    i = start
    while i < len(tokens):
        low = _strip(tokens[i]).lower()

        if re.fullmatch(r"[a-z0-9-]+(\.[a-z0-9-]+)+", low):
            # Already written out ("gmail.com"): take it whole and stop.
            labels.extend(low.split("."))
            i += 1
            break

        if _kind(tokens[i]) in ("CHAR", "DIGIT"):
            label = ""
            while i < len(tokens) and _kind(tokens[i]) in ("CHAR", "DIGIT"):
                label += _render(tokens[i])
                i += 1
            # Speech-to-text splits "gmail" into "g mail". A word straight after
            # spelled letters belongs to the same label when "dot" follows it.
            if (
                i + 1 < len(tokens)
                and _kind(tokens[i]) == "WORD"
                and re.fullmatch(r"[a-z0-9-]+", _strip(tokens[i]).lower())
                and _strip(tokens[i + 1]).lower() in _DOT_WORDS
            ):
                label += _strip(tokens[i]).lower()
                i += 1
        elif re.fullmatch(r"[a-z0-9-]+", low) and _kind(tokens[i]) == "WORD":
            label = low
            i += 1
            # "hot mail", "proton mail": a provider split in two.
            if (
                i < len(tokens)
                and tokens[i - 1] == _strip(tokens[i - 1])
                and low + _strip(tokens[i]).lower() in _PROVIDERS
            ):
                label = low + _strip(tokens[i]).lower()
                i += 1
        else:
            break
        labels.append(label)

        nxt = _strip(tokens[i]).lower() if i < len(tokens) else ""
        if tokens[i - 1] != _strip(tokens[i - 1]):
            # Speech-to-text punctuates "gmail dot com" as "Gmail. Com.": a
            # full stop followed by a common ending is still the address.
            if tokens[i - 1].endswith(".") and nxt in _SPOKEN_TLDS:
                continue
            # Any other sentence punctuation ends the address.
            break
        if nxt in _DOT_WORDS:
            i += 1
            continue
        # "gmail com": a known provider and an ending, with the dot not heard.
        if label in _PROVIDERS and nxt in _SPOKEN_TLDS:
            continue
        break

    if len(labels) < 2 or not all(labels) or labels[-1] not in TLDS:
        return None
    return ".".join(labels), i


def normalize_spoken_emails(text: str) -> str:
    """
    Rewrite an email address that was spoken ("sajid dot ali at the rate gmail
    dot com") as written (``sajid.ali@gmail.com``). Text with no spoken
    address, and addresses already written out, are returned unchanged.

    Deliberately conservative: it only acts around an "at" (or "at the rate",
    or what speech-to-text makes of it) when what follows is a domain ending in
    a real TLD, so "meet me at five dot" or "at the clinic" are left alone. The
    local part is read backwards from the "at": spelled-out letters, digits,
    "dot/underscore/dash" connectors and up to three plain words, which are
    joined ("sajid ali" becomes "sajidali"). It stops at sentence punctuation
    and at words that introduce an address ("my email is").
    """
    if not text:
        return text

    phrases: list[tuple[str, str]] = []

    def _stand_in(meaning: str):
        def replace(match: re.Match) -> str:
            phrases.append((match.group(0).strip(), meaning))
            return f" {_MARK}{len(phrases) - 1}{meaning} "
        return replace

    work = _AT_PHRASE.sub(_stand_in("@"), text)
    work = _DOT_PHRASE.sub(_stand_in("."), work)
    # A stand-in token is the mark, its index, then its meaning ("@" or ".").
    tokens = work.split()
    if not any(_kind(t) == "AT" for t in tokens):
        return text

    def _original(token: str) -> str:
        if token.startswith(_MARK):
            return phrases[int(token[1:-1])][0]
        return token

    out: list[str] = []
    changed = False
    i = 0
    while i < len(tokens):
        if _kind(tokens[i]) != "AT" or not out:
            out.append(tokens[i])
            i += 1
            continue

        domain = _domain(tokens, i + 1)
        if domain is None:
            out.append(tokens[i])
            i += 1
            continue

        # Walk back over the local part already emitted to `out`.
        j = len(out)
        words = 0
        while j > 0:
            token = out[j - 1]
            # Sentence punctuation before the address ends it ("Yes. sajid at …").
            if j < len(out) and not token.startswith(_MARK) and token != _strip(token):
                break
            kind = _kind(token)
            if kind in ("CHAR", "DIGIT", "CONNECTOR"):
                j -= 1
                continue
            if kind != "WORD":
                break
            low = _strip(token).lower()
            if low in _NOT_A_LOCAL_PART or not _LOCAL_WORD.fullmatch(low) or words == _MAX_LOCAL_WORDS:
                break
            words += 1
            j -= 1

        # Lowercased: speech-to-text capitalises letters at random ("a l I"), and
        # nobody's address depends on case. A local part cannot start or end on
        # a connector.
        local = "".join(_render(t) for t in out[j:]).lower().strip("._-+")
        if not local:
            out.append(tokens[i])
            i += 1
            continue
        trailing = ""
        last = tokens[domain[1] - 1] if domain[1] - 1 < len(tokens) else ""
        if last and last[-1] in _TRAILING_PUNCT and "." not in _strip(last).split(".")[-1:][0]:
            trailing = last[-1]
        del out[j:]
        out.append(f"{local}@{domain[0]}{trailing}")
        changed = True
        i = domain[1]

    if not changed:
        return text
    return " ".join(_original(t) for t in out)


def tidy_email_arguments(arguments: dict) -> dict:
    """
    Clean the email values in a tool call before the tool runs.

    The model sometimes passes an address the way it heard it ("Sajid Ali at
    gmail dot com", "sajid ali@gmail.com"). A booking or CRM tool then stores
    an address that bounces. Any string argument whose name mentions "email"
    is normalised and its spaces removed, but only when the result is one
    valid address; anything else is passed through untouched.
    """
    if not isinstance(arguments, dict):
        return arguments
    tidied = dict(arguments)
    for key, value in arguments.items():
        if "email" not in str(key).lower() or not isinstance(value, str) or not value.strip():
            continue
        candidate = re.sub(r"\s+", "", normalize_spoken_emails(value.strip())).lower()
        candidate = candidate.strip(_TRAILING_PUNCT)
        if _EMAIL.fullmatch(candidate):
            tidied[key] = candidate
    return tidied
