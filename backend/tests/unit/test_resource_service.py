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

pytestmark = [pytest.mark.unit, pytest.mark.asyncio]


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
