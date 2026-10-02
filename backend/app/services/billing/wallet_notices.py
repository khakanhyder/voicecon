"""
Emails and in-app notifications about the prepaid wallet.

Sent *after* the transaction that caused them has committed, and never allowed
to raise: a mail server that is down must not undo a top-up or fail the
callback that recorded a call. Each low-balance notice is sent once per
crossing — the wallet row remembers which one the owners have already had (see
``Wallet.notice_level``), so a busy afternoon of calls is one email, not fifty.
"""
from __future__ import annotations

import logging
import uuid
from typing import List, Optional, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.notification import Notification
from app.models.user import OrganizationMember, User
from app.models.wallet import NOTICE_EMPTY, NOTICE_LOW
from app.services.billing import wallet as wallet_service

logger = logging.getLogger(__name__)

BILLING_PATH = "/dashboard/settings/billing"
#: Lands on the wallet card of the billing page.
WALLET_PATH = f"{BILLING_PATH}#wallet"


def _url(path: str) -> str:
    return f"{(settings.FRONTEND_URL or '').rstrip('/')}{path}"


async def _recipients(db: AsyncSession, organization_id: uuid.UUID) -> List[User]:
    """The people who can see the billing page, as the reconciler notifies."""
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


async def notify(
    db: AsyncSession,
    organization_id: uuid.UUID,
    *,
    subject: str,
    heading: str,
    intro: str,
    bullets: Sequence[str] = (),
    closing: str = "",
    action_label: str = "Add credit",
    action_path: str = WALLET_PATH,
    notification_body: Optional[str] = None,
) -> None:
    """Email the owners and leave an in-app notification. Never raises."""
    try:
        recipients = await _recipients(db, organization_id)
        if not recipients:
            return
        for user in recipients:
            db.add(
                Notification(
                    user_id=user.id,
                    type="billing",
                    title=heading,
                    body=notification_body or intro,
                    data={"action_url": action_path},
                )
            )
        emails = [user.email for user in recipients]
        await db.commit()

        from app.services.email.service import email_service

        for email in emails:
            await email_service.send_billing_notice(
                to_email=email,
                subject=subject,
                heading=heading,
                intro=intro,
                bullets=list(bullets),
                closing=closing,
                action_url=_url(action_path),
                action_label=action_label,
            )
    except Exception as exc:  # noqa: BLE001 — a notice must not break what triggered it
        try:
            await db.rollback()
        except Exception:  # pragma: no cover - defensive
            pass
        logger.error(f"Could not send a wallet notice to org {organization_id}: {exc}")


async def after_movement(db: AsyncSession, movement: Optional[wallet_service.Movement]) -> None:
    """Follow-ups for a committed wallet movement: the notice it earned, and
    an automatic top-up if the balance has fallen under the owner's threshold.

    Call it only after the commit. Safe to call with ``None``.
    """
    if movement is None:
        return
    organization_id = movement.organization_id
    balance = movement.balance_cents
    currency = movement.currency
    auto_on = movement.auto_recharge_ready

    if movement.wants_recharge:
        try:
            from app.services.billing import wallet_topups

            wallet_topups.schedule_auto_recharge(organization_id)
        except Exception as exc:  # noqa: BLE001
            logger.error(f"Could not start auto-recharge for org {organization_id}: {exc}")

    if movement.notice == NOTICE_EMPTY:
        await notify(
            db,
            organization_id,
            subject="Your Voicecon balance has run out",
            heading="Your balance has run out",
            intro=(
                "Your Pay As You Go balance is used up, so your agents have stopped "
                "making and answering calls."
                + (" We are topping it up from your saved card now." if auto_on else "")
            ),
            bullets=[
                "Add credit and calls start again straight away.",
                "Your agents, phone numbers and call history are not affected.",
            ],
            notification_body="Calls are paused. Add credit to switch them back on.",
        )
    elif movement.notice == NOTICE_LOW and not auto_on:
        # With auto-recharge on, the card is about to be charged; a "running
        # low" email on top of the receipt is noise.
        await notify(
            db,
            organization_id,
            subject="Your Voicecon balance is running low",
            heading="Your balance is running low",
            intro=(
                f"You have {wallet_service.format_money(balance, currency)} of credit left. "
                "When it runs out your agents stop making and answering calls until you add more."
            ),
            bullets=["Add credit now, or turn on auto-recharge so it never runs out."],
            notification_body=(
                f"{wallet_service.format_money(balance, currency)} left. Add credit to keep calls running."
            ),
        )


async def topup_received(
    db: AsyncSession,
    organization_id: uuid.UUID,
    *,
    amount_cents: int,
    balance_cents: int,
    currency: str = "usd",
    automatic: bool = False,
) -> None:
    amount = wallet_service.format_money(amount_cents, currency)
    balance = wallet_service.format_money(balance_cents, currency)
    await notify(
        db,
        organization_id,
        subject=f"{amount} of credit added to your Voicecon balance",
        heading="Credit added",
        intro=(
            f"{'Auto-recharge added' if automatic else 'We added'} {amount} to your balance. "
            f"Your balance is now {balance}."
        ),
        bullets=(
            ["You can change or switch off auto-recharge under Settings, Billing."]
            if automatic
            else []
        ),
        action_label="View balance",
        notification_body=f"{amount} added. Balance: {balance}.",
    )


async def auto_recharge_failed(
    db: AsyncSession, organization_id: uuid.UUID, *, switched_off: bool
) -> None:
    await notify(
        db,
        organization_id,
        subject="We couldn't top up your Voicecon balance",
        heading="Auto-recharge didn't go through",
        intro=(
            "We tried to charge your saved card to top up your balance, but the payment "
            "was not approved."
            + (
                " Auto-recharge has been switched off after several failed attempts."
                if switched_off
                else ""
            )
        ),
        bullets=[
            "Add credit with your card to keep calls running.",
            "Paying by card again also updates the card auto-recharge uses.",
        ],
        notification_body="Your saved card was declined. Add credit to keep calls running.",
    )


async def plan_started(db: AsyncSession, organization_id: uuid.UUID, *, plan_name: str, balance_cents: int, currency: str = "usd") -> None:
    balance = wallet_service.format_money(balance_cents, currency)
    funded = balance_cents > 0
    await notify(
        db,
        organization_id,
        subject=f"You're now on {plan_name}",
        heading=f"Welcome to {plan_name}",
        intro=(
            f"Your workspace is on {plan_name}. There is no monthly fee: calls are paid "
            f"for from your balance, which is {balance}."
        ),
        bullets=(
            ["Your agents and workflows are switched on."]
            if funded
            else ["Add credit to start making and answering calls."]
        ),
        action_label="View balance" if funded else "Add credit",
        notification_body=(
            f"You're on {plan_name}. Balance: {balance}."
            if funded
            else f"You're on {plan_name}. Add credit to start taking calls."
        ),
    )


async def refund_applied(
    db: AsyncSession,
    organization_id: uuid.UUID,
    *,
    amount_cents: int,
    balance_cents: int,
    currency: str = "usd",
) -> None:
    await notify(
        db,
        organization_id,
        subject="A Voicecon top-up was refunded",
        heading="A top-up was refunded",
        intro=(
            f"{wallet_service.format_money(amount_cents, currency)} was returned to your card, "
            f"so the same amount has been taken off your balance. Your balance is now "
            f"{wallet_service.format_money(balance_cents, currency)}."
        ),
        action_label="View balance",
    )
