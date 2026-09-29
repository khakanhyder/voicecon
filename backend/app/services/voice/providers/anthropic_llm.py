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

    def _format_messages(self, messages: List[ChatMessage]) -> tuple[str, List[Dict[str, Any]]]:
        """
        Convert ChatMessage objects to Anthropic format.

        Anthropic uses a system parameter and messages array. A prior tool
        call/result — the shapes agents.py's function-calling loop pushes back
        as `ChatMessage(role="assistant", function_call={...})` and
        `ChatMessage(role="function", ...)` — used to fall through untouched
        (function_call was never read) or be dropped outright (role="function"
        matched neither branch), which silently erased the model's own tool
        calls from history. They're converted to Claude's tool_use /
        tool_result content blocks instead, so a multi-step tool turn keeps
        its history intact (B3).

        Args:
            messages: List of ChatMessage objects

        Returns:
            Tuple of (system_prompt, formatted_messages)
        """
        system_prompt = ""
        turns: List[Dict[str, Any]] = []
        # A stable id generated for each tool_use block and reused by the
        # tool_result message that follows — our internal FunctionCall/
        # ChatMessage shapes carry no id of their own. Mirrors the
        # `last_tool_call_id` bookkeeping in the OpenAI provider.
        last_tool_use_id: Optional[str] = None
        tool_seq = 0

        for msg in messages:
            text = msg.content or ""
            if msg.role == "system":
                if text:
                    system_prompt += text + "\n"
            elif msg.role == "assistant" and msg.function_call:
                fc = msg.function_call
                tool_seq += 1
                last_tool_use_id = f"toolu_{tool_seq}_{fc.get('name', 'fn')}"[:40]
                try:
                    tool_input = json.loads(fc.get("arguments") or "{}")
                except (TypeError, ValueError):
                    tool_input = {}
                # Claude requires the input to be an object.
                if not isinstance(tool_input, dict):
                    tool_input = {}
                blocks: List[Dict[str, Any]] = []
                if text:
                    blocks.append({"type": "text", "text": text})
                blocks.append({
                    "type": "tool_use",
                    "id": last_tool_use_id,
                    "name": fc.get("name") or "tool",
                    "input": tool_input,
                })
                turns.append({"role": "assistant", "content": blocks})
            elif msg.role == "function":
                turns.append({
                    "role": "user",
                    "content": [{
                        "type": "tool_result",
                        "tool_use_id": last_tool_use_id or f"toolu_{tool_seq or 1}",
                        "content": text or "(no output)",
                    }],
                })
            elif msg.role in ("user", "assistant") and text.strip():
                # Empty text is skipped: OpenAI accepts it, Claude rejects the
                # whole request ("text content blocks must be non-empty").
                turns.append({"role": msg.role, "content": [{"type": "text", "text": text}]})

        # Claude requires the conversation to open with the user. A call or a
        # test starts with the agent's own greeting, which OpenAI takes as-is
        # but Claude rejects — keep it as context in the system prompt.
        while turns and turns[0]["role"] == "assistant":
            opening = " ".join(
                b["text"] for b in turns.pop(0)["content"] if b.get("type") == "text"
            ).strip()
            if opening:
                system_prompt += f"\nYou opened this conversation by saying: \"{opening}\"\n"

        # Consecutive turns from the same side (a tool result followed by the
        # caller's next words, two agent lines in a row) are merged into one.
        formatted: List[Dict[str, Any]] = []
        for turn in turns:
            if formatted and formatted[-1]["role"] == turn["role"]:
                formatted[-1]["content"].extend(turn["content"])
            else:
                formatted.append({"role": turn["role"], "content": list(turn["content"])})

        return system_prompt.strip(), self._pair_tool_blocks(formatted)

    @staticmethod
    def _pair_tool_blocks(turns: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Claude rejects a tool_result whose tool_use is not in the turn right
        before it, and a tool_use with no tool_result right after. History is
        trimmed to a window (a call keeps its last 20 messages), which can cut
        such a pair in half. An unpaired block becomes plain text instead, so
        the model still sees what happened and the request stays valid.
        """
        def as_text(block: Dict[str, Any]) -> Dict[str, Any]:
            if block.get("type") == "tool_use":
                return {"type": "text", "text": f"(Called {block.get('name')} with {json.dumps(block.get('input', {}))}.)"}
            content = block.get("content")
            return {"type": "text", "text": f"(Tool result: {content})"}

        for i, turn in enumerate(turns):
            if turn["role"] == "user":
                prev = turns[i - 1] if i > 0 else None
                called = {
                    b["id"] for b in (prev or {}).get("content", [])
                    if prev and prev["role"] == "assistant" and b.get("type") == "tool_use"
                }
                blocks = [
                    b if b.get("type") != "tool_result" or b.get("tool_use_id") in called else as_text(b)
                    for b in turn["content"]
                ]
                # tool_result blocks must lead the turn.
                blocks.sort(key=lambda b: 0 if b.get("type") == "tool_result" else 1)
                turn["content"] = blocks
            else:
                nxt = turns[i + 1] if i + 1 < len(turns) else None
                answered = {
                    b.get("tool_use_id") for b in (nxt or {}).get("content", [])
                    if b.get("type") == "tool_result"
                }
                turn["content"] = [
                    b if b.get("type") != "tool_use" or b.get("id") in answered else as_text(b)
                    for b in turn["content"]
                ]
        return turns

    def _convert_tools(self, functions: Optional[List[Dict[str, Any]]]) -> Optional[List[Dict[str, Any]]]:
        """OpenAI-style {name, description, parameters} defs -> Claude's
        {name, description, input_schema} tool defs."""
        if not functions:
            return None

        def schema(params: Optional[Dict[str, Any]]) -> Dict[str, Any]:
            # Claude requires `type: object`. function_executor.object_schema
            # already guarantees it; kept here so the provider is safe on its own.
            s = dict(params or {})
            s["type"] = "object"
            s.setdefault("properties", {})
            return s

        return [
            {
                "name": f["name"],
                "description": f.get("description", ""),
                "input_schema": schema(f.get("parameters")),
            }
            for f in functions
        ]

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
            functions: Optional function definitions, converted to Claude's
                tools API (name/description/parameters -> input_schema)
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

            # Prepare request. Claude's temperature range is 0-1 (agents allow
            # 0-2, matching OpenAI's range) — clamped here rather than
            # rejected, since the UI slider doesn't know which provider is
            # active when the value is set.
            request_params = {
                "model": kwargs.get("model", self.model),
                "max_tokens": kwargs.get("max_tokens", self.max_tokens),
                "messages": formatted_messages,
                "temperature": min(float(kwargs.get("temperature", self.temperature)), 1.0),
            }

            if system_prompt:
                request_params["system"] = system_prompt

            if self.top_p is not None:
                request_params["top_p"] = self.top_p

            if self.top_k is not None:
                request_params["top_k"] = self.top_k

            tools = self._convert_tools(functions)
            if tools:
                request_params["tools"] = tools

            # Call Anthropic API
            response: Message = await self.client.messages.create(**request_params)

            # Extract response. One tool call per turn (matching the OpenAI
            # provider) — a model that both talks and calls a tool in the same
            # turn returns both block types; the text is kept for context but
            # the tool call still drives the loop in agents.py.
            content = ""
            function_call = None
            if response.content:
                for block in response.content:
                    if block.type == "text":
                        content += block.text
                    elif block.type == "tool_use":
                        function_call = FunctionCall(
                            name=block.name,
                            arguments=json.dumps(block.input),
                        )

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
                function_call=function_call,
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
            functions: Optional function definitions, sent as Claude tools.
            **kwargs: Additional parameters

        Yields:
            Text chunks as they're generated, then — if the model called a
            tool — one ``{"function_call": {"name", "arguments"}}`` dict,
            the same contract as the OpenAI provider. Phone calls
            (voice_session.py) run their tool loop on this; without it an
            agent on Claude could not use any tool during a real call.

        Raises:
            AuthenticationError: Invalid API key
            RateLimitError: Rate limit exceeded
            ProviderError: Other API errors
        """
        try:
            # Format messages
            system_prompt, formatted_messages = self._format_messages(messages)

            # Prepare request. `messages.stream()` is a dedicated streaming
            # helper with its own signature — streaming is implicit in the
            # method itself, and it has no `stream` parameter at all (unlike
            # `messages.create()`). Passing one raised a TypeError on every
            # single call, which is why every no-tool Anthropic reply came
            # back as "I'm having a technical issue" (M1).
            request_params = {
                "model": kwargs.get("model", self.model),
                "max_tokens": kwargs.get("max_tokens", self.max_tokens),
                "messages": formatted_messages,
                "temperature": min(float(kwargs.get("temperature", self.temperature)), 1.0),
            }

            if system_prompt:
                request_params["system"] = system_prompt

            if self.top_p is not None:
                request_params["top_p"] = self.top_p

            if self.top_k is not None:
                request_params["top_k"] = self.top_k

            tools = self._convert_tools(functions)
            if tools:
                request_params["tools"] = tools

            # Stream response
            async with self.client.messages.stream(**request_params) as stream:
                async for event in stream:
                    event: MessageStreamEvent

                    if event.type == "content_block_delta":
                        if event.delta.type == "text_delta":
                            yield event.delta.text

                # Get final message for usage stats (and any tool call — the
                # SDK assembles the streamed tool input JSON for us).
                final_message = await stream.get_final_message()

                tool_use = next(
                    (b for b in final_message.content or [] if b.type == "tool_use"), None
                )
                if tool_use is not None:
                    logger.info(f"Anthropic streaming produced tool call: {tool_use.name}")
                    yield {
                        "function_call": {
                            "name": tool_use.name,
                            "arguments": json.dumps(tool_use.input or {}),
                        }
                    }

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
