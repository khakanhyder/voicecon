"""Pydantic schemas for team invitations."""
import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, ConfigDict


class InviteRequest(BaseModel):
    email: EmailStr
    role: str = "member"


class InvitationResponse(BaseModel):
    """Full invitation record (org-side view, for admins)."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    role: str
    status: str
    invited_by_name: Optional[str] = None
    expires_at: datetime
    created_at: datetime


class PublicInvitationResponse(BaseModel):
    """What an invitee sees on the accept/reject landing page (token-scoped)."""
    email: str
    role: str
    status: str  # pending | accepted | rejected | canceled | expired
    organization_name: str
    inviter_name: Optional[str] = None
    expired: bool
    # True when the invited email already has a Voicecon account (can accept by signing in).
    account_exists: bool


class InvitationActionResponse(BaseModel):
    status: str
    message: str
    organization_name: Optional[str] = None
