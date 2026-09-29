"""
Per-model request rules that decide whether a dropdown model can answer at all.

- Claude Sonnet 5 / Opus 5.5 reject any temperature (400) and think before
  answering, so the agent's temperature is dropped and thinking gets room.
- OpenAI reasoning models spent a 150-token reply limit on reasoning and
  answered with nothing.
- OpenRouter needs vendor-prefixed model ids.
"""
from types import SimpleNamespace

import pytest

from app.services.voice.providers.anthropic_llm import AnthropicLLM
from app.services.voice.providers.base import ChatMessage
from app.services.voice.providers.openai_llm import OpenAILLM, gateway_model_id

MESSAGES = [ChatMessage(role="user", content="hi")]


class _Captured(Exception):
    pass


def _anthropic_request(model: str):
    sent = {}

    async def create(**params):
        sent.update(params)
        raise _Captured

    provider = AnthropicLLM(api_key="x", model=model, temperature=0.4, max_tokens=150)
    provider.client = SimpleNamespace(messages=SimpleNamespace(create=create))
    return provider, sent


@pytest.mark.asyncio
@pytest.mark.parametrize("model", ["claude-sonnet-5", "claude-opus-5-5"])
async def test_claude_models_without_sampling_get_no_temperature(model):
    provider, sent = _anthropic_request(model)
    with pytest.raises(Exception):
        await provider.chat_completion(MESSAGES)
    assert "temperature" not in sent
    assert sent["max_tokens"] > 150
    assert sent["extra_body"] == {"output_config": {"effort": "low"}}


@pytest.mark.asyncio
@pytest.mark.parametrize("model", ["claude-haiku-4-5-20251001", "claude-sonnet-4-6", "claude-opus-4-6"])
async def test_older_claude_models_keep_their_temperature(model):
    provider, sent = _anthropic_request(model)
    with pytest.raises(Exception):
        await provider.chat_completion(MESSAGES)
    assert sent["temperature"] == 0.4
    assert sent["max_tokens"] == 150
    assert "extra_body" not in sent


def _openai_request(model: str):
    sent = {}

    async def create(**params):
        sent.update(params)
        raise _Captured

    provider = OpenAILLM(api_key="sk-test", model=model, temperature=0.4, max_tokens=150)
    provider.client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    return provider, sent


@pytest.mark.asyncio
@pytest.mark.parametrize("model", ["gpt-5-nano", "gpt-5", "o3", "o4-mini"])
async def test_reasoning_models_get_room_and_low_effort(model):
    provider, sent = _openai_request(model)
    with pytest.raises(Exception):
        await provider.chat_completion(MESSAGES)
    assert sent["max_completion_tokens"] > 150
    assert sent["reasoning_effort"] == "low"


@pytest.mark.asyncio
async def test_later_gpt5_models_are_not_given_reasoning():
    provider, sent = _openai_request("gpt-5.4-nano")
    with pytest.raises(Exception):
        await provider.chat_completion(MESSAGES)
    assert "reasoning_effort" not in sent


@pytest.mark.asyncio
async def test_non_reasoning_models_keep_max_tokens():
    provider, sent = _openai_request("gpt-4o-mini")
    with pytest.raises(Exception):
        await provider.chat_completion(MESSAGES)
    assert sent["max_tokens"] == 150


def test_openrouter_model_ids_get_vendor_prefix():
    openrouter = "https://openrouter.ai/api/v1"
    assert gateway_model_id("gpt-5.4-nano", openrouter) == "openai/gpt-5.4-nano"
    assert gateway_model_id("anthropic/claude-haiku-4.5", openrouter) == "anthropic/claude-haiku-4.5"
    assert gateway_model_id("gpt-5.4-nano", None) == "gpt-5.4-nano"
