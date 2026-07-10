"""
Seed default subscription plans (the two plans shown on the Pricing screen).

Idempotent: skips entirely if any plan already exists. When Stripe is configured
it creates real Stripe products/prices; otherwise it stores unique placeholder
ids so the pricing page works offline and the ids are backfilled later at
checkout time (see ``StripeService.ensure_stripe_price``).
"""
import logging
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.subscription import SubscriptionPlan

logger = logging.getLogger(__name__)


# Plan definitions mirroring the Figma "Pricing and Plans" screen.
DEFAULT_PLANS = [
    {
        "slug": "sales-chatbot",
        "name": "Sales Chatbot",
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
                "Everything in Solo Starter, plus:",
                "Multiple Phone Numbers for Campaigns",
                "Virtual Meetings & Note Taking",
                "Lead Scoring & Real-Time Data Updates (Schools, Neighborhoods, etc.)",
                "600 Calls, 1,000 Texts, 5,000 Emails/Month",
            ]
        },
    },
]


async def seed_default_plans(db: AsyncSession) -> int:
    """Create the default plans if none exist. Returns the number created."""
    existing = await db.execute(select(SubscriptionPlan.id).limit(1))
    if existing.scalar_one_or_none() is not None:
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

        plan = SubscriptionPlan(
            name=spec["name"],
            description=spec["description"],
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
            sort_order=spec["sort_order"],
            is_active=True,
            is_public=True,
        )
        db.add(plan)
        created += 1

    await db.commit()
    logger.info(f"Seeded {created} default subscription plans")
    return created
