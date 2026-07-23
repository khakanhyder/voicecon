"""
Integration tests for the team-invitation + notification flow.

Covers: creating invites (team endpoint), listing/canceling pending invites,
the public token endpoints (details/accept/reject), email→membership on accept,
and the in-app notifications an existing invitee receives.

Uses the same in-loop httpx AsyncClient pattern as test_settings_api.py (see its
docstring for why the sync TestClient can't drive these write paths).
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
from app.models.invitation import Invitation
from app.models.notification import Notification

_ACTING: dict = {"id": None}


# ---------- Fixtures ----------
async def _org_id_of(db_session, user: User) -> uuid.UUID:
    result = await db_session.execute(
        select(OrganizationMember.organization_id).where(OrganizationMember.user_id == user.id)
    )
    return result.scalar_one()


async def _make_user(db_session, email: str) -> User:
    user = User(
        email=email,
        hashed_password=get_password_hash("password123"),
        full_name=email.split("@")[0].title(),
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def owner(db_session) -> User:
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
async def invitee(db_session) -> User:
    """An existing account NOT in the org — target for invites."""
    return await _make_user(db_session, "invitee@example.com")


@pytest_asyncio.fixture
async def client(db_engine):
    sessionmaker = async_sessionmaker(db_engine, expire_on_commit=False)

    async def override_get_db():
        async with sessionmaker() as session:
            yield session

    from fastapi import Depends

    async def _current_user(db=Depends(get_db)):
        result = await db.execute(select(User).where(User.id == _ACTING["id"]))
        return result.scalar_one()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = _current_user

    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


def as_user(client, user: User):
    _ACTING["id"] = user.id
    return client


async def _token_for(db_session, email: str) -> str:
    result = await db_session.execute(
        select(Invitation.token).where(Invitation.email == email.lower())
    )
    return result.scalar_one()


# ---------- Invite (team endpoint) ----------
@pytest.mark.integration
@pytest.mark.asyncio
class TestInviteCreation:
    async def test_invite_creates_pending(self, client, owner):
        res = await as_user(client, owner).post(
            "/api/v1/team/invite", json={"email": "new@example.com", "role": "member"}
        )
        assert res.status_code == 201
        body = res.json()
        assert body["email"] == "new@example.com"
        assert body["status"] == "pending"
        assert body["role"] == "member"
        # token is a secret — never returned by the org-side response
        assert "token" not in body

    async def test_pending_invite_listed_not_in_members(self, client, owner):
        await as_user(client, owner).post("/api/v1/team/invite", json={"email": "p@example.com"})
        invites = (await as_user(client, owner).get("/api/v1/team/invitations")).json()
        assert [i["email"] for i in invites] == ["p@example.com"]
        members = (await as_user(client, owner).get("/api/v1/team/members")).json()
        assert "p@example.com" not in [m["email"] for m in members]

    async def test_invite_existing_member_conflict(self, client, owner, viewer):
        res = await as_user(client, owner).post(
            "/api/v1/team/invite", json={"email": viewer.email}
        )
        assert res.status_code == 409

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

    async def test_cancel_invitation(self, client, owner):
        created = (await as_user(client, owner).post(
            "/api/v1/team/invite", json={"email": "c@example.com"}
        )).json()
        res = await as_user(client, owner).delete(f"/api/v1/team/invitations/{created['id']}")
        assert res.status_code == 204
        invites = (await as_user(client, owner).get("/api/v1/team/invitations")).json()
        assert invites == []


# ---------- Public token endpoints ----------
@pytest.mark.integration
@pytest.mark.asyncio
class TestInvitationTokenFlow:
    async def test_public_details(self, client, owner, invitee, db_session):
        await as_user(client, owner).post("/api/v1/team/invite", json={"email": invitee.email})
        token = await _token_for(db_session, invitee.email)

        res = await client.get(f"/api/v1/invitations/{token}")  # no auth needed
        assert res.status_code == 200
        body = res.json()
        assert body["organization_name"] == "Acme"
        assert body["status"] == "pending"
        assert body["account_exists"] is True
        assert body["role"] == "member"

    async def test_accept_creates_membership(self, client, owner, invitee, db_session):
        await as_user(client, owner).post("/api/v1/team/invite", json={"email": invitee.email})
        token = await _token_for(db_session, invitee.email)

        res = await as_user(client, invitee).post(f"/api/v1/invitations/{token}/accept")
        assert res.status_code == 200
        assert res.json()["status"] == "accepted"

        # Membership now exists.
        members = (await as_user(client, owner).get("/api/v1/team/members")).json()
        assert invitee.email in [m["email"] for m in members]

    async def test_accept_wrong_user_forbidden(self, client, owner, invitee, viewer, db_session):
        await as_user(client, owner).post("/api/v1/team/invite", json={"email": invitee.email})
        token = await _token_for(db_session, invitee.email)
        # viewer's email != invitee's email → 403
        res = await as_user(client, viewer).post(f"/api/v1/invitations/{token}/accept")
        assert res.status_code == 403

    async def test_reject_is_public(self, client, owner, db_session):
        await as_user(client, owner).post("/api/v1/team/invite", json={"email": "decline@example.com"})
        token = await _token_for(db_session, "decline@example.com")
        res = await client.post(f"/api/v1/invitations/{token}/reject")
        assert res.status_code == 200
        assert res.json()["status"] == "rejected"
        # No longer pending for the org.
        invites = (await as_user(client, owner).get("/api/v1/team/invitations")).json()
        assert invites == []

    async def test_new_email_no_account(self, client, owner, db_session):
        await as_user(client, owner).post("/api/v1/team/invite", json={"email": "ghost@example.com"})
        token = await _token_for(db_session, "ghost@example.com")
        body = (await client.get(f"/api/v1/invitations/{token}")).json()
        assert body["account_exists"] is False


# ---------- Notifications ----------
@pytest.mark.integration
@pytest.mark.asyncio
class TestNotifications:
    async def test_existing_invitee_gets_notification(self, client, owner, invitee):
        await as_user(client, owner).post("/api/v1/team/invite", json={"email": invitee.email})

        notifs = (await as_user(client, invitee).get("/api/v1/notifications")).json()
        assert len(notifs) == 1
        assert notifs[0]["type"] == "team_invitation"
        assert notifs[0]["data"]["organization_name"] == "Acme"
        assert notifs[0]["data"]["invitation_token"]

        count = (await as_user(client, invitee).get("/api/v1/notifications/unread-count")).json()
        assert count["count"] == 1

    async def test_new_email_no_notification(self, client, owner, invitee):
        # Inviting a non-existent account creates no notification for anyone.
        await as_user(client, owner).post("/api/v1/team/invite", json={"email": "nobody@example.com"})
        notifs = (await as_user(client, invitee).get("/api/v1/notifications")).json()
        assert notifs == []

    async def test_accept_from_notification_marks_actioned(self, client, owner, invitee):
        await as_user(client, owner).post("/api/v1/team/invite", json={"email": invitee.email})
        notifs = (await as_user(client, invitee).get("/api/v1/notifications")).json()
        token = notifs[0]["data"]["invitation_token"]

        await as_user(client, invitee).post(f"/api/v1/invitations/{token}/accept")

        after = (await as_user(client, invitee).get("/api/v1/notifications")).json()
        assert after[0]["is_actioned"] is True
        assert after[0]["is_read"] is True

    async def test_mark_read_and_read_all(self, client, owner, invitee):
        await as_user(client, owner).post("/api/v1/team/invite", json={"email": invitee.email})
        notifs = (await as_user(client, invitee).get("/api/v1/notifications")).json()
        nid = notifs[0]["id"]

        res = await as_user(client, invitee).post(f"/api/v1/notifications/{nid}/read")
        assert res.status_code == 200
        assert res.json()["is_read"] is True

        res = await as_user(client, invitee).post("/api/v1/notifications/read-all")
        assert res.status_code == 204
        count = (await as_user(client, invitee).get("/api/v1/notifications/unread-count")).json()
        assert count["count"] == 0
