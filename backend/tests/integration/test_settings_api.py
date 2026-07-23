"""
Integration tests for the Settings surface:
  - Profile          (/api/v1/users/me)
  - API keys         (/api/v1/api-keys)
  - Team management  (/api/v1/team)

These tests use an in-process httpx AsyncClient (ASGITransport) so the app runs
in the same event loop as the test, and override ``get_db`` to hand each request
a fresh session bound to the test engine. ``get_current_user`` is overridden to
load the acting user from that same request session, so endpoint writes persist
correctly (the shared-session sync TestClient can't do this for write paths).

Self-contained fixtures build a real User + Organization + OrganizationMember
graph — the shared conftest user fixtures predate the current model.
"""
import uuid

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.main import app
from app.database import get_db
from app.core.dependencies import get_current_user
from app.core.security import get_password_hash
from app.models.user import User, Organization, OrganizationMember


# Which user the next request acts as (set by ``as_user``).
_ACTING: dict = {"id": None}


# ---------- Fixtures ----------
async def _org_id_of(db_session, user: User) -> uuid.UUID:
    result = await db_session.execute(
        select(OrganizationMember.organization_id).where(OrganizationMember.user_id == user.id)
    )
    return result.scalar_one()


@pytest_asyncio.fixture
async def owner(db_session) -> User:
    """An org owner: user + organization (owner_id set) + owner membership —
    the same graph the register endpoint builds."""
    user = User(
        email="owner@example.com",
        hashed_password=get_password_hash("password123"),
        full_name="Owner",
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()

    org = Organization(
        name="Acme", slug=f"acme-{uuid.uuid4().hex[:8]}", owner_id=user.id, is_active=True
    )
    db_session.add(org)
    await db_session.flush()

    db_session.add(OrganizationMember(organization_id=org.id, user_id=user.id, role="owner"))
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def viewer(db_session, owner) -> User:
    """A viewer-role member of the owner's organization."""
    org_id = await _org_id_of(db_session, owner)
    user = User(
        email="viewer@example.com",
        hashed_password=get_password_hash("password123"),
        full_name="Viewer",
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    db_session.add(OrganizationMember(organization_id=org_id, user_id=user.id, role="viewer"))
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def member(db_session, owner) -> dict:
    """A plain member of the owner's org. Returns {'id': <membership_id>, ...}."""
    org_id = await _org_id_of(db_session, owner)
    user = User(
        email="member@example.com",
        hashed_password=get_password_hash("password123"),
        full_name="Member",
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    membership = OrganizationMember(organization_id=org_id, user_id=user.id, role="member")
    db_session.add(membership)
    await db_session.commit()
    await db_session.refresh(membership)
    return {"id": str(membership.id), "user_id": str(user.id)}


@pytest_asyncio.fixture
async def client(db_engine):
    """In-loop async HTTP client with per-request DB sessions from the test engine."""
    sessionmaker = async_sessionmaker(db_engine, expire_on_commit=False)

    async def override_get_db():
        async with sessionmaker() as session:
            yield session

    # Load the acting user from the *request's* session so endpoint writes persist.
    from fastapi import Depends

    async def _current_user(db=Depends(get_db)):
        result = await db.execute(select(User).where(User.id == _ACTING["id"]))
        return result.scalar_one()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = _current_user

    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


def as_user(client, user: User):
    """Make subsequent requests on ``client`` act as ``user``."""
    _ACTING["id"] = user.id
    return client


# ---------- Profile ----------
@pytest.mark.integration
@pytest.mark.asyncio
class TestProfile:
    async def test_get_me(self, client, owner):
        res = await as_user(client, owner).get("/api/v1/users/me")
        assert res.status_code == 200
        assert res.json()["email"] == owner.email

    async def test_update_profile(self, client, owner):
        res = await as_user(client, owner).patch(
            "/api/v1/users/me",
            json={"full_name": "Renamed", "bio": "hi there", "phone_number": "+123"},
        )
        assert res.status_code == 200
        body = res.json()
        assert body["full_name"] == "Renamed"
        assert body["bio"] == "hi there"
        assert body["phone_number"] == "+123"

    async def test_change_password_wrong_current(self, client, owner):
        res = await as_user(client, owner).post(
            "/api/v1/users/me/change-password",
            json={"current_password": "wrong", "new_password": "newpass123"},
        )
        assert res.status_code == 400

    async def test_change_password_success(self, client, owner):
        res = await as_user(client, owner).post(
            "/api/v1/users/me/change-password",
            json={"current_password": "password123", "new_password": "newpass123"},
        )
        assert res.status_code == 204

    async def test_change_password_too_short(self, client, owner):
        res = await as_user(client, owner).post(
            "/api/v1/users/me/change-password",
            json={"current_password": "password123", "new_password": "short"},
        )
        assert res.status_code == 422

    async def test_delete_account_deactivates(self, client, owner, db_session):
        res = await as_user(client, owner).delete("/api/v1/users/me")
        assert res.status_code == 204
        await db_session.refresh(owner)
        assert owner.is_active is False
        assert owner.deleted_at is not None


# ---------- API keys ----------
@pytest.mark.integration
@pytest.mark.asyncio
class TestApiKeys:
    async def test_create_returns_full_key_once(self, client, owner):
        res = await as_user(client, owner).post("/api/v1/api-keys", json={"name": "Prod", "scopes": []})
        assert res.status_code == 201
        body = res.json()
        assert body["key"].startswith("vcon_")
        assert body["name"] == "Prod"
        assert body["key_prefix"] == body["key"][:12]

    async def test_list_masks_secret(self, client, owner):
        await as_user(client, owner).post("/api/v1/api-keys", json={"name": "K1"})
        res = await as_user(client, owner).get("/api/v1/api-keys")
        assert res.status_code == 200
        keys = res.json()
        assert len(keys) == 1
        assert "key" not in keys[0]  # full secret never listed
        assert keys[0]["key_prefix"].startswith("vcon_")

    async def test_regenerate_changes_prefix(self, client, owner):
        created = (await as_user(client, owner).post("/api/v1/api-keys", json={"name": "K"})).json()
        res = await as_user(client, owner).post(f"/api/v1/api-keys/{created['id']}/regenerate")
        assert res.status_code == 200
        assert res.json()["key"] != created["key"]

    async def test_revoke(self, client, owner):
        created = (await as_user(client, owner).post("/api/v1/api-keys", json={"name": "K"})).json()
        res = await as_user(client, owner).delete(f"/api/v1/api-keys/{created['id']}")
        assert res.status_code == 204
        listed = (await as_user(client, owner).get("/api/v1/api-keys")).json()
        assert listed == []

    async def test_cannot_touch_other_orgs_key(self, client, owner):
        res = await as_user(client, owner).delete(f"/api/v1/api-keys/{uuid.uuid4()}")
        assert res.status_code == 404


# ---------- Team ----------
@pytest.mark.integration
@pytest.mark.asyncio
class TestTeam:
    async def test_list_members(self, client, owner):
        res = await as_user(client, owner).get("/api/v1/team/members")
        assert res.status_code == 200
        members = res.json()
        assert len(members) == 1
        assert members[0]["role"] == "owner"
        assert members[0]["status"] == "Active"

    async def test_invite_creates_pending(self, client, owner):
        # Inviting creates a *pending* invitation (not an immediate member).
        # The full invite/accept/notification flow is covered in test_invitations_api.py.
        res = await as_user(client, owner).post(
            "/api/v1/team/invite", json={"email": "new@example.com", "role": "member"}
        )
        assert res.status_code == 201
        body = res.json()
        assert body["email"] == "new@example.com"
        assert body["role"] == "member"
        assert body["status"] == "pending"
        # Not yet a member.
        members = (await as_user(client, owner).get("/api/v1/team/members")).json()
        assert "new@example.com" not in [m["email"] for m in members]

    async def test_invite_invalid_role(self, client, owner):
        res = await as_user(client, owner).post(
            "/api/v1/team/invite", json={"email": "x@example.com", "role": "owner"}
        )
        assert res.status_code == 400

    async def test_viewer_cannot_invite(self, client, viewer):
        res = await as_user(client, viewer).post(
            "/api/v1/team/invite", json={"email": "y@example.com"}
        )
        assert res.status_code == 403

    async def test_update_member_role(self, client, owner, member):
        res = await as_user(client, owner).patch(
            f"/api/v1/team/members/{member['id']}", json={"role": "admin"}
        )
        assert res.status_code == 200
        assert res.json()["role"] == "admin"

    async def test_cannot_change_owner_role(self, client, owner):
        members = (await as_user(client, owner).get("/api/v1/team/members")).json()
        owner_member = next(m for m in members if m["role"] == "owner")
        res = await as_user(client, owner).patch(
            f"/api/v1/team/members/{owner_member['id']}", json={"role": "admin"}
        )
        assert res.status_code == 400

    async def test_remove_member(self, client, owner, member):
        res = await as_user(client, owner).delete(f"/api/v1/team/members/{member['id']}")
        assert res.status_code == 204

    async def test_cannot_remove_owner(self, client, owner):
        members = (await as_user(client, owner).get("/api/v1/team/members")).json()
        owner_member = next(m for m in members if m["role"] == "owner")
        res = await as_user(client, owner).delete(f"/api/v1/team/members/{owner_member['id']}")
        assert res.status_code == 400
