"""
Authenticating a request that presents an API key.

Keys look like ``vcon_<43 url-safe chars>``. Only a bcrypt hash of the full key
is stored, so authentication is a two-step lookup: find candidates by the
non-secret ``key_prefix`` (indexed), then bcrypt-verify the presented secret
against each candidate's hash. The prefix is a lookup hint, never a credential.

This module owns *what makes a key valid*; the FastAPI wiring that decides when
to consult it lives in :mod:`app.core.dependencies`.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import verify_api_key as verify_key_hash
from app.models.user import ApiKey

logger = logging.getLogger(__name__)

#: Every key starts with this. Used to tell an API key from a JWT in the
#: ``Authorization`` header without trying to decode either.
KEY_PREFIX = "vcon_"

#: Alternative to ``Authorization: Bearer`` for clients that reserve the
#: Authorization header. Must match the scheme published in ``core.openapi``.
API_KEY_HEADER = "X-API-Key"

#: Length of the stored/display prefix. ``vcon_`` + 7 secret chars. Must match
#: ``endpoints.api_keys.KEY_PREFIX_LEN``.
KEY_PREFIX_LEN = 12

#: Don't write ``last_used_at`` more often than this. A busy integration would
#: otherwise turn every read into a write; minute-resolution is plenty for the
#: "when was this key last seen" question the column exists to answer.
LAST_USED_RESOLUTION = timedelta(minutes=1)


def looks_like_api_key(token: Optional[str]) -> bool:
    """Whether ``token`` is meant to be an API key rather than a JWT."""
    return bool(token) and token.startswith(KEY_PREFIX)


def _invalid() -> HTTPException:
    """One indistinguishable error for every failure mode.

    Telling a caller *why* their key was rejected ("no such key" vs "wrong
    secret") hands an attacker an oracle for enumerating valid prefixes. The
    reason is logged server-side instead.
    """
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired API key",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def authenticate_api_key(db: AsyncSession, token: str) -> ApiKey:
    """Resolve a presented key to its :class:`ApiKey` row, or raise 401.

    The returned row has ``user`` and ``organization`` eagerly loaded — the
    caller needs both to build a workspace context, and lazy-loading them on an
    async session would blow up.
    """
    if not looks_like_api_key(token):
        raise _invalid()

    prefix = token[:KEY_PREFIX_LEN]
    result = await db.execute(
        select(ApiKey)
        .options(selectinload(ApiKey.user), selectinload(ApiKey.organization))
        .where(ApiKey.key_prefix == prefix)
    )
    # ``.all()`` rather than ``.scalar_one_or_none()``: the prefix is not
    # unique, so a collision must fall through to the hash check instead of
    # raising MultipleResultsFound and 500-ing.
    candidates = result.scalars().all()

    api_key = next((k for k in candidates if verify_key_hash(token, k.key_hash)), None)
    if api_key is None:
        logger.warning("API key auth failed: no key matches prefix %s", prefix)
        raise _invalid()

    if not api_key.is_active:
        logger.info("API key auth failed: key %s is revoked", api_key.id)
        raise _invalid()

    if api_key.expires_at is not None and api_key.expires_at <= datetime.utcnow():
        logger.info("API key auth failed: key %s expired at %s", api_key.id, api_key.expires_at)
        raise _invalid()

    # The key is only as good as the account behind it: a deactivated user's
    # keys die with them, and so do keys for a workspace that was shut off.
    if api_key.user is None or not api_key.user.is_active:
        logger.info("API key auth failed: owner of key %s is inactive", api_key.id)
        raise _invalid()

    if api_key.organization is None or not api_key.organization.is_active:
        logger.info("API key auth failed: workspace for key %s is inactive", api_key.id)
        raise _invalid()

    await touch_last_used(db, api_key)
    return api_key


async def touch_last_used(db: AsyncSession, api_key: ApiKey) -> None:
    """Record that the key was just used, at most once per resolution window."""
    now = datetime.utcnow()
    if api_key.last_used_at is not None and now - api_key.last_used_at < LAST_USED_RESOLUTION:
        return
    api_key.last_used_at = now
    try:
        await db.commit()
    except Exception:  # pragma: no cover - telemetry must never fail a request
        logger.exception("Could not record last_used_at for key %s", api_key.id)
        await db.rollback()
