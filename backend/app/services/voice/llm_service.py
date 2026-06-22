"""
Large Language Model Service Manager.
Handles provider selection, instantiation, conversation management, and lifecycle.
"""
import logging
from typing import Optional, AsyncIterator, Dict, Type, List
from collections import deque

from app.services.voice.providers.base import (
    BaseLLMProvider,
    LLMProvider as LLMProviderEnum,
    ChatMessage,
    ChatCompletionResult,
)
from app.services.voice.providers.openai_llm import OpenAILLM
from app.services.voice.providers.anthropic_llm import AnthropicLLM
from app.core.config import settings

logger = logging.getLogger(__name__)


class ConversationContext:
    """
    Manages conversation history and context for LLM interactions.

    Handles:
    - Message history with sliding window
    - Token budget management
    - System prompt management
    """

    def __init__(
        self,
        system_prompt: Optional[str] = None,
        max_history: int = 20,
        max_tokens: int = 4000,
    ):
        """
        Initialize conversation context.

        Args:
            system_prompt: System prompt to prepend to conversations
            max_history: Maximum number of messages to keep
            max_tokens: Approximate max tokens for context (for truncation)
        """
        self.system_prompt = system_prompt
        self.max_history = max_history
        self.max_tokens = max_tokens
        self._messages: deque[ChatMessage] = deque(maxlen=max_history)
        self._rag_context: Optional[str] = None  # Knowledge base context

    def add_message(self, role: str, content: str, **kwargs):
        """
        Add a message to the conversation history.

        Args:
            role: Message role (user, assistant, system)
            content: Message content
            **kwargs: Additional message parameters
        """
        message = ChatMessage(role=role, content=content, **kwargs)
        self._messages.append(message)

    def set_rag_context(self, context: str):
        """
        Set knowledge base context from RAG.

        Args:
            context: Retrieved context from knowledge base
        """
        self._rag_context = context

    def clear_rag_context(self):
        """Clear knowledge base context."""
        self._rag_context = None

    def get_messages(self) -> List[ChatMessage]:
        """
        Get all messages including system prompt and RAG context.

        Returns:
            List of ChatMessage objects
        """
        messages = []

        # Add system prompt with RAG context if set
        if self.system_prompt:
            system_content = self.system_prompt

            # Inject RAG context if available
            if self._rag_context:
                system_content += f"\n\n{self._rag_context}"

            messages.append(ChatMessage(role="system", content=system_content))

        # Add conversation history
        messages.extend(list(self._messages))

        return messages

    def clear(self):
        """Clear conversation history (keeps system prompt)."""
        self._messages.clear()

    def set_system_prompt(self, prompt: str):
        """Update system prompt."""
        self.system_prompt = prompt

    def get_message_count(self) -> int:
        """Get number of messages in history."""
        return len(self._messages)

    def estimate_tokens(self) -> int:
        """
        Estimate total tokens in conversation.

        Note: This is a rough approximation.

        Returns:
            Approximate token count
        """
        total_chars = 0

        if self.system_prompt:
            total_chars += len(self.system_prompt)

        for msg in self._messages:
            total_chars += len(msg.content)

        # Rough approximation: 1 token ≈ 4 characters
        return total_chars // 4


class LLMService:
    """
    Large Language Model service manager.

    Provides a unified interface for different LLM providers.
    Handles provider selection, configuration, and lifecycle management.
    """

    # Registry of available providers
    PROVIDERS: Dict[str, Type[BaseLLMProvider]] = {
        LLMProviderEnum.OPENAI: OpenAILLM,
        LLMProviderEnum.ANTHROPIC: AnthropicLLM,
        # Add more providers as implemented
        # LLMProviderEnum.GOOGLE: GoogleLLM,
    }

    def __init__(self):
        """Initialize LLM service manager."""
        self._active_providers: Dict[str, BaseLLMProvider] = {}
        self._conversation_contexts: Dict[str, ConversationContext] = {}

    def get_provider(
        self,
        provider: str = LLMProviderEnum.OPENAI,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        **kwargs
    ) -> BaseLLMProvider:
        """
        Get or create an LLM provider instance.

        Args:
            provider: Provider name (openai, anthropic, etc.)
            api_key: Provider API key (uses config if not provided)
            model: Model to use
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            **kwargs: Additional provider-specific parameters

        Returns:
            LLM provider instance

        Raises:
            ValueError: If provider not supported
        """
        # Validate provider
        if provider not in self.PROVIDERS:
            available = ", ".join(self.PROVIDERS.keys())
            raise ValueError(
                f"Unsupported LLM provider: {provider}. "
                f"Available providers: {available}"
            )

        # Get API key from settings if not provided
        if api_key is None:
            api_key = self._get_api_key(provider)

        if not api_key:
            raise ValueError(f"No API key provided for {provider}")

        # Set defaults
        if model is None:
            model = self._get_default_model(provider)

        # Create cache key
        cache_key = f"{provider}:{model}:{temperature}"

        # Return cached provider if exists
        if cache_key in self._active_providers:
            return self._active_providers[cache_key]

        # Create new provider instance
        provider_class = self.PROVIDERS[provider]
        provider_instance = provider_class(
            api_key=api_key,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs
        )

        # Cache provider
        self._active_providers[cache_key] = provider_instance

        logger.info(f"Created {provider} LLM provider: model={model}, temperature={temperature}")

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
            LLMProviderEnum.OPENAI: settings.OPENAI_API_KEY,
            LLMProviderEnum.ANTHROPIC: settings.ANTHROPIC_API_KEY,
        }
        return key_mapping.get(provider)

    def _get_default_model(self, provider: str) -> str:
        """
        Get default model for provider.

        Args:
            provider: Provider name

        Returns:
            Default model name
        """
        defaults = {
            LLMProviderEnum.OPENAI: "gpt-5.4-nano",
            LLMProviderEnum.ANTHROPIC: "claude-haiku-4-5-20251001",
        }
        return defaults.get(provider, "default")

    def create_conversation(
        self,
        conversation_id: str,
        system_prompt: Optional[str] = None,
        max_history: int = 20,
        max_tokens: int = 4000,
    ) -> ConversationContext:
        """
        Create a new conversation context.

        Args:
            conversation_id: Unique identifier for conversation
            system_prompt: System prompt for the conversation
            max_history: Maximum messages to keep in history
            max_tokens: Approximate max tokens for context

        Returns:
            ConversationContext instance
        """
        context = ConversationContext(
            system_prompt=system_prompt,
            max_history=max_history,
            max_tokens=max_tokens,
        )
        self._conversation_contexts[conversation_id] = context
        return context

    def get_conversation(self, conversation_id: str) -> Optional[ConversationContext]:
        """
        Get existing conversation context.

        Args:
            conversation_id: Conversation identifier

        Returns:
            ConversationContext or None
        """
        return self._conversation_contexts.get(conversation_id)

    def delete_conversation(self, conversation_id: str):
        """
        Delete a conversation context.

        Args:
            conversation_id: Conversation identifier
        """
        if conversation_id in self._conversation_contexts:
            del self._conversation_contexts[conversation_id]

    async def chat(
        self,
        messages: List[ChatMessage],
        provider: str = LLMProviderEnum.OPENAI,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        functions: Optional[List[Dict]] = None,
        **kwargs
    ) -> ChatCompletionResult:
        """
        Generate chat completion.

        Args:
            messages: List of ChatMessage objects
            provider: LLM provider to use
            api_key: Provider API key (optional)
            model: Model to use
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            functions: Optional function definitions
            **kwargs: Additional parameters

        Returns:
            ChatCompletionResult

        Example:
            ```python
            llm = LLMService()
            messages = [
                ChatMessage(role="system", content="You are a helpful assistant."),
                ChatMessage(role="user", content="What is the capital of France?"),
            ]
            result = await llm.chat(messages, provider="openai")
            print(result.content)
            ```
        """
        provider_instance = self.get_provider(
            provider=provider,
            api_key=api_key,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs
        )

        result = await provider_instance.chat_completion(messages, functions=functions, **kwargs)
        return result

    async def chat_stream(
        self,
        messages: List[ChatMessage],
        provider: str = LLMProviderEnum.OPENAI,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        functions: Optional[List[Dict]] = None,
        **kwargs
    ) -> AsyncIterator[str]:
        """
        Generate chat completion with streaming.

        Args:
            messages: List of ChatMessage objects
            provider: LLM provider to use
            api_key: Provider API key (optional)
            model: Model to use
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            functions: Optional function definitions
            **kwargs: Additional parameters

        Yields:
            Text chunks as they're generated

        Example:
            ```python
            llm = LLMService()
            messages = [ChatMessage(role="user", content="Tell me a story.")]
            async for chunk in llm.chat_stream(messages):
                print(chunk, end='', flush=True)
            ```
        """
        provider_instance = self.get_provider(
            provider=provider,
            api_key=api_key,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs
        )

        async for chunk in provider_instance.chat_completion_stream(messages, functions=functions, **kwargs):
            yield chunk

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
        self._conversation_contexts.clear()


# Global LLM service instance
_llm_service: Optional[LLMService] = None


def get_llm_service() -> LLMService:
    """
    Get global LLM service instance (singleton).

    Returns:
        LLMService instance
    """
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service
