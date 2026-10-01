"""
Turn-taking rules for a live voice conversation.

Pure functions, shared by real phone calls (voice_session.py) and the browser
test relay (agents.py), so a test call takes turns the way the phone does.

A pause alone does not say whether a caller has finished: people stop
mid-sentence to think, and between the groups of a phone number. These rules
decide how much longer to wait after the pause, tell the agent's own voice
coming back down the line apart from the caller, and recognise sounds that
are not a turn at all.
"""
import re
from typing import List, Optional, Tuple

#: Longest extra wait any rule can add, in seconds.
MAX_EXTRA_WAIT = 1.5

# Words nobody ends a sentence on: the caller is still going.
_STRONG_TRAILING = {
    "and", "but", "or", "so", "because", "cause", "if", "to", "for", "with",
    "of", "at", "the", "a", "an", "my", "your", "our", "is", "are", "um",
    "uh", "er", "erm", "like", "plus", "than", "from", "by", "about",
}
# Words that usually mean more is coming, but can end a short sentence
# ("I'll take that."), so they only count when no full stop was heard.
_WEAK_TRAILING = {
    "that", "which", "who", "when", "where", "while", "then", "also", "well",
    "i", "i'm", "it's", "was", "on", "in", "as", "until", "between", "hmm",
}
_NUMBER_WORDS = {
    "zero", "oh", "one", "two", "three", "four", "five", "six", "seven",
    "eight", "nine", "ten", "eleven", "twelve", "thirteen", "fourteen",
    "fifteen", "sixteen", "seventeen", "eighteen", "nineteen", "twenty",
    "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety",
    "hundred", "thousand", "double", "triple",
}
# Sounds a listener makes while the other side talks. Deliberately narrow:
# "okay" and "yeah" are often real answers, so they are not here.
_BACKCHANNEL = {
    "mm", "mmm", "mhm", "mmhm", "mmhmm", "mm-hm", "mm-hmm", "hmm", "hm", "uh", "huh", "uh-huh",
    "um", "ah", "oh", "hello", "hi", "hey",
}
# The agent just asked for something people say slowly, in groups.
_SLOW_ANSWER_RE = re.compile(
    r"\b(number|email|e-mail|address|spell|spelling|date of birth|birthday|"
    r"post ?code|zip|card|digits?|reference|account)\b",
    re.IGNORECASE,
)
_WORD_RE = re.compile(r"[a-z0-9'À-ɏ-]+")
# Abbreviations whose full stop does not end a sentence.
_ABBREVIATIONS = {"mr", "mrs", "ms", "dr", "st", "vs", "no", "a.m", "p.m", "e.g", "i.e"}
_SENTENCE_END_RE = re.compile(r"(?<=[.!?])\s+")
#: Shortest piece worth its own text-to-speech request; anything shorter is
#: joined to the sentence after it.
MIN_SPOKEN_CHARS = 20


def _words(text: str) -> List[str]:
    return _WORD_RE.findall((text or "").lower())


def expects_slow_answer(agent_text: Optional[str]) -> bool:
    """Whether the agent's last line asked for a number, address, spelling…"""
    return bool(agent_text and _SLOW_ANSWER_RE.search(agent_text))


def extra_wait_seconds(
    text: str,
    agent_last: Optional[str] = None,
    language: str = "en",
) -> float:
    """
    Seconds to keep waiting after the caller's pause before answering.

    Zero when the words sound finished. Longer when they trail off ("I'd like
    to book for"), stop on a number, or the agent just asked for something
    said in groups. The agent's Silence Timeout has already elapsed when this
    is asked; this is the wait on top of it.

    Args:
        text: What the caller has said so far this turn
        agent_last: The agent's previous line, if any
        language: The agent's speech-recognition language

    Returns:
        Extra seconds to wait, between 0 and MAX_EXTRA_WAIT
    """
    stripped = (text or "").strip()
    words = _words(stripped)
    if not words:
        return 0.0
    if stripped.endswith(("?", "!")):
        return 0.0
    if stripped.endswith((",", "-", "…", "...")):
        return MAX_EXTRA_WAIT

    last = words[-1]
    has_full_stop = stripped.endswith(".")
    # The word lists are English; other languages use only the punctuation
    # and digit rules.
    english = (language or "en").lower().startswith("en")
    if english and last in _STRONG_TRAILING:
        return MAX_EXTRA_WAIT
    if english and last in _WEAK_TRAILING and not has_full_stop:
        return 1.2

    slow = expects_slow_answer(agent_last)
    ends_on_number = last.isdigit() or (english and last in _NUMBER_WORDS)
    if ends_on_number:
        return MAX_EXTRA_WAIT if slow else 0.8
    # Spelling something out, one letter at a time.
    if slow and len(last) == 1:
        return MAX_EXTRA_WAIT

    if not has_full_stop and len(words) > 3:
        return 0.6
    return 0.0


def is_backchannel(text: str) -> bool:
    """A listening noise ("mm-hm") or a "hello?" over the agent — not a turn."""
    words = _words(text)
    return 0 < len(words) <= 3 and all(w in _BACKCHANNEL for w in words)


def is_echo(heard: str, agent_text: str) -> bool:
    """
    Whether what was heard is the agent's own voice coming back (a caller on
    speakerphone), judged by how many of the words the agent is saying.

    One word is never called echo: it is too easily a real "yes".
    """
    heard_words = _words(heard)
    if len(heard_words) < 2:
        return False
    agent_words = set(_words(agent_text))
    if not agent_words:
        return False
    matched = sum(1 for w in heard_words if w in agent_words)
    return matched / len(heard_words) >= 0.75


def pop_sentences(buffer: str, final: bool = False) -> Tuple[List[str], str]:
    """
    Take the complete sentences off the front of streamed LLM text so they can
    be spoken while the rest is still being written.

    Args:
        buffer: Text received so far and not yet spoken
        final: The stream has ended, so whatever is left is spoken too

    Returns:
        (sentences ready to speak, text still waiting for its ending)
    """
    sentences: List[str] = []
    start = 0
    for match in _SENTENCE_END_RE.finditer(buffer):
        piece = buffer[start:match.start()]
        tail = piece.rstrip(".!?").rsplit(None, 1)[-1].lower() if piece.strip() else ""
        if len(piece.strip()) < MIN_SPOKEN_CHARS or tail in _ABBREVIATIONS:
            continue
        sentences.append(piece.strip())
        start = match.end()
    rest = buffer[start:]
    if final:
        if rest.strip():
            sentences.append(rest.strip())
        rest = ""
    return sentences, rest
