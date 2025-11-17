"""
Anthropic Claude Large Language Model Provider.

Implements LLM using Anthropic Claude API with streaming support.
"""
import logging
from typing import AsyncIterator, Optional, Dict, Any, List
import json

from anthropic import AsyncAnthropic
from anthropic.types import Message, MessageStreamEvent

from app.services.voice.providers.base import (
    BaseLLMProvider,
    ChatMessage,
    ChatCompletionResult,
    FunctionCall,
    LLMUsage,
    ProviderError,
    AuthenticationError,
    RateLimitError,
)

logger = logging.getLogger(__name__)


class AnthropicLLM(BaseLLMProvider):
    """
    Anthropic Claude LLM provider.

    Supports:
    - Claude 3 Opus, Claude 3 Sonnet, Claude 3 Haiku
    - Streaming for real-time responses
    - System prompts and conversation context
    - Token counting and cost tracking
    """

    # Pricing per 1M tokens (as of 2025)
    PRICING = {
        "claude-3-opus-20240229": {"prompt": 15.00, "completion": 75.00},
        "claude-3-sonnet-20240229": {"prompt": 3.00, "completion": 15.00},
        "claude-3-haiku-20240307": {"prompt": 0.25, "completion": 1.25},
        "claude-2.1": {"prompt": 8.00, "completion": 24.00},
        "claude-2.0": {"prompt": 8.00, "completion": 24.00},
        "claude-instant-1.2": {"prompt": 0.80, "completion": 2.40},
    }

    def __init__(
        self,
        api_key: str,
        model: str = "claude-3-sonnet-20240229",
        temperature: float = 0.7,
        max_tokens: int = 1000,
        **kwargs
    ):
        """
        Initialize Anthropic LLM provider.

        Args:
            api_key: Anthropic API key
            model: Model to use (claude-3-opus, claude-3-sonnet, claude-3-haiku)
            temperature: Sampling temperature (0-1)
            max_tokens: Maximum tokens to generate
            **kwargs: Additional configuration (top_p, top_k)
        """
        super().__init__(api_key, model, temperature, max_tokens, **kwargs)

        # Anthropic client
        self.client = AsyncAnthropic(api_key=api_key)

        # Additional parameters
        self.top_p = kwargs.get("top_p", None)
        self.top_k = kwargs.get("top_k", None)

        logger.info(f"Initialized Anthropic LLM: model={model}, temperature={temperature}")

    def _format_messages(self, messages: List[ChatMessage]) -> tuple[str, List[Dict[str, str]]]:
        """
        Convert ChatMessage objects to Anthropic format.

        Anthropic uses a system parameter and messages array.

        Args:
            messages: List of ChatMessage objects

        Returns:
            Tuple of (system_prompt, formatted_messages)
        """
        system_prompt = ""
        formatted = []

        for msg in messages:
            if msg.role == "system":
                system_prompt += msg.content + "\n"
            elif msg.role in ["user", "assistant"]:
                formatted.append({
                    "role": msg.role,
                    "content": msg.content,
                })

        return system_prompt.strip(), formatted

    async def chat_completion(
        self,
        messages: List[ChatMessage],
        functions: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> ChatCompletionResult:
        """
        Generate chat completion.

        Args:
            messages: List of ChatMessage objects
            functions: Optional function definitions (not supported by Claude)
            **kwargs: Additional parameters

        Returns:
            ChatCompletionResult

        Raises:
            AuthenticationError: Invalid API key
            RateLimitError: Rate limit exceeded
            ProviderError: Other API errors
        """
        try:
            # Format messages
            system_prompt, formatted_messages = self._format_messages(messages)

            # Prepare request
            request_params = {
                "model": kwargs.get("model", self.model),
                "max_tokens": kwargs.get("max_tokens", self.max_tokens),
                "messages": formatted_messages,
                "temperature": kwargs.get("temperature", self.temperature),
            }

            if system_prompt:
                request_params["system"] = system_prompt

            if self.top_p is not None:
                request_params["top_p"] = self.top_p

            if self.top_k is not None:
                request_params["top_k"] = self.top_k

            # Call Anthropic API
            response: Message = await self.client.messages.create(**request_params)

            # Extract response
            content = ""
            if response.content:
                for block in response.content:
                    if block.type == "text":
                        content += block.text

            # Calculate cost
            cost = self._calculate_cost(
                model=response.model,
                prompt_tokens=response.usage.input_tokens,
                completion_tokens=response.usage.output_tokens,
            )

            # Track usage
            self._track_usage(
                model=response.model,
                prompt_tokens=response.usage.input_tokens,
                completion_tokens=response.usage.output_tokens,
                cost=cost,
                request_id=response.id,
            )

            logger.info(
                f"Anthropic completion: {response.usage.input_tokens + response.usage.output_tokens} tokens, "
                f"${cost:.4f}"
            )

            return ChatCompletionResult(
                content=content,
                role="assistant",
                finish_reason=response.stop_reason,
                prompt_tokens=response.usage.input_tokens,
                completion_tokens=response.usage.output_tokens,
                total_tokens=response.usage.input_tokens + response.usage.output_tokens,
                model=response.model,
            )

        except Exception as e:
            error_msg = str(e)

            if "invalid_api_key" in error_msg or "authentication" in error_msg.lower():
                raise AuthenticationError(f"Invalid Anthropic API key: {error_msg}")
            elif "rate_limit" in error_msg or "429" in error_msg:
                raise RateLimitError(f"Anthropic rate limit exceeded: {error_msg}")
            else:
                logger.error(f"Anthropic API error: {error_msg}")
                raise ProviderError(f"Anthropic API error: {error_msg}")

    async def chat_completion_stream(
        self,
        messages: List[ChatMessage],
        functions: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> AsyncIterator[str]:
        """
        Generate chat completion with streaming.

        Args:
            messages: List of ChatMessage objects
            functions: Optional function definitions (not supported)
            **kwargs: Additional parameters

        Yields:
            Text chunks as they're generated

        Raises:
            AuthenticationError: Invalid API key
            RateLimitError: Rate limit exceeded
            ProviderError: Other API errors
        """
        try:
            # Format messages
            system_prompt, formatted_messages = self._format_messages(messages)

            # Prepare request
            request_params = {
                "model": kwargs.get("model", self.model),
                "max_tokens": kwargs.get("max_tokens", self.max_tokens),
                "messages": formatted_messages,
                "temperature": kwargs.get("temperature", self.temperature),
                "stream": True,
            }

            if system_prompt:
                request_params["system"] = system_prompt

            if self.top_p is not None:
                request_params["top_p"] = self.top_p

            if self.top_k is not None:
                request_params["top_k"] = self.top_k

            # Stream response
            async with self.client.messages.stream(**request_params) as stream:
                async for event in stream:
                    event: MessageStreamEvent

                    if event.type == "content_block_delta":
                        if event.delta.type == "text_delta":
                            yield event.delta.text

                # Get final message for usage stats
                final_message = await stream.get_final_message()

                # Track usage
                cost = self._calculate_cost(
                    model=final_message.model,
                    prompt_tokens=final_message.usage.input_tokens,
                    completion_tokens=final_message.usage.output_tokens,
                )

                self._track_usage(
                    model=final_message.model,
                    prompt_tokens=final_message.usage.input_tokens,
                    completion_tokens=final_message.usage.output_tokens,
                    cost=cost,
                    request_id=final_message.id,
                )

                logger.info(
                    f"Anthropic streaming completed: "
                    f"{final_message.usage.input_tokens + final_message.usage.output_tokens} tokens, "
                    f"${cost:.4f}"
                )

        except Exception as e:
            error_msg = str(e)

            if "invalid_api_key" in error_msg or "authentication" in error_msg.lower():
                raise AuthenticationError(f"Invalid Anthropic API key: {error_msg}")
            elif "rate_limit" in error_msg or "429" in error_msg:
                raise RateLimitError(f"Anthropic rate limit exceeded: {error_msg}")
            else:
                logger.error(f"Anthropic streaming error: {error_msg}")
                raise ProviderError(f"Anthropic streaming error: {error_msg}")

    def _calculate_cost(self, model: str, prompt_tokens: int, completion_tokens: int) -> float:
        """
        Calculate cost based on token usage.

        Args:
            model: Model used
            prompt_tokens: Number of prompt tokens
            completion_tokens: Number of completion tokens

        Returns:
            Cost in USD
        """
        pricing = self.PRICING.get(model, self.PRICING["claude-3-sonnet-20240229"])

        prompt_cost = (prompt_tokens / 1_000_000) * pricing["prompt"]
        completion_cost = (completion_tokens / 1_000_000) * pricing["completion"]

        return prompt_cost + completion_cost

    def _track_usage(
        self,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        cost: float,
        request_id: Optional[str] = None,
    ):
        """
        Track usage for cost monitoring.

        Args:
            model: Model used
            prompt_tokens: Prompt tokens
            completion_tokens: Completion tokens
            cost: Cost in USD
            request_id: Request ID
        """
        usage = LLMUsage(
            provider="anthropic",
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            cost=cost,
            request_id=request_id,
        )
        self._usage_stats.append(usage)

    async def count_tokens(self, text: str) -> int:
        """
        Estimate token count for text.

        Note: This is an approximation.

        Args:
            text: Text to count tokens for

        Returns:
            Approximate token count
        """
        # Rough approximation: 1 token ≈ 4 characters
        return len(text) // 4

    async def close(self):
        """Close HTTP client and cleanup resources."""
        await self.client.close()
        logger.info("Anthropic LLM client closed")
