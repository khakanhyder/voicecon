"""
Audio utilities for buffering, streaming, and processing.
"""
import asyncio
import logging
from typing import AsyncIterator, Optional
from collections import deque
from datetime import datetime

from app.services.voice.providers.base import AudioChunk

logger = logging.getLogger(__name__)


class AudioBuffer:
    """
    Thread-safe audio buffer for managing audio chunks.

    Features:
    - Asynchronous put/get operations
    - Configurable max size
    - Duration tracking
    - Automatic cleanup
    """

    def __init__(self, max_size: int = 1000):
        """
        Initialize audio buffer.

        Args:
            max_size: Maximum number of chunks to store
        """
        self.max_size = max_size
        self._buffer = deque(maxlen=max_size)
        self._lock = asyncio.Lock()
        self._event = asyncio.Event()
        self._closed = False
        self._total_duration = 0.0

    async def put(self, chunk: AudioChunk):
        """
        Add audio chunk to buffer.

        Args:
            chunk: AudioChunk to add
        """
        if self._closed:
            raise ValueError("Buffer is closed")

        async with self._lock:
            self._buffer.append(chunk)

            # Track duration
            chunk_duration = len(chunk.data) / (chunk.sample_rate * 2)
            self._total_duration += chunk_duration

            # Notify waiting consumers
            self._event.set()

    async def get(self) -> Optional[AudioChunk]:
        """
        Get audio chunk from buffer.

        Returns:
            AudioChunk or None if buffer is empty and closed
        """
        while True:
            async with self._lock:
                if self._buffer:
                    return self._buffer.popleft()

                if self._closed:
                    return None

            # Wait for new data
            self._event.clear()
            await self._event.wait()

    async def get_all(self) -> list[AudioChunk]:
        """
        Get all chunks from buffer.

        Returns:
            List of AudioChunk objects
        """
        async with self._lock:
            chunks = list(self._buffer)
            self._buffer.clear()
            return chunks

    def size(self) -> int:
        """Get current buffer size."""
        return len(self._buffer)

    def duration(self) -> float:
        """Get total audio duration in buffer (seconds)."""
        return self._total_duration

    def is_empty(self) -> bool:
        """Check if buffer is empty."""
        return len(self._buffer) == 0

    def is_closed(self) -> bool:
        """Check if buffer is closed."""
        return self._closed

    async def close(self):
        """Close buffer and notify consumers."""
        self._closed = True
        self._event.set()


class AudioStream:
    """
    Async audio stream generator.

    Converts buffer into async iterator for easy consumption.
    """

    def __init__(self, buffer: AudioBuffer):
        """
        Initialize audio stream.

        Args:
            buffer: AudioBuffer to stream from
        """
        self.buffer = buffer

    def __aiter__(self):
        return self

    async def __anext__(self) -> AudioChunk:
        """
        Get next audio chunk.

        Returns:
            Next AudioChunk

        Raises:
            StopAsyncIteration: When stream is complete
        """
        chunk = await self.buffer.get()
        if chunk is None:
            raise StopAsyncIteration
        return chunk


class AudioResampler:
    """
    Audio resampler for converting between sample rates.

    Note: This is a simplified implementation. For production,
    consider using libraries like librosa or scipy.
    """

    @staticmethod
    def resample(
        audio_data: bytes,
        from_rate: int,
        to_rate: int,
        channels: int = 1
    ) -> bytes:
        """
        Resample audio data.

        Args:
            audio_data: Input audio bytes
            from_rate: Source sample rate
            to_rate: Target sample rate
            channels: Number of audio channels

        Returns:
            Resampled audio bytes
        """
        # Simple linear interpolation resampling
        # For production, use proper resampling library

        import array
        import struct

        # Convert bytes to samples
        sample_width = 2  # 16-bit = 2 bytes
        samples = array.array('h', audio_data)

        # Calculate resampling ratio
        ratio = to_rate / from_rate
        new_length = int(len(samples) * ratio)

        # Resample
        resampled = array.array('h', [0] * new_length)
        for i in range(new_length):
            src_idx = i / ratio
            src_idx_int = int(src_idx)
            if src_idx_int < len(samples) - 1:
                # Linear interpolation
                frac = src_idx - src_idx_int
                resampled[i] = int(
                    samples[src_idx_int] * (1 - frac) +
                    samples[src_idx_int + 1] * frac
                )
            elif src_idx_int < len(samples):
                resampled[i] = samples[src_idx_int]

        return resampled.tobytes()


class ChunkAggregator:
    """
    Aggregates small audio chunks into larger ones.

    Useful for reducing network overhead when streaming.
    """

    def __init__(
        self,
        target_chunk_size: int = 8192,  # 8KB
        sample_rate: int = 16000,
        channels: int = 1,
    ):
        """
        Initialize chunk aggregator.

        Args:
            target_chunk_size: Target size for aggregated chunks (bytes)
            sample_rate: Audio sample rate
            channels: Number of audio channels
        """
        self.target_chunk_size = target_chunk_size
        self.sample_rate = sample_rate
        self.channels = channels
        self._buffer = bytearray()

    async def add_chunk(self, chunk: AudioChunk) -> Optional[AudioChunk]:
        """
        Add chunk to aggregator.

        Args:
            chunk: AudioChunk to add

        Returns:
            Aggregated AudioChunk if threshold reached, None otherwise
        """
        self._buffer.extend(chunk.data)

        if len(self._buffer) >= self.target_chunk_size:
            # Create aggregated chunk
            aggregated_data = bytes(self._buffer)
            self._buffer.clear()

            return AudioChunk(
                data=aggregated_data,
                sample_rate=self.sample_rate,
                channels=self.channels,
                encoding=chunk.encoding,
                timestamp=datetime.utcnow().timestamp(),
            )

        return None

    def flush(self) -> Optional[AudioChunk]:
        """
        Flush remaining data in buffer.

        Returns:
            AudioChunk with remaining data, or None if empty
        """
        if self._buffer:
            aggregated_data = bytes(self._buffer)
            self._buffer.clear()

            return AudioChunk(
                data=aggregated_data,
                sample_rate=self.sample_rate,
                channels=self.channels,
            )

        return None


async def create_audio_stream_from_file(
    file_path: str,
    chunk_size: int = 8192,
    sample_rate: int = 16000,
) -> AsyncIterator[AudioChunk]:
    """
    Create audio stream from file.

    Args:
        file_path: Path to audio file
        chunk_size: Size of each chunk (bytes)
        sample_rate: Audio sample rate

    Yields:
        AudioChunk objects

    Example:
        ```python
        async for chunk in create_audio_stream_from_file("audio.wav"):
            # Process chunk
            pass
        ```
    """
    import aiofiles

    try:
        async with aiofiles.open(file_path, "rb") as f:
            # Skip WAV header if present (44 bytes)
            header = await f.read(44)
            if not header.startswith(b'RIFF'):
                # Not a WAV file, rewind
                await f.seek(0)

            # Read and yield chunks
            while True:
                chunk_data = await f.read(chunk_size)
                if not chunk_data:
                    break

                yield AudioChunk(
                    data=chunk_data,
                    sample_rate=sample_rate,
                    channels=1,
                    encoding="linear16",
                    timestamp=datetime.utcnow().timestamp(),
                )

    except Exception as e:
        logger.error(f"Error creating audio stream from file: {e}")
        raise


class SilenceDetector:
    """
    Detects silence in audio stream.

    Useful for voice activity detection (VAD).
    """

    def __init__(
        self,
        threshold: int = 500,  # Amplitude threshold
        min_silence_duration: float = 0.5,  # Seconds
        sample_rate: int = 16000,
    ):
        """
        Initialize silence detector.

        Args:
            threshold: Amplitude threshold for silence
            min_silence_duration: Minimum silence duration to detect
            sample_rate: Audio sample rate
        """
        self.threshold = threshold
        self.min_silence_duration = min_silence_duration
        self.sample_rate = sample_rate
        self._silence_start = None

    def detect(self, chunk: AudioChunk) -> bool:
        """
        Detect if chunk contains significant silence.

        Args:
            chunk: AudioChunk to analyze

        Returns:
            True if silence detected, False otherwise
        """
        import array

        # Convert bytes to samples
        samples = array.array('h', chunk.data)

        # Calculate average amplitude
        avg_amplitude = sum(abs(s) for s in samples) / len(samples)

        # Check if below threshold
        is_silent = avg_amplitude < self.threshold

        # Track silence duration
        if is_silent:
            if self._silence_start is None:
                self._silence_start = datetime.utcnow()
            else:
                silence_duration = (datetime.utcnow() - self._silence_start).total_seconds()
                if silence_duration >= self.min_silence_duration:
                    return True
        else:
            self._silence_start = None

        return False

    def reset(self):
        """Reset silence detection state."""
        self._silence_start = None
