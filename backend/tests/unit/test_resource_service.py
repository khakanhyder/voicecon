"""
The resource listing path, from a connection row to a normalised dropdown.

Runs against a real (in-memory) database with a stub connector standing in for
Trello, so the parts that actually break in production are covered: a
disconnected integration, a provider that raises, the parent-before-child
sequencing, and the cache that stops a picker hammering the provider on every
keystroke.
"""

import uuid

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models.integration import IntegrationConnection, IntegrationConnector
from app.models.user import Organization, User
from app.services.integrations import resource_service
from app.services.integrations.resource_service import (
    ResourceError,
    invalidate_connection,
    list_resources,
)

# `asyncio_mode = auto` already runs coroutine tests, so an explicit
# asyncio mark here only warns on the sync tests in this module.
pytestmark = [pytest.mark.unit]


class FakeTrelloConnector:
    """Stands in for TrelloConnector, counting how often it is called."""

    calls = 0
    boards = [{"id": "b1", "name": "Operations"}, {"id": "b2", "name": "Leasing"}]
    lists_by_board = {
        "b1": [{"id": "l1", "name": "To Do"}, {"id": "l2", "name": "Done"}],
        "b2": [{"id": "l9", "name": "Viewings"}],
    }
    raise_on_call = False

    def __init__(self, connection=None, connector=None, db=None):
        self.connection = connection

    async def get_boards(self):
        type(self).calls += 1
        if type(self).raise_on_call:
            raise RuntimeError("Trello said 429")
        return {"boards": self.boards, "count": len(self.boards)}

    async def get_lists(self, board_id):
        type(self).calls += 1
        items = self.lists_by_board.get(board_id, [])
        return {"lists": items, "count": len(items)}

    async def close(self):
        pass


@pytest_asyncio.fixture
async def db() -> AsyncSession:
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


@pytest_asyncio.fixture(autouse=True)
def stub_connector(monkeypatch):
    """Point the service's dynamic lookup at the stub instead of real Trello."""
    from app.services.integrations import connectors as connector_module

    FakeTrelloConnector.calls = 0
    FakeTrelloConnector.raise_on_call = False
    monkeypatch.setattr(
        connector_module, "TrelloConnector", FakeTrelloConnector, raising=False
    )
    resource_service._cache.clear()
    yield
    resource_service._cache.clear()


@pytest_asyncio.fixture
async def connection(db: AsyncSession):
    user = User(
        email=f"owner-{uuid.uuid4().hex[:6]}@acme.test",
        hashed_password="x",
        full_name="Owner",
        is_active=True,
    )
    db.add(user)
    await db.flush()

    org = Organization(name="Acme", slug=f"acme-{uuid.uuid4().hex[:6]}", owner_id=user.id)
    db.add(org)
    await db.flush()

    connector = IntegrationConnector(
        slug="trello",
        name="Trello",
        category="project-management",
        auth_type="api_key",
    )
    db.add(connector)
    await db.flush()

    conn = IntegrationConnection(
        user_id=user.id,
        organization_id=org.id,
        connector_id=connector.id,
        name="Trello Connection",
        status="active",
        is_active=True,
        config={},
    )
    db.add(conn)
    await db.commit()
    return conn


class TestListing:
    async def test_returns_names_for_the_dropdown(self, db, connection):
        result = await list_resources(
            db, connection.organization_id, connection.id, "boards"
        )

        assert [r["name"] for r in result["resources"]] == ["Operations", "Leasing"]
        assert result["label"] == "Board"

    async def test_nested_kind_waits_for_its_parent(self, db, connection):
        """The List picker cannot know what to show until a board is chosen.

        This is not an error — the builder disables the field and asks again.
        """
        result = await list_resources(
            db, connection.organization_id, connection.id, "lists"
        )

        assert result["resources"] == []
        assert result["needs_parent"] == "boards"
        assert FakeTrelloConnector.calls == 0

    async def test_nested_kind_reads_the_chosen_parent(self, db, connection):
        result = await list_resources(
            db, connection.organization_id, connection.id, "lists", parent="b2"
        )

        assert [r["name"] for r in result["resources"]] == ["Viewings"]

    async def test_search_filters_by_name(self, db, connection):
        result = await list_resources(
            db, connection.organization_id, connection.id, "boards", query="leas"
        )

        assert [r["name"] for r in result["resources"]] == ["Leasing"]


class TestCaching:
    async def test_second_call_does_not_hit_the_provider(self, db, connection):
        """A picker fires on open and on every keystroke; Trello rate limits."""
        await list_resources(db, connection.organization_id, connection.id, "boards")
        await list_resources(db, connection.organization_id, connection.id, "boards")

        assert FakeTrelloConnector.calls == 1

    async def test_search_is_served_from_cache(self, db, connection):
        await list_resources(db, connection.organization_id, connection.id, "boards")
        result = await list_resources(
            db, connection.organization_id, connection.id, "boards", query="ops"
        )

        assert FakeTrelloConnector.calls == 1
        assert result["cached"] is True

    async def test_refresh_bypasses_the_cache(self, db, connection):
        """For "I just created that list and it isn't showing"."""
        await list_resources(db, connection.organization_id, connection.id, "boards")
        await list_resources(
            db, connection.organization_id, connection.id, "boards", refresh=True
        )

        assert FakeTrelloConnector.calls == 2

    async def test_different_parents_cache_separately(self, db, connection):
        await list_resources(
            db, connection.organization_id, connection.id, "lists", parent="b1"
        )
        await list_resources(
            db, connection.organization_id, connection.id, "lists", parent="b2"
        )

        assert FakeTrelloConnector.calls == 2

    async def test_invalidation_drops_every_kind(self, db, connection):
        """Reconnecting must not serve lists fetched under the old token."""
        await list_resources(db, connection.organization_id, connection.id, "boards")
        invalidate_connection(connection.id)
        await list_resources(db, connection.organization_id, connection.id, "boards")

        assert FakeTrelloConnector.calls == 2


class TestFailures:
    async def test_disconnected_integration_is_distinguishable(self, db, connection):
        """An empty dropdown reads as "you have no boards", which is a lie.

        The frontend switches on this code to offer a Reconnect button.
        """
        connection.status = "disconnected"
        connection.is_active = False
        await db.commit()

        with pytest.raises(ResourceError) as exc:
            await list_resources(db, connection.organization_id, connection.id, "boards")

        assert exc.value.code == "disconnected"

    async def test_provider_failure_is_reported_not_swallowed(self, db, connection):
        FakeTrelloConnector.raise_on_call = True

        with pytest.raises(ResourceError) as exc:
            await list_resources(db, connection.organization_id, connection.id, "boards")

        assert exc.value.code == "provider_error"

    async def test_unsupported_kind_is_rejected(self, db, connection):
        with pytest.raises(ResourceError) as exc:
            await list_resources(
                db, connection.organization_id, connection.id, "spaceships"
            )

        assert exc.value.code == "unsupported_kind"

    async def test_another_organization_cannot_read_the_connection(self, db, connection):
        """Connection ids are guessable enough that this must be enforced."""
        with pytest.raises(ResourceError) as exc:
            await list_resources(db, uuid.uuid4(), connection.id, "boards")

        assert exc.value.code == "not_found"

    async def test_a_failed_provider_call_is_not_cached(self, db, connection):
        """Otherwise a transient 429 blanks the picker for a full minute."""
        FakeTrelloConnector.raise_on_call = True
        with pytest.raises(ResourceError):
            await list_resources(db, connection.organization_id, connection.id, "boards")

        FakeTrelloConnector.raise_on_call = False
        result = await list_resources(
            db, connection.organization_id, connection.id, "boards"
        )

        assert len(result["resources"]) == 2


class TestErrorMessages:
    """The provider's own words reach the user — minus anything secret."""

    def test_provider_message_is_surfaced(self):
        from app.services.integrations.resource_service import _safe_provider_message

        assert "invalid token" in _safe_provider_message(Exception("invalid token"))

    def test_credentials_in_a_url_are_redacted(self):
        """Trello authenticates by query string, so its errors carry a live
        token — and that string is on its way to a browser and a log file."""
        from app.services.integrations.resource_service import _safe_provider_message

        exc = Exception(
            "Client error '401' for url "
            "'https://api.trello.com/1/members/me/boards?key=APPKEY123&token=USERTOKEN456'"
        )
        message = _safe_provider_message(exc)

        assert "APPKEY123" not in message
        assert "USERTOKEN456" not in message
        assert "key=***" in message and "token=***" in message

    def test_long_messages_are_truncated(self):
        from app.services.integrations.resource_service import _safe_provider_message

        assert len(_safe_provider_message(Exception("x" * 900))) <= 200

    def test_an_empty_exception_still_says_something(self):
        """A blank message would render as "Trello rejected the request: "."""
        from app.services.integrations.resource_service import _safe_provider_message

        assert _safe_provider_message(TimeoutError()) == "TimeoutError"


class TestConnectionBookkeeping:
    """A successful provider call must not be undone by telemetry.

    Regression guard: connector_base recorded usage into `usage_count` and
    `last_used_at`, which exist on ApiKey but not on IntegrationConnection.
    Every integration call raised AttributeError *after* the provider had
    already answered. It hid for so long because the write is skipped while a
    connection is still transient — so connecting an app worked and every use
    afterwards failed, which looks exactly like an expired credential.
    """

    def test_the_model_has_the_field_the_base_connector_writes(self):
        from app.models.integration import IntegrationConnection

        assert hasattr(IntegrationConnection, "last_sync_at")

    def test_the_model_does_not_have_the_fields_that_caused_the_bug(self):
        """If these are ever added, revisit connector_base — but until then a
        write to them is a crash, not a no-op."""
        from app.models.integration import IntegrationConnection

        assert not hasattr(IntegrationConnection, "usage_count")
        assert not hasattr(IntegrationConnection, "last_used_at")

    def test_base_connector_no_longer_references_the_missing_columns(self):
        import inspect

        from app.services.integrations import connector_base

        source = inspect.getsource(connector_base)
        assert "self.connection.usage_count" not in source
        assert "self.connection.last_used_at" not in source


class TestUrlModeAdvertising:
    """The UI must not offer "paste a link" where no link exists.

    Trello boards have an addressable URL; Trello *lists* do not, and neither
    do Google calendars. Advertising the mode there hands the user a tab whose
    only possible outcome is "that link was not recognised".
    """

    async def test_response_says_when_a_link_can_be_pasted(self, db, connection):
        result = await list_resources(
            db, connection.organization_id, connection.id, "boards"
        )

        assert result["supports_url"] is True

    async def test_response_says_when_it_cannot(self, db, connection):
        result = await list_resources(
            db, connection.organization_id, connection.id, "lists", parent="b1"
        )

        assert result["supports_url"] is False

    async def test_the_flag_survives_a_cache_hit(self, db, connection):
        """Second render must not silently lose the tab."""
        await list_resources(db, connection.organization_id, connection.id, "boards")
        cached = await list_resources(
            db, connection.organization_id, connection.id, "boards"
        )

        assert cached["cached"] is True
        assert cached["supports_url"] is True

    async def test_the_flag_is_present_before_a_parent_is_chosen(self, db, connection):
        result = await list_resources(
            db, connection.organization_id, connection.id, "lists"
        )

        assert result["needs_parent"] == "boards"
        assert result["supports_url"] is False
