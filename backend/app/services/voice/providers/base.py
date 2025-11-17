"""
Base classes for voice service providers (STT, TTS, LLM).
"""
from abc import ABC, abstractmethod
from typing import AsyncIterator, Optional, Dict, Any
from enum import Enum
from dataclasses import dataclass
from datetime import datetime


class STTProvider(str, Enum):
    """Speech-to-Text providers"""
    DEEPGRAM = "deepgram"
    ASSEMBLYAI = "assemblyai"
    GOOGLE = "google"
    WHISPER = "whisper"
    AZURE = "azure"


class TTSProvider(str, Enum):
    """Text-to-Speech providers"""
    ELEVENLABS = "elevenlabs"
    PLAYHT = "playht"
    GOOGLE = "google"
    AZURE = "azure"
    OPENAI = "openai"


class LLMProvider(str, Enum):
    """Large Language Model providers"""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    AZURE = "azure"


@dataclass
class TranscriptionResult:
    """Transcription result from STT provider"""
    text: str
    is_final: bool
    confidence: float
    language: Optional[str] = None
    words: Optional[list] = None
    duration: Optional[float] = None
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()


@dataclass
class AudioChunk:
    """Audio chunk for streaming"""
    data: bytes
    sample_rate: int
    channels: int = 1
    encoding: str = "linear16"  # linear16, mulaw, alaw, opus, etc.
    timestamp: Optional[float] = None


@dataclass
class STTUsage:
    """STT usage and cost tracking"""
    provider: str
    duration_seconds: float
    cost: float
    request_id: Optional[str] = None
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()


@dataclass
class TTSUsage:
    """TTS usage and cost tracking"""
    provider: str
    character_count: int
    cost: float
    voice_id: Optional[str] = None
    request_id: Optional[str] = None
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()


@dataclass
class SynthesisResult:
    """Result from TTS synthesis"""
    audio_data: bytes
    sample_rate: int
    format: str  # mp3, pcm, opus, etc.
    duration: Optional[float] = None
    character_count: int = 0
    voice_id: Optional[str] = None
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()


@dataclass
class LLMUsage:
    """LLM usage and cost tracking"""
    provider: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost: float
    request_id: Optional[str] = None
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()


@dataclass
class ChatMessage:
    """Chat message for LLM"""
    role: str  # system, user, assistant, function
    content: str
    name: Optional[str] = None  # Function name for function messages
    function_call: Optional[Dict[str, Any]] = None


@dataclass
class FunctionCall:
    """Function call from LLM"""
    name: str
    arguments: str  # JSON string


@dataclass
class ChatCompletionResult:
    """Result from LLM chat completion"""
    content: str
    role: str = "assistant"
    function_call: Optional[FunctionCall] = None
    finish_reason: Optional[str] = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    model: Optional[str] = None
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()


class BaseSTTProvider(ABC):
    """
    Abstract base class for Speech-to-Text providers.

    All STT providers must implement these methods.
    """

    def __init__(
        self,
        api_key: str,
        language: str = "en",
        model: Optional[str] = None,
        **kwargs
    ):
        """
        Initialize STT provider.

        Args:
            api_key: Provider API key
            language: Language code (e.g., "en", "es", "fr")
            model: Model to use (provider-specific)
            **kwargs: Additional provider-specific configuration
        """
        self.api_key = api_key
        self.language = language
        self.model = model
        self.config = kwargs
        self._usage_stats = []

    @abstractmethod
    async def transcribe_stream(
        self,
        audio_stream: AsyncIterator[AudioChunk],
        **kwargs
    ) -> AsyncIterator[TranscriptionResult]:
        """
        Transcribe audio stream in real-time.

        Args:
            audio_stream: Async iterator of audio chunks
            **kwargs: Additional transcription parameters

        Yields:
            TranscriptionResult objects with interim and final results
        """
        pass

    @abstractmethod
    async def transcribe_file(
        self,
        audio_file_path: str,
        **kwargs
    ) -> TranscriptionResult:
        """
        Transcribe a complete audio file.

        Args:
            audio_file_path: Path to audio file
            **kwargs: Additional transcription parameters

        Returns:
            TranscriptionResult with final transcription
        """
        pass

    @abstractmethod
    async def close(self):
        """
        Close connections and cleanup resources.
        """
        pass

    def get_usage_stats(self) -> list[STTUsage]:
        """
        Get usage statistics for cost tracking.

        Returns:
            List of STTUsage objects
        """
        return self._usage_stats

    def _track_usage(self, duration_seconds: float, cost: float, request_id: Optional[str] = None):
        """
        Track usage for cost calculation.

        Args:
            duration_seconds: Duration of audio transcribed
            cost: Cost of transcription
            request_id: Optional request ID for tracking
        """
        usage = STTUsage(
            provider=self.__class__.__name__,
            duration_seconds=duration_seconds,
            cost=cost,
            request_id=request_id,
        )
        self._usage_stats.append(usage)


class BaseTTSProvider(ABC):
    """
    Abstract base class for Text-to-Speech providers.
    """

    def __init__(
        self,
        api_key: str,
        voice_id: Optional[str] = None,
        model: Optional[str] = None,
        **kwargs
    ):
        self.api_key = api_key
        self.voice_id = voice_id
        self.model = model
        self.config = kwargs

    @abstractmethod
    async def synthesize(
        self,
        text: str,
        **kwargs
    ) -> bytes:
        """
        Synthesize speech from text.

        Args:
            text: Text to convert to speech
            **kwargs: Additional synthesis parameters

        Returns:
            Audio bytes
        """
        pass

    @abstractmethod
    async def synthesize_stream(
        self,
        text: str,
        **kwargs
    ) -> AsyncIterator[bytes]:
        """
        Synthesize speech from text with streaming.

        Args:
            text: Text to convert to speech
            **kwargs: Additional synthesis parameters

        Yields:
            Audio chunks as bytes
        """
        pass

    @abstractmethod
    async def close(self):
        """Close connections and cleanup resources."""
        pass


class BaseLLMProvider(ABC):
    """
    Abstract base class for Large Language Model providers.
    """

    def __init__(
        self,
        api_key: str,
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        **kwargs
    ):
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.config = kwargs
        self._usage_stats: list[LLMUsage] = []

    @abstractmethod
    async def chat_completion(
        self,
        messages: list[ChatMessage],
        functions: Optional[list[Dict[str, Any]]] = None,
        **kwargs
    ) -> ChatCompletionResult:
        """
        Generate chat completion.

        Args:
            messages: List of ChatMessage objects
            functions: Optional function definitions for function calling
            **kwargs: Additional generation parameters

        Returns:
            ChatCompletionResult
        """
        pass

    @abstractmethod
    async def chat_completion_stream(
        self,
        messages: list[ChatMessage],
        functions: Optional[list[Dict[str, Any]]] = None,
        **kwargs
    ) -> AsyncIterator[str]:
        """
        Generate chat completion with streaming.

        Args:
            messages: List of ChatMessage objects
            functions: Optional function definitions
            **kwargs: Additional generation parameters

        Yields:
            Text chunks as they're generated
        """
        pass

    def get_usage_stats(self) -> list[LLMUsage]:
        """
        Get usage statistics for cost tracking.

        Returns:
            List of LLMUsage objects
        """
        return self._usage_stats.copy()

    @abstractmethod
    async def close(self):
        """Close connections and cleanup resources."""
        pass


class ProviderError(Exception):
    """Base exception for provider errors"""
    pass


class ConnectionError(ProviderError):
    """Raised when connection to provider fails"""
    pass


class AuthenticationError(ProviderError):
    """Raised when authentication fails"""
    pass


class RateLimitError(ProviderError):
    """Raised when rate limit is exceeded"""
    pass


class TranscriptionError(ProviderError):
    """Raised when transcription fails"""
    pass
