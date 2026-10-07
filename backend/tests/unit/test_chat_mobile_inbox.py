"""
The chat inbox the mobile app is built on.

Pins: a team member's reply takes the conversation over and the agent goes
quiet; the visitor's widget can fetch that reply (and only their own chat);
the inbox spans every chatbot in the workspace with search and unread; live
events are published; push goes only to signed-in members who can read chats.
"""
import uuid
from types import SimpleNamespace

import pytest
import pytest_asyncio
from fastapi import BackgroundTasks, HTTPException
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool
from starlette.requests import Request

from app.api.v1.endpoints import chat, devices
from app.api.v1.endpoints.chat import ChatbotCreate, HumanReply
from app.core.config import settings
from app.database import Base
from app.models.agent import Agent
from app.models.chat import ChatMessage, ChatSession, DeviceToken
from app.models.user import Organization, OrganizationMember, User
from app.services.chat import push
from app.services.chat.events import chat_events


@pytest_asyncio.fixture
async def db(monkeypatch):
    monkeypatch.setattr(settings, "API_BASE_URL", "https://api.voicecon.ai")
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine.sync_engine, "connect")
    def _fk_on(dbapi_connection, _record):
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


class FakeAgentChat:
    """Stands in for the LLM: records turns, answers with a fixed reply."""

    def __init__(self, reply="Agent answer", before_reply=None):
        self.calls = []
        self.reply = reply
        self.before_reply = before_reply

    async def respond(self, agent, history, message):
        self.calls.append((history, message))
        if self.before_reply:
            await self.before_reply()
        return SimpleNamespace(reply=self.reply, tool_name=None)


@pytest.fixture
def fake_agent(monkeypatch):
    fake = FakeAgentChat()
    import app.services.chat.agent_chat_service as svc

    monkeypatch.setattr(svc, "get_agent_chat_service", lambda db: fake)
    return fake


def _request() -> Request:
    return Request({"type": "http", "method": "POST", "path": "/", "headers": [(b"user-agent", b"pytest")],
                    "query_string": b"", "server": ("testserver", 80), "scheme": "http"})


async def _workspace(db, name="Owner Person"):
    user = User(email=f"o-{uuid.uuid4().hex[:6]}@example.com", hashed_password="x", full_name=name, is_active=True)
    db.add(user)
    await db.flush()
    org = Organization(name="Acme", slug=f"acme-{uuid.uuid4().hex[:6]}", owner_id=user.id)
    db.add(org)
    await db.flush()
    db.add(OrganizationMember(organization_id=org.id, user_id=user.id, role="owner"))
    await db.commit()
    return user, org


async def _chatbot(db, user, org, name="Main site"):
    agent = Agent(user_id=user.id, organization_id=org.id, name="Riley", system_prompt="Help.", is_active=True)
    db.add(agent)
    await db.commit()
    return await chat.create_chatbot(
        ChatbotCreate(name=name, agent_id=agent.id), _request(), db=db, current_user=user, org_id=org.id,
    )


async def _visitor_says(db, bot, text, session_id=None, visitor_id="v_abc123"):
    tasks = BackgroundTasks()
    out = await chat.send_widget_message(
        bot["public_key"],
        {"message": text, "session_id": session_id, "visitor_id": visitor_id, "source_url": "https://acme.test/pricing"},
        _request(), tasks, db=db,
    )
    return out, tasks


def _ctx(user, org):
    return dict(current_user=user, org_id=org.id)


@pytest.mark.asyncio
async def test_ai_mode_answers_and_counts_unread(db, fake_agent):
    user, org = await _workspace(db)
    bot = await _chatbot(db, user, org)

    out, tasks = await _visitor_says(db, bot, "Do you open on Sundays?")
    assert out["mode"] == "ai" and out["reply"] == "Agent answer"
    assert out["message_id"] and out["reply_message_id"]
    # The push runs after the response, on its own DB session.
    assert [t.func.__name__ for t in tasks.tasks] == ["_push_visitor_message"]

    session = await db.get(ChatSession, uuid.UUID(out["session_id"]))
    assert session.unread_count == 1
    assert session.last_message_preview == "Agent answer"
    assert session.last_message_role == "assistant"


@pytest.mark.asyncio
async def test_human_reply_takes_over_and_the_agent_goes_quiet(db, fake_agent):
    user, org = await _workspace(db)
    bot = await _chatbot(db, user, org)
    out, _ = await _visitor_says(db, bot, "I want a human")
    sid = out["session_id"]

    replied = await chat.send_human_reply(sid, HumanReply(content="Hi, Sara here."), db=db, **_ctx(user, org))
    assert replied["message"]["role"] == "human"
    assert replied["message"]["sender"]["name"] == "Owner Person"
    assert replied["session"]["mode"] == "human"
    assert replied["session"]["unread_count"] == 0  # answering it = read

    fake_agent.calls.clear()
    out2, _ = await _visitor_says(db, bot, "Thanks Sara", session_id=sid)
    assert out2["mode"] == "human" and out2["reply"] is None
    assert fake_agent.calls == []  # the agent did not run

    # Release: the agent answers again, and sees the human turn as its own.
    released = await chat.release_session(sid, db=db, **_ctx(user, org))
    assert released["mode"] == "ai"
    out3, _ = await _visitor_says(db, bot, "One more question", session_id=sid)
    assert out3["reply"] == "Agent answer"
    history, _ = fake_agent.calls[0]
    assert {"role": "assistant", "content": "Hi, Sara here."} in history


@pytest.mark.asyncio
async def test_takeover_during_an_agent_turn_drops_the_late_answer(db, monkeypatch):
    user, org = await _workspace(db)
    bot = await _chatbot(db, user, org)
    out, _ = await _visitor_says_with(db, bot, monkeypatch, "first")
    sid = out["session_id"]

    async def take_over_mid_turn():
        s = await db.get(ChatSession, uuid.UUID(sid))
        s.mode = "human"
        await db.commit()

    out2, _ = await _visitor_says_with(db, bot, monkeypatch, "second", sid, before_reply=take_over_mid_turn)
    assert out2["reply"] is None and out2["mode"] == "human"
    roles = [m["role"] for m in (await chat.get_session_messages(sid, db=db, **_ctx(user, org)))["messages"]]
    assert roles == ["user", "assistant", "user"]


async def _visitor_says_with(db, bot, monkeypatch, text, session_id=None, before_reply=None):
    import app.services.chat.agent_chat_service as svc

    fake = FakeAgentChat(before_reply=before_reply)
    monkeypatch.setattr(svc, "get_agent_chat_service", lambda _db: fake)
    return await _visitor_says(db, bot, text, session_id=session_id)


@pytest.mark.asyncio
async def test_visitor_fetches_the_team_reply_but_not_someone_elses_chat(db, fake_agent):
    user, org = await _workspace(db, name="Sara Khan")
    bot = await _chatbot(db, user, org)
    out, _ = await _visitor_says(db, bot, "hello", visitor_id="v_me")
    sid = out["session_id"]
    first = await chat.get_visitor_messages(bot["public_key"], sid, visitor_id="v_me", after=None, db=db)
    cursor = first["messages"][-1]["created_at"]

    await chat.send_human_reply(sid, HumanReply(content="On it!"), db=db, **_ctx(user, org))

    newer = await chat.get_visitor_messages(bot["public_key"], sid, visitor_id="v_me", after=cursor, db=db)
    assert [(m["role"], m["content"], m["sender_name"]) for m in newer["messages"]] == [("human", "On it!", "Sara")]
    assert newer["mode"] == "human"

    with pytest.raises(HTTPException) as exc:
        await chat.get_visitor_messages(bot["public_key"], sid, visitor_id="v_someone_else", after=None, db=db)
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_inbox_spans_chatbots_with_search_and_unread(db, fake_agent):
    user, org = await _workspace(db)
    main = await _chatbot(db, user, org, "Main site")
    shop = await _chatbot(db, user, org, "Shop")
    a, _ = await _visitor_says(db, main, "What are your prices?", visitor_id="v_1")
    b, _ = await _visitor_says(db, shop, "Where is my order 5512?", visitor_id="v_2")

    filters = dict(page=1, page_size=20, chatbot_id=None, q=None, mode=None, unread=None,
                   date_from=None, date_to=None, sort="recent")
    inbox = await chat.list_inbox(db=db, **{**filters}, **_ctx(user, org))
    assert inbox["total"] == 2
    assert {s["chatbot_name"] for s in inbox["sessions"]} == {"Main site", "Shop"}
    assert inbox["sessions"][0]["id"] == b["session_id"]  # most recent first
    assert inbox["sessions"][0]["visitor_label"].startswith("Visitor ")

    found = await chat.list_inbox(db=db, **{**filters, "q": "order 5512"}, **_ctx(user, org))
    assert [s["id"] for s in found["sessions"]] == [b["session_id"]]

    only_main = await chat.list_inbox(db=db, **{**filters, "chatbot_id": uuid.UUID(main["id"])}, **_ctx(user, org))
    assert [s["id"] for s in only_main["sessions"]] == [a["session_id"]]

    await chat.mark_session_read(a["session_id"], db=db, **_ctx(user, org))
    unread = await chat.list_inbox(db=db, **{**filters, "unread": True}, **_ctx(user, org))
    assert [s["id"] for s in unread["sessions"]] == [b["session_id"]]
    assert await chat.inbox_unread_count(db=db, **_ctx(user, org)) == {"unread_count": 1, "unread_sessions": 1}

    bots = {b_["name"]: b_ for b_ in (await chat.list_chatbots(_request(), db=db, **_ctx(user, org)))["chatbots"]}
    assert bots["Shop"]["unread_count"] == 1 and bots["Main site"]["unread_count"] == 0

    # Another workspace sees none of it.
    other_user, other_org = await _workspace(db)
    assert (await chat.list_inbox(db=db, **filters, **_ctx(other_user, other_org)))["total"] == 0
    with pytest.raises(HTTPException):
        await chat.get_session(a["session_id"], db=db, **_ctx(other_user, other_org))


@pytest.mark.asyncio
async def test_live_events_are_published_to_the_workspace(db, fake_agent):
    user, org = await _workspace(db)
    bot = await _chatbot(db, user, org)
    queue = chat_events.subscribe(org.id)
    try:
        out, _ = await _visitor_says(db, bot, "hi")
        await chat.send_human_reply(out["session_id"], HumanReply(content="hello"), db=db, **_ctx(user, org))
        events = []
        while not queue.empty():
            events.append(queue.get_nowait())
    finally:
        chat_events.unsubscribe(org.id, queue)

    names = [e["event"] for e in events]
    assert names[:2] == ["message.created", "session.created"]
    assert "session.updated" in names
    human = [e for e in events if e["event"] == "message.created" and e["data"]["message"]["role"] == "human"]
    assert human and human[0]["data"]["session_id"] == out["session_id"]


@pytest.mark.asyncio
async def test_push_recipients_are_signed_in_members_who_can_read_chats(db):
    owner, org = await _workspace(db)
    viewer = User(email="viewer@example.com", hashed_password="x", full_name="V", is_active=True)
    outsider = User(email="out@example.com", hashed_password="x", full_name="X", is_active=True)
    db.add_all([viewer, outsider])
    await db.flush()
    db.add(OrganizationMember(organization_id=org.id, user_id=viewer.id, role="viewer"))
    await db.commit()

    reg = devices.DeviceRegister
    await devices.register_device(reg(token="owner-token-123", platform="ios"), current_user=owner, db=db)
    await devices.register_device(reg(token="viewer-token-123", platform="android"), current_user=viewer, db=db)
    await devices.register_device(reg(token="outsider-token-1", platform="android"), current_user=outsider, db=db)

    assert sorted(await push.recipient_tokens(db, org.id)) == ["owner-token-123", "viewer-token-123"]

    # Signing out everywhere bumps the session version: that phone stops
    # getting pushes and its row is cleaned up.
    viewer.token_version = (viewer.token_version or 0) + 1
    await db.commit()
    assert await push.recipient_tokens(db, org.id) == ["owner-token-123"]
    assert (await db.execute(select(DeviceToken.token).where(DeviceToken.user_id == viewer.id))).all() == []

    # The same phone signing in as someone else moves the token.
    await devices.register_device(reg(token="owner-token-123", platform="ios"), current_user=outsider, db=db)
    assert await push.recipient_tokens(db, org.id) == []

    await devices.unregister_device(devices.DeviceUnregister(token="owner-token-123"), current_user=outsider, db=db)
    assert (await db.execute(select(DeviceToken.token))).scalars().all() == ["outsider-token-1"]


def test_fcm_message_collapses_per_conversation():
    msg = push._fcm_message("tok", "Main site", "hello", {"session_id": "s1", "n": 3, "skip": None}, collapse="s1")["message"]
    assert msg["data"] == {"session_id": "s1", "n": "3"}  # strings only, None dropped
    assert msg["android"]["notification"]["tag"] == "s1"
    assert msg["android"]["notification"]["channel_id"] == push.ANDROID_CHANNEL_ID
    assert msg["apns"]["headers"]["apns-collapse-id"] == "s1"


def test_dead_token_detection():
    import httpx

    dead = httpx.Response(404, json={"error": {"details": [{"errorCode": "UNREGISTERED"}]}})
    busy = httpx.Response(429, json={"error": {"details": [{"errorCode": "QUOTA_EXCEEDED"}]}})
    assert push._is_dead_token(dead) is True
    assert push._is_dead_token(busy) is False


def test_after_cursor_accepts_api_timestamps():
    for value in ("2026-10-07T10:00:00+00:00", "2026-10-07T10:00:00Z", "2026-10-07T10:00:00 00:00"):
        assert chat._parse_after(value).isoformat() == "2026-10-07T10:00:00"
    assert chat._parse_after("2026-10-07T15:00:00+05:00").isoformat() == "2026-10-07T10:00:00"
    with pytest.raises(HTTPException):
        chat._parse_after("yesterday")


def test_google_sign_in_needs_a_code_or_an_id_token():
    from pydantic import ValidationError

    from app.schemas.auth import GoogleAuthRequest

    assert GoogleAuthRequest(id_token="abc").id_token == "abc"
    assert GoogleAuthRequest(code="xyz").code == "xyz"
    with pytest.raises(ValidationError):
        GoogleAuthRequest()


def test_mobile_audiences_extend_the_web_ones(monkeypatch):
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "web.apps.googleusercontent.com")
    monkeypatch.setattr(settings, "GOOGLE_MOBILE_CLIENT_IDS", "ios.apps.googleusercontent.com, android.apps.googleusercontent.com")
    monkeypatch.setattr(settings, "APPLE_CLIENT_ID", "com.voicecon.web")
    monkeypatch.setattr(settings, "APPLE_BUNDLE_IDS", "ai.voicecon.app")
    assert settings.google_audiences == [
        "web.apps.googleusercontent.com", "ios.apps.googleusercontent.com", "android.apps.googleusercontent.com",
    ]
    assert settings.apple_audiences == ["com.voicecon.web", "ai.voicecon.app"]


@pytest.mark.asyncio
async def test_visitor_message_pushes_to_phones_and_prunes_dead_tokens(db, fake_agent, monkeypatch):
    """The whole push path against a fake FCM: who gets it, what it says, and
    that a token FCM reports as uninstalled is deleted."""
    import httpx

    import app.database as database

    owner, org = await _workspace(db)
    bot = await _chatbot(db, owner, org, "Main site")
    reg = devices.DeviceRegister
    await devices.register_device(reg(token="live-phone-token", platform="android"), current_user=owner, db=db)
    await devices.register_device(reg(token="uninstalled-token", platform="ios"), current_user=owner, db=db)

    sent = []

    def fcm(request: httpx.Request) -> httpx.Response:
        body = __import__("json").loads(request.content)["message"]
        sent.append(body)
        if body["token"] == "uninstalled-token":
            return httpx.Response(404, json={"error": {"details": [{"errorCode": "UNREGISTERED"}]}})
        return httpx.Response(200, json={"name": "projects/p/messages/1"})

    real_client = httpx.AsyncClient
    monkeypatch.setattr(push.httpx, "AsyncClient", lambda **kw: real_client(transport=httpx.MockTransport(fcm), **kw))
    monkeypatch.setattr(settings, "FIREBASE_SERVICE_ACCOUNT_JSON", '{"project_id": "voicecon-test"}')

    async def fake_token():
        return "access-token"

    monkeypatch.setattr(push, "_access_token", fake_token)
    monkeypatch.setattr(push, "_project_id", "voicecon-test")

    # The push opens its own session (it runs after the response); point it
    # at the test database.
    class _SameSession:
        async def __aenter__(self):
            return db

        async def __aexit__(self, *exc):
            return False

    monkeypatch.setattr(database, "AsyncSessionLocal", lambda: _SameSession())

    out, tasks = await _visitor_says(db, bot, "Hi, is anyone there?")
    for task in tasks.tasks:
        await task()

    assert sorted(m["token"] for m in sent) == ["live-phone-token", "uninstalled-token"]
    msg = sent[0]
    assert msg["notification"] == {"title": "New conversation · Main site", "body": "Hi, is anyone there?"}
    assert msg["data"]["session_id"] == out["session_id"]
    assert msg["data"]["organization_id"] == str(org.id)
    assert msg["data"]["chatbot_id"] == bot["id"]
    assert msg["data"]["type"] == "chat_message"
    remaining = (await db.execute(select(DeviceToken.token))).scalars().all()
    assert remaining == ["live-phone-token"]
