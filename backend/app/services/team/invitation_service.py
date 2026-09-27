"""
Invitation lifecycle: create → (resend)* → (accept | reject | cancel | expire).

Keeps the create/accept/reject logic in one place so the team endpoints, the
public token endpoints, and the notification-bell actions all behave
identically. On create we also fan out an in-app notification (if the invitee
already has an account) and an email (via the pluggable email service). When
an invitation is accepted, the workspace owner (and the inviter, if that was
someone else) is told by email and in-app.
"""
import logging
import secrets
import uuid
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import UserFacingError
from app.models.invitation import Invitation
from app.models.notification import (
    NOTIFY_TEAM_INVITATION,
    NOTIFY_TEAM_MEMBER_JOINED,
    Notification,
)
from app.models.user import User, Organization, OrganizationMember
from app.services.email import email_service

logger = logging.getLogger(__name__)

from app.core.permissions import ASSIGNABLE_ROLES

INVITE_TTL_DAYS = 7
#: Minimum gap between two emails for the same invitation, so a double click
#: (or an impatient owner) can't flood someone's inbox — which is also exactly
#: the pattern that gets a sender marked as spam.
RESEND_COOLDOWN_SECONDS = 60


def _accept_url(token: str) -> str:
    return f"{settings.FRONTEND_URL.rstrip('/')}/invite/{token}"


def _reject_url(token: str) -> str:
    return f"{_accept_url(token)}?action=reject"


def _team_url() -> str:
    return f"{settings.FRONTEND_URL.rstrip('/')}/dashboard/settings/team"


def _display_name(user: Optional[User]) -> Optional[str]:
    if user is None:
        return None
    return user.full_name or user.email


async def _send_invitation_email(
    invitation: Invitation,
    organization: Organization,
    inviter_name: Optional[str],
    expires_at: Optional[datetime] = None,
) -> bool:
    """Email the invitee their Accept/Decline links. Returns whether it was sent."""
    return await email_service.send_invitation(
        to_email=invitation.email,
        organization_name=organization.name,
        inviter_name=inviter_name,
        role=invitation.role,
        accept_url=_accept_url(invitation.token),
        reject_url=_reject_url(invitation.token),
        expires_at=expires_at or invitation.expires_at,
    )


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

    # Send the email. A failure doesn't undo the invitation (it can be resent),
    # but the caller is told, so the UI can say so instead of a false "sent".
    invitation.email_sent = await _send_invitation_email(
        invitation, organization, _display_name(inviter)
    )
    return invitation


async def resend_invitation(
    db: AsyncSession, *, invitation: Invitation, organization: Organization
) -> Invitation:
    """Email the same pending invitation again.

    The invitation row and its token stay the same — no duplicate is created,
    and a link from an earlier email keeps working. The expiry is pushed out a
    full ``INVITE_TTL_DAYS`` so a lapsed invite can be revived by resending it.
    The new expiry is only saved once the email has actually gone out.

    Raises ``InvitationError`` with code 'not_pending', 'too_soon' or
    'email_failed'.
    """
    if invitation.status != "pending":
        raise _err("not_pending", "Only pending invitations can be resent.")

    now = datetime.utcnow()
    last_sent = invitation.updated_at or invitation.created_at
    if last_sent is not None:
        wait = RESEND_COOLDOWN_SECONDS - int((now - last_sent).total_seconds())
        if wait > 0:
            raise _err(
                "too_soon",
                f"This invitation was just sent. Please wait {wait} seconds before resending it.",
            )

    inviter = await db.get(User, invitation.invited_by) if invitation.invited_by else None
    new_expiry = now + timedelta(days=INVITE_TTL_DAYS)

    # Nothing is written until the email has gone out, so a failed send leaves
    # the invitation exactly as it was (and the cooldown untouched).
    sent = await _send_invitation_email(
        invitation, organization, _display_name(inviter), expires_at=new_expiry
    )
    if not sent:
        raise _err(
            "email_failed",
            "We couldn't send the invitation email. Please try again in a moment.",
        )

    invitation.expires_at = new_expiry
    invitation.updated_at = now
    # They may have signed up since the first email; link the account so the
    # accept page and notifications recognise them.
    if invitation.invited_user_id is None:
        existing_user = await _user_by_email(db, invitation.email)
        if existing_user is not None:
            invitation.invited_user_id = existing_user.id
    await db.commit()
    await db.refresh(invitation)
    invitation.email_sent = True
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

    organization = await db.get(Organization, invitation.organization_id)
    if organization is None or not organization.is_active:
        raise _err("org_inactive", "That workspace is no longer available")

    # Create membership if not already present.
    joined = not await _is_member(db, invitation.organization_id, user.id)
    if joined:
        db.add(
            OrganizationMember(
                organization_id=invitation.organization_id,
                user_id=user.id,
                role=invitation.role,
                invited_by=invitation.invited_by,
            )
        )

    # Land them *inside* the workspace they just joined. Without this the next
    # request resolves to their own workspace and the invitation looks like it
    # did nothing — they can still switch back at any time.
    user.active_organization_id = invitation.organization_id

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
    membership = result.scalar_one()

    # Only after the membership is committed, and only when this acceptance is
    # what added them — never for someone who was already a member.
    if joined:
        await _notify_member_joined(db, organization, invitation, user)
    return membership


async def _notify_member_joined(
    db: AsyncSession, organization: Organization, invitation: Invitation, member: User
) -> None:
    """Tell the owner (and the inviter, if different) that someone joined.

    Best-effort: the member has already joined, so a notification failure is
    logged and never turns a successful acceptance into an error.
    """
    try:
        recipient_ids = [organization.owner_id]
        if invitation.invited_by and invitation.invited_by != organization.owner_id:
            recipient_ids.append(invitation.invited_by)

        member_name = _display_name(member) or invitation.email
        recipients = []
        for user_id in recipient_ids:
            if user_id is None or user_id == member.id:
                continue
            recipient = await db.get(User, user_id)
            if recipient is None or not recipient.is_active:
                continue
            recipients.append(recipient)
            db.add(
                Notification(
                    user_id=recipient.id,
                    type=NOTIFY_TEAM_MEMBER_JOINED,
                    title=f"{member_name} joined {organization.name}",
                    body=f"{member_name} has accepted your invitation and joined "
                    f"{organization.name} as a {invitation.role}.",
                    data={
                        "organization_id": str(organization.id),
                        "organization_name": organization.name,
                        "member_email": member.email,
                        "role": invitation.role,
                    },
                )
            )
        await db.commit()

        for recipient in recipients:
            await email_service.send_member_joined(
                to_email=recipient.email,
                recipient_name=recipient.full_name,
                member_name=member_name,
                member_email=member.email,
                organization_name=organization.name,
                role=invitation.role,
                team_url=_team_url(),
            )
    except Exception:  # noqa: BLE001 — the join itself already succeeded
        logger.exception("Could not notify the owner that %s joined %s", member.email, organization.id)


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


class InvitationError(UserFacingError, ValueError):
    """An invitation cannot be created or accepted. The message is user-facing.

    Still a ``ValueError`` for existing callers. Endpoints catch this class
    rather than ``ValueError`` itself, which would also catch unrelated failures
    and send their raw text to the client.
    """

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def _err(code: str, message: str) -> InvitationError:
    return InvitationError(code, message)
