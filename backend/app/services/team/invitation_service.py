"""
Invitation lifecycle: create → (accept | reject | cancel | expire).

Keeps the create/accept/reject logic in one place so the team endpoints, the
public token endpoints, and the notification-bell actions all behave
identically. On create we also fan out an in-app notification (if the invitee
already has an account) and an email (via the pluggable email service).
"""
import logging
import secrets
import uuid
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.invitation import Invitation
from app.models.notification import Notification, NOTIFY_TEAM_INVITATION
from app.models.user import User, Organization, OrganizationMember
from app.services.email import email_service

logger = logging.getLogger(__name__)

INVITE_TTL_DAYS = 7
ASSIGNABLE_ROLES = {"admin", "member", "viewer"}


def _accept_url(token: str) -> str:
    return f"{settings.FRONTEND_URL.rstrip('/')}/invite/{token}"


def _reject_url(token: str) -> str:
    return f"{_accept_url(token)}?action=reject"


async def _user_by_email(db: AsyncSession, email: str) -> Optional[User]:
    result = await db.execute(select(User).where(func.lower(User.email) == email.lower()))
    return result.scalar_one_or_none()


async def _is_member(db: AsyncSession, org_id: uuid.UUID, user_id: uuid.UUID) -> bool:
    result = await db.execute(
        select(OrganizationMember.id).where(
            OrganizationMember.organization_id == org_id,
            OrganizationMember.user_id == user_id,
        )
    )
    return result.scalar_one_or_none() is not None


async def create_invitation(
    db: AsyncSession,
    *,
    organization: Organization,
    inviter: User,
    email: str,
    role: str,
) -> Invitation:
    """Create a pending invitation, notify the invitee in-app, and email them.

    Raises ValueError with a stable ``code`` attribute for the endpoint to map
    to an HTTP status: 'invalid_role', 'already_member', 'already_invited'.
    """
    email = email.lower().strip()
    role = role.lower()
    if role not in ASSIGNABLE_ROLES:
        raise _err("invalid_role", "Invalid role")

    existing_user = await _user_by_email(db, email)
    if existing_user and await _is_member(db, organization.id, existing_user.id):
        raise _err("already_member", "This person is already a member of the team")

    # Re-use / refresh an outstanding pending invite for the same email.
    result = await db.execute(
        select(Invitation).where(
            Invitation.organization_id == organization.id,
            func.lower(Invitation.email) == email,
            Invitation.status == "pending",
        )
    )
    invitation = result.scalar_one_or_none()

    now = datetime.utcnow()
    expires_at = now + timedelta(days=INVITE_TTL_DAYS)

    if invitation is not None:
        # Refresh the existing pending invite (new token, new expiry, latest role).
        invitation.role = role
        invitation.token = secrets.token_urlsafe(32)
        invitation.expires_at = expires_at
        invitation.invited_by = inviter.id
        invitation.invited_user_id = existing_user.id if existing_user else None
    else:
        invitation = Invitation(
            organization_id=organization.id,
            email=email,
            role=role,
            token=secrets.token_urlsafe(32),
            status="pending",
            invited_by=inviter.id,
            invited_user_id=existing_user.id if existing_user else None,
            expires_at=expires_at,
        )
        db.add(invitation)

    await db.flush()

    # In-app notification for an existing account.
    if existing_user is not None:
        db.add(
            Notification(
                user_id=existing_user.id,
                type=NOTIFY_TEAM_INVITATION,
                title=f"Invitation to join {organization.name}",
                body=f"{inviter.full_name or inviter.email} invited you to join "
                f"{organization.name} as a {role}.",
                data={
                    "invitation_token": invitation.token,
                    "invitation_id": str(invitation.id),
                    "organization_name": organization.name,
                    "role": role,
                    "inviter_name": inviter.full_name or inviter.email,
                },
            )
        )

    await db.commit()
    await db.refresh(invitation)

    # Send the email (best-effort; failures are logged, not raised).
    await email_service.send_invitation(
        to_email=email,
        organization_name=organization.name,
        inviter_name=inviter.full_name or inviter.email,
        role=role,
        accept_url=_accept_url(invitation.token),
        reject_url=_reject_url(invitation.token),
        expires_at=expires_at,
    )

    return invitation


async def get_by_token(db: AsyncSession, token: str) -> Optional[Invitation]:
    result = await db.execute(select(Invitation).where(Invitation.token == token))
    return result.scalar_one_or_none()


def is_actionable(invitation: Invitation) -> bool:
    return invitation.status == "pending" and invitation.expires_at > datetime.utcnow()


async def _mark_notification_actioned(db: AsyncSession, invitation: Invitation) -> None:
    result = await db.execute(select(Notification).where(Notification.type == NOTIFY_TEAM_INVITATION))
    for notif in result.scalars().all():
        if (notif.data or {}).get("invitation_token") == invitation.token:
            notif.is_actioned = True
            notif.is_read = True


async def accept_invitation(db: AsyncSession, invitation: Invitation, user: User) -> OrganizationMember:
    """Accept: create the membership, mark the invite accepted, resolve notification."""
    if not is_actionable(invitation):
        raise _err("not_actionable", "This invitation is no longer valid")

    # Create membership if not already present.
    if not await _is_member(db, invitation.organization_id, user.id):
        db.add(
            OrganizationMember(
                organization_id=invitation.organization_id,
                user_id=user.id,
                role=invitation.role,
                invited_by=invitation.invited_by,
            )
        )

    invitation.status = "accepted"
    invitation.responded_at = datetime.utcnow()
    invitation.invited_user_id = user.id
    await _mark_notification_actioned(db, invitation)
    await db.commit()

    result = await db.execute(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == invitation.organization_id,
            OrganizationMember.user_id == user.id,
        )
    )
    return result.scalar_one()


async def reject_invitation(db: AsyncSession, invitation: Invitation) -> None:
    """Decline the invitation (idempotent for already-responded invites)."""
    if invitation.status == "pending":
        invitation.status = "rejected"
        invitation.responded_at = datetime.utcnow()
        await _mark_notification_actioned(db, invitation)
        await db.commit()


async def cancel_invitation(db: AsyncSession, invitation: Invitation) -> None:
    """Admin cancels a pending invite."""
    if invitation.status == "pending":
        invitation.status = "canceled"
        invitation.responded_at = datetime.utcnow()
        await _mark_notification_actioned(db, invitation)
        await db.commit()


def _err(code: str, message: str) -> ValueError:
    e = ValueError(message)
    e.code = code  # type: ignore[attr-defined]
    return e
