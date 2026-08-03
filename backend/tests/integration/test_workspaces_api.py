"""
End-to-end tests for multi-workspace access and role-based permissions.

Covers the full journey the feature exists for: an owner invites someone, the
invitee accepts, lands *inside* the shared workspace, sees the team's agents
rather than their own, can switch back to their personal workspace, and is held
to exactly the permissions their role grants.

The escalation tests are the important half — an admin must be able to run the
team without being able to seize it. Each one asserts a specific attack is
refused: demoting the owner, removing the owner, promoting yourself, minting a
peer admin, reading another workspace by id, and so on.

Uses the same in-loop httpx AsyncClient pattern as test_invitations_api.py (see
its docstring for why the sync TestClient can't drive these write paths).
"""
import uuid
from datetime import datetime, timedelta

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.security import get_password_hash
from app.database import get_db
from app.core.dependencies import get_current_user
from app.main import app
from app.models.agent import Agent
from app.models.invitation import Invitation
from app.models.user import Organization, OrganizationMember, User

_ACTING: dict = {"id": None}


# ---------- Fixtures ----------
async def _make_user(db, email: str, name: str) -> User:
    user = User(
        email=email,
        hashed_password=get_password_hash("password123"),
        full_name=name,
        is_active=True,
    )
    db.add(user)
    await db.flush()
    return user


async def _make_org(db, owner: User, name: str) -> Organization:
    org = Organization(
        name=name, slug=f"{name.lower()}-{uuid.uuid4().hex[:8]}", owner_id=owner.id, is_active=True
    )
    db.add(org)
    await db.flush()
    db.add(OrganizationMember(organization_id=org.id, user_id=owner.id, role="owner"))
    return org


async def _join(db, org: Organization, user: User, role: str) -> OrganizationMember:
    membership = OrganizationMember(organization_id=org.id, user_id=user.id, role=role)
    db.add(membership)
    await db.flush()
    return membership


@pytest_asyncio.fixture
async def team(db_session):
    """Acme (owner + admin + member + viewer) and a separate outsider workspace.

    ``invitee`` owns their own personal workspace *and* belongs to Acme — the
    exact two-workspace shape the bug report describes.
    """
    owner = await _make_user(db_session, "owner@example.com", "Olive Owner")
    admin = await _make_user(db_session, "admin@example.com", "Adam Admin")
    member = await _make_user(db_session, "member@example.com", "Mia Member")
    viewer = await _make_user(db_session, "viewer@example.com", "Vic Viewer")
    outsider = await _make_user(db_session, "outsider@example.com", "Otto Outsider")

    acme = await _make_org(db_session, owner, "Acme")
    await _join(db_session, acme, admin, "admin")
    await _join(db_session, acme, member, "member")
    await _join(db_session, acme, viewer, "viewer")

    # The member also owns a personal workspace they created on sign-up.
    personal = await _make_org(db_session, member, "MiaPersonal")
    other = await _make_org(db_session, outsider, "Rival")

    # An agent in each workspace, so cross-workspace leakage is visible.
    db_session.add(
        Agent(user_id=owner.id, organization_id=acme.id, name="Acme Agent", system_prompt="hi")
    )
    db_session.add(
        Agent(user_id=member.id, organization_id=personal.id, name="Personal Agent", system_prompt="hi")
    )
    db_session.add(
        Agent(user_id=outsider.id, organization_id=other.id, name="Rival Agent", system_prompt="hi")
    )

    await db_session.commit()
    for u in (owner, admin, member, viewer, outsider):
        await db_session.refresh(u)

    return {
        "owner": owner,
        "admin": admin,
        "member": member,
        "viewer": viewer,
        "outsider": outsider,
        "acme": acme,
        "personal": personal,
        "other": other,
    }


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


def as_user(client, user: User, org: Organization | None = None):
    """Act as ``user``, optionally pinning the request to a specific workspace."""
    _ACTING["id"] = user.id
    client.headers.pop("X-Organization-Id", None)
    if org is not None:
        client.headers["X-Organization-Id"] = str(org.id)
    return client


# ---------- Workspace resolution ----------
@pytest.mark.integration
@pytest.mark.asyncio
class TestWorkspaceResolution:
    async def test_lists_every_workspace_the_user_belongs_to(self, client, team):
        res = await as_user(client, team["member"]).get("/api/v1/workspaces")
        assert res.status_code == 200
        names = {w["name"] for w in res.json()}
        assert names == {"Acme", "MiaPersonal"}

    async def test_default_workspace_is_the_one_they_own(self, client, team):
        """Deterministic, not "whichever row came back first"."""
        res = await as_user(client, team["member"]).get("/api/v1/workspaces/current")
        assert res.json()["name"] == "MiaPersonal"
        assert res.json()["role"] == "owner"

    async def test_switch_changes_the_workspace_for_later_requests(self, client, team):
        member = team["member"]
        res = await as_user(client, member).post(
            f"/api/v1/workspaces/{team['acme'].id}/switch"
        )
        assert res.status_code == 200
        assert res.json()["workspace"]["name"] == "Acme"
        assert res.json()["workspace"]["role"] == "member"

        # Sticky: a later request with no header stays in Acme.
        current = await as_user(client, member).get("/api/v1/workspaces/current")
        assert current.json()["name"] == "Acme"

    async def test_header_overrides_the_active_workspace(self, client, team):
        member = team["member"]
        await as_user(client, member).post(f"/api/v1/workspaces/{team['acme'].id}/switch")
        res = await as_user(client, member, team["personal"]).get("/api/v1/workspaces/current")
        assert res.json()["name"] == "MiaPersonal"

    async def test_header_for_a_foreign_workspace_is_refused(self, client, team):
        """Never silently falls back — a wrong id is a 403, not someone else's data."""
        res = await as_user(client, team["member"], team["other"]).get("/api/v1/agents")
        assert res.status_code == 403

    async def test_malformed_header_is_rejected(self, client, team):
        client.headers["X-Organization-Id"] = "not-a-uuid"
        _ACTING["id"] = team["member"].id
        res = await client.get("/api/v1/workspaces/current")
        client.headers.pop("X-Organization-Id")
        assert res.status_code == 400

    async def test_switching_to_a_foreign_workspace_is_refused(self, client, team):
        res = await as_user(client, team["member"]).post(
            f"/api/v1/workspaces/{team['other'].id}/switch"
        )
        assert res.status_code == 403

    async def test_stale_active_workspace_heals(self, client, db_session, team):
        """Removed from a workspace? The next request re-derives, it doesn't 404."""
        member = team["member"]
        await as_user(client, member).post(f"/api/v1/workspaces/{team['acme'].id}/switch")

        membership = (
            await db_session.execute(
                select(OrganizationMember).where(
                    OrganizationMember.user_id == member.id,
                    OrganizationMember.organization_id == team["acme"].id,
                )
            )
        ).scalar_one()
        await db_session.delete(membership)
        await db_session.commit()

        res = await as_user(client, member).get("/api/v1/workspaces/current")
        assert res.status_code == 200
        assert res.json()["name"] == "MiaPersonal"


# ---------- Data is workspace-scoped, not user-scoped ----------
@pytest.mark.integration
@pytest.mark.asyncio
class TestWorkspaceDataScoping:
    async def test_invited_member_sees_the_teams_agents(self, client, team):
        """The core bug: an invited user must work on the team's data, not their own."""
        res = await as_user(client, team["member"], team["acme"]).get("/api/v1/agents")
        assert res.status_code == 200
        assert [a["name"] for a in res.json()["agents"]] == ["Acme Agent"]

    async def test_switching_back_shows_their_own_agents(self, client, team):
        res = await as_user(client, team["member"], team["personal"]).get("/api/v1/agents")
        assert [a["name"] for a in res.json()["agents"]] == ["Personal Agent"]

    async def test_agent_created_by_a_member_belongs_to_the_workspace(self, client, team):
        created = await as_user(client, team["member"], team["acme"]).post(
            "/api/v1/agents", json={"name": "Shared", "system_prompt": "hello"}
        )
        assert created.status_code == 201, created.text

        # The owner, who did not create it, can see and edit it.
        listed = await as_user(client, team["owner"]).get("/api/v1/agents")
        assert "Shared" in [a["name"] for a in listed.json()["agents"]]

        edited = await as_user(client, team["owner"]).patch(
            f"/api/v1/agents/{created.json()['id']}", json={"name": "Renamed"}
        )
        assert edited.status_code == 200

    async def test_another_workspace_cannot_read_the_agent(self, client, team):
        agent_id = (
            await as_user(client, team["owner"]).get("/api/v1/agents")
        ).json()["agents"][0]["id"]
        res = await as_user(client, team["outsider"]).get(f"/api/v1/agents/{agent_id}")
        assert res.status_code == 404

    async def test_another_workspace_cannot_clone_the_agent(self, client, team):
        agent_id = (
            await as_user(client, team["owner"]).get("/api/v1/agents")
        ).json()["agents"][0]["id"]
        res = await as_user(client, team["outsider"]).post(
            f"/api/v1/agents/{agent_id}/clone", json={"name": "Stolen"}
        )
        assert res.status_code == 404


# ---------- Role permissions ----------
@pytest.mark.integration
@pytest.mark.asyncio
class TestRolePermissions:
    async def test_viewer_can_read(self, client, team):
        res = await as_user(client, team["viewer"]).get("/api/v1/agents")
        assert res.status_code == 200

    async def test_viewer_cannot_create(self, client, team):
        res = await as_user(client, team["viewer"]).post(
            "/api/v1/agents", json={"name": "Nope", "system_prompt": "x"}
        )
        assert res.status_code == 403

    async def test_viewer_cannot_delete(self, client, team):
        agent_id = (
            await as_user(client, team["owner"]).get("/api/v1/agents")
        ).json()["agents"][0]["id"]
        res = await as_user(client, team["viewer"]).delete(f"/api/v1/agents/{agent_id}")
        assert res.status_code == 403

    async def test_member_can_write_agents(self, client, team):
        res = await as_user(client, team["member"], team["acme"]).post(
            "/api/v1/agents", json={"name": "Member Agent", "system_prompt": "x"}
        )
        assert res.status_code == 201

    async def test_member_cannot_manage_the_team(self, client, team):
        res = await as_user(client, team["member"], team["acme"]).post(
            "/api/v1/team/invite", json={"email": "x@example.com", "role": "member"}
        )
        assert res.status_code == 403

    async def test_member_cannot_mint_api_keys(self, client, team):
        res = await as_user(client, team["member"], team["acme"]).post(
            "/api/v1/api-keys", json={"name": "key"}
        )
        assert res.status_code == 403

    async def test_admin_can_mint_api_keys(self, client, team):
        res = await as_user(client, team["admin"]).post(
            "/api/v1/api-keys", json={"name": "key"}
        )
        assert res.status_code in (200, 201), res.text

    async def test_every_member_can_read_the_member_list(self, client, team):
        for role in ("viewer", "member", "admin", "owner"):
            res = await as_user(client, team[role], team["acme"]).get("/api/v1/team/members")
            assert res.status_code == 200, role

    async def test_current_workspace_reports_the_permission_set(self, client, team):
        res = await as_user(client, team["viewer"]).get("/api/v1/workspaces/current")
        body = res.json()
        assert body["role"] == "viewer"
        assert "agents:read" in body["permissions"]
        assert "agents:write" not in body["permissions"]
        assert "team:manage" not in body["permissions"]


# ---------- Owner-only powers ----------
@pytest.mark.integration
@pytest.mark.asyncio
class TestOwnerProtections:
    async def test_admin_cannot_demote_the_owner(self, client, team, db_session):
        owner_membership = (
            await db_session.execute(
                select(OrganizationMember).where(
                    OrganizationMember.user_id == team["owner"].id,
                    OrganizationMember.organization_id == team["acme"].id,
                )
            )
        ).scalar_one()
        res = await as_user(client, team["admin"]).patch(
            f"/api/v1/team/members/{owner_membership.id}", json={"role": "member"}
        )
        assert res.status_code == 403

    async def test_admin_cannot_remove_the_owner(self, client, team, db_session):
        owner_membership = (
            await db_session.execute(
                select(OrganizationMember).where(
                    OrganizationMember.user_id == team["owner"].id,
                    OrganizationMember.organization_id == team["acme"].id,
                )
            )
        ).scalar_one()
        res = await as_user(client, team["admin"]).delete(
            f"/api/v1/team/members/{owner_membership.id}"
        )
        assert res.status_code in (400, 403)

    async def test_owner_cannot_be_removed_even_by_the_owner(self, client, team, db_session):
        owner_membership = (
            await db_session.execute(
                select(OrganizationMember).where(
                    OrganizationMember.user_id == team["owner"].id,
                    OrganizationMember.organization_id == team["acme"].id,
                )
            )
        ).scalar_one()
        res = await as_user(client, team["owner"]).delete(
            f"/api/v1/team/members/{owner_membership.id}"
        )
        assert res.status_code == 400

    async def test_admin_cannot_promote_anyone_to_owner(self, client, team, db_session):
        member_membership = (
            await db_session.execute(
                select(OrganizationMember).where(
                    OrganizationMember.user_id == team["member"].id,
                    OrganizationMember.organization_id == team["acme"].id,
                )
            )
        ).scalar_one()
        res = await as_user(client, team["admin"]).patch(
            f"/api/v1/team/members/{member_membership.id}", json={"role": "owner"}
        )
        assert res.status_code == 400

    async def test_admin_cannot_promote_a_member_to_admin(self, client, team, db_session):
        """Minting a peer would let an admin manufacture allies."""
        member_membership = (
            await db_session.execute(
                select(OrganizationMember).where(
                    OrganizationMember.user_id == team["member"].id,
                    OrganizationMember.organization_id == team["acme"].id,
                )
            )
        ).scalar_one()
        res = await as_user(client, team["admin"]).patch(
            f"/api/v1/team/members/{member_membership.id}", json={"role": "admin"}
        )
        assert res.status_code == 403

    async def test_admin_cannot_invite_another_admin(self, client, team):
        res = await as_user(client, team["admin"]).post(
            "/api/v1/team/invite", json={"email": "new-admin@example.com", "role": "admin"}
        )
        assert res.status_code == 403

    async def test_owner_can_invite_an_admin(self, client, team):
        res = await as_user(client, team["owner"]).post(
            "/api/v1/team/invite", json={"email": "new-admin@example.com", "role": "admin"}
        )
        assert res.status_code == 201

    async def test_admin_can_manage_a_member(self, client, team, db_session):
        member_membership = (
            await db_session.execute(
                select(OrganizationMember).where(
                    OrganizationMember.user_id == team["member"].id,
                    OrganizationMember.organization_id == team["acme"].id,
                )
            )
        ).scalar_one()
        res = await as_user(client, team["admin"]).patch(
            f"/api/v1/team/members/{member_membership.id}", json={"role": "viewer"}
        )
        assert res.status_code == 200
        assert res.json()["role"] == "viewer"

    async def test_admin_cannot_act_on_a_fellow_admin(self, client, db_session, team):
        second_admin = await _make_user(db_session, "admin2@example.com", "Second Admin")
        membership = await _join(db_session, team["acme"], second_admin, "admin")
        await db_session.commit()

        res = await as_user(client, team["admin"]).delete(
            f"/api/v1/team/members/{membership.id}"
        )
        assert res.status_code == 403

    async def test_admin_cannot_transfer_ownership(self, client, team):
        res = await as_user(client, team["admin"]).post(
            "/api/v1/workspaces/current/transfer-ownership",
            json={"user_id": str(team["admin"].id)},
        )
        assert res.status_code == 403

    async def test_admin_cannot_delete_the_workspace(self, client, team):
        res = await as_user(client, team["admin"]).delete("/api/v1/workspaces/current")
        assert res.status_code == 403

    async def test_owner_transfers_ownership_and_becomes_admin(self, client, db_session, team):
        res = await as_user(client, team["owner"]).post(
            "/api/v1/workspaces/current/transfer-ownership",
            json={"user_id": str(team["admin"].id)},
        )
        assert res.status_code == 200, res.text
        assert res.json()["role"] == "admin"
        assert res.json()["is_owner"] is False

        # Exactly one owner, and organizations.owner_id agrees with it.
        org = await db_session.get(Organization, team["acme"].id)
        await db_session.refresh(org)
        assert org.owner_id == team["admin"].id
        owners = (
            await db_session.execute(
                select(OrganizationMember).where(
                    OrganizationMember.organization_id == team["acme"].id,
                    OrganizationMember.role == "owner",
                )
            )
        ).scalars().all()
        assert [m.user_id for m in owners] == [team["admin"].id]

    async def test_owner_cannot_leave_without_transferring(self, client, team):
        res = await as_user(client, team["owner"]).post("/api/v1/workspaces/current/leave")
        assert res.status_code == 400

    async def test_member_can_leave_and_loses_access(self, client, team):
        member = team["member"]
        res = await as_user(client, member, team["acme"]).post(
            "/api/v1/workspaces/current/leave"
        )
        assert res.status_code == 204

        after = await as_user(client, member).get("/api/v1/workspaces")
        assert [w["name"] for w in after.json()] == ["MiaPersonal"]

        denied = await as_user(client, member, team["acme"]).get("/api/v1/agents")
        assert denied.status_code == 403

    async def test_cannot_delete_your_only_workspace(self, client, team):
        res = await as_user(client, team["outsider"]).delete("/api/v1/workspaces/current")
        assert res.status_code == 400

    async def test_nobody_can_change_their_own_role(self, client, team, db_session):
        admin_membership = (
            await db_session.execute(
                select(OrganizationMember).where(
                    OrganizationMember.user_id == team["admin"].id,
                    OrganizationMember.organization_id == team["acme"].id,
                )
            )
        ).scalar_one()
        res = await as_user(client, team["admin"]).patch(
            f"/api/v1/team/members/{admin_membership.id}", json={"role": "member"}
        )
        assert res.status_code == 400

    async def test_member_ids_from_another_workspace_are_invisible(self, client, team, db_session):
        """A member id is not a capability — it must not work across workspaces."""
        foreign = (
            await db_session.execute(
                select(OrganizationMember).where(
                    OrganizationMember.organization_id == team["other"].id
                )
            )
        ).scalar_one()
        res = await as_user(client, team["owner"]).delete(f"/api/v1/team/members/{foreign.id}")
        assert res.status_code == 404


# ---------- Invitation → membership → working inside the workspace ----------
@pytest.mark.integration
@pytest.mark.asyncio
class TestInvitationJourney:
    async def test_accepting_lands_the_user_in_the_new_workspace(
        self, client, db_session, team
    ):
        newcomer = await _make_user(db_session, "newcomer@example.com", "Nina Newcomer")
        await _make_org(db_session, newcomer, "NinaPersonal")
        await db_session.commit()

        invited = await as_user(client, team["owner"]).post(
            "/api/v1/team/invite", json={"email": newcomer.email, "role": "member"}
        )
        assert invited.status_code == 201

        token = (
            await db_session.execute(
                select(Invitation.token).where(Invitation.email == newcomer.email)
            )
        ).scalar_one()

        accepted = await as_user(client, newcomer).post(f"/api/v1/invitations/{token}/accept")
        assert accepted.status_code == 200
        assert accepted.json()["organization_id"] == str(team["acme"].id)

        # The whole point: their next request is inside Acme, not their own workspace.
        current = await as_user(client, newcomer).get("/api/v1/workspaces/current")
        assert current.json()["name"] == "Acme"
        assert current.json()["role"] == "member"

        agents = await as_user(client, newcomer).get("/api/v1/agents")
        assert "Acme Agent" in [a["name"] for a in agents.json()["agents"]]

    async def test_accepting_an_invite_addressed_to_someone_else_is_refused(
        self, client, db_session, team
    ):
        await as_user(client, team["owner"]).post(
            "/api/v1/team/invite", json={"email": "someone@example.com", "role": "member"}
        )
        token = (
            await db_session.execute(
                select(Invitation.token).where(Invitation.email == "someone@example.com")
            )
        ).scalar_one()

        res = await as_user(client, team["outsider"]).post(
            f"/api/v1/invitations/{token}/accept"
        )
        assert res.status_code == 403

    async def test_expired_invitation_cannot_be_accepted(self, client, db_session, team):
        newcomer = await _make_user(db_session, "late@example.com", "Late")
        await _make_org(db_session, newcomer, "LatePersonal")
        await db_session.commit()

        await as_user(client, team["owner"]).post(
            "/api/v1/team/invite", json={"email": newcomer.email, "role": "member"}
        )
        invitation = (
            await db_session.execute(
                select(Invitation).where(Invitation.email == newcomer.email)
            )
        ).scalar_one()
        invitation.expires_at = datetime.utcnow() - timedelta(days=1)
        await db_session.commit()

        res = await as_user(client, newcomer).post(
            f"/api/v1/invitations/{invitation.token}/accept"
        )
        assert res.status_code == 400

    async def test_a_second_accept_is_harmless(self, client, db_session, team):
        newcomer = await _make_user(db_session, "twice@example.com", "Twice")
        await _make_org(db_session, newcomer, "TwicePersonal")
        await db_session.commit()

        await as_user(client, team["owner"]).post(
            "/api/v1/team/invite", json={"email": newcomer.email, "role": "member"}
        )
        token = (
            await db_session.execute(
                select(Invitation.token).where(Invitation.email == newcomer.email)
            )
        ).scalar_one()

        assert (
            await as_user(client, newcomer).post(f"/api/v1/invitations/{token}/accept")
        ).status_code == 200
        # The invite is spent; replaying it must not create a duplicate membership.
        assert (
            await as_user(client, newcomer).post(f"/api/v1/invitations/{token}/accept")
        ).status_code == 400

        memberships = (
            await db_session.execute(
                select(OrganizationMember).where(
                    OrganizationMember.user_id == newcomer.id,
                    OrganizationMember.organization_id == team["acme"].id,
                )
            )
        ).scalars().all()
        assert len(memberships) == 1

    async def test_creating_a_workspace_switches_into_it(self, client, team):
        res = await as_user(client, team["outsider"]).post(
            "/api/v1/workspaces", json={"name": "Side Project"}
        )
        assert res.status_code == 201
        assert res.json()["role"] == "owner"

        current = await as_user(client, team["outsider"]).get("/api/v1/workspaces/current")
        assert current.json()["name"] == "Side Project"
