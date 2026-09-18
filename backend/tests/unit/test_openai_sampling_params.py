"""
A model that only accepts its default temperature must not break the agent.

GPT-5.5 answers any temperature but 1 with a 400, and the agent form allows
that combination, so every voice turn of such an agent ended in "I'm having a
technical issue". The provider now drops the rejected parameter and retries.
"""
from types import SimpleNamespace

import httpx
import pytest
from openai import BadRequestError

from app.services.voice.providers.base import ChatMessage, ProviderError
from app.services.voice.providers.openai_llm import OpenAILLM


def _bad_request(param: str) -> BadRequestError:
    body = {
        "message": f"Unsupported value: '{param}' does not support 0.4 with this model.",
        "type": "invalid_request_error",
        "param": param,
        "code": "unsupported_value",
    }
    request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    return BadRequestError(body["message"], response=httpx.Response(400, request=request), body=body)


def _completion(text: str):
    return SimpleNamespace(
        id="x",
        model="gpt-5.5",
        choices=[SimpleNamespace(
            message=SimpleNamespace(content=text, role="assistant", tool_calls=None),
            finish_reason="stop",
        )],
        usage=SimpleNamespace(prompt_tokens=1, completion_tokens=1, total_tokens=2),
    )


class _FakeCompletions:
    def __init__(self, rejects: set):
        self.rejects = rejects
        self.calls = []

    async def create(self, **params):
        self.calls.append(dict(params))
        for param in self.rejects:
            if param in params:
                raise _bad_request(param)
        return _completion("hello")


def _provider(rejects: set) -> tuple[OpenAILLM, _FakeCompletions]:
    provider = OpenAILLM(api_key="sk-test", model="gpt-5.5", temperature=0.4)
    fake = _FakeCompletions(rejects)
    provider.client = SimpleNamespace(chat=SimpleNamespace(completions=fake))
    return provider, fake


@pytest.fixture(autouse=True)
def _forget_learned_params():
    OpenAILLM._rejected_params.clear()
    yield
    OpenAILLM._rejected_params.clear()


@pytest.mark.asyncio
async def test_rejected_temperature_is_dropped_and_remembered():
    provider, fake = _provider({"temperature"})
    messages = [ChatMessage(role="user", content="hi")]

    result = await provider.chat_completion(messages)
    assert result.content == "hello"
    assert "temperature" in fake.calls[0]
    assert "temperature" not in fake.calls[1]

    # The next turn goes straight through without a wasted 400.
    fake.calls.clear()
    await provider.chat_completion(messages)
    assert len(fake.calls) == 1
    assert "temperature" not in fake.calls[0]


@pytest.mark.asyncio
async def test_other_bad_requests_still_fail():
    provider, _ = _provider({"messages"})
    with pytest.raises(ProviderError):
        await provider.chat_completion([ChatMessage(role="user", content="hi")])
