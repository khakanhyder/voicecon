"""
Text-to-Speech Service Manager.
Handles provider selection, instantiation, and management.
"""
import logging
from typing import Optional, AsyncIterator, Dict, Type

from app.services.voice.providers.base import (
    BaseTTSProvider,
    TTSProvider as TTSProviderEnum,
    SynthesisResult,
)
from app.services.voice.providers.elevenlabs import ElevenLabsTTS
from app.core.config import settings

logger = logging.getLogger(__name__)


class TTSService:
    """
    Text-to-Speech service manager.

    Provides a unified interface for different TTS providers.
    Handles provider selection, configuration, and lifecycle management.
    """

    # Registry of available providers
    PROVIDERS: Dict[str, Type[BaseTTSProvider]] = {
        TTSProviderEnum.ELEVENLABS: ElevenLabsTTS,
        # Add more providers as implemented
        # TTSProviderEnum.PLAYHT: PlayHTTTS,
        # TTSProviderEnum.GOOGLE: GoogleTTS,
        # TTSProviderEnum.AZURE: AzureTTS,
        # TTSProviderEnum.OPENAI: OpenAITTS,
    }

    def __init__(self):
        """Initialize TTS service manager."""
        self._active_providers: Dict[str, BaseTTSProvider] = {}

    def get_provider(
        self,
        provider: str = TTSProviderEnum.ELEVENLABS,
        api_key: Optional[str] = None,
        voice_id: Optional[str] = None,
        model: Optional[str] = None,
        **kwargs
    ) -> BaseTTSProvider:
        """
        Get or create a TTS provider instance.

        Args:
            provider: Provider name (elevenlabs, playht, etc.)
            api_key: Provider API key (uses config if not provided)
            voice_id: Voice ID to use
            model: Model to use
            **kwargs: Additional provider-specific parameters

        Returns:
            TTS provider instance

        Raises:
            ValueError: If provider not supported
        """
        # Validate provider
        if provider not in self.PROVIDERS:
            available = ", ".join(self.PROVIDERS.keys())
            raise ValueError(
                f"Unsupported TTS provider: {provider}. "
                f"Available providers: {available}"
            )

        # Get API key from settings if not provided
        if api_key is None:
            api_key = self._get_api_key(provider)

        if not api_key:
            raise ValueError(f"No API key provided for {provider}")

        # Set defaults
        if voice_id is None:
            voice_id = self._get_default_voice(provider)

        if model is None:
            model = self._get_default_model(provider)

        # Create cache key
        cache_key = f"{provider}:{voice_id}:{model}"

        # Return cached provider if exists
        if cache_key in self._active_providers:
            return self._active_providers[cache_key]

        # Create new provider instance
        provider_class = self.PROVIDERS[provider]
        provider_instance = provider_class(
            api_key=api_key,
            voice_id=voice_id,
            model_id=model,
            **kwargs
        )

        # Cache provider
        self._active_providers[cache_key] = provider_instance

        logger.info(f"Created {provider} TTS provider: voice={voice_id}, model={model}")

        return provider_instance

    def _get_api_key(self, provider: str) -> Optional[str]:
        """
        Get API key for provider from settings.

        Args:
            provider: Provider name

        Returns:
            API key or None
        """
        key_mapping = {
            TTSProviderEnum.ELEVENLABS: settings.ELEVENLABS_API_KEY,
            # Add more mappings as needed
            # TTSProviderEnum.PLAYHT: settings.PLAYHT_API_KEY,
        }
        return key_mapping.get(provider)

    def _get_default_voice(self, provider: str) -> str:
        """
        Get default voice for provider.

        Args:
            provider: Provider name

        Returns:
            Default voice ID
        """
        defaults = {
            TTSProviderEnum.ELEVENLABS: "21m00Tcm4TlvDq8ikWAM",  # Rachel
            # TTSProviderEnum.PLAYHT: "larry",
            # TTSProviderEnum.GOOGLE: "en-US-Wavenet-D",
        }
        return defaults.get(provider, "default")

    def _get_default_model(self, provider: str) -> str:
        """
        Get default model for provider.

        Args:
            provider: Provider name

        Returns:
            Default model ID
        """
        defaults = {
            TTSProviderEnum.ELEVENLABS: "eleven_monolingual_v1",
            # TTSProviderEnum.PLAYHT: "PlayHT2.0",
            # TTSProviderEnum.OPENAI: "tts-1",
        }
        return defaults.get(provider, "default")

    async def synthesize(
        self,
        text: str,
        provider: str = TTSProviderEnum.ELEVENLABS,
        api_key: Optional[str] = None,
        voice_id: Optional[str] = None,
        model: Optional[str] = None,
        **kwargs
    ) -> SynthesisResult:
        """
        Synthesize speech from text using specified provider.

        Args:
            text: Text to convert to speech
            provider: TTS provider to use
            api_key: Provider API key (optional)
            voice_id: Voice to use
            model: Model to use
            **kwargs: Additional provider parameters

        Returns:
            SynthesisResult with audio data

        Example:
            ```python
            tts = TTSService()
            result = await tts.synthesize(
                text="Hello, how can I help you today?",
                provider="elevenlabs",
                voice_id="rachel",
            )
            # result.audio_data contains MP3 audio bytes
            ```
        """
        provider_instance = self.get_provider(
            provider=provider,
            api_key=api_key,
            voice_id=voice_id,
            model=model,
            **kwargs
        )

        result = await provider_instance.synthesize(text, **kwargs)
        return result

    async def synthesize_stream(
        self,
        text: str,
        provider: str = TTSProviderEnum.ELEVENLABS,
        api_key: Optional[str] = None,
        voice_id: Optional[str] = None,
        model: Optional[str] = None,
        **kwargs
    ) -> AsyncIterator[bytes]:
        """
        Synthesize speech with streaming for low latency.

        Args:
            text: Text to convert to speech
            provider: TTS provider to use
            api_key: Provider API key (optional)
            voice_id: Voice to use
            model: Model to use
            **kwargs: Additional provider parameters

        Yields:
            Audio chunks as bytes

        Example:
            ```python
            tts = TTSService()
            async for chunk in tts.synthesize_stream(
                text="Hello, how can I help you today?",
                provider="elevenlabs",
                voice_id="rachel",
            ):
                # Stream chunk to client
                await websocket.send(chunk)
            ```
        """
        provider_instance = self.get_provider(
            provider=provider,
            api_key=api_key,
            voice_id=voice_id,
            model=model,
            **kwargs
        )

        async for chunk in provider_instance.synthesize_stream(text, **kwargs):
            yield chunk

    async def get_voices(
        self,
        provider: str = TTSProviderEnum.ELEVENLABS,
        api_key: Optional[str] = None,
    ) -> list:
        """
        Get available voices for provider.

        Args:
            provider: TTS provider
            api_key: Provider API key (optional)

        Returns:
            List of available voices
        """
        provider_instance = self.get_provider(
            provider=provider,
            api_key=api_key,
        )

        if hasattr(provider_instance, 'get_voices'):
            return await provider_instance.get_voices()
        return []

    async def get_usage_stats(self, provider: Optional[str] = None) -> list:
        """
        Get usage statistics for cost tracking.

        Args:
            provider: Optional provider filter

        Returns:
            List of usage statistics
        """
        all_stats = []

        for provider_instance in self._active_providers.values():
            if provider is None or provider_instance.__class__.__name__.lower().startswith(provider):
                stats = provider_instance.get_usage_stats()
                all_stats.extend(stats)

        return all_stats

    def clear_cache(self, provider: Optional[str] = None):
        """
        Clear audio cache for providers.

        Args:
            provider: Optional provider filter (clears all if None)
        """
        for cache_key, provider_instance in self._active_providers.items():
            if provider is None or cache_key.startswith(provider):
                if hasattr(provider_instance, 'clear_cache'):
                    provider_instance.clear_cache()
                    logger.info(f"Cleared cache for {cache_key}")

    def get_cache_stats(self, provider: Optional[str] = None) -> Dict[str, Any]:
        """
        Get cache statistics for providers.

        Args:
            provider: Optional provider filter

        Returns:
            Dictionary of cache statistics by provider
        """
        stats = {}

        for cache_key, provider_instance in self._active_providers.items():
            if provider is None or cache_key.startswith(provider):
                if hasattr(provider_instance, 'get_cache_stats'):
                    stats[cache_key] = provider_instance.get_cache_stats()

        return stats

    async def close_all(self):
        """
        Close all active provider connections.
        """
        for cache_key, provider in self._active_providers.items():
            try:
                await provider.close()
                logger.info(f"Closed provider: {cache_key}")
            except Exception as e:
                logger.error(f"Error closing provider {cache_key}: {e}")

        self._active_providers.clear()


# Global TTS service instance
_tts_service: Optional[TTSService] = None


def get_tts_service() -> TTSService:
    """
    Get global TTS service instance (singleton).

    Returns:
        TTSService instance
    """
    global _tts_service
    if _tts_service is None:
        _tts_service = TTSService()
    return _tts_service
