"""
Integration tests for authenticating *with* an API key.

The point of this file is that it does **not** override ``get_current_user``.
Every request here runs the real credential path — header parsing, prefix
lookup, bcrypt verification, expiry, scope narrowing, workspace pinning — and
hits a real business endpoint (``/agents``, ``/workspaces/current``) rather
than the key-management endpoints. A key that "exists" but authenticates
nothing would pass a management-only test suite; it cannot pass this one.

See ``test_settings_api.py`` for the CRUD side of Settings → API Keys.
"""
import uuid
from datetime import datetime, timedelta

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.main import app
from app.database import get_db
from app.core import permissions as perms
from app.core.security import create_access_token, generate_api_key, get_password_hash
from app.models.user import ApiKey, Organization, OrganizationMember, User

AGENTS = "/api/v1/agents"
CURRENT_WORKSPACE = "/api/v1/workspaces/current"
API_KEYS = "/api/v1/api-keys"


# ---------- Fixtures ----------
async def _make_org(db, user: User, name: str, role: str = "owner") -> Organization:
    org = Organization(
        name=name, slug=f"{name.lower()}-{uuid.uuid4().hex[:8]}", owner_id=user.id, is_active=True
    )
    db.add(org)
    await db.flush()
    db.add(OrganizationMember(organization_id=org.id, user_id=user.id, role=role))
    return org


@pytest_asyncio.fixture
async def owner(db_session) -> User:
    user = User(
        email=f"key-owner-{uuid.uuid4().hex[:8]}@example.com",
        hashed_password=get_password_hash("password123"),
        full_name="Key Owner",
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    await _make_org(db_session, user, "Primary")
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def client(db_engine):
    """Async client with real auth: only ``get_db`` is overridden."""
    sessionmaker = async_sessionmaker(db_engine, expire_on_commit=False)

    async def override_get_db():
        async with sessionmaker() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def org_id(db_session, owner) -> uuid.UUID:
    return (
        await db_session.execute(
            select(OrganizationMember.organization_id).where(
                OrganizationMember.user_id == owner.id
            )
        )
    ).scalars().first()


@pytest_asyncio.fixture
async def make_key(db_session, owner, org_id):
    """Mint a real key straight into the DB; returns the plaintext secret."""

    async def _make(*, scopes=None, expires_at=None, is_active=True, user=None, organization_id=None):
        plain, key_hash = generate_api_key()
        api_key = ApiKey(
            user_id=(user or owner).id,
            organization_id=organization_id or org_id,
            name="test key",
            key_hash=key_hash,
            key_prefix=plain[:12],
            scopes=scopes or [],
            expires_at=expires_at,
            is_active=is_active,
        )
        db_session.add(api_key)
        await db_session.commit()
        await db_session.refresh(api_key)
        return plain, api_key

    return _make


def bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def jwt_for(user: User) -> dict:
    return bearer(create_access_token(subject=str(user.id)))


# ---------- The core promise: a key authenticates a real endpoint ----------
@pytest.mark.integration
@pytest.mark.asyncio
class TestApiKeyAuthenticates:
    async def test_key_can_call_a_business_endpoint(self, client, make_key):
        plain, _ = await make_key()
        res = await client.get(AGENTS, headers=bearer(plain))
        assert res.status_code == 200, res.text

    async def test_key_works_via_x_api_key_header(self, client, make_key):
        plain, _ = await make_key()
        res = await client.get(AGENTS, headers={"X-API-Key": plain})
        assert res.status_code == 200, res.text

    async def test_jwt_still_works(self, client, owner):
        res = await client.get(AGENTS, headers=jwt_for(owner))
        assert res.status_code == 200, res.text

    async def test_no_credential_is_401(self, client):
        res = await client.get(AGENTS)
        assert res.status_code == 401

    async def test_garbage_key_is_401(self, client, make_key):
        await make_key()  # a real key exists, so this isn't an empty-table pass
        res = await client.get(AGENTS, headers=bearer("vcon_totally-made-up-key-value-here"))
        assert res.status_code == 401

    async def test_right_prefix_wrong_secret_is_401(self, client, make_key):
        """The prefix is a lookup hint, not a credential."""
        plain, _ = await make_key()
        forged = plain[:12] + "X" * (len(plain) - 12)
        res = await client.get(AGENTS, headers=bearer(forged))
        assert res.status_code == 401

    async def test_last_used_at_is_recorded(self, client, db_session, make_key):
        plain, api_key = await make_key()
        assert api_key.last_used_at is None

        res = await client.get(AGENTS, headers=bearer(plain))
        assert res.status_code == 200

        refreshed = (
            await db_session.execute(select(ApiKey).where(ApiKey.id == api_key.id))
        ).scalar_one()
        await db_session.refresh(refreshed)
        assert refreshed.last_used_at is not None


# ---------- Lifecycle: revoked, disabled, expired, orphaned ----------
@pytest.mark.integration
@pytest.mark.asyncio
class TestApiKeyLifecycle:
    async def test_disabled_key_is_rejected(self, client, make_key):
        plain, _ = await make_key(is_active=False)
        res = await client.get(AGENTS, headers=bearer(plain))
        assert res.status_code == 401

    async def test_expired_key_is_rejected(self, client, make_key):
        plain, _ = await make_key(expires_at=datetime.utcnow() - timedelta(seconds=1))
        res = await client.get(AGENTS, headers=bearer(plain))
        assert res.status_code == 401

    async def test_future_expiry_still_works(self, client, make_key):
        plain, _ = await make_key(expires_at=datetime.utcnow() + timedelta(days=30))
        res = await client.get(AGENTS, headers=bearer(plain))
        assert res.status_code == 200

    async def test_deleted_key_stops_working(self, client, db_session, make_key):
        plain, api_key = await make_key()
        assert (await client.get(AGENTS, headers=bearer(plain))).status_code == 200

        await db_session.delete(api_key)
        await db_session.commit()

        assert (await client.get(AGENTS, headers=bearer(plain))).status_code == 401

    async def test_deactivated_owner_kills_the_key(self, client, db_session, owner, make_key):
        plain, _ = await make_key()
        owner.is_active = False
        await db_session.commit()

        res = await client.get(AGENTS, headers=bearer(plain))
        assert res.status_code == 401

    async def test_key_dies_when_owner_loses_membership(
        self, client, db_session, owner, org_id, make_key
    ):
        plain, _ = await make_key()
        membership = (
            await db_session.execute(
                select(OrganizationMember).where(
                    OrganizationMember.user_id == owner.id,
                    OrganizationMember.organization_id == org_id,
                )
            )
        ).scalar_one()
        await db_session.delete(membership)
        await db_session.commit()

        res = await client.get(AGENTS, headers=bearer(plain))
        assert res.status_code == 403


# ---------- Workspace binding ----------
@pytest.mark.integration
@pytest.mark.asyncio
class TestApiKeyWorkspaceBinding:
    async def test_key_acts_in_its_own_workspace(self, client, make_key, org_id):
        plain, _ = await make_key()
        res = await client.get(CURRENT_WORKSPACE, headers=bearer(plain))
        assert res.status_code == 200
        assert res.json()["id"] == str(org_id)

    async def test_matching_org_header_is_accepted(self, client, make_key, org_id):
        plain, _ = await make_key()
        res = await client.get(
            CURRENT_WORKSPACE,
            headers={**bearer(plain), "X-Organization-Id": str(org_id)},
        )
        assert res.status_code == 200

    async def test_key_cannot_be_pointed_at_another_workspace(
        self, client, db_session, owner, make_key
    ):
        """The header trick that works for a login token must not work for a key."""
        second = await _make_org(db_session, owner, "Second")
        await db_session.commit()
        plain, _ = await make_key()

        res = await client.get(
            CURRENT_WORKSPACE,
            headers={**bearer(plain), "X-Organization-Id": str(second.id)},
        )
        assert res.status_code == 403

        # Same user, same second workspace, but a login token — allowed.
        res = await client.get(
            CURRENT_WORKSPACE,
            headers={**jwt_for(owner), "X-Organization-Id": str(second.id)},
        )
        assert res.status_code == 200

    async def test_key_does_not_move_the_users_active_workspace(
        self, client, db_session, owner, make_key, org_id
    ):
        """A background integration must not yank the workspace out from under the browser."""
        second = await _make_org(db_session, owner, "Third")
        await db_session.commit()
        await client.post(f"/api/v1/workspaces/{second.id}/switch", headers=jwt_for(owner))

        plain, _ = await make_key()  # bound to the *first* workspace
        assert (await client.get(AGENTS, headers=bearer(plain))).status_code == 200

        await db_session.refresh(owner)
        assert owner.active_organization_id == second.id


# ---------- Scopes and the escalation ceiling ----------
@pytest.mark.integration
@pytest.mark.asyncio
class TestApiKeyScopes:
    async def test_unscoped_key_inherits_the_role(self, client, make_key):
        plain, _ = await make_key(scopes=[])
        res = await client.get(CURRENT_WORKSPACE, headers=bearer(plain))
        assert res.status_code == 200
        granted = set(res.json()["permissions"])
        assert perms.AGENTS_READ in granted
        # ...but never the escalation set, even for an owner's key.
        assert not (granted & perms.API_KEY_FORBIDDEN)

    async def test_scoped_key_is_limited_to_its_scopes(self, client, make_key):
        plain, _ = await make_key(scopes=[perms.AGENTS_READ])
        res = await client.get(CURRENT_WORKSPACE, headers=bearer(plain))
        assert res.status_code == 200
        assert set(res.json()["permissions"]) == {perms.AGENTS_READ}

    async def test_scoped_key_is_refused_outside_its_scopes(self, client, make_key):
        """calls:read is not in scope, so the calls endpoint must refuse it."""
        plain, _ = await make_key(scopes=[perms.AGENTS_READ])
        assert (await client.get(AGENTS, headers=bearer(plain))).status_code == 200

        res = await client.get("/api/v1/calls", headers=bearer(plain))
        assert res.status_code == 403
        assert "scopes" in res.json()["detail"].lower()

    async def test_key_cannot_mint_another_key(self, client, make_key):
        """The escalation ceiling: a leaked key must not be able to replace itself."""
        plain, _ = await make_key()
        res = await client.post(API_KEYS, headers=bearer(plain), json={"name": "child"})
        assert res.status_code == 403
        assert "api key" in res.json()["detail"].lower()

    async def test_key_cannot_manage_the_team(self, client, make_key):
        plain, _ = await make_key()
        res = await client.post(
            "/api/v1/team/invite",
            headers=bearer(plain),
            json={"email": "someone@example.com", "role": "admin"},
        )
        assert res.status_code == 403

    async def test_key_inherits_a_narrower_role(self, client, db_session, org_id, make_key):
        """A viewer's key can read but not write, however wide its scopes claim to be."""
        viewer = User(
            email=f"key-viewer-{uuid.uuid4().hex[:8]}@example.com",
            hashed_password=get_password_hash("password123"),
            full_name="Viewer",
            is_active=True,
        )
        db_session.add(viewer)
        await db_session.flush()
        db_session.add(
            OrganizationMember(organization_id=org_id, user_id=viewer.id, role="viewer")
        )
        await db_session.commit()

        plain, _ = await make_key(user=viewer, scopes=[perms.AGENTS_READ, perms.AGENTS_WRITE])
        assert (await client.get(AGENTS, headers=bearer(plain))).status_code == 200

        res = await client.post(AGENTS, headers=bearer(plain), json={"name": "nope"})
        assert res.status_code == 403


# ---------- Management endpoints gained by this change ----------
@pytest.mark.integration
@pytest.mark.asyncio
class TestApiKeyManagement:
    async def test_scopes_endpoint_lists_assignable_only(self, client, owner):
        res = await client.get(f"{API_KEYS}/scopes", headers=jwt_for(owner))
        assert res.status_code == 200
        published = set(res.json())
        assert perms.AGENTS_READ in published
        assert not (published & perms.API_KEY_FORBIDDEN)

    async def test_create_rejects_unknown_scope(self, client, owner):
        res = await client.post(
            API_KEYS, headers=jwt_for(owner), json={"name": "k", "scopes": ["agents:teleport"]}
        )
        assert res.status_code == 422

    async def test_create_rejects_forbidden_scope(self, client, owner):
        res = await client.post(
            API_KEYS,
            headers=jwt_for(owner),
            json={"name": "k", "scopes": [perms.API_KEYS_MANAGE]},
        )
        assert res.status_code == 422

    async def test_create_rejects_past_expiry(self, client, owner):
        res = await client.post(
            API_KEYS,
            headers=jwt_for(owner),
            json={"name": "k", "expires_at": "2020-01-01T00:00:00"},
        )
        assert res.status_code == 422

    async def test_create_rejects_empty_name(self, client, owner):
        res = await client.post(API_KEYS, headers=jwt_for(owner), json={"name": ""})
        assert res.status_code == 422

    async def test_patch_disables_and_reenables(self, client, owner, make_key):
        plain, api_key = await make_key()
        assert (await client.get(AGENTS, headers=bearer(plain))).status_code == 200

        res = await client.patch(
            f"{API_KEYS}/{api_key.id}", headers=jwt_for(owner), json={"is_active": False}
        )
        assert res.status_code == 200
        assert res.json()["is_active"] is False
        assert (await client.get(AGENTS, headers=bearer(plain))).status_code == 401

        res = await client.patch(
            f"{API_KEYS}/{api_key.id}", headers=jwt_for(owner), json={"is_active": True}
        )
        assert res.status_code == 200
        assert (await client.get(AGENTS, headers=bearer(plain))).status_code == 200

    async def test_patch_renames(self, client, owner, make_key):
        _, api_key = await make_key()
        res = await client.patch(
            f"{API_KEYS}/{api_key.id}", headers=jwt_for(owner), json={"name": "Renamed"}
        )
        assert res.status_code == 200
        assert res.json()["name"] == "Renamed"

    async def test_patch_narrows_scopes_immediately(self, client, owner, make_key):
        plain, api_key = await make_key()
        assert (await client.get("/api/v1/calls", headers=bearer(plain))).status_code == 200

        res = await client.patch(
            f"{API_KEYS}/{api_key.id}",
            headers=jwt_for(owner),
            json={"scopes": [perms.AGENTS_READ]},
        )
        assert res.status_code == 200
        assert (await client.get("/api/v1/calls", headers=bearer(plain))).status_code == 403

    async def test_patch_rejects_forbidden_scope(self, client, owner, make_key):
        _, api_key = await make_key()
        res = await client.patch(
            f"{API_KEYS}/{api_key.id}",
            headers=jwt_for(owner),
            json={"scopes": [perms.BILLING_MANAGE]},
        )
        assert res.status_code == 422

    async def test_patch_on_another_orgs_key_is_404(self, client, db_session, owner, make_key):
        other = User(
            email=f"other-{uuid.uuid4().hex[:8]}@example.com",
            hashed_password=get_password_hash("password123"),
            full_name="Other",
            is_active=True,
        )
        db_session.add(other)
        await db_session.flush()
        other_org = await _make_org(db_session, other, "Foreign")
        await db_session.commit()

        _, foreign_key = await make_key(user=other, organization_id=other_org.id)
        res = await client.patch(
            f"{API_KEYS}/{foreign_key.id}", headers=jwt_for(owner), json={"name": "hijacked"}
        )
        assert res.status_code == 404

    async def test_regenerate_invalidates_the_old_secret(self, client, owner, make_key):
        old, api_key = await make_key()
        assert (await client.get(AGENTS, headers=bearer(old))).status_code == 200

        res = await client.post(f"{API_KEYS}/{api_key.id}/regenerate", headers=jwt_for(owner))
        assert res.status_code == 200
        new = res.json()["key"]

        assert (await client.get(AGENTS, headers=bearer(old))).status_code == 401
        assert (await client.get(AGENTS, headers=bearer(new))).status_code == 200
