"""
Taking back Voicecon numbers a workspace is no longer paying for.

A number bought on Voicecon's own carrier account is billed to us every month
for as long as it exists there, whether or not the workspace that picked it
still has a plan. This module is what ends that:

1. **Hold.** When a workspace has no live subscription (or has been suspended),
   its Voicecon numbers are marked ``suspended``, stamped with the date they
   will be released, and the owners are told that date.
2. **Remind.** A few days before the date, the owners are told again.
3. **Release.** On the date the number is released at the carrier and its row
   deleted. This cannot be undone — the same number cannot be bought back.
4. **Restore.** A workspace that subscribes again before the date gets its
   held numbers back, as far as the new plan has room.

It is derived from state, not from transitions: every pass looks at each
workspace that holds a Voicecon number and asks whether it is entitled to it
now. So it does not matter *how* a subscription ended — trial lapse, failed
payments, cancellation, a provider webhook, an admin suspending the workspace —
and a pass that was missed is simply made up by the next one.

Numbers on a customer's own carrier account are never touched: they are theirs
and they pay for them.

The schedule lives in ``provider_metadata["reclaim"]`` on the number::

    {"suspended_at": "...", "release_after": "..." | null,
     "reminded": bool, "attempts": int, "last_error": str}
"""
from __future__ import annotations

import logging
import uuid
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.call import PhoneNumber
from app.models.notification import Notification
from app.models.user import Organization, OrganizationMember, User
from app.services.billing import catalog, events
from app.services.billing.entitlements import Entitlements, get_entitlement_service
from app.services.telephony import number_guard
from app.services.telephony.provider_registry import (
    CREDENTIAL_SOURCE_KEY,
    PLATFORM_SOURCE,
    resolve_provider_for_number,
)
from app.services.telephony.providers import NumberProviderError
from app.services.telephony.purchase_account import is_voicecon_number

logger = logging.getLogger(__name__)

STATUS_ACTIVE = "active"
STATUS_SUSPENDED = "suspended"

#: ``provider_metadata`` key holding a held number's release schedule.
RECLAIM_KEY = "reclaim"
#: Set on numbers brought in from the customer's own account. Mirrors
#: ``IMPORTED_KEY`` in the phone-number endpoints.
_IMPORTED_KEY = "imported"

#: Send the reminder this long before the release date.
REMINDER_DAYS = 3

#: Releases per pass. Releasing is irreversible, so a pass that has somehow
#: decided to release everything gets through this many before anyone notices.
MAX_RELEASES_PER_PASS = 25

PHONE_NUMBERS_PATH = "/dashboard/phone-numbers"


class ReclaimReport:
    """What one pass did."""

    def __init__(self) -> None:
        self.suspended = 0
        self.reminded = 0
        self.released = 0
        self.restored = 0
        self.failed = 0

    @property
    def changed(self) -> int:
        return self.suspended + self.reminded + self.released + self.restored + self.failed

    def __str__(self) -> str:
        return (
            f"suspended={self.suspended} reminded={self.reminded} "
            f"released={self.released} restored={self.restored} failed={self.failed}"
        )


# ---- Schedule stored on the number ----


def _parse(value: Any) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return None


def reclaim_state(number: PhoneNumber) -> Dict[str, Any]:
    return dict((number.provider_metadata or {}).get(RECLAIM_KEY) or {})


def suspended_at(number: PhoneNumber) -> Optional[datetime]:
    return _parse(reclaim_state(number).get("suspended_at"))


def release_after(number: PhoneNumber) -> Optional[datetime]:
    """When a held number will be released; ``None`` when no date is set."""
    return _parse(reclaim_state(number).get("release_after"))


def _set_state(number: PhoneNumber, state: Optional[Dict[str, Any]]) -> None:
    # JSON columns do not track in-place mutation: reassign the whole value.
    metadata = dict(number.provider_metadata or {})
    if state is None:
        metadata.pop(RECLAIM_KEY, None)
    else:
        metadata[RECLAIM_KEY] = state
    number.provider_metadata = metadata


def is_reclaimable(number: PhoneNumber) -> bool:
    """A number we pay for: bought on Voicecon's carrier account, not brought
    in by the customer, and known to the carrier by an id we can release."""
    return bool(
        number.provider_sid
        and number.integration_connection_id is None
        and not (number.provider_metadata or {}).get(_IMPORTED_KEY)
        and is_voicecon_number(number)
    )


def grace_days() -> int:
    return max(0, int(settings.VOICECON_NUMBER_RELEASE_GRACE_DAYS))


def _day(value: datetime) -> str:
    return f"{value.day} {value.strftime('%B %Y')}"


# ---- The sweep ----


async def reclaim_numbers(db: AsyncSession, *, now: Optional[datetime] = None) -> ReclaimReport:
    """Run one pass over every workspace holding a Voicecon number.

    Commits as it goes: a release at the carrier cannot be rolled back, so each
    one is recorded the moment it happens rather than at the end of the pass.
    """
    now = now or datetime.utcnow()
    report = ReclaimReport()

    result = await db.execute(
        select(PhoneNumber)
        .where(
            PhoneNumber.status.in_((STATUS_ACTIVE, STATUS_SUSPENDED)),
            PhoneNumber.integration_connection_id.is_(None),
            PhoneNumber.provider_sid.is_not(None),
        )
        .order_by(PhoneNumber.created_at.asc())
    )
    # Ids only: a rollback for one workspace expires every loaded row, so each
    # workspace reloads its own numbers when its turn comes.
    by_org: Dict[uuid.UUID, List[uuid.UUID]] = defaultdict(list)
    for number in result.scalars().all():
        if is_reclaimable(number):
            by_org[number.organization_id].append(number.id)

    budget = MAX_RELEASES_PER_PASS
    for organization_id, number_ids in by_org.items():
        try:
            numbers = list(
                (
                    await db.execute(
                        select(PhoneNumber)
                        .where(PhoneNumber.id.in_(number_ids))
                        .order_by(PhoneNumber.created_at.asc())
                    )
                ).scalars().all()
            )
            budget -= await _reclaim_for_org(db, organization_id, numbers, now, report, budget)
        except Exception as exc:  # noqa: BLE001 — one workspace must not stop the sweep
            await db.rollback()
            logger.error(
                f"Number reclaim failed for org {organization_id}: {exc}", exc_info=True
            )

    if report.changed:
        logger.info(f"Voicecon number reclaim: {report}")
    return report


async def _reclaim_for_org(
    db: AsyncSession,
    organization_id: uuid.UUID,
    numbers: List[PhoneNumber],
    now: datetime,
    report: ReclaimReport,
    budget: int,
) -> int:
    """Handle one workspace. Returns how many numbers it released."""
    organization = await db.get(Organization, organization_id)
    entitlements = await get_entitlement_service().resolve(db, organization_id, fresh=True)
    entitled = entitlements.is_live and bool(organization and organization.is_active)

    held = [n for n in numbers if n.status == STATUS_SUSPENDED]
    if entitled:
        if held:
            report.restored += await restore_numbers(db, organization_id, entitlements)
        return 0

    days = grace_days()

    # 1. Hold what is still active, and give a date to anything held without one
    #    (numbers suspended before releases were automatic).
    to_hold = [n for n in numbers if n.status == STATUS_ACTIVE]
    undated = [n for n in held if release_after(n) is None] if days else []
    if to_hold or undated:
        date = now + timedelta(days=days) if days else None
        affected = [n.phone_number for n in [*to_hold, *undated]]
        for number in [*to_hold, *undated]:
            state = reclaim_state(number)
            state.setdefault("suspended_at", now.isoformat())
            state["release_after"] = date.isoformat() if date else None
            state["reminded"] = False
            number.status = STATUS_SUSPENDED
            _set_state(number, state)
        await events.record_event(
            db,
            organization_id=organization_id,
            event_type=events.NUMBER_SUSPENDED,
            payload={
                "phone_numbers": affected,
                "release_after": date.isoformat() if date else None,
            },
        )
        await db.commit()
        report.suspended += len(affected)
        await _notify_held(db, organization_id, affected, date)
        return 0  # the clock has only just started

    if not days:
        return 0

    # Worked out before anything commits, while the rows are certainly loaded.
    reminder_window = timedelta(days=REMINDER_DAYS)
    due = [n for n in held if (date := release_after(n)) is not None and date <= now]
    to_remind = [
        n
        for n in held
        if (date := release_after(n)) is not None
        and now < date <= now + reminder_window
        and not reclaim_state(n).get("reminded")
        # No reminder when the whole hold is shorter than the reminder window:
        # the first notice was already "a few days".
        and (suspended_at(n) is None or date - suspended_at(n) > reminder_window)
    ]

    # 2. Remind once, shortly before the date.
    if to_remind:
        reminded = [n.phone_number for n in to_remind]
        earliest = min(release_after(n) for n in to_remind)
        for number in to_remind:
            _set_state(number, {**reclaim_state(number), "reminded": True})
        await db.commit()
        report.reminded += len(reminded)
        await _notify_reminder(db, organization_id, reminded, earliest)

    # 3. Release what is due.
    released: List[str] = []
    for number in due[: max(0, budget)]:
        phone_number = await release_to_carrier(db, number, reason="subscription_ended")
        if phone_number:
            released.append(phone_number)
            report.released += 1
        else:
            report.failed += 1
    if released:
        await _notify_released(db, organization_id, released)
    return len(released)


async def release_to_carrier(
    db: AsyncSession,
    number: PhoneNumber,
    *,
    reason: str,
    actor_type: str = events.ACTOR_SYSTEM,
    actor_id: Optional[uuid.UUID] = None,
) -> Optional[str]:
    """Release a Voicecon number at the carrier and delete its row.

    Always aimed at Voicecon's own account, whatever the row's metadata says,
    so a workspace's own carrier account can never be asked about a number it
    does not hold. Returns the number once it is gone; on failure returns
    ``None`` and keeps the row (with the error noted) so the next pass tries
    again.
    """
    # An earlier commit in the same pass may have expired the row.
    await db.refresh(number)
    phone_number, organization_id = number.phone_number, number.organization_id
    metadata = {**(number.provider_metadata or {}), CREDENTIAL_SOURCE_KEY: PLATFORM_SOURCE}
    try:
        resolved = await resolve_provider_for_number(
            db,
            organization_id,
            provider_slug=number.provider,
            connection_id=None,
            provider_metadata=metadata,
        )
        await resolved.provider.release_number(
            provider_sid=number.provider_sid,
            phone_number=phone_number,
            provider_metadata=metadata,
        )
    except Exception as exc:  # noqa: BLE001
        already_gone = isinstance(exc, NumberProviderError) and exc.status_code == 404
        if not already_gone:
            state = reclaim_state(number)
            state["attempts"] = int(state.get("attempts") or 0) + 1
            state["last_error"] = str(exc)[:300]
            _set_state(number, state)
            await db.commit()
            logger.error(
                f"Could not release {phone_number} (org {organization_id}, "
                f"attempt {state['attempts']}): {exc}"
            )
            return None
        logger.warning(f"{phone_number} was already gone at the carrier; removing its record")

    await db.delete(number)
    await events.record_event(
        db,
        organization_id=organization_id,
        event_type=events.NUMBER_RELEASED,
        actor_type=actor_type,
        actor_id=actor_id,
        payload={"phone_number": phone_number, "reason": reason},
    )
    await db.commit()
    logger.info(f"Released {phone_number} (org {organization_id}): {reason}")
    return phone_number


async def restore_numbers(
    db: AsyncSession,
    organization_id: uuid.UUID,
    entitlements: Optional[Entitlements] = None,
) -> int:
    """Give a paying workspace its held numbers back, as far as its plan has room.

    Oldest first. Anything the plan has no room for stays held and keeps its
    release date. Returns how many were restored.
    """
    if entitlements is None:
        entitlements = await get_entitlement_service().resolve(db, organization_id, fresh=True)
    organization = await db.get(Organization, organization_id)
    if not entitlements.is_live or not (organization and organization.is_active):
        return 0

    limit = catalog.LIMIT_PHONE_NUMBERS

    async def restorable() -> List[PhoneNumber]:
        rows = (
            await db.execute(
                select(PhoneNumber)
                .where(
                    PhoneNumber.organization_id == organization_id,
                    PhoneNumber.status == STATUS_SUSPENDED,
                )
                .order_by(PhoneNumber.created_at.asc())
            )
        ).scalars().all()
        # Only what this module holds; a number set aside by other means is
        # not ours to switch back on.
        rows = [n for n in rows if is_reclaimable(n)]
        if rows and not entitlements.is_unlimited(limit):
            # Held numbers count towards the plan's allowance like any other,
            # so the room for them is what the rest leave free.
            others = await get_entitlement_service().count_for_limit(
                db, organization_id, limit
            ) - await _held_count(db, organization_id)
            rows = rows[: max(0, entitlements.limit(limit) - others)]
        return rows

    if not await restorable():
        return 0

    # Restoring changes how many numbers the workspace holds, so it must not
    # interleave with a purchase. If one is in flight, the next pass (or the
    # next visit to the Phone Numbers page) does it instead. Counted again
    # under the lock, like a purchase.
    if not await number_guard.lock_workspace_numbers(db, organization_id, wait=0):
        return 0
    held = await restorable()
    if not held:
        await db.commit()  # nothing changed; this only lets go of the lock
        return 0

    for number in held:
        number.status = STATUS_ACTIVE
        _set_state(number, None)
    await events.record_event(
        db,
        organization_id=organization_id,
        event_type=events.NUMBER_RESTORED,
        payload={"phone_numbers": [n.phone_number for n in held]},
    )
    restored = len(held)
    await db.commit()
    logger.info(f"Restored {restored} held number(s) for org {organization_id}")
    return restored


async def _held_count(db: AsyncSession, organization_id: uuid.UUID) -> int:
    return int(
        (
            await db.execute(
                select(func.count(PhoneNumber.id)).where(
                    PhoneNumber.organization_id == organization_id,
                    PhoneNumber.status == STATUS_SUSPENDED,
                )
            )
        ).scalar()
        or 0
    )


# ---- Notices ----


async def _owners(db: AsyncSession, organization_id: uuid.UUID) -> List[User]:
    result = await db.execute(
        select(User)
        .join(OrganizationMember, OrganizationMember.user_id == User.id)
        .where(
            OrganizationMember.organization_id == organization_id,
            OrganizationMember.role.in_(("owner", "admin")),
            User.is_active.is_(True),
        )
    )
    return list(result.scalars().unique().all())


async def _notify(
    db: AsyncSession,
    organization_id: uuid.UUID,
    *,
    subject: str,
    heading: str,
    intro: str,
    bullets: Sequence[str] = (),
    notification_body: str,
    action_label: str = "Choose a plan",
) -> None:
    """Email the owners and leave an in-app notification. Never raises: the
    state change it reports has already been committed."""
    try:
        owners = await _owners(db, organization_id)
        if not owners:
            return
        for owner in owners:
            db.add(
                Notification(
                    user_id=owner.id,
                    type="billing",
                    title=heading,
                    body=notification_body,
                    data={"action_url": PHONE_NUMBERS_PATH},
                )
            )
        recipients = [owner.email for owner in owners]
        await db.commit()

        from app.services.email.service import email_service

        base = (settings.FRONTEND_URL or "").rstrip("/")
        for email in recipients:
            await email_service.send_billing_notice(
                to_email=email,
                subject=subject,
                heading=heading,
                intro=intro,
                bullets=list(bullets),
                action_url=f"{base}/dashboard/settings/billing",
                action_label=action_label,
            )
    except Exception as exc:  # noqa: BLE001
        await db.rollback()
        logger.error(f"Could not send a phone number notice to org {organization_id}: {exc}")


async def _notify_held(
    db: AsyncSession,
    organization_id: uuid.UUID,
    phone_numbers: Sequence[str],
    date: Optional[datetime],
) -> None:
    many = len(phone_numbers) > 1
    listed = ", ".join(phone_numbers)
    heading = f"Your {'phone numbers are' if many else 'phone number is'} on hold"
    stopped = (
        f"Your workspace no longer has an active plan, so {listed} "
        f"{'have' if many else 'has'} stopped taking calls."
    )
    if date is None:
        await _notify(
            db,
            organization_id,
            subject=heading,
            heading=heading,
            intro=(
                f"{stopped} Choose a plan and "
                f"{'they switch' if many else 'it switches'} back on."
            ),
            notification_body="Choose a plan to switch your phone number back on.",
        )
        return
    await _notify(
        db,
        organization_id,
        subject=(
            f"Your {'phone numbers' if many else 'phone number'} will be released "
            f"on {_day(date)}"
        ),
        heading=heading,
        intro=f"{stopped} We will keep {'them' if many else 'it'} for you until {_day(date)}.",
        bullets=[
            f"Choose a plan before {_day(date)} and "
            f"{'they switch' if many else 'it switches'} back on, unchanged.",
            f"After that {'the numbers are' if many else 'the number is'} released "
            "and cannot be recovered.",
            "Your agents, workflows and call history are not affected.",
        ],
        notification_body=(
            f"{listed} will be released on {_day(date)} unless you choose a plan."
        ),
    )


async def _notify_reminder(
    db: AsyncSession,
    organization_id: uuid.UUID,
    phone_numbers: Sequence[str],
    date: datetime,
) -> None:
    many = len(phone_numbers) > 1
    listed = ", ".join(phone_numbers)
    await _notify(
        db,
        organization_id,
        subject=(
            f"Last reminder: your {'phone numbers' if many else 'phone number'} "
            f"will be released on {_day(date)}"
        ),
        heading=f"Your {'phone numbers' if many else 'phone number'} will be released soon",
        intro=(
            f"{listed} {'are' if many else 'is'} still on hold and will be released "
            f"on {_day(date)}. Once released, {'they' if many else 'it'} cannot be recovered."
        ),
        bullets=[f"Choose a plan before {_day(date)} to keep {'them' if many else 'it'}."],
        notification_body=(
            f"{listed} will be released on {_day(date)} unless you choose a plan."
        ),
    )


async def _notify_released(
    db: AsyncSession, organization_id: uuid.UUID, phone_numbers: Sequence[str]
) -> None:
    many = len(phone_numbers) > 1
    listed = ", ".join(phone_numbers)
    await _notify(
        db,
        organization_id,
        subject=f"Your {'phone numbers have' if many else 'phone number has'} been released",
        heading=f"Your {'phone numbers have' if many else 'phone number has'} been released",
        intro=(
            f"{listed} {'were' if many else 'was'} on hold because your workspace has "
            f"no active plan, and {'have' if many else 'has'} now been released."
        ),
        bullets=[
            "Your agents, workflows and call history are still here.",
            "Choose a plan and you can pick a new number under Phone Numbers.",
        ],
        notification_body=f"{listed} {'were' if many else 'was'} released.",
    )
