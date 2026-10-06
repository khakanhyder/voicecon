"""Account deactivation, recovery and permanent deletion.

The lifecycle of an account that its owner closes:

1. **Deactivated** (``deactivate_account``) — signed out everywhere, cannot sign
   in, workspaces switched off and their billing cancelled. Nothing is erased.
   A permanent-deletion date is fixed ``ACCOUNT_DELETION_RETENTION_DAYS`` ahead.
2. **Reactivated** (``reactivate_account``) — support brings it back from the
   admin console before that date. The account and the workspaces that went
   down with it come back as they were. Billing does not: the subscription was
   cancelled, so the owner picks a plan again.
3. **Permanently deleted** (``purge_account``) — run by ``purge_due_accounts``
   once the date passes, or at once by an admin. Irreversible.

What "permanently deleted" means here
-------------------------------------
The user row is *anonymised*, not dropped. Agents, calls and workflows carry a
``user_id`` with ON DELETE CASCADE, including ones the person created inside
somebody else's workspace, and trial grants and invoices reference rows that
must outlive the account. Dropping the row would take other customers' data and
the billing ledger with it.

So the purge removes everything that identifies or authenticates the person —
email, name, phone, bio, picture, password, Google/Apple link, API keys,
notifications, one-time codes, memberships of other people's workspaces, and
the third-party credentials stored in the workspaces they owned — and leaves an
anonymous tombstone. The email address is released, so it can register again
and is then a brand-new account with no link to the old one.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.subscription import LIVE_STATUSES, STATUS_CANCELED, Subscription
from app.models.user import ApiKey, Organization, OrganizationMember, User
from app.services.billing import get_stripe_service

logger = logging.getLogger(__name__)

#: Most accounts one sweep deletes. A backlog drains over a few sweeps instead
#: of holding one long transaction.
PURGE_BATCH_SIZE = 50

TOMBSTONE_DOMAIN = "deleted.invalid"


def retention_days() -> int:
    """Days between deactivation and permanent deletion. Never less than one,
    so a mistyped setting cannot delete an account the moment it is closed."""
    try:
        return max(1, int(settings.ACCOUNT_DELETION_RETENTION_DAYS))
    except (TypeError, ValueError):
        return 30


def support_email() -> str:
    return settings.EMAIL_REPLY_TO or "support@voicecon.ai"


def tombstone_email(user: User) -> str:
    return f"deleted-{user.id.hex}@{TOMBSTONE_DOMAIN}"


def account_status(user: User) -> str:
    """``active`` | ``disabled`` | ``deactivated`` | ``deleted``."""
    if user.deleted_at is not None:
        return "deleted"
    if user.deactivated_at is not None:
        return "deactivated"
    return "active" if user.is_active else "disabled"


def inactive_account_message(user: User) -> str:
    """What to tell someone who signs in to an account that is switched off."""
    if user.deactivated_at is not None and user.deleted_at is None:
        return (
            "This account has been deactivated. To reactivate it, contact us at "
            f"{support_email()}."
        )
    return f"This account has been disabled. Contact us at {support_email()} for help."


async def deactivate_owned_workspaces(db: AsyncSession, user: User, now: datetime) -> list[Organization]:
    """Switch off every active workspace ``user`` owns and cancel its billing.

    Workspaces are soft-deactivated, not dropped, so calls, recordings and
    invoices stay attributable. Each one is stamped so reactivating the account
    can tell it from a workspace the owner had already deleted. Nothing is
    committed here.
    """
    organizations = (
        await db.execute(
            select(Organization).where(
                Organization.owner_id == user.id, Organization.is_active.is_(True)
            )
        )
    ).scalars().all()

    for org in organizations:
        org.is_active = False
        org.owner_deactivated_at = now
        org.updated_at = now

        subscriptions = (
            await db.execute(
                select(Subscription).where(
                    and_(
                        Subscription.organization_id == org.id,
                        Subscription.status.in_(LIVE_STATUSES),
                    )
                )
            )
        ).scalars().all()
        for subscription in subscriptions:
            trial_without_stripe = not (
                subscription.stripe_subscription_id or subscription.polar_subscription_id
            )
            if trial_without_stripe:
                subscription.status = STATUS_CANCELED
                subscription.canceled_at = now
                subscription.ended_at = now
                subscription.current_period_end = min(subscription.current_period_end, now)
            elif subscription.polar_subscription_id:
                try:
                    from app.services.billing import polar_service

                    await polar_service.cancel(subscription, immediate=True)
                    subscription.status = STATUS_CANCELED
                    subscription.canceled_at = subscription.canceled_at or now
                    subscription.ended_at = now
                    subscription.current_period_end = min(subscription.current_period_end, now)
                    subscription.cancel_at_period_end = False
                except Exception as e:
                    logger.error("Failed to revoke Polar subscription %s for org %s: %s", subscription.id, org.id, e)
            else:
                try:
                    stripe_service = await get_stripe_service()
                    await stripe_service.cancel_subscription(
                        db=db, subscription_id=subscription.id, immediate=True
                    )
                    await db.refresh(subscription)
                    subscription.canceled_at = subscription.canceled_at or now
                    subscription.cancel_at_period_end = False
                except Exception as e:
                    logger.error("Failed to cancel Stripe subscription %s for org %s: %s", subscription.id, org.id, e)

    return list(organizations)


async def deactivate_account(db: AsyncSession, user: User, now: Optional[datetime] = None) -> datetime:
    """Close ``user``'s account, recoverably. Returns the permanent-deletion date.

    Nothing is committed here.
    """
    now = now or datetime.utcnow()
    scheduled = now + timedelta(days=retention_days())

    user.is_active = False
    user.deactivated_at = now
    user.deletion_scheduled_at = scheduled
    # Every session and refresh token stops working at once.
    user.token_version = (user.token_version or 0) + 1

    await deactivate_owned_workspaces(db, user, now)
    return scheduled


async def reactivate_account(db: AsyncSession, user: User, now: Optional[datetime] = None) -> Dict[str, Any]:
    """Bring a deactivated account back, with the workspaces that went down with it.

    Billing is not restored — the subscription was cancelled at deactivation —
    so a restored workspace is on no plan until its owner chooses one.

    Returns ``{"workspaces_restored": [...], "workspaces_skipped": [...]}`` (names).
    Nothing is committed here.
    """
    now = now or datetime.utcnow()

    user.is_active = True
    user.deactivated_at = None
    user.deletion_scheduled_at = None
    # Nothing issued before the deactivation should start working again.
    user.token_version = (user.token_version or 0) + 1

    organizations = (
        await db.execute(
            select(Organization).where(
                Organization.owner_id == user.id,
                Organization.is_active.is_(False),
                Organization.owner_deactivated_at.is_not(None),
            )
        )
    ).scalars().all()

    active_names = {
        name
        for (name,) in (
            await db.execute(
                select(func.lower(func.trim(Organization.name))).where(
                    Organization.owner_id == user.id, Organization.is_active.is_(True)
                )
            )
        ).all()
    }

    restored: List[str] = []
    skipped: List[str] = []
    for org in organizations:
        key = (org.name or "").strip().lower()
        # One owner cannot have two active workspaces with the same name
        # (migration 0034). Leave a clashing one off rather than fail the
        # whole reactivation; an admin can rename and enable it by hand.
        if key in active_names:
            skipped.append(org.name)
            continue
        org.is_active = True
        org.owner_deactivated_at = None
        org.updated_at = now
        active_names.add(key)
        restored.append(org.name)

    return {"workspaces_restored": restored, "workspaces_skipped": skipped}


async def purge_account(db: AsyncSession, user: User, now: Optional[datetime] = None) -> Dict[str, Any]:
    """Permanently delete ``user``'s account. Irreversible.

    See the module docstring for exactly what is erased and what is kept.
    Returns a summary for the audit log, including the original email — the
    caller decides what to do with it. Nothing is committed here.
    """
    from app.models.integration import IntegrationConnection
    from app.models.invitation import Invitation
    from app.models.notification import Notification
    from app.models.verification import VerificationCode
    from app.services.auth import login_throttle
    from app.services.storage import delete_avatar

    now = now or datetime.utcnow()
    original_email = user.email
    original_name = user.full_name

    # An active account deleted outright by an admin skips the deactivated
    # state, so its workspaces and billing are closed here instead.
    newly_deactivated = await deactivate_owned_workspaces(db, user, now)

    owned_ids = [
        org_id
        for (org_id,) in (
            await db.execute(select(Organization.id).where(Organization.owner_id == user.id))
        ).all()
    ]

    # Leave other people's workspaces, so the account stops showing in their team.
    leave = delete(OrganizationMember).where(OrganizationMember.user_id == user.id)
    if owned_ids:
        leave = leave.where(OrganizationMember.organization_id.not_in(owned_ids))
    left = await db.execute(leave)

    # Credentials: the person's own API keys, every key in the workspaces they
    # owned, and the third-party tokens those workspaces had connected.
    await db.execute(delete(ApiKey).where(ApiKey.user_id == user.id))
    if owned_ids:
        await db.execute(delete(ApiKey).where(ApiKey.organization_id.in_(owned_ids)))
        await db.execute(
            update(IntegrationConnection)
            .where(IntegrationConnection.organization_id.in_(owned_ids))
            .values(
                auth_data_encrypted=None,
                api_key_encrypted=None,
                access_token_encrypted=None,
                refresh_token_encrypted=None,
                token_expires_at=None,
                is_active=False,
                status="revoked",
            )
        )

    await db.execute(delete(Notification).where(Notification.user_id == user.id))
    await db.execute(delete(VerificationCode).where(VerificationCode.email == original_email))
    # A pending invitation to this address stays valid for whoever registers it
    # next, but must not stay pinned to the account that no longer exists.
    await db.execute(
        update(Invitation).where(Invitation.invited_user_id == user.id).values(invited_user_id=None)
    )

    delete_avatar(user.avatar_url)

    user.is_active = False
    user.is_verified = False
    user.deleted_at = now
    user.deactivated_at = user.deactivated_at or now
    user.deletion_scheduled_at = None
    user.token_version = (user.token_version or 0) + 1
    user.active_organization_id = None
    # Their posts keep the byline copied onto them (BlogPost.author_name).
    user.blog_role = None
    # Free the unique email and the social ids, and drop everything personal.
    user.email = tombstone_email(user)
    user.google_id = None
    user.apple_id = None
    user.hashed_password = None
    user.full_name = None
    user.company_name = None
    user.phone_number = None
    user.bio = None
    user.avatar_url = None
    user.email_verified_at = None
    login_throttle.clear(original_email)

    return {
        "email": original_email,
        "full_name": original_name,
        "workspaces_deactivated": [str(org.id) for org in newly_deactivated],
        "workspaces_owned": len(owned_ids),
        "memberships_removed": left.rowcount or 0,
    }


async def purge_due_accounts(db: AsyncSession, now: Optional[datetime] = None) -> int:
    """Permanently delete every deactivated account whose recovery window has
    closed. Returns how many were deleted.

    Each account is its own transaction, so one that fails is logged and retried
    on the next sweep without holding up the rest. Safe to run from several
    processes at once: the second finds the row already deleted.
    """
    from app.core.admin import audit
    from app.services.email.service import email_service

    now = now or datetime.utcnow()
    due = (
        await db.execute(
            select(User.id)
            .where(
                User.deletion_scheduled_at.is_not(None),
                User.deletion_scheduled_at <= now,
                User.deactivated_at.is_not(None),
                User.deleted_at.is_(None),
                User.is_active.is_(False),
                # Never delete staff automatically, whatever state the row is in.
                User.is_platform_admin.is_(False),
            )
            .order_by(User.deletion_scheduled_at)
            .limit(PURGE_BATCH_SIZE)
        )
    ).scalars().all()

    purged = 0
    for user_id in due:
        try:
            # Re-read under a row lock: a support agent may be reactivating
            # this very account, and whichever of us gets the row first must
            # be seen by the other.
            user = await db.get(User, user_id, populate_existing=True, with_for_update=True)
            if (
                user is None
                or user.deleted_at is not None
                or user.is_active
                or user.deletion_scheduled_at is None
                or user.deletion_scheduled_at > now
            ):
                await db.rollback()
                continue
            deactivated_at = user.deactivated_at
            summary = await purge_account(db, user, now)
            audit(
                db, None, "user.purge", target_type="user", target_id=user_id,
                summary=f"Permanently deleted {summary['email']} (deactivated account, retention period over)",
                details={**summary, "deactivated_at": deactivated_at.isoformat() if deactivated_at else None},
            )
            await db.commit()
            purged += 1
        except Exception:
            await db.rollback()
            logger.exception("Permanent deletion failed for user %s; will retry next sweep", user_id)
            continue

        # After the commit, and never fatal: the account is gone either way.
        try:
            await email_service.send_account_deleted(
                to_email=summary["email"], recipient_name=summary["full_name"]
            )
        except Exception:
            logger.exception("Could not send the deletion notice for user %s", user_id)

    if purged:
        logger.info("Permanently deleted %d deactivated account(s)", purged)
    return purged
