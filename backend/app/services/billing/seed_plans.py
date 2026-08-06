"""
Seed default subscription plans (the two plans shown on the Pricing screen).

Two jobs, both idempotent and both run at startup:

1. **Create** the default plans when the table is empty. When Stripe is
   configured it creates real products/prices; otherwise it stores unique
   placeholder ids so the pricing page works offline and the ids are backfilled
   later at checkout time (see ``StripeService.ensure_stripe_price``).
2. **Backfill** the enforcement fields on plans that already exist. Rows seeded
   before entitlements existed have no ``slug``, ``tier`` or ``entitlements``
   document, and without those every gate in the product would resolve to "not
   included" — so this is not optional tidying, it is what stops an upgrade
   shipping as an outage.
"""
import logging
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.subscription import SubscriptionPlan
from app.services.billing import catalog

logger = logging.getLogger(__name__)


# Plan definitions mirroring the Figma "Pricing and Plans" screen.
DEFAULT_PLANS = [
    {
        "slug": "sales-chatbot",
        "name": "Sales Chatbot",
        "tier": 1,
        "description": "Custom phone number, CRM integrations, scheduling & follow-up automation.",
        "price_monthly": Decimal("119.00"),
        "price_yearly": Decimal("1071.00"),  # ~25% off (Save 25% toggle)
        "included_minutes": 1000,
        "included_calls": 350,
        "max_agents": 1,
        "max_phone_numbers": 1,
        "max_knowledge_bases": 1,
        "sort_order": 1,
        "features": {
            "highlights": [
                "Custom Phone Number",
                "Seamless CRM Integrations (Salesforce, MLS, Zillow, and more)",
                "Scheduling & Follow-Up Automation",
                "Outbound & Inbound Calls with Real-Time Conversational AI",
                "350 Calls, 600 Texts, 2,500 Emails/Month",
            ]
        },
    },
    {
        "slug": "voice-ai",
        "name": "Voice AI",
        "tier": 2,
        "description": "Everything in Sales Chatbot, plus multiple numbers, meetings & lead scoring.",
        "price_monthly": Decimal("359.00"),
        "price_yearly": Decimal("3231.00"),  # ~25% off
        "included_minutes": 3000,
        "included_calls": 600,
        "max_agents": 5,
        "max_phone_numbers": 5,
        "max_knowledge_bases": 5,
        "sort_order": 2,
        "features": {
            "highlights": [
                "Everything in Sales Chatbot, plus:",
                "Multiple Phone Numbers for Campaigns",
                "Virtual Meetings & Note Taking",
                "Lead Scoring & Real-Time Data Updates (Schools, Neighborhoods, etc.)",
                "600 Calls, 1,000 Texts, 5,000 Emails/Month",
            ]
        },
    },
]

#: Plan a card-free trial is attached to. Deliberately the *top* plan: trials
#: convert on feature discovery, so trialling the cheaper plan means nobody ever
#: sees what the expensive one does. Consumption is what costs us money, and the
#: trial's own limits (``catalog.TRIAL_ENTITLEMENTS``) cap that hard.
TRIAL_PLAN_SLUG = "voice-ai"


def _slug_for(plan: SubscriptionPlan) -> str:
    """Best-effort slug for a plan seeded before slugs existed."""
    name = (plan.name or "").lower()
    if "voice" in name:
        return "voice-ai"
    if "chatbot" in name or "sales" in name:
        return "sales-chatbot"
    return name.replace(" ", "-") or "plan"


async def backfill_plan_entitlements(db: AsyncSession) -> int:
    """Give existing plans a slug, tier and entitlement document.

    Runs on every startup and touches only what is missing, so it is safe to
    leave in place permanently and safe to run against a database an operator
    has since customised by hand.
    """
    result = await db.execute(select(SubscriptionPlan))
    plans = result.scalars().all()

    tiers = {"sales-chatbot": 1, "voice-ai": 2}
    updated = 0

    for plan in plans:
        changed = False

        if not plan.slug:
            plan.slug = _slug_for(plan)
            changed = True

        if not plan.tier:
            plan.tier = tiers.get(plan.slug, 0)
            changed = True

        if not plan.entitlements:
            document = catalog.entitlements_for_plan(plan.slug)
            # Respect any per-plan capacity an operator set in the database
            # rather than blindly stamping the catalogue defaults over it.
            limits = dict(document["limits"])
            limits[catalog.LIMIT_AGENTS] = plan.max_agents
            limits[catalog.LIMIT_PHONE_NUMBERS] = plan.max_phone_numbers
            limits[catalog.LIMIT_KNOWLEDGE_BASES] = plan.max_knowledge_bases
            limits[catalog.LIMIT_MINUTES] = plan.included_minutes
            limits[catalog.LIMIT_CALLS] = plan.included_calls
            plan.entitlements = {
                "features": dict(document["features"]),
                "limits": limits,
                "overage": {
                    "allowed": True,
                    "per_minute": float(plan.overage_rate_per_minute),
                    "per_call": float(plan.overage_rate_per_call),
                },
            }
            changed = True

        if not plan.trial_days:
            plan.trial_days = 7
            changed = True

        if changed:
            updated += 1

    if updated:
        await db.commit()
        logger.info(f"Backfilled entitlements on {updated} subscription plan(s)")
    return updated


async def seed_default_plans(db: AsyncSession) -> int:
    """Create the default plans if none exist. Returns the number created."""
    existing = await db.execute(select(SubscriptionPlan.id).limit(1))
    if existing.scalar_one_or_none() is not None:
        # Plans exist, but they may predate entitlements.
        await backfill_plan_entitlements(db)
        return 0

    # Optionally create real Stripe products/prices when configured.
    stripe_service = None
    try:
        from app.core.config import settings

        if settings.stripe_configured:
            from app.services.billing import StripeService

            stripe_service = StripeService(
                api_key=settings.stripe_secret_key,
                webhook_secret=settings.STRIPE_WEBHOOK_SECRET or "not_configured",
            )
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning(f"Stripe not available for seeding, using placeholders: {exc}")
        stripe_service = None

    created = 0
    for spec in DEFAULT_PLANS:
        slug = spec["slug"]
        product_id = f"local_{slug}"
        price_id = f"local_{slug}_monthly"

        if stripe_service is not None:
            try:
                import asyncio
                import stripe

                product = await asyncio.to_thread(
                    stripe.Product.create,
                    name=spec["name"],
                    description=spec["description"],
                )
                product_id = product.id
                price = await asyncio.to_thread(
                    stripe.Price.create,
                    product=product_id,
                    unit_amount=int(spec["price_monthly"] * 100),
                    currency="usd",
                    recurring={"interval": "month"},
                )
                price_id = price.id
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning(
                    f"Failed to create Stripe product for {slug}, using placeholder: {exc}"
                )

        entitlements = catalog.entitlements_for_plan(slug)
        plan = SubscriptionPlan(
            slug=slug,
            name=spec["name"],
            description=spec["description"],
            tier=spec["tier"],
            stripe_product_id=product_id,
            stripe_price_id=price_id,
            price_monthly=spec["price_monthly"],
            price_yearly=spec["price_yearly"],
            included_minutes=spec["included_minutes"],
            included_calls=spec["included_calls"],
            max_agents=spec["max_agents"],
            max_phone_numbers=spec["max_phone_numbers"],
            max_knowledge_bases=spec["max_knowledge_bases"],
            features=spec["features"],
            entitlements={
                "features": dict(entitlements["features"]),
                "limits": dict(entitlements["limits"]),
                "overage": dict(entitlements["overage"]),
            },
            trial_days=7,
            is_trialable=slug == TRIAL_PLAN_SLUG,
            sort_order=spec["sort_order"],
            is_active=True,
            is_public=True,
        )
        db.add(plan)
        created += 1

    await db.commit()
    logger.info(f"Seeded {created} default subscription plans")
    return created
