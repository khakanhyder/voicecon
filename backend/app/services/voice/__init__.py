"""
Voice services for Speech-to-Text, Text-to-Speech, and LLM integration.
"""
from app.services.voice.stt_service import STTService, get_stt_service
from app.services.voice.tts_service import TTSService, get_tts_service
from app.services.voice.llm_service import LLMService, get_llm_service, ConversationContext
from app.services.voice.call_manager import CallManager, CallSession, get_call_manager, CallState
from app.services.voice.providers.base import (
    TranscriptionResult,
    AudioChunk,
    STTProvider,
    TTSProvider,
    LLMProvider,
    SynthesisResult,
    TTSUsage,
    ChatMessage,
    ChatCompletionResult,
    LLMUsage,
)

__all__ = [
    "STTService",
    "get_stt_service",
    "TTSService",
    "get_tts_service",
    "LLMService",
    "get_llm_service",
    "ConversationContext",
    "CallManager",
    "CallSession",
    "get_call_manager",
    "CallState",
    "TranscriptionResult",
    "AudioChunk",
    "STTProvider",
    "TTSProvider",
    "LLMProvider",
    "SynthesisResult",
    "TTSUsage",
    "ChatMessage",
    "ChatCompletionResult",
    "LLMUsage",
]
