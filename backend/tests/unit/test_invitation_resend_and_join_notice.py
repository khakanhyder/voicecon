"""
Resending a pending invitation, and telling the owner when an invitee joins.

- Resend re-emails the *same* invitation (same row, same token), extends its
  expiry, is rate-limited, and never saves anything when the email fails.
- Accepting emails and notifies the owner (and a different inviter) only when
  the acceptance actually added the member.
- Email templates escape user-controlled names, so nobody can put a link into
  an email sent from our domain.
"""
import uuid
from datetime import datetime, timedelta

import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.api.v1.endpoints import team as team_endpoints
from app.core.workspace import WorkspaceContext
from app.database import Base
from app.models.invitation import Invitation
from app.models.notification import NOTIFY_TEAM_MEMBER_JOINED, Notification
from app.models.user import Organization, OrganizationMember, User
from app.services.email import email_service
from app.services.email.templates import render_invitation_email, render_member_joined_email
from app.services.team import invitation_service
from app.services.team.invitation_service import InvitationError


@pytest_asyncio.fixture
async def db():
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


@pytest.fixture
def outbox(monkeypatch):
    """Capture every email instead of sending it; flip `fail` to simulate an outage."""
    sent = []
    state = {"fail": False}

    async def fake_send(message, *, raise_on_error=False):
        if state["fail"]:
            return False
        sent.append(message)
        return True

    monkeypatch.setattr(email_service, "send", fake_send)
    return types_ns(sent=sent, state=state)


class types_ns:
    def __init__(self, **kw):
        self.__dict__.update(kw)


async def _user(db, email, name):
    user = User(email=email, hashed_password="x", full_name=name, is_active=True)
    db.add(user)
    await db.flush()
    return user


async def _workspace(db):
    owner = await _user(db, f"owner-{uuid.uuid4().hex[:6]}@example.com", "Iqbal Haider")
    org = Organization(name="IQb", slug=f"iqb-{uuid.uuid4().hex[:6]}", owner_id=owner.id)
    db.add(org)
    await db.flush()
    owner_membership = OrganizationMember(organization_id=org.id, user_id=owner.id, role="owner")
    db.add(owner_membership)
    await db.commit()
    return owner, org, owner_membership


async def _pending(db, org, inviter, email="invitee@example.com", role="member", sent_minutes_ago=10):
    sent_at = datetime.utcnow() - timedelta(minutes=sent_minutes_ago)
    invitation = Invitation(
        organization_id=org.id,
        email=email,
        role=role,
        token=uuid.uuid4().hex,
        status="pending",
        invited_by=inviter.id,
        expires_at=sent_at + timedelta(days=7),
        created_at=sent_at,
        updated_at=sent_at,
    )
    db.add(invitation)
    await db.commit()
    return invitation


# ------------------------------------------------------------------ resend

@pytest.mark.asyncio
async def test_resend_emails_the_same_invitation_and_extends_it(db, outbox):
    owner, org, _ = await _workspace(db)
    invitation = await _pending(db, org, owner)
    token, old_expiry = invitation.token, invitation.expires_at

    resent = await invitation_service.resend_invitation(db, invitation=invitation, organization=org)

    assert resent.id == invitation.id and resent.token == token  # the old link keeps working
    assert resent.expires_at > old_expiry
    assert resent.email_sent is True
    assert [m.to for m in outbox.sent] == ["invitee@example.com"]
    assert token in outbox.sent[0].html
    count = (await db.execute(select(func.count()).select_from(Invitation))).scalar_one()
    assert count == 1  # no duplicate invitation


@pytest.mark.asyncio
async def test_resend_revives_an_expired_invitation(db, outbox):
    owner, org, _ = await _workspace(db)
    invitation = await _pending(db, org, owner, sent_minutes_ago=60 * 24 * 8)
    assert invitation.expires_at < datetime.utcnow()

    resent = await invitation_service.resend_invitation(db, invitation=invitation, organization=org)
    assert invitation_service.is_actionable(resent)


@pytest.mark.asyncio
async def test_resend_is_rate_limited(db, outbox):
    owner, org, _ = await _workspace(db)
    invitation = await _pending(db, org, owner, sent_minutes_ago=0)

    with pytest.raises(InvitationError) as exc:
        await invitation_service.resend_invitation(db, invitation=invitation, organization=org)
    assert exc.value.code == "too_soon"
    assert "seconds" in str(exc.value)
    assert outbox.sent == []


@pytest.mark.asyncio
async def test_a_failed_email_saves_nothing(db, outbox):
    owner, org, _ = await _workspace(db)
    invitation = await _pending(db, org, owner)
    invitation_id, old_expiry = invitation.id, invitation.expires_at
    outbox.state["fail"] = True

    with pytest.raises(InvitationError) as exc:
        await invitation_service.resend_invitation(db, invitation=invitation, organization=org)
    assert exc.value.code == "email_failed"

    reloaded = await db.get(Invitation, invitation_id)
    await db.refresh(reloaded)
    assert reloaded.expires_at == old_expiry


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["accepted", "rejected", "canceled"])
async def test_only_pending_invitations_can_be_resent(db, outbox, status):
    owner, org, _ = await _workspace(db)
    invitation = await _pending(db, org, owner)
    invitation.status = status
    await db.commit()

    with pytest.raises(InvitationError) as exc:
        await invitation_service.resend_invitation(db, invitation=invitation, organization=org)
    assert exc.value.code == "not_pending"


def _context(user, org, membership):
    return WorkspaceContext(user=user, organization=org, membership=membership)


@pytest.mark.asyncio
async def test_endpoint_maps_errors_to_clear_statuses(db, outbox):
    owner, org, owner_membership = await _workspace(db)
    ctx = _context(owner, org, owner_membership)

    fresh = await _pending(db, org, owner, email="fresh@example.com", sent_minutes_ago=0)
    with pytest.raises(HTTPException) as exc:
        await team_endpoints.resend_invitation(fresh.id, workspace=ctx, db=db)
    assert exc.value.status_code == 429

    older = await _pending(db, org, owner, email="older@example.com")
    outbox.state["fail"] = True
    with pytest.raises(HTTPException) as exc:
        await team_endpoints.resend_invitation(older.id, workspace=ctx, db=db)
    assert exc.value.status_code == 502

    outbox.state["fail"] = False
    older = await db.get(Invitation, older.id)
    response = await team_endpoints.resend_invitation(older.id, workspace=ctx, db=db)
    assert response.email_sent is True and response.last_sent_at is not None

    with pytest.raises(HTTPException) as exc:
        await team_endpoints.resend_invitation(uuid.uuid4(), workspace=ctx, db=db)
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_an_admin_cannot_resend_an_admin_invitation(db, outbox):
    owner, org, _ = await _workspace(db)
    admin = await _user(db, "admin@example.com", "Admin")
    admin_membership = OrganizationMember(organization_id=org.id, user_id=admin.id, role="admin")
    db.add(admin_membership)
    await db.commit()
    invitation = await _pending(db, org, owner, email="new-admin@example.com", role="admin")

    with pytest.raises(HTTPException) as exc:
        await team_endpoints.resend_invitation(
            invitation.id, workspace=_context(admin, org, admin_membership), db=db
        )
    assert exc.value.status_code == 403
    assert outbox.sent == []


# ------------------------------------------------------------------ join notice

@pytest.mark.asyncio
async def test_accepting_tells_the_owner(db, outbox):
    owner, org, _ = await _workspace(db)
    invitation = await _pending(db, org, owner)
    invitee = await _user(db, "invitee@example.com", "Sara Khan")
    await db.commit()

    membership = await invitation_service.accept_invitation(db, invitation, invitee)

    assert membership.user_id == invitee.id
    assert [m.to for m in outbox.sent] == [owner.email]
    email = outbox.sent[0]
    assert email.subject == "Sara Khan joined IQb on Voicecon"
    assert "Sara Khan (invitee@example.com) has accepted your invitation and joined IQb" in email.text
    notices = (
        await db.execute(select(Notification).where(Notification.type == NOTIFY_TEAM_MEMBER_JOINED))
    ).scalars().all()
    assert [n.user_id for n in notices] == [owner.id]


@pytest.mark.asyncio
async def test_an_admin_who_invited_is_told_too(db, outbox):
    owner, org, _ = await _workspace(db)
    admin = await _user(db, "admin@example.com", "Admin")
    db.add(OrganizationMember(organization_id=org.id, user_id=admin.id, role="admin"))
    await db.commit()
    invitation = await _pending(db, org, admin)
    invitee = await _user(db, "invitee@example.com", None)
    await db.commit()

    await invitation_service.accept_invitation(db, invitation, invitee)

    assert sorted(m.to for m in outbox.sent) == sorted([owner.email, admin.email])
    assert all("invitee@example.com has accepted" in m.text for m in outbox.sent)


@pytest.mark.asyncio
async def test_no_notice_when_nobody_was_added(db, outbox):
    owner, org, _ = await _workspace(db)
    invitation = await _pending(db, org, owner)
    already = await _user(db, "invitee@example.com", "Already Here")
    db.add(OrganizationMember(organization_id=org.id, user_id=already.id, role="member"))
    await db.commit()

    await invitation_service.accept_invitation(db, invitation, already)
    assert outbox.sent == []


@pytest.mark.asyncio
async def test_no_notice_when_the_invitation_is_not_accepted(db, outbox):
    owner, org, _ = await _workspace(db)
    invitation = await _pending(db, org, owner, sent_minutes_ago=60 * 24 * 8)  # expired
    invitee = await _user(db, "invitee@example.com", "Late")
    await db.commit()

    with pytest.raises(InvitationError):
        await invitation_service.accept_invitation(db, invitation, invitee)
    assert outbox.sent == []


@pytest.mark.asyncio
async def test_a_mail_outage_does_not_undo_the_join(db, outbox):
    owner, org, _ = await _workspace(db)
    invitation = await _pending(db, org, owner)
    invitee = await _user(db, "invitee@example.com", "Sara")
    await db.commit()
    outbox.state["fail"] = True

    membership = await invitation_service.accept_invitation(db, invitation, invitee)
    assert membership.role == "member"
    assert invitation.status == "accepted"


# ------------------------------------------------------------------ escaping

def test_templates_escape_user_controlled_names():
    evil = '<a href="https://evil.example">Claim your prize</a>'
    html, _ = render_invitation_email(
        brand="Voicecon", organization_name=evil, inviter_name=evil, role="member",
        accept_url="https://app.voicecon.ai/invite/t", reject_url="https://app.voicecon.ai/invite/t?action=reject",
        expires_human="October 4, 2026",
    )
    assert 'href="https://evil.example"' not in html
    assert 'href="https://app.voicecon.ai/invite/t"' in html  # our own links still render

    html, _, _ = render_member_joined_email(
        brand="Voicecon", member_name=evil, member_email="x@example.com", organization_name="IQb",
        role="member", team_url="https://app.voicecon.ai/dashboard/settings/team",
    )
    assert 'href="https://evil.example"' not in html
