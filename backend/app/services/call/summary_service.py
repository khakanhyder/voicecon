"""
Call summary service.

Produces a concise, human-readable recap of a call plus a sentiment read,
using the configured LLM. Falls back to a deterministic heuristic when no LLM
is configured or the provider errors, so every completed call still gets a
summary and a sentiment score for the analytics dashboard.
"""
import logging
import re
from dataclasses import dataclass
from typing import List, Optional

from app.services.voice.llm_service import get_llm_service
from app.services.voice.providers.base import ChatMessage
from app.services.call.transcript_service import TranscriptEntry

logger = logging.getLogger(__name__)


@dataclass
class CallSummaryResult:
    """Result of summarizing a call."""
    summary: str
    sentiment_label: str          # positive | neutral | negative
    sentiment_score: float        # 0.0 - 1.0
    generated_by: str             # "llm" or "heuristic"


_POSITIVE_WORDS = {
    "thanks", "thank", "great", "perfect", "awesome", "good", "helpful",
    "appreciate", "excellent", "happy", "resolved", "yes", "sure", "wonderful",
    "love", "glad", "fantastic", "confirmed", "sounds good",
}
_NEGATIVE_WORDS = {
    "no", "not", "never", "bad", "terrible", "awful", "angry", "frustrated",
    "wrong", "cancel", "refund", "complaint", "problem", "issue", "unhappy",
    "disappointed", "hate", "worse", "worst", "annoyed", "useless",
}


class CallSummaryService:
    """Generates conversation summaries and sentiment for finished calls."""

    def __init__(self):
        self.llm_service = get_llm_service()

    async def summarize(
        self,
        transcript: List[TranscriptEntry],
        *,
        provider: str = "openai",
        model: Optional[str] = None,
    ) -> Optional[CallSummaryResult]:
        """
        Summarize a transcript.

        Args:
            transcript: Ordered transcript entries for the call.
            provider: LLM provider to use (falls back to heuristic on failure).
            model: Optional model override.

        Returns:
            CallSummaryResult, or None if the transcript is empty.
        """
        if not transcript:
            return None

        transcript_text = self._format(transcript)

        # Try the LLM first for a high-quality summary.
        try:
            result = await self._summarize_with_llm(transcript_text, provider, model)
            if result:
                return result
        except Exception as e:  # noqa: BLE001 - never fail call teardown on this
            logger.warning(f"LLM summary failed, using heuristic fallback: {e}")

        # Deterministic fallback.
        return self._summarize_heuristic(transcript, transcript_text)

    # ------------------------------------------------------------------ #

    def _format(self, transcript: List[TranscriptEntry], max_chars: int = 6000) -> str:
        lines = []
        for entry in transcript:
            speaker = "Caller" if entry.speaker == "user" else "Agent"
            lines.append(f"{speaker}: {entry.text}")
        text = "\n".join(lines)
        # Keep the prompt bounded for very long calls.
        if len(text) > max_chars:
            text = text[-max_chars:]
        return text

    async def _summarize_with_llm(
        self, transcript_text: str, provider: str, model: Optional[str]
    ) -> Optional[CallSummaryResult]:
        system = (
            "You are an analyst that summarizes phone conversations between a "
            "caller and an AI voice agent. Respond in strict JSON with keys: "
            '"summary" (2-4 sentence recap of what the caller wanted and how it '
            'was resolved), "sentiment" (one of "positive", "neutral", '
            '"negative"), and "sentiment_score" (a number from 0 to 1 where 1 is '
            "very positive). Do not include any text outside the JSON."
        )
        messages = [
            ChatMessage(role="system", content=system),
            ChatMessage(role="user", content=f"Transcript:\n{transcript_text}"),
        ]

        result = await self.llm_service.chat(
            messages,
            provider=provider or "openai",
            model=model,
            temperature=0.3,
            max_tokens=400,
        )

        content = (result.content or "").strip()
        if not content:
            return None

        import json

        # Be forgiving: pull the first JSON object out of the response.
        match = re.search(r"\{.*\}", content, re.DOTALL)
        payload = match.group(0) if match else content
        data = json.loads(payload)

        summary = str(data.get("summary", "")).strip()
        if not summary:
            return None

        label = str(data.get("sentiment", "neutral")).lower().strip()
        if label not in ("positive", "neutral", "negative"):
            label = "neutral"

        try:
            score = float(data.get("sentiment_score"))
        except (TypeError, ValueError):
            score = {"positive": 0.8, "neutral": 0.5, "negative": 0.2}[label]
        score = max(0.0, min(1.0, score))

        return CallSummaryResult(
            summary=summary,
            sentiment_label=label,
            sentiment_score=round(score, 2),
            generated_by="llm",
        )

    def _summarize_heuristic(
        self, transcript: List[TranscriptEntry], transcript_text: str
    ) -> CallSummaryResult:
        label, score = self._heuristic_sentiment(transcript_text)

        turns = len(transcript)
        first_user = next(
            (e.text.strip() for e in transcript if e.speaker == "user" and e.text.strip()),
            None,
        )
        topics = self._top_keywords(transcript_text)

        parts = []
        if first_user:
            snippet = first_user if len(first_user) <= 140 else first_user[:137] + "..."
            parts.append(f'Caller opened with: "{snippet}"')
        parts.append(f"{turns} turn{'s' if turns != 1 else ''} exchanged.")
        if topics:
            parts.append(f"Key topics: {', '.join(topics)}.")
        parts.append(f"Overall sentiment read as {label}.")

        return CallSummaryResult(
            summary=" ".join(parts),
            sentiment_label=label,
            sentiment_score=round(score, 2),
            generated_by="heuristic",
        )

    def _heuristic_sentiment(self, text: str) -> tuple[str, float]:
        words = re.findall(r"[a-z']+", text.lower())
        if not words:
            return "neutral", 0.5
        pos = sum(1 for w in words if w in _POSITIVE_WORDS)
        neg = sum(1 for w in words if w in _NEGATIVE_WORDS)
        if pos == 0 and neg == 0:
            return "neutral", 0.5
        # Map the pos/neg balance onto a 0-1 score centred at 0.5.
        score = 0.5 + (pos - neg) / (2 * (pos + neg))
        score = max(0.0, min(1.0, score))
        if score > 0.6:
            return "positive", score
        if score < 0.4:
            return "negative", score
        return "neutral", score

    def _top_keywords(self, text: str, top_n: int = 4) -> List[str]:
        stop = {
            "the", "and", "you", "for", "that", "this", "with", "have", "your",
            "was", "are", "will", "would", "can", "could", "there", "what",
            "okay", "yeah", "yes", "just", "like", "want", "need", "know",
        }
        freq: dict[str, int] = {}
        for word in re.findall(r"[a-z']{4,}", text.lower()):
            if word not in stop:
                freq[word] = freq.get(word, 0) + 1
        return [w for w, _ in sorted(freq.items(), key=lambda kv: kv[1], reverse=True)[:top_n]]


_summary_service: Optional[CallSummaryService] = None


def get_summary_service() -> CallSummaryService:
    """Get the global call summary service (singleton)."""
    global _summary_service
    if _summary_service is None:
        _summary_service = CallSummaryService()
    return _summary_service
