"""
An agent must behave the same whichever LLM provider it is set to — OpenAI or
Anthropic — on every path: browser test calls (/respond), real phone calls
(voice_session), the chat widget, tools, and the workflows those tools run.

CI (and local dev) has no working key for either provider, so each provider's
real SDK is pointed at a fake API that enforces the request rules the real one
enforces. A request that production would reject fails here too; the fakes
then answer from a small script so the whole tool loop can be exercised:

* ask about the armchair with tools available -> the model calls the tool
* send it the tool's result                  -> it answers from the result
* anything else                              -> "Hello from <provider>."
"""
import json
import types
import uuid

import httpx
import pytest
from anthropic import AsyncAnthropic
from openai import AsyncOpenAI

from app.services.voice.providers.anthropic_llm import AnthropicLLM
from app.services.voice.providers.base import ChatMessage
from app.services.voice.providers.openai_llm import OpenAILLM

MODELS = {"openai": "gpt-5.4-nano", "anthropic": "claude-haiku-4-5-20251001"}
PROVIDERS = list(MODELS)
TOOL_RESULT = '{"width_cm": 106}'
LOOKUP_TOOL = {
    "name": "product_lookup",
    "description": "Look up a product's dimensions.",
    "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
}
ARMCHAIR_ARGS = {"query": "Totem armchair width"}


def _answer(tool_output):
    return f"The Totem armchair is 106 cm wide. ({tool_output})"


# ── Fake OpenAI Chat Completions API ─────────────────────────────────────────


class FakeOpenAI:
    name = "OpenAI"

    def __init__(self):
        self.requests = []

    @staticmethod
    def _problems(body):
        errors = []
        msgs = body.get("messages") or []
        if not msgs:
            errors.append("messages: must be non-empty")
        if body["model"].startswith(("gpt-5", "o1", "o3", "o4")) and "max_tokens" in body:
            errors.append("Unsupported parameter: 'max_tokens' — use 'max_completion_tokens'")
        if not 0 <= float(body.get("temperature", 1)) <= 2:
            errors.append("temperature: must be between 0 and 2")
        for tool in body.get("tools") or []:
            if (tool["function"].get("parameters") or {}).get("type") != "object":
                errors.append(f"Invalid schema for function '{tool['function']['name']}': "
                              "schema must be a JSON Schema of 'type: \"object\"'")
        for i, m in enumerate(msgs):
            if m["role"] == "tool":
                j = i - 1
                while j >= 0 and msgs[j]["role"] == "tool":
                    j -= 1
                ids = {c["id"] for c in (msgs[j].get("tool_calls") or [])} if j >= 0 else set()
                if msgs[j]["role"] != "assistant" or m.get("tool_call_id") not in ids:
                    errors.append("messages with role 'tool' must be a response to a preceding "
                                  "message with 'tool_calls'")
            if m["role"] == "assistant" and m.get("tool_calls"):
                answered = set()
                for later in msgs[i + 1:]:
                    if later["role"] != "tool":
                        break
                    answered.add(later.get("tool_call_id"))
                for call in m["tool_calls"]:
                    if call["id"] not in answered:
                        errors.append("An assistant message with 'tool_calls' must be followed by "
                                      "tool messages responding to each 'tool_call_id'")
        return errors

    @staticmethod
    def _reply(body):
        last = body["messages"][-1]
        if last["role"] == "tool":
            return {"content": _answer(last["content"])}, "stop"
        said = str(last.get("content") or "").lower()
        if body.get("tools") and "armchair" in said:
            return {"content": None, "tool_calls": [{
                "id": "call_1", "type": "function",
                "function": {"name": body["tools"][0]["function"]["name"], "arguments": json.dumps(ARMCHAIR_ARGS)},
            }]}, "tool_calls"
        return {"content": "Hello from OpenAI."}, "stop"

    def handle(self, request):
        body = json.loads(request.content)
        self.requests.append(body)
        problems = self._problems(body)
        if problems:
            return httpx.Response(400, json={"error": {
                "message": "; ".join(problems), "type": "invalid_request_error", "param": None, "code": None}})
        message, finish = self._reply(body)
        base = {"id": "chatcmpl-1", "created": 0, "model": body["model"]}
        if not body.get("stream"):
            return httpx.Response(200, json={**base, "object": "chat.completion", "choices": [{
                "index": 0, "message": {"role": "assistant", **message}, "finish_reason": finish}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}})
        chunks = []
        if message.get("content"):
            for word in message["content"].split(" "):
                chunks.append({"content": word + " "})
        for call in message.get("tool_calls") or []:
            chunks.append({"tool_calls": [{"index": 0, "id": call["id"], "type": "function",
                                           "function": {"name": call["function"]["name"], "arguments": ""}}]})
            args = call["function"]["arguments"]
            for part in (args[: len(args) // 2], args[len(args) // 2:]):  # arguments arrive in slices
                chunks.append({"tool_calls": [{"index": 0, "function": {"arguments": part}}]})
        events = [{**base, "object": "chat.completion.chunk",
                   "choices": [{"index": 0, "delta": d, "finish_reason": None}]} for d in chunks]
        events.append({**base, "object": "chat.completion.chunk",
                       "choices": [{"index": 0, "delta": {}, "finish_reason": finish}]})
        sse = "".join(f"data: {json.dumps(e)}\n\n" for e in events) + "data: [DONE]\n\n"
        return httpx.Response(200, headers={"content-type": "text/event-stream"}, content=sse.encode())


# ── Fake Anthropic Messages API ──────────────────────────────────────────────


class FakeAnthropic:
    name = "Claude"

    def __init__(self):
        self.requests = []

    @staticmethod
    def _problems(body):
        errors = []
        msgs = body.get("messages") or []
        if not msgs:
            errors.append("messages: at least one message is required")
        if msgs and msgs[0]["role"] != "user":
            errors.append("messages: first message must use the user role")
        for a, b in zip(msgs, msgs[1:]):
            if a["role"] == b["role"]:
                errors.append("messages: roles must alternate")
        if "max_tokens" not in body:
            errors.append("max_tokens: required")
        if float(body.get("temperature", 0)) > 1:
            errors.append("temperature: must be <= 1")
        for tool in body.get("tools") or []:
            if (tool.get("input_schema") or {}).get("type") != "object":
                errors.append(f"tools.{tool.get('name')}.input_schema.type: must be object")
        for i, m in enumerate(msgs):
            content = m["content"]
            blocks = [{"type": "text", "text": content}] if isinstance(content, str) else content
            if not blocks:
                errors.append(f"messages.{i}: content must be non-empty")
            seen_other = False
            for blk in blocks:
                if blk["type"] == "text" and not str(blk.get("text", "")).strip():
                    errors.append(f"messages.{i}: text content blocks must be non-empty")
                if blk["type"] == "tool_result":
                    if seen_other:
                        errors.append(f"messages.{i}: tool_result blocks must come first")
                    prev = msgs[i - 1] if i else None
                    ids = {b["id"] for b in (prev or {}).get("content", [])
                           if isinstance(b, dict) and b.get("type") == "tool_use"}
                    if blk["tool_use_id"] not in ids:
                        errors.append(f"messages.{i}: tool_result has no tool_use in the previous message")
                else:
                    seen_other = True
                if blk["type"] == "tool_use":
                    if not isinstance(blk.get("input"), dict):
                        errors.append(f"messages.{i}: tool_use.input must be an object")
                    nxt = msgs[i + 1] if i + 1 < len(msgs) else None
                    answered = {b.get("tool_use_id") for b in (nxt or {}).get("content", [])
                                if isinstance(b, dict) and b.get("type") == "tool_result"}
                    if blk["id"] not in answered:
                        errors.append(f"messages.{i}: tool_use without a tool_result after it")
        return errors

    @staticmethod
    def _reply(body):
        last = body["messages"][-1]
        content = last["content"] if isinstance(last["content"], list) else [
            {"type": "text", "text": last["content"]}]
        results = [b for b in content if b["type"] == "tool_result"]
        if results:
            return [{"type": "text", "text": _answer(results[0]["content"])}], "end_turn"
        said = " ".join(b.get("text", "") for b in content if b["type"] == "text").lower()
        if body.get("tools") and "armchair" in said:
            return [{"type": "text", "text": "Let me check."},
                    {"type": "tool_use", "id": "toolu_01", "name": body["tools"][0]["name"],
                     "input": ARMCHAIR_ARGS}], "tool_use"
        return [{"type": "text", "text": "Hello from Claude."}], "end_turn"

    def handle(self, request):
        body = json.loads(request.content)
        self.requests.append(body)
        problems = self._problems(body)
        if problems:
            return httpx.Response(400, json={"type": "error", "error": {
                "type": "invalid_request_error", "message": "; ".join(problems)}})
        blocks, stop = self._reply(body)
        if not body.get("stream"):
            return httpx.Response(200, json={
                "id": "msg_1", "type": "message", "role": "assistant", "model": body["model"],
                "content": blocks, "stop_reason": stop, "stop_sequence": None,
                "usage": {"input_tokens": 10, "output_tokens": 5}})

        def ev(name, data):
            return f"event: {name}\ndata: {json.dumps(data)}\n\n"
        out = [ev("message_start", {"type": "message_start", "message": {
            "id": "msg_1", "type": "message", "role": "assistant", "model": body["model"], "content": [],
            "stop_reason": None, "stop_sequence": None, "usage": {"input_tokens": 10, "output_tokens": 1}}})]
        for i, blk in enumerate(blocks):
            if blk["type"] == "text":
                out.append(ev("content_block_start", {"type": "content_block_start", "index": i,
                                                      "content_block": {"type": "text", "text": ""}}))
                for word in blk["text"].split(" "):
                    out.append(ev("content_block_delta", {"type": "content_block_delta", "index": i,
                                                          "delta": {"type": "text_delta", "text": word + " "}}))
            else:
                out.append(ev("content_block_start", {"type": "content_block_start", "index": i, "content_block": {
                    "type": "tool_use", "id": blk["id"], "name": blk["name"], "input": {}}}))
                out.append(ev("content_block_delta", {"type": "content_block_delta", "index": i, "delta": {
                    "type": "input_json_delta", "partial_json": json.dumps(blk["input"])}}))
            out.append(ev("content_block_stop", {"type": "content_block_stop", "index": i}))
        out.append(ev("message_delta", {"type": "message_delta", "delta": {"stop_reason": stop, "stop_sequence": None},
                                        "usage": {"output_tokens": 5}}))
        out.append(ev("message_stop", {"type": "message_stop"}))
        return httpx.Response(200, headers={"content-type": "text/event-stream"}, content="".join(out).encode())


# ── Wiring ───────────────────────────────────────────────────────────────────


def _provider(name):
    """(real provider class with its real SDK client on a fake API, the fake)."""
    if name == "openai":
        fake = FakeOpenAI()
        llm = OpenAILLM(api_key="test-key", model=MODELS[name])
        llm.client = AsyncOpenAI(api_key="test-key", max_retries=0,
                                 http_client=httpx.AsyncClient(transport=httpx.MockTransport(fake.handle)))
    else:
        fake = FakeAnthropic()
        llm = AnthropicLLM(api_key="test-key", model=MODELS[name])
        llm.client = AsyncAnthropic(api_key="test-key", max_retries=0,
                                    http_client=httpx.AsyncClient(transport=httpx.MockTransport(fake.handle)))
    return llm, fake


def _llm_service(name, monkeypatch, seen=None):
    """The real LLMService, with the named provider wired to its fake API.
    Fails if a call asks for any other provider than the agent's."""
    from app.services.voice.llm_service import LLMService

    service = LLMService()
    instance, fake = _provider(name)

    def get_provider(provider=None, model=None, **_kwargs):
        if seen is not None:
            seen.append({"provider": provider, "model": model})
        assert provider == name, f"agent is on {name}, but {provider!r} was called"
        return instance

    monkeypatch.setattr(service, "get_provider", get_provider)
    return service, fake


def _agent(provider, model="default"):
    return types.SimpleNamespace(
        id=uuid.uuid4(), llm_provider=provider, llm_model=MODELS[provider] if model == "default" else model,
        llm_temperature=0.7, llm_max_tokens=300, end_call_phrases=[], interrupt_enabled=True,
        system_prompt="You are Claire at Diamant Versatile.", tts_provider="elevenlabs",
        tts_voice_id="v", tts_speed=1.0, knowledge_base_config=None,
    )


GREETING_THEN_QUESTION = [
    ChatMessage(role="system", content="You are Claire."),
    ChatMessage(role="assistant", content="Hello, this is Claire. How can I help?"),
    ChatMessage(role="user", content="How wide is the Totem armchair?"),
]


class _Executor:
    """Stands in for function_executor: one API tool that returns the width."""

    def __init__(self):
        self.ran = []

    def get_function_definition(self, f):
        raise AssertionError("no per-agent functions in these tests")

    async def build_tool_definitions(self, tools, db=None):
        return [LOOKUP_TOOL]

    async def execute_global_tool(self, tool, parameters, call_id=None, db=None, channel=None, llm=None):
        self.ran.append({"parameters": parameters, "llm": llm})
        return {"success": True, "result": json.loads(TOOL_RESULT)}

    async def execute_function(self, *_a, **_k):
        raise AssertionError("unused")

    async def get_agent_functions(self, *_a, **_k):
        return []

    async def get_agent_assigned_tools(self, *_a, **_k):
        return [types.SimpleNamespace(name="product_lookup", tool_type="api_request")]


# ── Provider level ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
@pytest.mark.parametrize("name", PROVIDERS)
async def test_plain_reply_to_a_conversation_that_opens_with_the_greeting(name):
    llm, fake = _provider(name)
    messages = GREETING_THEN_QUESTION[:2] + [ChatMessage(role="user", content="Hi there")]
    result = await llm.chat_completion(messages)
    assert result.content == f"Hello from {fake.name}."


@pytest.mark.asyncio
@pytest.mark.parametrize("name", PROVIDERS)
async def test_tool_round_trip_without_streaming(name):
    """The loop /respond and the chat widget run: call, execute, answer."""
    llm, _fake = _provider(name)
    messages = list(GREETING_THEN_QUESTION)
    first = await llm.chat_completion(messages, functions=[LOOKUP_TOOL])
    assert first.function_call.name == "product_lookup"
    assert json.loads(first.function_call.arguments) == ARMCHAIR_ARGS

    messages += [
        ChatMessage(role="assistant", content="", function_call={
            "name": first.function_call.name, "arguments": first.function_call.arguments}),
        ChatMessage(role="function", name="product_lookup", content=TOOL_RESULT),
    ]
    final = await llm.chat_completion(messages, functions=[LOOKUP_TOOL])
    assert final.function_call is None
    assert final.content == _answer(TOOL_RESULT)


@pytest.mark.asyncio
@pytest.mark.parametrize("name", PROVIDERS)
async def test_streaming_without_tools_returns_text(name):
    llm, fake = _provider(name)
    chunks = [c async for c in llm.chat_completion_stream(
        [ChatMessage(role="user", content="Hi")], temperature=0.7)]
    assert "".join(chunks).strip() == f"Hello from {fake.name}."


@pytest.mark.asyncio
@pytest.mark.parametrize("name", PROVIDERS)
async def test_streaming_reports_a_tool_call_the_same_way(name):
    """Phone calls run their tool loop on the stream; both providers must end
    it with the same {"function_call": {name, arguments}} dict."""
    llm, _fake = _provider(name)
    chunks = [c async for c in llm.chat_completion_stream(list(GREETING_THEN_QUESTION), functions=[LOOKUP_TOOL])]
    calls = [c["function_call"] for c in chunks if isinstance(c, dict)]
    assert len(calls) == 1
    assert calls[0]["name"] == "product_lookup"
    assert json.loads(calls[0]["arguments"]) == ARMCHAIR_ARGS


def test_a_tool_schema_without_a_type_is_fixed_for_every_provider():
    """User-entered schemas can be {} — both providers reject that."""
    from app.services.function_executor import FunctionExecutor

    fn = types.SimpleNamespace(name="save_lead", description="Save a lead.", parameters={})
    definition = FunctionExecutor().get_function_definition(fn)
    assert definition["parameters"] == {"type": "object", "properties": {}}


# ── Real phone calls ─────────────────────────────────────────────────────────


def _phone_session(name, monkeypatch, model="default", seen=None, tools=True):
    from app.services.websocket.voice_session import VoiceSession

    service, _fake = _llm_service(name, monkeypatch, seen)
    session = VoiceSession.__new__(VoiceSession)
    session.agent = _agent(name, model)
    session.llm_service = service
    session.function_executor = _Executor()
    session.agent_functions = []
    session.agent_tools = [types.SimpleNamespace(name="product_lookup", tool_type="api_request")] if tools else []
    if not tools:
        async def no_defs(*_a, **_k):
            return []
        session.function_executor.build_tool_definitions = no_defs
    session.call_id, session.db = "call-1", None
    session.conversation = types.SimpleNamespace(get_messages=lambda: list(GREETING_THEN_QUESTION))
    return session


@pytest.mark.asyncio
@pytest.mark.parametrize("name", PROVIDERS)
async def test_a_phone_call_uses_the_agents_tools(name, monkeypatch):
    seen = []
    session = _phone_session(name, monkeypatch, seen=seen)

    reply = await session._generate_llm_response()

    # The model answered from what the tool returned.
    assert "106 cm" in reply and '"width_cm": 106' in reply
    ran = session.function_executor.ran
    assert ran == [{"parameters": ARMCHAIR_ARGS, "llm": {"provider": name, "model": MODELS[name]}}]
    assert all(s == {"provider": name, "model": MODELS[name]} for s in seen)


@pytest.mark.asyncio
@pytest.mark.parametrize("name", PROVIDERS)
async def test_a_phone_call_with_no_model_set_uses_the_providers_default(name, monkeypatch):
    seen = []
    session = _phone_session(name, monkeypatch, model="", seen=seen, tools=False)
    session.conversation = types.SimpleNamespace(get_messages=lambda: [ChatMessage(role="user", content="Hi")])

    reply = await session._generate_llm_response()

    assert reply.strip().startswith("Hello from")
    assert seen[0]["model"] is None  # never another provider's model name


# ── Browser test calls (/respond) ────────────────────────────────────────────


async def _respond(name, monkeypatch, message, model="default"):
    import app.database
    import app.services.function_executor as fe_module
    import app.api.v1.endpoints.agents as agents_module
    from app.api.v1.endpoints.agents import RespondRequest, agent_respond

    agent = _agent(name, model)
    executor, seen = _Executor(), []
    service, _fake = _llm_service(name, monkeypatch, seen)

    class _Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def commit(self):
            pass

        async def rollback(self):
            pass

    class _TTS:
        async def synthesize(self, **_k):
            raise RuntimeError("no audio in this test")

    class _DB:
        async def execute(self, *_a, **_k):
            return types.SimpleNamespace(scalar_one_or_none=lambda: agent)

    async def _none(*_a, **_k):
        return None

    monkeypatch.setattr(app.database, "AsyncSessionLocal", lambda: _Session())
    monkeypatch.setattr(fe_module, "get_function_executor", lambda: executor)
    monkeypatch.setattr(agents_module, "get_llm_service", lambda: service)
    monkeypatch.setattr(agents_module, "get_tts_service", lambda: _TTS())
    monkeypatch.setattr(agents_module, "get_agent_kb_context", _none)
    monkeypatch.setattr(agents_module, "resolve_tts_api_key", _none)

    response = await agent_respond(
        agent.id,
        RespondRequest(message=message, history=[{"role": "agent", "text": "Hello, this is Claire."}]),
        current_user=object(), org_id=uuid.uuid4(), db=_DB(),
    )
    body = "".join([chunk async for chunk in response.body_iterator])
    events = [json.loads(l[6:]) for l in body.splitlines() if l.startswith("data: ")]
    return events, executor, seen


@pytest.mark.asyncio
@pytest.mark.parametrize("name", PROVIDERS)
async def test_a_test_call_uses_the_agents_tools(name, monkeypatch):
    events, executor, _seen = await _respond(name, monkeypatch, "How wide is the Totem armchair?")

    assert not [e for e in events if e["type"] == "error"], events
    assert [e["name"] for e in events if e["type"] == "tool_call"] == ["product_lookup"]
    assert "106 cm" in next(e for e in events if e["type"] == "done")["full_text"]
    assert executor.ran[0]["llm"] == {"provider": name, "model": MODELS[name]}


@pytest.mark.asyncio
@pytest.mark.parametrize("name", PROVIDERS)
async def test_a_test_call_with_no_model_set_never_borrows_another_providers_model(name, monkeypatch):
    # This agent has tools, but "Hi" doesn't need one — so it takes the tool
    # path; the streaming path is covered by the phone-call test above.
    events, _executor, seen = await _respond(name, monkeypatch, "Hi", model="")

    assert not [e for e in events if e["type"] == "error"], events
    for call in seen:
        assert call["model"] is None or call["model"].startswith("gpt-") == (name == "openai")


# ── Chat widget ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
@pytest.mark.parametrize("name", PROVIDERS)
async def test_the_chat_widget_uses_the_agents_tools(name, monkeypatch):
    from app.services.chat.agent_chat_service import AgentChatService

    service, _fake = _llm_service(name, monkeypatch)
    chat = AgentChatService.__new__(AgentChatService)
    chat.db, chat.llm, chat.functions = None, service, _Executor()

    async def no_kb(*_a, **_k):
        return None
    chat._knowledge_context = no_kb

    result = await chat.respond(_agent(name), [
        {"role": "assistant", "content": "Hi! Ask me about our furniture."}], "How wide is the Totem armchair?")

    assert "106 cm" in result.reply
    assert chat.functions.ran[0]["llm"] == {"provider": name, "model": MODELS[name]}


# ── Workflows run by an agent ────────────────────────────────────────────────


class _RecordingLLM:
    def __init__(self):
        self.calls = []

    async def chat(self, messages, **kwargs):
        self.calls.append(kwargs)
        return types.SimpleNamespace(content="Your order is on its way.")


class _Channel:
    def __init__(self):
        self.said = []

    async def speak(self, text):
        self.said.append(text)


@pytest.mark.asyncio
@pytest.mark.parametrize("name", PROVIDERS)
async def test_an_ai_step_uses_the_provider_of_the_agent_that_ran_the_workflow(name, monkeypatch):
    import app.services.voice.llm_service as llm_module
    from app.services.workflows.step_handlers import AIStepHandler, WorkflowContext

    llm, channel = _RecordingLLM(), _Channel()
    monkeypatch.setattr(llm_module, "get_llm_service", lambda: llm)
    context = WorkflowContext({}, channel=channel, llm={"provider": name, "model": MODELS[name]})

    await AIStepHandler().execute({"config": {"context": "Tell them the order shipped."}}, context)

    assert (llm.calls[0]["provider"], llm.calls[0]["model"]) == (name, MODELS[name])
    assert channel.said == ["Your order is on its way."]


@pytest.mark.asyncio
async def test_a_standalone_workflow_ai_step_keeps_the_platform_default(monkeypatch):
    import app.services.voice.llm_service as llm_module
    from app.services.workflows.step_handlers import AIStepHandler, WorkflowContext

    llm = _RecordingLLM()
    monkeypatch.setattr(llm_module, "get_llm_service", lambda: llm)

    await AIStepHandler().execute({"config": {"context": "Say hi."}}, WorkflowContext({}, channel=_Channel()))

    assert (llm.calls[0]["provider"], llm.calls[0]["model"]) == ("openai", "gpt-4o-mini")


# ── Anthropic-only request rules ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_claude_accepts_empty_and_orphaned_turns_that_it_would_otherwise_reject():
    """Claude rejects empty text and a tool_result without its tool_use in the
    turn before (history trimming can split a pair); the provider repairs both."""
    llm, fake = _provider("anthropic")
    result = await llm.chat_completion([
        ChatMessage(role="function", name="product_lookup", content=TOOL_RESULT),
        ChatMessage(role="assistant", content=""),
        ChatMessage(role="assistant", content="It is 106 cm wide."),
        ChatMessage(role="user", content="Thanks, anything else?"),
    ], temperature=1.8)
    assert result.content == "Hello from Claude."
    assert fake.requests[0]["temperature"] == 1.0  # clamped to Claude's 0-1
