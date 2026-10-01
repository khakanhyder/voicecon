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
_DIGIT_WORDS = {
    "zero": "0", "oh": "0", "one": "1", "two": "2", "three": "3", "four": "4",
    "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9",
}
#: "at the rate (of)" is how many callers say @.
_AT_THE_RATE = re.compile(r"\bat\s+the\s+rate(?:\s+of)?\b", re.IGNORECASE)
_TRAILING_PUNCT = ".,;:!?"
#: Words that stand right before "at" in ordinary speech ("is that at gmail dot
#: com?"), never as the end of an address. Without this a question about gmail
#: became "is that@gmail.com".
_NOT_A_LOCAL_PART = {
    "is", "that", "this", "it", "its", "it's", "the", "a", "an", "me", "my", "you",
    "your", "we", "they", "he", "she", "and", "or", "to", "of", "on", "in", "for",
    "so", "if", "then", "there", "here", "who", "what", "was", "are", "am", "be",
    "from", "with", "email", "mail", "address", "id", "emailed", "mailed",
}


def _strip(token: str) -> str:
    return token.strip(_TRAILING_PUNCT + "\"'()")


def _kind(token: str) -> str:
    """CONNECTOR, DIGIT, CHAR (one letter/digit), or WORD."""
    low = _strip(token).lower()
    if low in _CONNECTORS:
        return "CONNECTOR"
    if low in _DIGIT_WORDS:
        return "DIGIT"
    if len(low) == 1 and low.isalnum():
        return "CHAR"
    return "WORD"


def _render(token: str) -> str:
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
                and _strip(tokens[i + 1]).lower() in ("dot", "period", "point")
            ):
                label += _strip(tokens[i]).lower()
                i += 1
        elif re.fullmatch(r"[a-z0-9-]+", low) and _kind(tokens[i]) == "WORD":
            label = low
            i += 1
        else:
            break
        labels.append(label)

        # Sentence punctuation on the label's last token ends the address.
        if tokens[i - 1] != _strip(tokens[i - 1]):
            break
        if i < len(tokens) and _strip(tokens[i]).lower() in ("dot", "period", "point"):
            i += 1
            continue
        break

    if len(labels) < 2 or not all(labels) or labels[-1] not in TLDS:
        return None
    return ".".join(labels), i


def normalize_spoken_emails(text: str) -> str:
    """
    Rewrite an email address that was spoken ("john dot smith at gmail dot com")
    as written (``john.smith@gmail.com``). Text with no spoken address, and
    addresses already written out, are returned unchanged.

    Deliberately conservative: it only acts around the word "at" when what
    follows is a domain ending in a real TLD, so "meet me at five dot" or "at
    the clinic" are left alone. The local part takes spelled-out letters,
    digit words and "dot/underscore/dash" connectors, plus at most one plain
    word glued on by a connector or standing right before "at".
    """
    if not text or not re.search(r"\bat\b", text, re.IGNORECASE):
        return text

    text = _AT_THE_RATE.sub("at", text)
    tokens = text.split()
    out: list[str] = []
    i = 0
    while i < len(tokens):
        if _strip(tokens[i]).lower() != "at" or not out:
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
        taken = 0
        while j > 0:
            kind = _kind(out[j - 1])
            if kind in ("CHAR", "DIGIT", "CONNECTOR"):
                j -= 1
                taken += 1
                continue
            if kind == "WORD":
                nearest = j == len(out)
                after_connector = j < len(out) and _kind(out[j]) == "CONNECTOR"
                before_connector = j > 1 and _kind(out[j - 2]) == "CONNECTOR"
                before_digits = j < len(out) and _kind(out[j]) == "DIGIT"
                if nearest and _strip(out[j - 1]).lower() in _NOT_A_LOCAL_PART:
                    break
                if nearest or after_connector or before_connector or before_digits:
                    j -= 1
                    taken += 1
                    # A plain word only ever joins to a neighbour by a
                    # connector, so a second bare word ends the walk.
                    if not (before_connector or after_connector or before_digits) and j > 0 and _kind(out[j - 1]) == "WORD":
                        break
                    continue
            break

        if taken == 0:
            out.append(tokens[i])
            i += 1
            continue

        # Lowercased: speech-to-text capitalises letters at random ("a l I"), and
        # nobody's address depends on case.
        local = "".join(_render(t) for t in out[j:]).lower()
        # A local part cannot start or end on a connector.
        local = local.strip("._-+")
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
        i = domain[1]
    return " ".join(out)
