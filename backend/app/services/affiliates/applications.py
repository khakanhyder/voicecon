"""Requests to join the affiliate program, sent from the public form.

An application is only a request. Staff review it in the admin console and
create the affiliate with the normal form (``POST /admin/affiliates`` with
``application_id``), so the terms are set exactly as for any other affiliate.

A new request tells every platform admin twice: a notification in the admin
console's bell, and an email.
"""
from __future__ import annotations

import logging
import time
import uuid
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.affiliate import APPLICATION_PENDING, AffiliateApplication
from app.models.notification import NOTIFY_AFFILIATE_APPLICATION, Notification
from app.models.user import User

logger = logging.getLogger(__name__)

#: Requests one address may send per window. The form is anonymous and every
#: new request emails the admins, so this is what stops it being used to flood
#: their inboxes. Counted in this process, like the login throttle.
MAX_PER_IP = 5
WINDOW_SECONDS = 3600

_recent: Dict[str, List[float]] = defaultdict(list)


def allow_submission(ip: Optional[str]) -> bool:
    """Count one attempt from ``ip`` and say whether it is within the limit."""
    if not ip:
        return True
    now = time.time()
    cutoff = now - WINDOW_SECONDS
    for key in [k for k, stamps in _recent.items() if not any(t > cutoff for t in stamps)]:
        del _recent[key]
    stamps = [t for t in _recent.get(ip, []) if t > cutoff]
    if len(stamps) >= MAX_PER_IP:
        _recent[ip] = stamps
        return False
    stamps.append(now)
    _recent[ip] = stamps
    return True


def reset_throttle() -> None:
    _recent.clear()


def review_url(application: AffiliateApplication) -> str:
    return f"{(settings.FRONTEND_URL or '').rstrip('/')}/admin/affiliates/requests?focus={application.id}"


async def submit(
    db: AsyncSession,
    *,
    name: str,
    email: str,
    company: Optional[str],
    website: Optional[str],
    message: Optional[str],
    ip_address: Optional[str],
) -> Tuple[AffiliateApplication, bool]:
    """Store a request. Returns it and whether it is new.

    Someone who applies again while their request is still waiting updates that
    request instead of adding a second one, and staff are not told twice.
    """
    existing = await db.scalar(
        select(AffiliateApplication)
        .where(AffiliateApplication.email == email, AffiliateApplication.status == APPLICATION_PENDING)
        .order_by(AffiliateApplication.created_at.desc())
        .limit(1)
    )
    if existing is not None:
        existing.name = name
        existing.company = company
        existing.website = website
        existing.message = message
        return existing, False

    application = AffiliateApplication(
        name=name,
        email=email,
        company=company,
        website=website,
        message=message,
        status=APPLICATION_PENDING,
        ip_address=ip_address,
    )
    db.add(application)
    await db.flush()
    return application, True


async def _admins(db: AsyncSession) -> List[User]:
    return list(
        (
            await db.execute(
                select(User).where(
                    User.is_platform_admin.is_(True), User.is_active.is_(True), User.deleted_at.is_(None)
                )
            )
        )
        .scalars()
        .all()
    )


async def notify_admins(db: AsyncSession, application: AffiliateApplication) -> List[str]:
    """Stage a bell notification for every platform admin. Returns their emails.

    The caller commits, then passes the emails to :func:`email_admins`, so a
    slow mail server never holds the transaction open.
    """
    admins = await _admins(db)
    who = f"{application.name} ({application.email})"
    for admin in admins:
        db.add(
            Notification(
                user_id=admin.id,
                type=NOTIFY_AFFILIATE_APPLICATION,
                title="New affiliate request",
                body=f"{who} applied to join the affiliate program.",
                data={
                    "application_id": str(application.id),
                    "href": f"/admin/affiliates/requests?focus={application.id}",
                },
            )
        )
    if not admins:
        logger.warning("Affiliate request %s has no platform admin to notify", application.id)
    return [admin.email for admin in admins]


async def email_admins(application: AffiliateApplication, emails: List[str]) -> int:
    """Email the request to each admin. Returns how many were sent."""
    from app.services.email.service import email_service

    sent = 0
    for email in emails:
        if await email_service.send_affiliate_application_notice(
            to_email=email,
            applicant_name=application.name,
            applicant_email=application.email,
            company=application.company,
            website=application.website,
            message=application.message,
            action_url=review_url(application),
        ):
            sent += 1
    return sent


async def resolve_notifications(db: AsyncSession, application_id: uuid.UUID) -> None:
    """Mark every admin's notification about this request as dealt with.

    One admin handling a request should clear it from the other admins' bells.
    """
    rows = (
        await db.execute(
            select(Notification).where(
                Notification.type == NOTIFY_AFFILIATE_APPLICATION,
                Notification.is_actioned.is_(False),
            )
        )
    ).scalars().all()
    for row in rows:
        if (row.data or {}).get("application_id") == str(application_id):
            row.is_actioned = True
            row.is_read = True
