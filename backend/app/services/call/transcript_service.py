"""
Transcript Service.

Handles call transcript generation, storage, and analysis.
"""
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
from dataclasses import dataclass
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.call import Call, CallLog

logger = logging.getLogger(__name__)


@dataclass
class TranscriptEntry:
    """Single transcript entry with metadata."""
    speaker: str  # "user" or "assistant"
    text: str
    timestamp: datetime
    confidence: Optional[float] = None
    duration_ms: Optional[int] = None


@dataclass
class TranscriptAnalysis:
    """Analysis of call transcript."""
    total_words: int
    user_words: int
    assistant_words: int
    turn_count: int
    average_turn_length: float
    user_talk_time_percentage: float
    key_topics: List[str]
    sentiment: Optional[str] = None
    sentiment_score: Optional[float] = None


class TranscriptService:
    """
    Service for managing call transcripts.

    Features:
    - Build transcripts from call logs
    - Format transcripts (plain text, JSON, SRT)
    - Analyze transcripts
    - Extract key information
    - Search transcripts
    """

    def __init__(self):
        """Initialize transcript service."""
        pass

    async def build_transcript(
        self,
        call: Call,
        db: AsyncSession,
    ) -> List[TranscriptEntry]:
        """
        Build complete transcript from call logs.

        Args:
            call: Call record
            db: Database session

        Returns:
            List of transcript entries
        """
        try:
            # Get all call logs for transcriptions
            result = await db.execute(
                select(CallLog)
                .where(CallLog.call_id == call.id)
                .where(CallLog.log_type.in_(["stt", "llm"]))
                .order_by(CallLog.timestamp)
            )
            logs = result.scalars().all()

            transcript = []

            for log in logs:
                details = log.details or {}

                if log.log_type == "stt":
                    # User speech (from STT)
                    transcript.append(TranscriptEntry(
                        speaker="user",
                        text=details.get("transcript", ""),
                        timestamp=log.timestamp,
                        confidence=details.get("confidence"),
                        duration_ms=log.duration_ms,
                    ))

                elif log.log_type == "llm":
                    # Assistant response (from LLM)
                    transcript.append(TranscriptEntry(
                        speaker="assistant",
                        text=details.get("response", ""),
                        timestamp=log.timestamp,
                        duration_ms=log.duration_ms,
                    ))

            logger.info(f"Built transcript with {len(transcript)} entries for call {call.id}")

            return transcript

        except Exception as e:
            logger.error(f"Error building transcript: {e}", exc_info=True)
            return []

    async def save_transcript(
        self,
        call: Call,
        transcript: List[TranscriptEntry],
        db: AsyncSession,
    ) -> bool:
        """
        Save transcript to call record.

        Args:
            call: Call record
            transcript: List of transcript entries
            db: Database session

        Returns:
            True if saved successfully
        """
        try:
            # Format as plain text
            transcript_text = self.format_transcript_text(transcript)

            # Format as JSON for structured data
            transcript_json = self.format_transcript_json(transcript)

            # Update call record
            call.transcript = transcript_text
            call.transcript_json = transcript_json

            await db.commit()

            logger.info(f"Saved transcript for call {call.id}")

            return True

        except Exception as e:
            logger.error(f"Error saving transcript: {e}", exc_info=True)
            return False

    def format_transcript_text(self, transcript: List[TranscriptEntry]) -> str:
        """
        Format transcript as plain text.

        Args:
            transcript: List of transcript entries

        Returns:
            Formatted text
        """
        lines = []

        for entry in transcript:
            timestamp = entry.timestamp.strftime("%H:%M:%S")
            speaker = entry.speaker.upper()
            lines.append(f"[{timestamp}] {speaker}: {entry.text}")

        return "\n".join(lines)

    def format_transcript_json(self, transcript: List[TranscriptEntry]) -> Dict[str, Any]:
        """
        Format transcript as JSON.

        Args:
            transcript: List of transcript entries

        Returns:
            JSON structure
        """
        return {
            "entries": [
                {
                    "speaker": entry.speaker,
                    "text": entry.text,
                    "timestamp": entry.timestamp.isoformat(),
                    "confidence": entry.confidence,
                    "duration_ms": entry.duration_ms,
                }
                for entry in transcript
            ],
            "entry_count": len(transcript),
        }

    def format_transcript_srt(self, transcript: List[TranscriptEntry]) -> str:
        """
        Format transcript as SRT subtitle format.

        Args:
            transcript: List of transcript entries

        Returns:
            SRT formatted text
        """
        lines = []
        start_time = transcript[0].timestamp if transcript else datetime.utcnow()

        for i, entry in enumerate(transcript, 1):
            # Calculate time offset from start
            offset_ms = int((entry.timestamp - start_time).total_seconds() * 1000)
            duration_ms = entry.duration_ms or 2000  # Default 2 seconds

            # Format timestamps
            start = self._format_srt_timestamp(offset_ms)
            end = self._format_srt_timestamp(offset_ms + duration_ms)

            # Add SRT entry
            lines.append(f"{i}")
            lines.append(f"{start} --> {end}")
            lines.append(f"{entry.speaker.upper()}: {entry.text}")
            lines.append("")  # Blank line

        return "\n".join(lines)

    def _format_srt_timestamp(self, milliseconds: int) -> str:
        """
        Format milliseconds as SRT timestamp.

        Args:
            milliseconds: Time in milliseconds

        Returns:
            Formatted timestamp (HH:MM:SS,mmm)
        """
        hours = milliseconds // 3600000
        milliseconds %= 3600000
        minutes = milliseconds // 60000
        milliseconds %= 60000
        seconds = milliseconds // 1000
        milliseconds %= 1000

        return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"

    async def analyze_transcript(
        self,
        transcript: List[TranscriptEntry],
    ) -> TranscriptAnalysis:
        """
        Analyze transcript for insights.

        Args:
            transcript: List of transcript entries

        Returns:
            Transcript analysis
        """
        try:
            # Count words by speaker
            user_words = []
            assistant_words = []

            for entry in transcript:
                words = entry.text.split()
                if entry.speaker == "user":
                    user_words.extend(words)
                else:
                    assistant_words.extend(words)

            total_words = len(user_words) + len(assistant_words)

            # Calculate turn count
            turn_count = len(transcript)

            # Calculate average turn length
            avg_turn_length = total_words / turn_count if turn_count > 0 else 0

            # Calculate talk time percentage
            user_percentage = (len(user_words) / total_words * 100) if total_words > 0 else 0

            # Extract key topics (simple word frequency)
            key_topics = self._extract_key_topics(transcript)

            # Sentiment analysis (placeholder)
            sentiment, sentiment_score = self._analyze_sentiment(transcript)

            return TranscriptAnalysis(
                total_words=total_words,
                user_words=len(user_words),
                assistant_words=len(assistant_words),
                turn_count=turn_count,
                average_turn_length=avg_turn_length,
                user_talk_time_percentage=user_percentage,
                key_topics=key_topics,
                sentiment=sentiment,
                sentiment_score=sentiment_score,
            )

        except Exception as e:
            logger.error(f"Error analyzing transcript: {e}", exc_info=True)
            return TranscriptAnalysis(
                total_words=0,
                user_words=0,
                assistant_words=0,
                turn_count=0,
                average_turn_length=0.0,
                user_talk_time_percentage=0.0,
                key_topics=[],
            )

    def _extract_key_topics(self, transcript: List[TranscriptEntry], top_n: int = 5) -> List[str]:
        """
        Extract key topics from transcript.

        Simple implementation using word frequency.
        In production, use NLP libraries like spaCy or transformers.

        Args:
            transcript: List of transcript entries
            top_n: Number of top topics to return

        Returns:
            List of key topics
        """
        # Combine all text
        all_text = " ".join(entry.text for entry in transcript)

        # Simple word frequency (excluding common words)
        stop_words = {
            "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
            "of", "with", "is", "was", "are", "were", "be", "been", "being",
            "have", "has", "had", "do", "does", "did", "will", "would", "should",
            "could", "may", "might", "can", "i", "you", "he", "she", "it", "we",
            "they", "my", "your", "his", "her", "its", "our", "their", "this",
            "that", "these", "those", "what", "which", "who", "when", "where",
            "why", "how", "just", "so", "very", "too", "also", "only", "more",
        }

        words = all_text.lower().split()
        word_freq = {}

        for word in words:
            # Remove punctuation
            word = word.strip(".,!?;:")

            if word and len(word) > 3 and word not in stop_words:
                word_freq[word] = word_freq.get(word, 0) + 1

        # Sort by frequency
        sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)

        # Return top N
        return [word for word, _ in sorted_words[:top_n]]

    def _analyze_sentiment(self, transcript: List[TranscriptEntry]) -> tuple[Optional[str], Optional[float]]:
        """
        Analyze sentiment of transcript.

        Placeholder implementation.
        In production, use sentiment analysis models.

        Args:
            transcript: List of transcript entries

        Returns:
            Tuple of (sentiment label, sentiment score)
        """
        # TODO: Implement real sentiment analysis
        # For now, return neutral
        return "neutral", 0.5

    async def search_transcripts(
        self,
        query: str,
        db: AsyncSession,
        user_id: str,
        limit: int = 50,
    ) -> List[Call]:
        """
        Search transcripts for text.

        Args:
            query: Search query
            db: Database session
            user_id: User ID for filtering
            limit: Maximum results

        Returns:
            List of matching calls
        """
        try:
            # Search in transcript field
            result = await db.execute(
                select(Call)
                .where(Call.user_id == user_id)
                .where(Call.transcript.ilike(f"%{query}%"))
                .order_by(Call.created_at.desc())
                .limit(limit)
            )

            calls = result.scalars().all()

            logger.info(f"Found {len(calls)} calls matching '{query}'")

            return calls

        except Exception as e:
            logger.error(f"Error searching transcripts: {e}", exc_info=True)
            return []


# Global transcript service instance
_transcript_service: Optional[TranscriptService] = None


def get_transcript_service() -> TranscriptService:
    """
    Get global transcript service instance (singleton).

    Returns:
        TranscriptService instance
    """
    global _transcript_service
    if _transcript_service is None:
        _transcript_service = TranscriptService()
    return _transcript_service
