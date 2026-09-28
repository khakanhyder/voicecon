"""
Chatbots as a standalone section (Dashboard → Chatbot).

A chatbot is its own object, linked to (not owned by) the agent that answers
it. These pin what must not break while moving it out of the agent screen:
embed keys never change, the older per-agent routes still answer, the public
endpoints keep working, and an unlinked chatbot hides itself instead of
erroring on a customer's site.
"""
import uuid

import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy import event
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool
from starlette.requests import Request

from app.api.v1.endpoints import chat
from app.api.v1.endpoints.chat import ChatbotCreate, ChatbotUpdate
from app.core.config import settings
from app.database import Base
from app.models.agent import Agent
from app.models.chat import ChatSession, ChatWidget
from app.models.user import Organization, OrganizationMember, User


@pytest_asyncio.fixture
async def db(monkeypatch):
    monkeypatch.setattr(settings, "API_BASE_URL", "https://api.voicecon.ai")
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    # SQLite only enforces ON DELETE rules with foreign keys switched on.
    @event.listens_for(engine.sync_engine, "connect")
    def _fk_on(dbapi_connection, _record):
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


def _request() -> Request:
    return Request({"type": "http", "method": "GET", "path": "/", "headers": [], "query_string": b"",
                    "server": ("testserver", 80), "scheme": "http"})


async def _workspace(db):
    user = User(email=f"o-{uuid.uuid4().hex[:6]}@example.com", hashed_password="x", full_name="O", is_active=True)
    db.add(user)
    await db.flush()
    org = Organization(name="Acme", slug=f"acme-{uuid.uuid4().hex[:6]}", owner_id=user.id)
    db.add(org)
    await db.flush()
    db.add(OrganizationMember(organization_id=org.id, user_id=user.id, role="owner"))
    await db.commit()
    return user, org


async def _agent(db, user, org, name="Riley"):
    agent = Agent(user_id=user.id, organization_id=org.id, name=name, system_prompt="Help.", is_active=True)
    db.add(agent)
    await db.commit()
    await db.refresh(agent)
    return agent


def _ctx(user, org):
    return dict(current_user=user, org_id=org.id)


@pytest.mark.asyncio
async def test_create_list_and_live_state(db):
    user, org = await _workspace(db)
    agent = await _agent(db, user, org)

    bot = await chat.create_chatbot(
        ChatbotCreate(name="Website help", agent_id=agent.id, config={"title": "Hi there"}),
        _request(), db=db, **_ctx(user, org),
    )
    assert bot["name"] == "Website help"
    assert bot["agent"] == {"id": str(agent.id), "name": "Riley", "is_active": True}
    assert bot["live"] is True
    assert bot["config"]["title"] == "Hi there"
    assert bot["config"]["greeting"]  # defaults fill the rest
    assert f'data-voicecon-key="{bot["public_key"]}"' in bot["embed_snippet"]
    assert bot["embed_snippet"].startswith('<script src="https://api.voicecon.ai/api/v1/chat/widget.js"')

    listed = (await chat.list_chatbots(_request(), db=db, **_ctx(user, org)))["chatbots"]
    assert [b["id"] for b in listed] == [bot["id"]]


@pytest.mark.asyncio
async def test_a_chatbot_can_exist_without_an_agent_and_stays_hidden(db):
    user, org = await _workspace(db)
    bot = await chat.create_chatbot(ChatbotCreate(name="Draft"), _request(), db=db, **_ctx(user, org))
    assert bot["agent"] is None and bot["live"] is False

    # The embed hides itself (404) rather than showing a chat nobody answers.
    with pytest.raises(HTTPException) as exc:
        await chat.get_widget_config(bot["public_key"], db=db)
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_one_agent_can_answer_several_chatbots(db):
    user, org = await _workspace(db)
    agent = await _agent(db, user, org)
    for name in ("Main site", "Help centre"):
        await chat.create_chatbot(ChatbotCreate(name=name, agent_id=agent.id), _request(), db=db, **_ctx(user, org))
    listed = (await chat.list_chatbots(_request(), db=db, **_ctx(user, org)))["chatbots"]
    assert sorted(b["name"] for b in listed) == ["Help centre", "Main site"]


@pytest.mark.asyncio
async def test_relinking_keeps_the_embed_key(db):
    user, org = await _workspace(db)
    first, second = await _agent(db, user, org, "Riley"), await _agent(db, user, org, "Nova")
    bot = await chat.create_chatbot(ChatbotCreate(name="Site", agent_id=first.id), _request(), db=db, **_ctx(user, org))

    moved = await chat.update_chatbot(
        bot["id"], ChatbotUpdate(agent_id=second.id, config={"accent_color": "#0f6a59"}),
        _request(), db=db, **_ctx(user, org),
    )
    assert moved["public_key"] == bot["public_key"]
    assert moved["agent"]["name"] == "Nova"
    assert moved["config"]["accent_color"] == "#0f6a59"
    assert moved["name"] == "Site"  # untouched fields stay

    unlinked = await chat.update_chatbot(
        bot["id"], ChatbotUpdate.model_validate({"agent_id": None}), _request(), db=db, **_ctx(user, org),
    )
    assert unlinked["agent"] is None and unlinked["live"] is False


@pytest.mark.asyncio
async def test_agents_from_another_workspace_are_refused(db):
    user, org = await _workspace(db)
    other_user, other_org = await _workspace(db)
    foreign = await _agent(db, other_user, other_org)
    with pytest.raises(HTTPException) as exc:
        await chat.create_chatbot(ChatbotCreate(name="x", agent_id=foreign.id), _request(), db=db, **_ctx(user, org))
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_other_workspaces_cannot_see_or_edit_a_chatbot(db):
    user, org = await _workspace(db)
    other_user, other_org = await _workspace(db)
    bot = await chat.create_chatbot(ChatbotCreate(name="Mine"), _request(), db=db, **_ctx(user, org))
    for call in (
        chat.get_chatbot(bot["id"], _request(), db=db, **_ctx(other_user, other_org)),
        chat.update_chatbot(bot["id"], ChatbotUpdate(name="Theirs"), _request(), db=db, **_ctx(other_user, other_org)),
        chat.delete_chatbot(bot["id"], db=db, **_ctx(other_user, other_org)),
    ):
        with pytest.raises(HTTPException) as exc:
            await call
        assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_deleting_the_agent_keeps_the_chatbot_and_its_history(db):
    user, org = await _workspace(db)
    agent = await _agent(db, user, org)
    bot = await chat.create_chatbot(ChatbotCreate(name="Site", agent_id=agent.id), _request(), db=db, **_ctx(user, org))
    db.add(ChatSession(widget_id=uuid.UUID(bot["id"]), agent_id=agent.id, organization_id=org.id))
    await db.commit()

    ctx = _ctx(user, org)
    await db.delete(agent)
    await db.commit()
    db.expire_all()  # read the chatbot back as the database now has it

    kept = await chat.get_chatbot(bot["id"], _request(), db=db, **ctx)
    assert kept["public_key"] == bot["public_key"]
    assert kept["agent"] is None
    assert kept["session_count"] == 1


@pytest.mark.asyncio
async def test_branding_keeps_only_known_plain_fields(db):
    user, org = await _workspace(db)
    bot = await chat.create_chatbot(
        ChatbotCreate(name="x", config={"title": "Hi", "position": "top-middle", "evil": "<script>", "nested": {"a": 1}}),
        _request(), db=db, **_ctx(user, org),
    )
    assert bot["config"]["title"] == "Hi"
    assert bot["config"]["position"] == "bottom-right"  # invalid value falls back to the default
    assert "evil" not in bot["config"] and "nested" not in bot["config"]


@pytest.mark.asyncio
async def test_the_older_per_agent_routes_still_work(db):
    user, org = await _workspace(db)
    agent = await _agent(db, user, org)

    assert (await chat.get_agent_widget(str(agent.id), _request(), db=db, **_ctx(user, org))) == {"exists": False}

    created = await chat.upsert_agent_widget(
        str(agent.id), {"enabled": True, "config": {"title": "Old API"}}, _request(), db=db, **_ctx(user, org),
    )
    fetched = await chat.get_agent_widget(str(agent.id), _request(), db=db, **_ctx(user, org))
    assert fetched["public_key"] == created["public_key"]
    assert fetched["config"]["title"] == "Old API"

    # And it shows up in the new section, named after the agent.
    listed = (await chat.list_chatbots(_request(), db=db, **_ctx(user, org)))["chatbots"]
    assert [(b["name"], b["public_key"]) for b in listed] == [("Riley chatbot", created["public_key"])]


@pytest.mark.asyncio
async def test_public_config_is_unchanged_for_a_linked_chatbot(db):
    user, org = await _workspace(db)
    agent = await _agent(db, user, org)
    bot = await chat.create_chatbot(ChatbotCreate(name="x", agent_id=agent.id, config={"title": "Hello"}), _request(), db=db, **_ctx(user, org))

    config = await chat.get_widget_config(bot["public_key"], db=db)
    assert config["public_key"] == bot["public_key"]
    assert config["config"]["title"] == "Hello"

    await chat.update_chatbot(bot["id"], ChatbotUpdate(enabled=False), _request(), db=db, **_ctx(user, org))
    with pytest.raises(HTTPException):
        await chat.get_widget_config(bot["public_key"], db=db)


@pytest.mark.asyncio
async def test_transcripts_are_scoped_by_workspace(db):
    user, org = await _workspace(db)
    other_user, other_org = await _workspace(db)
    bot = await chat.create_chatbot(ChatbotCreate(name="x"), _request(), db=db, **_ctx(user, org))
    session = ChatSession(widget_id=uuid.UUID(bot["id"]), agent_id=uuid.uuid4(), organization_id=org.id)
    db.add(session)
    await db.commit()

    page = await chat.list_chatbot_sessions(bot["id"], page=1, page_size=20, db=db, **_ctx(user, org))
    assert page["total"] == 1 and page["sessions"][0]["chatbot_id"] == bot["id"]

    with pytest.raises(HTTPException) as exc:
        await chat.get_session_messages(str(session.id), db=db, **_ctx(other_user, other_org))
    assert exc.value.status_code == 404
    mine = await chat.get_session_messages(str(session.id), db=db, **_ctx(user, org))
    assert mine["messages"] == []
