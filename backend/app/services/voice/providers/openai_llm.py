"""
OpenAI Large Language Model Provider.

Implements LLM using OpenAI API with streaming and function calling support.
"""
import logging
from typing import AsyncIterator, Optional, Dict, Any, List
import json

from openai import AsyncOpenAI
from openai.types.chat import ChatCompletion, ChatCompletionChunk

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


class OpenAILLM(BaseLLMProvider):
    """
    OpenAI LLM provider.

    Supports:
    - GPT-4, GPT-4 Turbo, GPT-3.5 Turbo models
    - Streaming for real-time responses
    - Function calling
    - Token counting and cost tracking
    """

    # Pricing per 1M tokens (as of 2025-2026, estimated)
    PRICING = {
        # GPT-5.5 series (Apr 2026)
        "gpt-5.5":             {"prompt": 15.00, "completion": 60.00},
        "gpt-5.5-pro":         {"prompt": 30.00, "completion": 120.00},
        # GPT-5.4 series (Mar 2026)
        "gpt-5.4":             {"prompt": 8.00,  "completion": 32.00},
        "gpt-5.4-mini":        {"prompt": 0.60,  "completion": 2.40},
        "gpt-5.4-nano":        {"prompt": 0.12,  "completion": 0.48},
        "gpt-5.4-pro":         {"prompt": 20.00, "completion": 80.00},
        # GPT-5.2 series (Dec 2025)
        "gpt-5.2":             {"prompt": 8.00,  "completion": 32.00},
        "gpt-5.2-pro":         {"prompt": 20.00, "completion": 80.00},
        # GPT-5.1 series (Nov 2025)
        "gpt-5.1":             {"prompt": 7.00,  "completion": 28.00},
        # GPT-5 base (Aug 2025)
        "gpt-5":               {"prompt": 5.00,  "completion": 20.00},
        "gpt-5-mini":          {"prompt": 0.50,  "completion": 2.00},
        "gpt-5-nano":          {"prompt": 0.12,  "completion": 0.48},
        "gpt-5-pro":           {"prompt": 15.00, "completion": 60.00},
        # GPT-4.1 series (Apr 2025)
        "gpt-4.1":             {"prompt": 2.00,  "completion": 8.00},
        "gpt-4.1-mini":        {"prompt": 0.40,  "completion": 1.60},
        "gpt-4.1-nano":        {"prompt": 0.10,  "completion": 0.40},
        # GPT-4o series
        "gpt-4o":              {"prompt": 2.50,  "completion": 10.00},
        "gpt-4o-mini":         {"prompt": 0.15,  "completion": 0.60},
        # Reasoning models
        "o4-mini":             {"prompt": 1.10,  "completion": 4.40},
        "o3":                  {"prompt": 10.00, "completion": 40.00},
        "o3-mini":             {"prompt": 1.10,  "completion": 4.40},
        "o1-pro":              {"prompt": 150.00, "completion": 600.00},
        "o1":                  {"prompt": 15.00, "completion": 60.00},
        "o1-mini":             {"prompt": 3.00,  "completion": 12.00},
        # Legacy
        "gpt-4":               {"prompt": 30.00, "completion": 60.00},
        "gpt-4-turbo":         {"prompt": 10.00, "completion": 30.00},
        "gpt-4-turbo-preview": {"prompt": 10.00, "completion": 30.00},
        "gpt-3.5-turbo":       {"prompt": 0.50,  "completion": 1.50},
        "gpt-3.5-turbo-16k":   {"prompt": 3.00,  "completion": 4.00},
    }

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-5.4-nano",
        temperature: float = 0.7,
        max_tokens: int = 1000,
        **kwargs
    ):
        """
        Initialize OpenAI LLM provider.

        Args:
            api_key: OpenAI API key
            model: Model to use (gpt-4, gpt-4-turbo-preview, gpt-3.5-turbo)
            temperature: Sampling temperature (0-2)
            max_tokens: Maximum tokens to generate
            **kwargs: Additional configuration (top_p, frequency_penalty, etc.)
        """
        super().__init__(api_key, model, temperature, max_tokens, **kwargs)

        # OpenAI client
        self.client = AsyncOpenAI(api_key=api_key)

        # Additional parameters
        self.top_p = kwargs.get("top_p", 1.0)
        self.frequency_penalty = kwargs.get("frequency_penalty", 0.0)
        self.presence_penalty = kwargs.get("presence_penalty", 0.0)
        self.stop = kwargs.get("stop", None)

        logger.info(f"Initialized OpenAI LLM: model={model}, temperature={temperature}")

    def _format_messages(self, messages: List[ChatMessage]) -> List[Dict[str, Any]]:
        """
        Convert ChatMessage objects to OpenAI format.

        Args:
            messages: List of ChatMessage objects

        Returns:
            List of message dicts for OpenAI API
        """
        formatted = []
        for msg in messages:
            message_dict = {
                "role": msg.role,
                "content": msg.content,
            }

            if msg.name:
                message_dict["name"] = msg.name

            if msg.function_call:
                message_dict["function_call"] = msg.function_call

            formatted.append(message_dict)

        return formatted

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
            functions: Optional function definitions
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
            formatted_messages = self._format_messages(messages)

            model_id = kwargs.get("model", self.model)
            # GPT-5.x and o-series require max_completion_tokens; all others accept both
            use_completion_tokens = any(
                model_id.startswith(p) for p in ("gpt-5", "o1", "o3", "o4")
            )
            token_key = "max_completion_tokens" if use_completion_tokens else "max_tokens"

            # Prepare request
            request_params = {
                "model": model_id,
                "messages": formatted_messages,
                "temperature": kwargs.get("temperature", self.temperature),
                token_key: kwargs.get("max_tokens", self.max_tokens),
                "top_p": kwargs.get("top_p", self.top_p),
                "frequency_penalty": kwargs.get("frequency_penalty", self.frequency_penalty),
                "presence_penalty": kwargs.get("presence_penalty", self.presence_penalty),
            }

            if self.stop:
                request_params["stop"] = self.stop

            if functions:
                request_params["functions"] = functions
                request_params["function_call"] = kwargs.get("function_call", "auto")

            # Call OpenAI API
            response: ChatCompletion = await self.client.chat.completions.create(**request_params)

            # Extract response
            choice = response.choices[0]
            message = choice.message

            # Handle function call
            function_call = None
            if message.function_call:
                function_call = FunctionCall(
                    name=message.function_call.name,
                    arguments=message.function_call.arguments,
                )

            # Calculate cost
            cost = self._calculate_cost(
                model=response.model,
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens,
            )

            # Track usage
            self._track_usage(
                model=response.model,
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens,
                cost=cost,
                request_id=response.id,
            )

            logger.info(
                f"OpenAI completion: {response.usage.total_tokens} tokens, "
                f"${cost:.4f}"
            )

            return ChatCompletionResult(
                content=message.content or "",
                role=message.role,
                function_call=function_call,
                finish_reason=choice.finish_reason,
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens,
                total_tokens=response.usage.total_tokens,
                model=response.model,
            )

        except Exception as e:
            error_msg = str(e)

            if "invalid_api_key" in error_msg or "Incorrect API key" in error_msg:
                raise AuthenticationError(f"Invalid OpenAI API key: {error_msg}")
            elif "rate_limit" in error_msg:
                raise RateLimitError(f"OpenAI rate limit exceeded: {error_msg}")
            else:
                logger.error(f"OpenAI API error: {error_msg}")
                raise ProviderError(f"OpenAI API error: {error_msg}")

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
            functions: Optional function definitions
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
            formatted_messages = self._format_messages(messages)

            model_id = kwargs.get("model", self.model)
            use_completion_tokens = any(
                model_id.startswith(p) for p in ("gpt-5", "o1", "o3", "o4")
            )
            token_key = "max_completion_tokens" if use_completion_tokens else "max_tokens"

            # Prepare request
            request_params = {
                "model": model_id,
                "messages": formatted_messages,
                "temperature": kwargs.get("temperature", self.temperature),
                token_key: kwargs.get("max_tokens", self.max_tokens),
                "top_p": kwargs.get("top_p", self.top_p),
                "frequency_penalty": kwargs.get("frequency_penalty", self.frequency_penalty),
                "presence_penalty": kwargs.get("presence_penalty", self.presence_penalty),
                "stream": True,
            }

            if self.stop:
                request_params["stop"] = self.stop

            if functions:
                request_params["functions"] = functions
                request_params["function_call"] = kwargs.get("function_call", "auto")

            # Stream response
            stream = await self.client.chat.completions.create(**request_params)

            # Track tokens for cost calculation (approximate)
            completion_tokens = 0

            async for chunk in stream:
                chunk: ChatCompletionChunk

                if chunk.choices:
                    choice = chunk.choices[0]

                    if choice.delta.content:
                        content = choice.delta.content
                        completion_tokens += len(content.split())  # Approximate
                        yield content

            # Note: We can't get exact token counts in streaming mode
            # This is an approximation
            logger.info(f"OpenAI streaming completed: ~{completion_tokens} tokens")

        except Exception as e:
            error_msg = str(e)

            if "invalid_api_key" in error_msg or "Incorrect API key" in error_msg:
                raise AuthenticationError(f"Invalid OpenAI API key: {error_msg}")
            elif "rate_limit" in error_msg:
                raise RateLimitError(f"OpenAI rate limit exceeded: {error_msg}")
            else:
                logger.error(f"OpenAI streaming error: {error_msg}")
                raise ProviderError(f"OpenAI streaming error: {error_msg}")

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
        # Get base model name (remove -0125, -0613, etc. suffixes)
        base_model = model.split("-20")[0] if "-20" in model else model

        pricing = self.PRICING.get(base_model, self.PRICING["gpt-3.5-turbo"])

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
            provider="openai",
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

        Note: This is an approximation. For exact counts, use tiktoken library.

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
        logger.info("OpenAI LLM client closed")
