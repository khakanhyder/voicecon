"""
The agent reply stream must not use the request's database session.

FastAPI (0.106+) closes a yield dependency before a streamed body runs. The
reply stream kept using that closed session for tool lookups and workflow
runs, and each use quietly checked out a new connection that was never
returned: one leaked connection per agent reply. After about fifteen test-call
turns the pool was empty and every request that touched the database hung for
30 seconds and failed, across the whole backend.
"""
import types
import uuid

import pytest

from app.api.v1.endpoints import agents as agents_module
from app.api.v1.endpoints.agents import RespondRequest, agent_respond


class _Result:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class _RequestSession:
    """Stands in for the dependency session; FastAPI closes it before streaming."""

    def __init__(self, agent):
        self.agent = agent
        self.closed = False

    async def execute(self, *_args, **_kwargs):
        if self.closed:
            raise AssertionError("the stream used the request's closed session")
        return _Result(self.agent)


class _StreamSession:
    def __init__(self):
        self.entered = self.exited = self.committed = False

    async def __aenter__(self):
        self.entered = True
        return self

    async def __aexit__(self, *exc):
        self.exited = True
        return False

    async def commit(self):
        self.committed = True

    async def rollback(self):
        pass


@pytest.mark.asyncio
async def test_stream_uses_its_own_session_and_closes_it(monkeypatch):
    agent = types.SimpleNamespace(
        id=uuid.uuid4(), end_call_phrases=[], interrupt_enabled=True, llm_max_tokens=150,
        system_prompt="Be brief.", llm_model="gpt-5.4-mini", llm_provider="openai",
        llm_temperature=0.4, tts_provider="elevenlabs", tts_voice_id="v",
    )
    request_db = _RequestSession(agent)
    stream_session = _StreamSession()
    seen = {}

    class _Executor:
        async def get_agent_functions(self, _agent_id, db):
            seen["functions_db"] = db
            return []

        async def get_agent_assigned_tools(self, _agent_id, db):
            seen["tools_db"] = db
            return []

        async def build_tool_definitions(self, _tools, db=None):
            return []

    class _LLM:
        async def chat_stream(self, **_kwargs):
            yield "Hello there."

    class _TTS:
        async def synthesize(self, **_kwargs):
            raise RuntimeError("no audio in this test")

    import app.database
    import app.services.function_executor as fe_module

    monkeypatch.setattr(app.database, "AsyncSessionLocal", lambda: stream_session)
    monkeypatch.setattr(fe_module, "get_function_executor", lambda: _Executor())
    monkeypatch.setattr(agents_module, "get_llm_service", lambda: _LLM())
    monkeypatch.setattr(agents_module, "get_tts_service", lambda: _TTS())

    response = await agent_respond(
        agent.id, RespondRequest(message="Hi", history=[]),
        current_user=object(), org_id=uuid.uuid4(), db=request_db,
    )
    request_db.closed = True  # what FastAPI does before the body is sent

    body = "".join([chunk async for chunk in response.body_iterator])

    assert '"type": "done"' in body
    assert seen["functions_db"] is stream_session
    assert seen["tools_db"] is stream_session
    assert stream_session.entered and stream_session.exited and stream_session.committed
