"""
Local QA helper: pretend a referred customer paid, was refunded, or waited out the hold.

Runs the same code the Stripe/Polar webhooks run (``affiliates.commissions``),
so the commission rules — annual-only, eligible plans, payment limits, the
referral window — apply exactly as they would for a real payment. Use it where
there are no working payment keys. Never run it against production.

    python -m scripts.simulate_affiliate_payment pay customer@example.com
    python -m scripts.simulate_affiliate_payment pay customer@example.com --period monthly
    python -m scripts.simulate_affiliate_payment pay customer@example.com --reason subscription_cycle
    python -m scripts.simulate_affiliate_payment refund customer@example.com --fraction 0.5
    python -m scripts.simulate_affiliate_payment mature        # end every hold period now
"""
import argparse
import asyncio
import logging
import sys
import warnings
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select, update  # noqa: E402

from app.database import AsyncSessionLocal, async_engine  # noqa: E402
from app.models.affiliate import COMMISSION_PENDING, AffiliateCommission, AffiliateReferral  # noqa: E402
from app.models.subscription import SubscriptionPlan  # noqa: E402
from app.models.user import User  # noqa: E402
from app.services.affiliates import commissions  # noqa: E402
from app.services.auth.verification import normalize_email  # noqa: E402


async def _referral(db, email: str):
    user = await db.scalar(select(User).where(User.email == normalize_email(email)))
    if user is None:
        print(f"No account with email {email}.")
        return None
    referral = await db.scalar(select(AffiliateReferral).where(AffiliateReferral.user_id == user.id))
    if referral is None:
        print(f"{email} was not referred by an affiliate (sign up with a ?ref= link or apply a coupon first).")
    return referral


async def pay(args) -> int:
    async with AsyncSessionLocal() as db:
        referral = await _referral(db, args.email)
        if referral is None:
            return 1
        plan = await db.scalar(select(SubscriptionPlan).where(SubscriptionPlan.slug == args.plan))
        if plan is None:
            print(f"No plan with slug {args.plan}.")
            return 1
        amount = Decimal(args.amount) if args.amount else (
            plan.price_yearly if args.period == "yearly" else plan.price_monthly
        )
        ref = f"simulated:{uuid.uuid4().hex[:12]}"
        now = datetime.utcnow()
        commission = await commissions.record_payment(
            db,
            commissions.Payment(
                provider="stripe",
                external_ref=ref,
                organization_id=referral.organization_id,
                plan_slug=plan.slug,
                billing_period=args.period,
                billing_reason=args.reason,
                base_amount=Decimal(amount),
                currency="usd",
                paid_at=now,
                service_period_end=now + timedelta(days=365 if args.period == "yearly" else 30),
            ),
        )
        await db.commit()
        if commission is None:
            print(f"Paid {amount} ({args.period}, {args.reason}) -> NO commission.")
        else:
            print(
                f"Paid {amount} ({args.period}, {args.reason}) -> commission {commission.amount} "
                f"[{commission.status}, payable {commission.available_at:%Y-%m-%d}] ref={ref}"
            )
    return 0


async def refund(args) -> int:
    async with AsyncSessionLocal() as db:
        referral = await _referral(db, args.email)
        if referral is None:
            return 1
        latest = await db.scalar(
            select(AffiliateCommission)
            .where(AffiliateCommission.referral_id == referral.id, AffiliateCommission.kind == "commission")
            .order_by(AffiliateCommission.earned_at.desc())
            .limit(1)
        )
        if latest is None:
            print("No commission to refund.")
            return 1
        await commissions.apply_refund(db, latest.external_ref, Decimal(args.fraction))
        await db.commit()
        await db.refresh(latest)
        print(f"Refunded {Decimal(args.fraction) * 100:.0f}% -> commission now {latest.amount} [{latest.status}]")
    return 0


async def mature(_args) -> int:
    async with AsyncSessionLocal() as db:
        await db.execute(
            update(AffiliateCommission)
            .where(AffiliateCommission.status == COMMISSION_PENDING)
            .values(available_at=datetime.utcnow())
        )
        moved = await commissions.mature(db)
        await db.commit()
        print(f"{moved} commission(s) moved from pending to approved.")
    return 0


def _quiet_logs() -> None:
    """Hide SQL echo; print the commission module's reason for skipping a payment."""
    warnings.filterwarnings("ignore", category=DeprecationWarning)
    async_engine.echo = False  # DEBUG=true in .env turns SQL echo on
    reasons = logging.getLogger("app.services.affiliates.commissions")
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("  · %(message)s"))
    reasons.addHandler(handler)
    reasons.setLevel(logging.INFO)
    reasons.propagate = False


def main() -> int:
    _quiet_logs()
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("pay", help="simulate a paid invoice for a referred customer")
    p.add_argument("email")
    p.add_argument("--period", choices=["yearly", "monthly"], default="yearly")
    p.add_argument("--plan", default="growth")
    p.add_argument("--amount", help="what was paid after discount, before tax (default: the plan price)")
    p.add_argument(
        "--reason", default="subscription_create",
        choices=["subscription_create", "subscription_cycle", "subscription_update"],
    )
    r = sub.add_parser("refund", help="refund the customer's latest commissioned payment")
    r.add_argument("email")
    r.add_argument("--fraction", default="1", help="share refunded so far, 0..1 (default: full)")
    sub.add_parser("mature", help="end every hold period now")
    args = parser.parse_args()
    return asyncio.run({"pay": pay, "refund": refund, "mature": mature}[args.command](args))


if __name__ == "__main__":
    raise SystemExit(main())
