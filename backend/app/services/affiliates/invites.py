"""Invitations into the affiliate portal.

The invite link carries a signed token naming the user and their
``token_version``. Accepting it sets the password (when the account has none)
and bumps ``token_version``, so a link works once; staff can send a new one.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Optional
from urllib.parse import quote

from jose import JWTError, jwt

from app.core.config import settings
from app.core.security import TOKEN_VERSION_CLAIM
from app.models.affiliate import Affiliate
from app.services.affiliates.program import describe_earning

logger = logging.getLogger(__name__)

INVITE_TOKEN_TYPE = "affiliate_invite"
INVITE_TTL = timedelta(days=7)


def invite_token(affiliate: Affiliate) -> str:
    payload = {
        "exp": datetime.utcnow() + INVITE_TTL,
        "sub": str(affiliate.user_id),
        "aff": str(affiliate.id),
        "type": INVITE_TOKEN_TYPE,
        TOKEN_VERSION_CLAIM: int(affiliate.user.token_version or 0),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def read_invite_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        return None
    if payload.get("type") != INVITE_TOKEN_TYPE or not payload.get("sub") or not payload.get("aff"):
        return None
    return payload


def portal_url(path: str = "/affiliate") -> str:
    return f"{(settings.FRONTEND_URL or '').rstrip('/')}{path}"


def invite_url(affiliate: Affiliate) -> str:
    return portal_url(f"/affiliate/accept-invite?token={quote(invite_token(affiliate))}")


async def send_invite(affiliate: Affiliate) -> bool:
    from app.services.email.service import email_service

    return await email_service.send_affiliate_invite(
        to_email=affiliate.user.email,
        name=affiliate.name,
        action_url=invite_url(affiliate),
        needs_password=not affiliate.user.hashed_password,
        earning_terms=describe_earning(affiliate),
    )
