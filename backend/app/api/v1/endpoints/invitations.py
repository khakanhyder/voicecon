"""
Invitation accept/reject endpoints (token-addressed).

These back both the email Accept/Reject links and the notification-bell actions:
  GET  /invitations/{token}          → public details for the landing page
  POST /invitations/{token}/accept   → authenticated; email must match the invite
  POST /invitations/{token}/reject   → public (declining is harmless)
"""
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.core.dependencies import get_current_user
from app.models.invitation import Invitation
from app.models.user import User, Organization
from app.schemas.invitation import PublicInvitationResponse, InvitationActionResponse
from app.services.team import invitation_service

router = APIRouter()


async def _load(db: AsyncSession, token: str) -> Invitation:
    invitation = await invitation_service.get_by_token(db, token)
    if invitation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invitation not found")
    return invitation


async def _org_name(db: AsyncSession, org_id: uuid.UUID) -> str:
    org = (await db.execute(select(Organization).where(Organization.id == org_id))).scalar_one_or_none()
    return org.name if org else "the organization"


async def _inviter_name(db: AsyncSession, invitation: Invitation) -> str | None:
    if not invitation.invited_by:
        return None
    user = (await db.execute(select(User).where(User.id == invitation.invited_by))).scalar_one_or_none()
    return (user.full_name or user.email) if user else None


@router.get("/{token}", response_model=PublicInvitationResponse)
async def get_invitation(token: str, db: AsyncSession = Depends(get_db)):
    """Public: details an invitee needs to decide (no auth — the token is the key)."""
    invitation = await _load(db, token)

    expired = invitation.expires_at <= datetime.utcnow()
    account = (
        await db.execute(select(User.id).where(func.lower(User.email) == invitation.email.lower()))
    ).scalar_one_or_none()

    # Surface an accurate status even when the stored value is stale (pending-but-expired).
    display_status = invitation.status
    if display_status == "pending" and expired:
        display_status = "expired"

    return PublicInvitationResponse(
        email=invitation.email,
        role=invitation.role,
        status=display_status,
        organization_name=await _org_name(db, invitation.organization_id),
        inviter_name=await _inviter_name(db, invitation),
        expired=expired,
        account_exists=account is not None,
    )


@router.post("/{token}/accept", response_model=InvitationActionResponse)
async def accept_invitation(
    token: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Accept an invitation. The signed-in user's email must match the invite."""
    invitation = await _load(db, token)

    if current_user.email.lower() != invitation.email.lower():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"This invitation was sent to {invitation.email}. "
            f"Sign in as {invitation.email} to accept it.",
        )

    if not invitation_service.is_actionable(invitation):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This invitation has expired or is no longer valid",
        )

    org_name = await _org_name(db, invitation.organization_id)
    try:
        await invitation_service.accept_invitation(db, invitation, current_user)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    return InvitationActionResponse(
        status="accepted",
        message=f"You've joined {org_name}.",
        organization_name=org_name,
    )


@router.post("/{token}/reject", response_model=InvitationActionResponse)
async def reject_invitation(token: str, db: AsyncSession = Depends(get_db)):
    """Decline an invitation. Public and idempotent."""
    invitation = await _load(db, token)
    org_name = await _org_name(db, invitation.organization_id)
    await invitation_service.reject_invitation(db, invitation)
    return InvitationActionResponse(
        status="rejected",
        message=f"You've declined the invitation to {org_name}.",
        organization_name=org_name,
    )
