"""
What an agent remembers across the turns of a test call, and what it may book.

In a real test call the booking agent forgot the day it had offered (only the
spoken words of earlier turns came back, never what its tools returned), and
called its booking workflow with patient_name "Unknown" and phone "Unknown".
"""
import json
import types
import uuid

import pytest

from app.api.v1.endpoints import agents as agents_module
from app.api.v1.endpoints.agents import RespondRequest, agent_respond
from app.services.function_executor import FunctionExecutor, _is_placeholder


# ---------------------------------------------------------------- placeholders

@pytest.mark.parametrize("value", [None, "", "  ", "Unknown", "unknown.", "N/A", "none", "TBD", "-", "Caller"])
def test_placeholders_count_as_missing(value):
    assert _is_placeholder(value)


@pytest.mark.parametrize("value", ["Sajid Ali", "0300 1234567", "2026-09-21", "13:00", 0])
def test_real_values_are_kept(value):
    assert not _is_placeholder(value)


@pytest.mark.asyncio
async def test_workflow_tool_refuses_a_placeholder_for_a_required_input():
    graph = {
        "schema_version": 2,
        "nodes": [{
            "id": "trigger", "type": "trigger", "name": "Start", "position": {"x": 0, "y": 0},
            "config": {"inputs": [
                {"name": "patient_name", "type": "string", "required": True},
                {"name": "phone", "type": "string", "required": True},
            ]},
        }],
        "edges": [],
    }

    class _DB:
        async def get(self, _model, _id):
            return types.SimpleNamespace(workflow_steps=graph)

    result = await FunctionExecutor()._execute_workflow_tool(
        {"workflow_id": str(uuid.uuid4())},
        {"patient_name": "Unknown", "phone": "Unknown"},
        db=_DB(),
    )
    assert result["error"] == "missing_parameters"
    assert result["missing"] == ["patient_name", "phone"]


# ---------------------------------------------------------------- the reply stream

def _agent():
    return types.SimpleNamespace(
        id=uuid.uuid4(), end_call_phrases=[], interrupt_enabled=True, llm_max_tokens=150,
        system_prompt="Be brief.", llm_model="gpt-5.4-mini", llm_provider="openai",
        llm_temperature=0.4, tts_provider="elevenlabs", tts_voice_id="v",
    )


class _Result:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class _RequestDB:
    def __init__(self, agent):
        self.agent = agent

    async def execute(self, *_a, **_k):
        return _Result(self.agent)


class _StreamSession:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def commit(self):
        pass

    async def rollback(self):
        pass


def _patch_common(monkeypatch, executor, llm):
    import app.database
    import app.services.function_executor as fe_module

    class _TTS:
        async def synthesize(self, **_kwargs):
            raise RuntimeError("no audio in this test")

    monkeypatch.setattr(app.database, "AsyncSessionLocal", lambda: _StreamSession())
    monkeypatch.setattr(fe_module, "get_function_executor", lambda: executor)
    monkeypatch.setattr(agents_module, "get_llm_service", lambda: llm)
    monkeypatch.setattr(agents_module, "get_tts_service", lambda: _TTS())


async def _run(history, message="Hi"):
    agent = _agent()
    response = await agent_respond(
        agent.id, RespondRequest(message=message, history=history),
        current_user=object(), org_id=uuid.uuid4(), db=_RequestDB(agent),
    )
    return "".join([chunk async for chunk in response.body_iterator])


class _NoTools:
    async def get_agent_functions(self, *_a, **_k):
        return []

    async def get_agent_assigned_tools(self, *_a, **_k):
        return []

    async def build_tool_definitions(self, *_a, **_k):
        return []


@pytest.mark.asyncio
async def test_earlier_tool_results_reach_the_model(monkeypatch):
    seen = {}

    class _LLM:
        async def chat_stream(self, messages, **_kwargs):
            seen["messages"] = messages
            yield "Monday at one is free."

    _patch_common(monkeypatch, _NoTools(), _LLM())
    await _run([
        {"role": "user", "text": "Anything on Monday?"},
        {"role": "tool", "text": 'the check_available_times tool returned: {"free_times": ["13:00"]}'},  # older clients
        {"role": "agent", "text": "One o'clock is free."},
    ])

    roles = [(m.role, m.content) for m in seen["messages"]]
    assert ("user", "Anything on Monday?") in roles
    assert ("assistant", "One o'clock is free.") in roles
    assert any(r == "system" and "Earlier in this call" in c and "13:00" in c for r, c in roles)


@pytest.mark.asyncio
async def test_the_test_panels_system_notes_are_kept_as_is(monkeypatch):
    seen = {}

    class _LLM:
        async def chat_stream(self, messages, **_kwargs):
            seen["messages"] = messages
            yield "Okay."

    _patch_common(monkeypatch, _NoTools(), _LLM())
    note = 'Earlier in this call, the book_appointment tool returned: {"booking_status": "Booked"}'
    await _run([{"role": "system", "text": note}])
    assert any(m.role == "system" and m.content == note for m in seen["messages"])


@pytest.mark.asyncio
async def test_tool_results_are_streamed_so_the_client_can_keep_them(monkeypatch):
    tool = types.SimpleNamespace(name="Check Available Times")

    class _Executor(_NoTools):
        async def get_agent_assigned_tools(self, *_a, **_k):
            return [tool]

        async def build_tool_definitions(self, *_a, **_k):
            return [{"name": "check_available_times", "parameters": {"type": "object", "properties": {}}}]

        async def execute_global_tool(self, **_kwargs):
            return {"success": True, "result": {"output": {"free_times": ["13:00", "14:00"]}}}

    calls = {"n": 0}

    class _LLM:
        async def chat(self, **_kwargs):
            calls["n"] += 1
            if calls["n"] == 1:
                return types.SimpleNamespace(
                    content="", function_call=types.SimpleNamespace(name="check_available_times", arguments="{}"),
                )
            return types.SimpleNamespace(content="One or two o'clock is free.", function_call=None)

    _patch_common(monkeypatch, _Executor(), _LLM())
    body = await _run([], "Anything free?")

    events = [json.loads(line[6:]) for line in body.splitlines() if line.startswith("data: ")]
    results = [e for e in events if e["type"] == "tool_result"]
    assert results and results[0]["name"] == "check_available_times"
    assert "13:00" in results[0]["result"]
