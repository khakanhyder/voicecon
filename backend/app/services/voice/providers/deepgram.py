"""
Deepgram Speech-to-Text provider implementation.
Supports real-time streaming transcription via WebSocket.
"""
import asyncio
import json
import logging
from typing import AsyncIterator, Optional, Dict, Any
from datetime import datetime
import websockets
from websockets.exceptions import WebSocketException

from .base import (
    BaseSTTProvider,
    TranscriptionResult,
    AudioChunk,
    ConnectionError,
    AuthenticationError,
    TranscriptionError,
)

logger = logging.getLogger(__name__)


class DeepgramSTT(BaseSTTProvider):
    """
    Deepgram Speech-to-Text provider with WebSocket streaming.

    Features:
    - Real-time streaming transcription
    - Interim and final results
    - Automatic reconnection
    - Cost tracking
    - Support for multiple languages and models
    """

    # Deepgram pricing (per minute)
    PRICING = {
        "nova-2": 0.0043,  # $0.0043 per minute
        "nova": 0.0043,
        "enhanced": 0.0125,
        "base": 0.0125,
    }

    def __init__(
        self,
        api_key: str,
        language: str = "en",
        model: str = "nova-2",
        punctuate: bool = True,
        interim_results: bool = True,
        smart_format: bool = True,
        diarize: bool = False,
        **kwargs
    ):
        """
        Initialize Deepgram STT provider.

        Args:
            api_key: Deepgram API key
            language: Language code (e.g., "en", "es", "fr")
            model: Model to use (nova-2, nova, enhanced, base)
            punctuate: Add punctuation to transcription
            interim_results: Return interim results before final
            smart_format: Apply smart formatting (numbers, dates, etc.)
            diarize: Enable speaker diarization
            **kwargs: Additional configuration
        """
        super().__init__(api_key, language, model, **kwargs)
        self.punctuate = punctuate
        self.interim_results = interim_results
        self.smart_format = smart_format
        self.diarize = diarize
        self.websocket = None
        self._is_connected = False
        self._reconnect_attempts = 0
        self._max_reconnect_attempts = 3
        self._audio_duration = 0.0

    def _build_websocket_url(self, **extra_params) -> str:
        """
        Build Deepgram WebSocket URL with parameters.

        Returns:
            WebSocket URL with query parameters
        """
        base_url = "wss://api.deepgram.com/v1/listen"

        params = {
            "language": self.language,
            "model": self.model,
            "punctuate": str(self.punctuate).lower(),
            "interim_results": str(self.interim_results).lower(),
            "smart_format": str(self.smart_format).lower(),
        }

        if self.diarize:
            params["diarize"] = "true"

        # Add extra parameters
        params.update(extra_params)

        # Build query string
        query_string = "&".join([f"{k}={v}" for k, v in params.items()])
        return f"{base_url}?{query_string}"

    async def _connect(self, **params) -> None:
        """
        Establish WebSocket connection to Deepgram.

        Raises:
            ConnectionError: If connection fails
            AuthenticationError: If API key is invalid
        """
        try:
            url = self._build_websocket_url(**params)

            logger.info(f"Connecting to Deepgram: {self.model} model, language: {self.language}")

            self.websocket = await websockets.connect(
                url,
                extra_headers={
                    "Authorization": f"Token {self.api_key}"
                },
                ping_interval=20,
                ping_timeout=10,
            )

            self._is_connected = True
            self._reconnect_attempts = 0
            logger.info("Connected to Deepgram WebSocket")

        except WebSocketException as e:
            logger.error(f"WebSocket connection failed: {e}")
            if "401" in str(e) or "403" in str(e):
                raise AuthenticationError(f"Invalid Deepgram API key: {e}")
            raise ConnectionError(f"Failed to connect to Deepgram: {e}")

    async def _reconnect(self, **params) -> bool:
        """
        Attempt to reconnect to Deepgram.

        Returns:
            True if reconnection successful, False otherwise
        """
        if self._reconnect_attempts >= self._max_reconnect_attempts:
            logger.error("Max reconnection attempts reached")
            return False

        self._reconnect_attempts += 1
        wait_time = 2 ** self._reconnect_attempts  # Exponential backoff

        logger.info(f"Reconnecting to Deepgram (attempt {self._reconnect_attempts}/{self._max_reconnect_attempts}) in {wait_time}s...")
        await asyncio.sleep(wait_time)

        try:
            await self._connect(**params)
            return True
        except Exception as e:
            logger.error(f"Reconnection failed: {e}")
            return False

    async def transcribe_stream(
        self,
        audio_stream: AsyncIterator[AudioChunk],
        **kwargs
    ) -> AsyncIterator[TranscriptionResult]:
        """
        Transcribe audio stream in real-time.

        Args:
            audio_stream: Async iterator of audio chunks
            **kwargs: Additional Deepgram parameters

        Yields:
            TranscriptionResult objects with interim and final transcriptions

        Raises:
            ConnectionError: If connection fails
            TranscriptionError: If transcription fails
        """
        # Connect to Deepgram
        await self._connect(**kwargs)

        try:
            # Create tasks for sending and receiving
            send_task = asyncio.create_task(
                self._send_audio_stream(audio_stream)
            )
            receive_task = asyncio.create_task(
                self._receive_transcriptions()
            )

            # Yield transcriptions as they arrive
            async for result in receive_task:
                yield result

            # Wait for send task to complete
            await send_task

        except Exception as e:
            logger.error(f"Transcription stream error: {e}")
            raise TranscriptionError(f"Transcription failed: {e}")
        finally:
            await self.close()

    async def _send_audio_stream(self, audio_stream: AsyncIterator[AudioChunk]) -> None:
        """
        Send audio chunks to Deepgram WebSocket.

        Args:
            audio_stream: Async iterator of audio chunks
        """
        try:
            chunk_count = 0
            start_time = datetime.utcnow()

            async for chunk in audio_stream:
                if not self._is_connected or self.websocket is None:
                    logger.warning("WebSocket not connected, stopping audio send")
                    break

                # Send audio chunk
                await self.websocket.send(chunk.data)
                chunk_count += 1

                # Track duration for cost calculation
                # Assuming 16kHz sample rate, 16-bit PCM
                chunk_duration = len(chunk.data) / (chunk.sample_rate * 2)  # 2 bytes per sample
                self._audio_duration += chunk_duration

                # Log progress every 100 chunks
                if chunk_count % 100 == 0:
                    elapsed = (datetime.utcnow() - start_time).total_seconds()
                    logger.debug(f"Sent {chunk_count} chunks ({elapsed:.2f}s)")

            # Send close message to signal end of audio
            if self.websocket:
                close_msg = json.dumps({"type": "CloseStream"})
                await self.websocket.send(close_msg)
                logger.info(f"Audio stream complete: {chunk_count} chunks, {self._audio_duration:.2f}s")

        except WebSocketException as e:
            logger.error(f"Error sending audio: {e}")
            # Attempt reconnection
            if await self._reconnect():
                logger.info("Reconnected, but stream is broken")
            raise ConnectionError(f"Lost connection while sending audio: {e}")

    async def _receive_transcriptions(self) -> AsyncIterator[TranscriptionResult]:
        """
        Receive and parse transcription results from Deepgram.

        Yields:
            TranscriptionResult objects
        """
        try:
            async for message in self.websocket:
                try:
                    data = json.loads(message)

                    # Check for errors
                    if "error" in data:
                        logger.error(f"Deepgram error: {data['error']}")
                        raise TranscriptionError(f"Deepgram error: {data['error']}")

                    # Parse transcription result
                    if data.get("type") == "Results":
                        result = self._parse_result(data)
                        if result:
                            yield result

                    # Handle metadata
                    elif data.get("type") == "Metadata":
                        logger.debug(f"Metadata received: {data}")

                    # Handle other message types
                    else:
                        logger.debug(f"Unknown message type: {data.get('type')}")

                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse message: {e}")
                except Exception as e:
                    logger.error(f"Error processing message: {e}")

        except WebSocketException as e:
            logger.error(f"WebSocket receive error: {e}")
            raise ConnectionError(f"Lost connection while receiving: {e}")
        finally:
            # Track usage and cost
            self._track_final_usage()

    def _parse_result(self, data: Dict[str, Any]) -> Optional[TranscriptionResult]:
        """
        Parse Deepgram result into TranscriptionResult.

        Args:
            data: Deepgram result data

        Returns:
            TranscriptionResult or None if no transcript
        """
        try:
            channel = data.get("channel", {})
            alternatives = channel.get("alternatives", [])

            if not alternatives:
                return None

            # Get best alternative
            alternative = alternatives[0]
            transcript = alternative.get("transcript", "")

            if not transcript:
                return None

            # Determine if final
            is_final = data.get("is_final", False) or data.get("speech_final", False)

            # Extract words with timestamps
            words = alternative.get("words", [])

            # Calculate confidence
            confidence = alternative.get("confidence", 0.0)

            return TranscriptionResult(
                text=transcript,
                is_final=is_final,
                confidence=confidence,
                language=self.language,
                words=words if words else None,
                duration=channel.get("duration"),
            )

        except Exception as e:
            logger.error(f"Error parsing result: {e}")
            return None

    def _track_final_usage(self) -> None:
        """
        Track final usage and calculate cost.
        """
        if self._audio_duration > 0:
            # Calculate cost based on duration (in minutes)
            duration_minutes = self._audio_duration / 60
            cost_per_minute = self.PRICING.get(self.model, 0.0125)
            total_cost = duration_minutes * cost_per_minute

            self._track_usage(
                duration_seconds=self._audio_duration,
                cost=total_cost,
            )

            logger.info(
                f"Transcription usage: {self._audio_duration:.2f}s "
                f"({duration_minutes:.4f} min) = ${total_cost:.4f}"
            )

    async def transcribe_file(
        self,
        audio_file_path: str,
        **kwargs
    ) -> TranscriptionResult:
        """
        Transcribe a complete audio file.

        Args:
            audio_file_path: Path to audio file
            **kwargs: Additional Deepgram parameters

        Returns:
            TranscriptionResult with final transcription
        """
        import aiohttp
        import aiofiles

        try:
            url = "https://api.deepgram.com/v1/listen"

            # Build query parameters
            params = {
                "language": self.language,
                "model": self.model,
                "punctuate": self.punctuate,
                "smart_format": self.smart_format,
            }
            params.update(kwargs)

            # Read audio file
            async with aiofiles.open(audio_file_path, "rb") as f:
                audio_data = await f.read()

            # Send request
            headers = {
                "Authorization": f"Token {self.api_key}",
                "Content-Type": "audio/wav",  # Adjust based on file type
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, params=params, data=audio_data) as response:
                    if response.status == 401:
                        raise AuthenticationError("Invalid Deepgram API key")
                    if response.status != 200:
                        raise TranscriptionError(f"Deepgram API error: {response.status}")

                    data = await response.json()

                    # Parse result
                    result = self._parse_result(data["results"]["channels"][0])

                    # Track usage
                    duration = data["metadata"]["duration"]
                    cost = (duration / 60) * self.PRICING.get(self.model, 0.0125)
                    self._track_usage(duration, cost)

                    return result

        except Exception as e:
            logger.error(f"File transcription error: {e}")
            raise TranscriptionError(f"Failed to transcribe file: {e}")

    async def close(self) -> None:
        """
        Close WebSocket connection and cleanup.
        """
        if self.websocket:
            try:
                await self.websocket.close()
                logger.info("Deepgram WebSocket closed")
            except Exception as e:
                logger.error(f"Error closing WebSocket: {e}")
            finally:
                self.websocket = None
                self._is_connected = False
