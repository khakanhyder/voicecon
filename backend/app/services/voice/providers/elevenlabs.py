"""
ElevenLabs Text-to-Speech Provider.

Implements TTS using ElevenLabs API with streaming support.
"""
import asyncio
import logging
from typing import AsyncIterator, Optional, Dict, Any
import json
import hashlib

import httpx

from app.services.voice.providers.base import (
    BaseTTSProvider,
    SynthesisResult,
    TTSUsage,
    ProviderError,
    AuthenticationError,
    RateLimitError,
)

logger = logging.getLogger(__name__)


class ElevenLabsTTS(BaseTTSProvider):
    """
    ElevenLabs Text-to-Speech provider.

    Supports:
    - High-quality voice synthesis
    - Streaming for low latency
    - Multiple voices and models
    - Voice settings customization
    - Cost tracking
    """

    # API Configuration
    BASE_URL = "https://api.elevenlabs.io/v1"

    # Pricing (per 1,000 characters)
    PRICING = {
        "free": 0.00,  # Free tier (10,000 chars/month)
        "starter": 0.30,  # $0.30 per 1,000 chars
        "creator": 0.24,  # $0.24 per 1,000 chars (volume discount)
        "pro": 0.18,  # $0.18 per 1,000 chars (volume discount)
        "scale": 0.15,  # $0.15 per 1,000 chars (enterprise)
    }

    # Default voices
    DEFAULT_VOICES = {
        "rachel": "21m00Tcm4TlvDq8ikWAM",
        "domi": "AZnzlk1XvdvUeBnXmlld",
        "bella": "EXAVITQu4vr4xnSDxMaL",
        "antoni": "ErXwobaYiN019PkySvjV",
        "elli": "MF3mGyEYCl7XYWbV9V6O",
        "josh": "TxGEqnHWrfWFTfGW9XjX",
        "arnold": "VR6AewLTigWG4xSOukaG",
        "adam": "pNInz6obpgDQGcFmaJgB",
        "sam": "yoZ06aMxZJJ28mfd3POQ",
    }

    def __init__(
        self,
        api_key: str,
        voice_id: str = "21m00Tcm4TlvDq8ikWAM",  # Rachel
        # eleven_monolingual_v1 / eleven_multilingual_v1 are deprecated upstream
        # and rejected for new synthesis.
        model_id: str = "eleven_turbo_v2_5",
        tier: str = "starter",
        **kwargs
    ):
        """
        Initialize ElevenLabs TTS provider.

        Args:
            api_key: ElevenLabs API key
            voice_id: Voice ID or name
            model_id: Model to use (eleven_monolingual_v1, eleven_multilingual_v2, etc.)
            tier: Pricing tier for cost calculation
            **kwargs: Additional configuration (stability, similarity_boost, etc.)
        """
        super().__init__(api_key, voice_id, model_id, **kwargs)

        # Resolve voice name to ID
        if voice_id in self.DEFAULT_VOICES:
            self.voice_id = self.DEFAULT_VOICES[voice_id]
        else:
            self.voice_id = voice_id

        self.tier = tier
        self.model_id = model_id

        # Voice settings
        self.stability = kwargs.get("stability", 0.5)
        self.similarity_boost = kwargs.get("similarity_boost", 0.75)
        self.style = kwargs.get("style", 0.0)
        self.use_speaker_boost = kwargs.get("use_speaker_boost", True)

        # HTTP client
        self.client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers={
                "xi-api-key": self.api_key,
                "Content-Type": "application/json",
            },
            timeout=httpx.Timeout(30.0, read=60.0),
        )

        # Cache for repeated phrases
        self._cache: Dict[str, bytes] = {}
        self._cache_enabled = kwargs.get("enable_cache", True)
        self._max_cache_size = kwargs.get("max_cache_size", 100)

        # Usage tracking
        self._usage_stats = []

        logger.info(f"Initialized ElevenLabs TTS: voice={voice_id}, model={model_id}")

    def _get_cache_key(self, text: str, voice_id: str, settings: Dict) -> str:
        """Generate cache key for text."""
        key_data = f"{text}:{voice_id}:{json.dumps(settings, sort_keys=True)}"
        return hashlib.md5(key_data.encode()).hexdigest()

    def _get_from_cache(self, text: str) -> Optional[bytes]:
        """Get cached audio if available."""
        if not self._cache_enabled:
            return None

        settings = {
            "stability": self.stability,
            "similarity_boost": self.similarity_boost,
            "style": self.style,
        }
        cache_key = self._get_cache_key(text, self.voice_id, settings)
        return self._cache.get(cache_key)

    def _add_to_cache(self, text: str, audio_data: bytes):
        """Add audio to cache."""
        if not self._cache_enabled:
            return

        # Evict oldest if cache is full
        if len(self._cache) >= self._max_cache_size:
            self._cache.pop(next(iter(self._cache)))

        settings = {
            "stability": self.stability,
            "similarity_boost": self.similarity_boost,
            "style": self.style,
        }
        cache_key = self._get_cache_key(text, self.voice_id, settings)
        self._cache[cache_key] = audio_data

    async def synthesize(self, text: str, **kwargs) -> SynthesisResult:
        """
        Synthesize speech from text (non-streaming).

        Args:
            text: Text to convert to speech
            **kwargs: Optional overrides for voice_id, stability, etc.

        Returns:
            SynthesisResult with complete audio

        Raises:
            AuthenticationError: Invalid API key
            RateLimitError: Rate limit exceeded
            ProviderError: Other API errors
        """
        # Check cache
        cached_audio = self._get_from_cache(text)
        if cached_audio:
            logger.info(f"Cache hit for text: {text[:50]}...")
            return SynthesisResult(
                audio_data=cached_audio,
                sample_rate=44100,  # ElevenLabs default
                format="mp3",
                character_count=len(text),
                voice_id=self.voice_id,
            )

        voice_id = kwargs.get("voice_id", self.voice_id)

        # Prepare request
        url = f"/text-to-speech/{voice_id}"
        data = {
            "text": text,
            "model_id": kwargs.get("model_id", self.model_id),
            "voice_settings": {
                "stability": kwargs.get("stability", self.stability),
                "similarity_boost": kwargs.get("similarity_boost", self.similarity_boost),
                "style": kwargs.get("style", self.style),
                "use_speaker_boost": kwargs.get("use_speaker_boost", self.use_speaker_boost),
            },
        }

        try:
            response = await self.client.post(url, json=data)

            # Handle errors
            if response.status_code == 401:
                # 401 covers both a bad key and a valid key missing a permission
                # scope; surface the body so the two are distinguishable.
                raise AuthenticationError(f"ElevenLabs auth failed: {response.text[:300]}")
            elif response.status_code == 429:
                raise RateLimitError("ElevenLabs rate limit exceeded")
            elif response.status_code != 200:
                error_detail = response.text
                raise ProviderError(f"ElevenLabs API error: {error_detail}")

            # Get audio data
            audio_data = response.content

            # Cache the result
            self._add_to_cache(text, audio_data)

            # Track usage
            cost = self._calculate_cost(len(text))
            self._track_usage(len(text), cost, voice_id)

            logger.info(f"Synthesized {len(text)} characters with voice {voice_id}")

            return SynthesisResult(
                audio_data=audio_data,
                sample_rate=44100,
                format="mp3",
                character_count=len(text),
                voice_id=voice_id,
            )

        except httpx.HTTPError as e:
            logger.error(f"HTTP error in ElevenLabs synthesis: {e}")
            raise ProviderError(f"Network error: {e}")

    async def synthesize_stream(self, text: str, **kwargs) -> AsyncIterator[bytes]:
        """
        Synthesize speech with streaming for low latency.

        Args:
            text: Text to convert to speech
            **kwargs: Optional overrides for voice_id, stability, etc.

        Yields:
            Audio chunks as bytes

        Raises:
            AuthenticationError: Invalid API key
            RateLimitError: Rate limit exceeded
            ProviderError: Other API errors
        """
        voice_id = kwargs.get("voice_id", self.voice_id)

        # Prepare request
        url = f"/text-to-speech/{voice_id}/stream"
        data = {
            "text": text,
            "model_id": kwargs.get("model_id", self.model_id),
            "voice_settings": {
                "stability": kwargs.get("stability", self.stability),
                "similarity_boost": kwargs.get("similarity_boost", self.similarity_boost),
                "style": kwargs.get("style", self.style),
                "use_speaker_boost": kwargs.get("use_speaker_boost", self.use_speaker_boost),
            },
        }

        try:
            async with self.client.stream("POST", url, json=data) as response:
                # Handle errors
                if response.status_code == 401:
                    # 401 covers both a bad key and a valid key missing a
                    # permission scope; surface the body to distinguish them.
                    body = (await response.aread()).decode()[:300]
                    raise AuthenticationError(f"ElevenLabs auth failed: {body}")
                elif response.status_code == 429:
                    raise RateLimitError("ElevenLabs rate limit exceeded")
                elif response.status_code != 200:
                    error_detail = await response.aread()
                    raise ProviderError(f"ElevenLabs API error: {error_detail.decode()}")

                # Stream audio chunks
                total_bytes = 0
                async for chunk in response.aiter_bytes(chunk_size=4096):
                    if chunk:
                        total_bytes += len(chunk)
                        yield chunk

                # Track usage
                cost = self._calculate_cost(len(text))
                self._track_usage(len(text), cost, voice_id)

                logger.info(
                    f"Streamed {len(text)} characters with voice {voice_id}, "
                    f"received {total_bytes} bytes"
                )

        except httpx.HTTPError as e:
            logger.error(f"HTTP error in ElevenLabs streaming: {e}")
            raise ProviderError(f"Network error: {e}")

    async def get_voices(self) -> list[Dict[str, Any]]:
        """
        Get available voices.

        Returns:
            List of voice dictionaries with id, name, category, etc.
        """
        try:
            response = await self.client.get("/voices")

            if response.status_code == 401:
                # 401 covers both a bad key and a valid key missing a permission
                # scope; surface the body so the two are distinguishable.
                raise AuthenticationError(f"ElevenLabs auth failed: {response.text[:300]}")
            elif response.status_code != 200:
                raise ProviderError(f"Failed to get voices: {response.text}")

            data = response.json()
            return data.get("voices", [])

        except httpx.HTTPError as e:
            logger.error(f"Error getting voices: {e}")
            raise ProviderError(f"Network error: {e}")

    async def get_voice_settings(self, voice_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get settings for a specific voice.

        Args:
            voice_id: Voice ID (uses default if not provided)

        Returns:
            Voice settings dictionary
        """
        voice_id = voice_id or self.voice_id

        try:
            response = await self.client.get(f"/voices/{voice_id}/settings")

            if response.status_code == 401:
                # 401 covers both a bad key and a valid key missing a permission
                # scope; surface the body so the two are distinguishable.
                raise AuthenticationError(f"ElevenLabs auth failed: {response.text[:300]}")
            elif response.status_code != 200:
                raise ProviderError(f"Failed to get voice settings: {response.text}")

            return response.json()

        except httpx.HTTPError as e:
            logger.error(f"Error getting voice settings: {e}")
            raise ProviderError(f"Network error: {e}")

    def _calculate_cost(self, character_count: int) -> float:
        """
        Calculate cost based on character count.

        Args:
            character_count: Number of characters synthesized

        Returns:
            Cost in USD
        """
        price_per_1k = self.PRICING.get(self.tier, self.PRICING["starter"])
        return (character_count / 1000.0) * price_per_1k

    def _track_usage(self, character_count: int, cost: float, voice_id: str):
        """
        Track usage for cost monitoring.

        Args:
            character_count: Number of characters
            cost: Cost in USD
            voice_id: Voice ID used
        """
        usage = TTSUsage(
            provider="elevenlabs",
            character_count=character_count,
            cost=cost,
            voice_id=voice_id,
        )
        self._usage_stats.append(usage)

    async def close(self):
        """Close HTTP client and cleanup resources."""
        await self.client.aclose()
        logger.info("ElevenLabs TTS client closed")

    def clear_cache(self):
        """Clear the audio cache."""
        self._cache.clear()
        logger.info("Cleared ElevenLabs TTS cache")

    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache size and hit rate
        """
        return {
            "size": len(self._cache),
            "max_size": self._max_cache_size,
            "enabled": self._cache_enabled,
        }
