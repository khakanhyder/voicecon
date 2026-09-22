"""
Platform-admin access control and audit logging.

The admin API sits outside every workspace: it reads and changes data across
all tenants and manages the platform's own credentials. Access therefore rests
on one flag, ``User.is_platform_admin``, and never on a workspace role.

Two rules the dependency enforces:

* **Login sessions only.** An API key is a long-lived credential meant for a
  customer's integrations; letting one carry platform-admin power would make a
  leaked key a platform compromise. Keys are refused even when their owner is
  an admin.
* **Console sessions only.** The staff console has its own sign-in, and its
  tokens carry an ``admin`` session scope. A session opened in the customer
  app is refused even when it belongs to a platform admin.
* **Every write is recorded** via :func:`audit`, in the same transaction as the
  change it describes, so the trail cannot disagree with the data.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_optional_api_key

logger = logging.getLogger(__name__)


async def require_platform_admin(
    request: Request,
    current_user=Depends(get_current_user),
    api_key=Depends(get_optional_api_key),
):
    """The acting platform admin, or 403."""
    if api_key is not None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The admin API cannot be used with an API key. Sign in instead.",
        )
    # The console is a separate sign-in (``/auth/admin/login``) with its own
    # session scope, so being a platform admin in the customer app is not
    # enough. ``get_principal`` already refuses the wrong scope here; this
    # repeats it at the point the power is actually granted.
    principal = getattr(request.state, "principal", None)
    if principal is not None and not principal.is_admin_session:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Sign in through the admin console to use the admin API.",
        )
    if not getattr(current_user, "is_platform_admin", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Platform admin access required",
        )
    return current_user


def _client_ip(request: Optional[Request]) -> Optional[str]:
    if request is None:
        return None
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()[:64]
    return request.client.host if request.client else None


def audit(
    db: AsyncSession,
    actor,
    action: str,
    *,
    target_type: Optional[str] = None,
    target_id: Any = None,
    summary: Optional[str] = None,
    details: Optional[dict] = None,
    request: Optional[Request] = None,
) -> None:
    """Stage an audit row on ``db``. The caller's commit persists it with the change."""
    from app.models.platform import AdminAuditLog

    db.add(
        AdminAuditLog(
            actor_id=getattr(actor, "id", None),
            actor_email=getattr(actor, "email", None),
            action=action,
            target_type=target_type,
            target_id=str(target_id) if target_id is not None else None,
            summary=summary,
            details=details,
            ip_address=_client_ip(request),
        )
    )


def _parse_emails(raw: str) -> list[str]:
    # Same normalisation registration applies, so the lookup matches the row.
    from app.services.auth.verification import normalize_email

    return [normalize_email(e) for e in (raw or "").split(",") if e.strip()]


async def promote_bootstrap_admins(db: AsyncSession, raw_emails: str) -> int:
    """Grant platform admin to the addresses in ``PLATFORM_ADMIN_EMAILS``.

    Idempotent and promote-only. Returns how many accounts were promoted now.
    """
    from app.models.user import User

    emails = _parse_emails(raw_emails)
    if not emails:
        return 0
    result = await db.execute(
        update(User)
        .where(User.email.in_(emails), User.is_platform_admin.is_(False))
        .values(is_platform_admin=True)
    )
    await db.commit()
    promoted = result.rowcount or 0
    if promoted:
        logger.info(f"Promoted {promoted} account(s) to platform admin from PLATFORM_ADMIN_EMAILS")
    missing = set(emails) - set(
        (await db.execute(select(User.email).where(User.email.in_(emails)))).scalars().all()
    )
    if missing:
        logger.warning(
            "PLATFORM_ADMIN_EMAILS lists addresses with no account yet "
            f"({', '.join(sorted(missing))}); they will be promoted on the next start after signing up."
        )
    return promoted
