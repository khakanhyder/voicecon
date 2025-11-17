"""
Speech-to-Text Service Manager.
Handles provider selection, instantiation, and management.
"""
import logging
from typing import Optional, AsyncIterator, Dict, Type
from app.services.voice.providers.base import (
    BaseSTTProvider,
    STTProvider as STTProviderEnum,
    TranscriptionResult,
    AudioChunk,
)
from app.services.voice.providers.deepgram import DeepgramSTT
from app.core.config import settings

logger = logging.getLogger(__name__)


class STTService:
    """
    Speech-to-Text service manager.

    Provides a unified interface for different STT providers.
    Handles provider selection, configuration, and lifecycle management.
    """

    # Registry of available providers
    PROVIDERS: Dict[str, Type[BaseSTTProvider]] = {
        STTProviderEnum.DEEPGRAM: DeepgramSTT,
        # Add more providers as implemented
        # STTProviderEnum.ASSEMBLYAI: AssemblyAISTT,
        # STTProviderEnum.GOOGLE: GoogleSTT,
        # STTProviderEnum.WHISPER: WhisperSTT,
    }

    def __init__(self):
        """Initialize STT service manager."""
        self._active_providers: Dict[str, BaseSTTProvider] = {}

    def get_provider(
        self,
        provider: str = STTProviderEnum.DEEPGRAM,
        api_key: Optional[str] = None,
        language: str = "en",
        model: Optional[str] = None,
        **kwargs
    ) -> BaseSTTProvider:
        """
        Get or create an STT provider instance.

        Args:
            provider: Provider name (deepgram, assemblyai, etc.)
            api_key: Provider API key (uses config if not provided)
            language: Language code
            model: Model to use
            **kwargs: Additional provider-specific parameters

        Returns:
            STT provider instance

        Raises:
            ValueError: If provider not supported
        """
        # Validate provider
        if provider not in self.PROVIDERS:
            available = ", ".join(self.PROVIDERS.keys())
            raise ValueError(
                f"Unsupported STT provider: {provider}. "
                f"Available providers: {available}"
            )

        # Get API key from settings if not provided
        if api_key is None:
            api_key = self._get_api_key(provider)

        if not api_key:
            raise ValueError(f"No API key provided for {provider}")

        # Create cache key
        cache_key = f"{provider}:{language}:{model}"

        # Return cached provider if exists
        if cache_key in self._active_providers:
            return self._active_providers[cache_key]

        # Create new provider instance
        provider_class = self.PROVIDERS[provider]
        provider_instance = provider_class(
            api_key=api_key,
            language=language,
            model=model,
            **kwargs
        )

        # Cache provider
        self._active_providers[cache_key] = provider_instance

        logger.info(f"Created {provider} STT provider: language={language}, model={model}")

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
            STTProviderEnum.DEEPGRAM: settings.DEEPGRAM_API_KEY,
            # Add more mappings as needed
            # STTProviderEnum.ASSEMBLYAI: settings.ASSEMBLYAI_API_KEY,
        }
        return key_mapping.get(provider)

    async def transcribe_stream(
        self,
        audio_stream: AsyncIterator[AudioChunk],
        provider: str = STTProviderEnum.DEEPGRAM,
        api_key: Optional[str] = None,
        language: str = "en",
        model: Optional[str] = None,
        **kwargs
    ) -> AsyncIterator[TranscriptionResult]:
        """
        Transcribe audio stream using specified provider.

        Args:
            audio_stream: Async iterator of audio chunks
            provider: STT provider to use
            api_key: Provider API key (optional)
            language: Language code
            model: Model to use
            **kwargs: Additional provider parameters

        Yields:
            TranscriptionResult objects

        Example:
            ```python
            async def audio_generator():
                # Generate audio chunks
                yield AudioChunk(data=b'...', sample_rate=16000)

            stt = STTService()
            async for result in stt.transcribe_stream(audio_generator()):
                if result.is_final:
                    print(f"Final: {result.text}")
                else:
                    print(f"Interim: {result.text}")
            ```
        """
        provider_instance = self.get_provider(
            provider=provider,
            api_key=api_key,
            language=language,
            model=model,
            **kwargs
        )

        try:
            async for result in provider_instance.transcribe_stream(audio_stream, **kwargs):
                yield result
        finally:
            # Provider cleanup is handled in provider.close()
            pass

    async def transcribe_file(
        self,
        audio_file_path: str,
        provider: str = STTProviderEnum.DEEPGRAM,
        api_key: Optional[str] = None,
        language: str = "en",
        model: Optional[str] = None,
        **kwargs
    ) -> TranscriptionResult:
        """
        Transcribe audio file using specified provider.

        Args:
            audio_file_path: Path to audio file
            provider: STT provider to use
            api_key: Provider API key (optional)
            language: Language code
            model: Model to use
            **kwargs: Additional provider parameters

        Returns:
            TranscriptionResult with final transcription

        Example:
            ```python
            stt = STTService()
            result = await stt.transcribe_file("recording.wav", provider="deepgram")
            print(f"Transcription: {result.text}")
            print(f"Confidence: {result.confidence}")
            ```
        """
        provider_instance = self.get_provider(
            provider=provider,
            api_key=api_key,
            language=language,
            model=model,
            **kwargs
        )

        result = await provider_instance.transcribe_file(audio_file_path, **kwargs)
        return result

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


# Global STT service instance
_stt_service: Optional[STTService] = None


def get_stt_service() -> STTService:
    """
    Get global STT service instance (singleton).

    Returns:
        STTService instance
    """
    global _stt_service
    if _stt_service is None:
        _stt_service = STTService()
    return _stt_service
