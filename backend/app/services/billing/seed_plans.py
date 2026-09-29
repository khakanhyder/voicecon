"""
Seed the subscription plans shown on the pricing screens.

Two jobs, both idempotent and both run at startup:

1. **Create** any plan in :data:`DEFAULT_PLANS` whose slug is missing — on an
   empty table and on a database that predates a plan alike. When Stripe is
   configured it creates real products/prices; otherwise it stores unique
   placeholder ids so the pricing page works offline and the ids are backfilled
   later at checkout time (see ``StripeService.ensure_stripe_price``). The
   first time the current plans are created, the launch plans they replace are
   retired: hidden from sale, but left in place for anyone subscribed to them.
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


# From "VoiceCon Pricing Packages — Final" (29 Sep 2026). Pay-As-You-Go is not
# offered (the free trial covers trying the product) and Enterprise is sold by
# contract, so neither is a row here. Yearly prices are the per-month yearly
# rate times twelve.
#
# ``features`` is the marketing column. Plan cards build their bullets from the
# entitlements document, not from ``highlights``; ``support`` and ``popular``
# are read by the cards directly (frontend/src/lib/pricing.ts).
DEFAULT_PLANS = [
    {
        "slug": "starter",
        "name": "Starter",
        "tier": 1,
        "description": "For a solo business owner who wants every call answered.",
        "price_monthly": Decimal("49.00"),
        "price_yearly": Decimal("468.00"),  # $39/mo billed yearly
        "included_minutes": 200,
        "overage_rate_per_minute": Decimal("0.30"),
        "sort_order": 1,
        "features": {
            "support": "Email support",
            "highlights": [
                "Inbound calls, 24/7 answering",
                "Appointment booking via Google Calendar",
                "Call recordings and transcripts",
            ],
        },
    },
    {
        "slug": "growth",
        "name": "Growth",
        "tier": 2,
        "description": "For clinics, salons and restaurants handling calls all day.",
        "price_monthly": Decimal("149.00"),
        "price_yearly": Decimal("1428.00"),  # $119/mo billed yearly
        "included_minutes": 750,
        "overage_rate_per_minute": Decimal("0.25"),
        "sort_order": 2,
        "features": {
            "support": "Priority email support",
            "popular": True,
            "highlights": [
                "Everything in Starter, plus:",
                "Outbound calls and transfer to a human",
                "All integrations, webhooks and custom tools",
                "API access",
            ],
        },
    },
    {
        "slug": "scale",
        "name": "Scale",
        "tier": 3,
        "description": "For sales teams running high call volume.",
        "price_monthly": Decimal("349.00"),
        "price_yearly": Decimal("3348.00"),  # $279/mo billed yearly
        "included_minutes": 2000,
        "overage_rate_per_minute": Decimal("0.20"),
        "sort_order": 3,
        "features": {
            "support": "Chat support and an onboarding call",
            "highlights": [
                "Everything in Growth, plus:",
                "Scheduled and cron workflows",
                "Custom voices",
            ],
        },
    },
    {
        "slug": "agency",
        "name": "Agency",
        "tier": 4,
        "description": "For agencies and resellers serving many clients.",
        "price_monthly": Decimal("499.00"),
        "price_yearly": Decimal("4788.00"),  # $399/mo billed yearly
        "included_minutes": 3000,
        "overage_rate_per_minute": Decimal("0.15"),
        "sort_order": 4,
        "features": {
            "support": "Slack support and an account manager",
            "highlights": [
                "Everything in Scale, plus:",
                "Unlimited AI agents",
            ],
        },
    },
]

#: Plans the pricing sheet replaced. Retired, never deleted: subscribers keep
#: them until they choose one of the current plans.
LEGACY_PLAN_SLUGS = ("sales-chatbot", "voice-ai")

#: Where retired plans sort, after every current plan.
_LEGACY_SORT_ORDER = 90

#: Plan a card-free trial is attached to: Growth, the plan the pricing page
#: recommends. The trial's own limits (``catalog.TRIAL_ENTITLEMENTS``) apply
#: whichever plan it is attached to.
TRIAL_PLAN_SLUG = catalog.TRIAL_PLAN_SLUG

_TIERS = {
    **{spec["slug"]: spec["tier"] for spec in DEFAULT_PLANS},
    "sales-chatbot": 1,
    "voice-ai": 2,
}


def _slug_for(plan: SubscriptionPlan) -> str:
    """Best-effort slug for a plan seeded before slugs existed."""
    name = (plan.name or "").lower()
    if "voice" in name:
        return "voice-ai"
    if "chatbot" in name or "sales" in name:
        return "sales-chatbot"
    return name.replace(" ", "-") or "plan"


#: Marketing bullets we shipped that quoted a monthly call allowance, mapped to
#: their replacements. Matched exactly so a bullet an operator has since edited
#: is left alone — this corrects our own stale copy, it does not own the column.
#: A value of ``None`` drops the bullet outright rather than rewording it.
_LEGACY_CALL_BULLETS = {
    "350 Calls, 600 Texts, 2,500 Emails/Month":
        "Unlimited Calls & Minutes, 600 Texts, 2,500 Emails/Month",
    "600 Calls, 1,000 Texts, 5,000 Emails/Month":
        "Unlimited Calls & Minutes, 1,000 Texts, 5,000 Emails/Month",
    # Retired 29 Sep 2026 (QA M6/M7, 25 Sep report): real-estate-specific
    # copy (MLS, Zillow, Schools, Neighborhoods) and numeric call/text/email
    # counts that can drift from the live entitlements document nothing here
    # keeps in sync — plus two features ("Virtual Meetings & Note Taking",
    # "Lead Scoring...") that were advertised but never actually built.
    "Seamless CRM Integrations (Salesforce, MLS, Zillow, and more)":
        "CRM Integrations",
    "Unlimited Calls & Minutes, 600 Texts, 2,500 Emails/Month":
        "Unlimited Calls & Minutes",
    "Unlimited Calls & Minutes, 1,000 Texts, 5,000 Emails/Month":
        "Unlimited Calls & Minutes",
    "Multiple Phone Numbers for Campaigns":
        "Multiple Phone Numbers",
    "Virtual Meetings & Note Taking": None,
    "Lead Scoring & Real-Time Data Updates (Schools, Neighborhoods, etc.)": None,
}


def _refresh_stale_copy(plan: SubscriptionPlan) -> bool:
    """Rewrite (or drop) pricing bullets per `_LEGACY_CALL_BULLETS`.

    Without this an existing install shows "Unlimited calls & minutes" and
    "350 Calls/Month" on the same card — and it does so on the screen where
    someone decides whether to pay. It's also how a feature that turned out
    to be unshipped, or copy nobody meant to keep public (MLS/Zillow), gets
    retired from installs that were already seeded before the source spec
    in `DEFAULT_PLANS` changed — that spec only applies to a brand-new table.
    """
    features = dict(plan.features or {})
    highlights = features.get("highlights")
    if not isinstance(highlights, list):
        return False

    replaced = []
    for line in highlights:
        if line in _LEGACY_CALL_BULLETS:
            new_line = _LEGACY_CALL_BULLETS[line]
            if new_line is not None:
                replaced.append(new_line)
        else:
            replaced.append(line)

    if replaced == highlights:
        return False

    features["highlights"] = replaced
    plan.features = features  # JSON column: reassign, do not mutate in place.
    return True


def _relax_stored_document(plan: SubscriptionPlan) -> bool:
    """Bring one stored entitlement document up to the current contract.

    Idempotent: it lifts the retired per-call ceiling, grants paid plans the
    phone-number purchase feature and drops SMS from the current plans,
    leaving every other key an
    operator may have tuned by hand exactly as it was found. Minutes are *not*
    touched — they are a real allowance again (pricing sheet, 29 Sep 2026), and
    lifting them here would undo it on every restart. Returns whether anything
    moved.

    ``plan.entitlements`` is a JSON column, so it is reassigned wholesale rather
    than mutated in place — SQLAlchemy does not track mutation inside a JSON
    value and the change would not be persisted.
    """
    document = dict(plan.entitlements or {})
    limits = dict(document.get("limits") or {})
    features = dict(document.get("features") or {})
    changed = False

    if catalog.LIMIT_CALLS in limits and limits[catalog.LIMIT_CALLS] != catalog.UNLIMITED:
        limits[catalog.LIMIT_CALLS] = catalog.UNLIMITED
        changed = True

    # Every paid plan may buy numbers; only the trial may not, and the trial
    # never reaches this function because it resolves from the catalogue.
    if features.get(catalog.PHONE_NUMBER_PURCHASE) is not True:
        features[catalog.PHONE_NUMBER_PURCHASE] = True
        changed = True

    # Text messages are not part of the current plans (29 Sep 2026). Rows
    # seeded before that carry an SMS allowance; drop it. Retired plans keep
    # theirs for the customers still on them.
    if plan.slug in catalog.PLAN_ENTITLEMENTS:
        if catalog.LIMIT_SMS in limits:
            del limits[catalog.LIMIT_SMS]
            changed = True
        if features.get(catalog.SMS):
            features[catalog.SMS] = False
            changed = True

    if changed:
        document["limits"] = limits
        document["features"] = features
        plan.entitlements = document
    return changed


def _fill_missing_keys(plan: SubscriptionPlan) -> bool:
    """Add feature and limit keys the stored document predates.

    A key added to the catalogue (``concurrent_calls``, ``custom_voices``) is
    absent from every document stored before it, and an absent limit reads as
    zero — so without this, adding a limit would lock every existing plan out
    of the thing it limits. Only missing keys are written, never changed ones,
    which is why this is safe on a plan a platform admin manages.
    """
    if not plan.entitlements:
        return False
    default = catalog.entitlements_for_plan(plan.slug)
    document = dict(plan.entitlements)
    changed = False
    for section in ("features", "limits", "overage"):
        stored = dict(document.get(section) or {})
        missing = {k: v for k, v in (default.get(section) or {}).items() if k not in stored}
        if missing:
            stored.update(missing)
            document[section] = stored
            changed = True
    if changed:
        plan.entitlements = document
    return changed


async def backfill_plan_entitlements(db: AsyncSession) -> int:
    """Give existing plans a slug, tier and entitlement document.

    Runs on every startup and touches only what is missing, so it is safe to
    leave in place permanently and safe to run against a database an operator
    has since customised by hand.
    """
    result = await db.execute(select(SubscriptionPlan))
    plans = result.scalars().all()

    updated = 0

    for plan in plans:
        changed = False

        # First: the slug decides which catalogue document fills the gaps.
        if not plan.slug:
            plan.slug = _slug_for(plan)
            changed = True

        if _fill_missing_keys(plan):
            changed = True

        # A platform admin owns this row now. Everything below re-syncs it to
        # the code's catalogue, which would silently undo their edit on the
        # next restart.
        if plan.admin_managed:
            if changed:
                updated += 1
            continue

        if not plan.tier:
            plan.tier = _TIERS.get(plan.slug, 0)
            changed = True

        if not plan.entitlements:
            document = catalog.entitlements_for_plan(plan.slug)
            # Respect any per-plan capacity an operator set in the database
            # rather than blindly stamping the catalogue defaults over it.
            limits = dict(document["limits"])
            limits[catalog.LIMIT_AGENTS] = plan.max_agents
            limits[catalog.LIMIT_PHONE_NUMBERS] = plan.max_phone_numbers
            limits[catalog.LIMIT_KNOWLEDGE_BASES] = plan.max_knowledge_bases
            plan.entitlements = {
                "features": dict(document["features"]),
                "limits": limits,
                "overage": {
                    "allowed": True,
                    "per_minute": float(plan.overage_rate_per_minute),
                },
            }
            changed = True

        else:
            # A plan seeded before the per-call cap was retired still has it
            # baked into its stored document, and the resolver reads the column
            # rather than the catalogue.
            if _relax_stored_document(plan):
                changed = True

        if _refresh_stale_copy(plan):
            changed = True

        # Trial length is owned by the row: platform admins set it from the
        # admin console (Plans & Pricing), and that must survive a restart. Only
        # a row with no usable value falls back to the catalogue default.
        if not plan.trial_days or plan.trial_days < 1:
            plan.trial_days = catalog.DEFAULT_TRIAL_DAYS
            changed = True

        if changed:
            updated += 1

    if updated:
        await db.commit()
        logger.info(f"Backfilled entitlements on {updated} subscription plan(s)")
    return updated


async def _stripe_for_seeding():
    """A Stripe client when Stripe is configured, else ``None`` (placeholders)."""
    try:
        from app.core.config import settings

        if settings.stripe_configured:
            from app.services.billing import StripeService

            return StripeService(
                api_key=settings.stripe_secret_key,
                webhook_secret=settings.STRIPE_WEBHOOK_SECRET or "not_configured",
            )
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning(f"Stripe not available for seeding, using placeholders: {exc}")
    return None


async def _create_plan(spec: dict, stripe_service) -> SubscriptionPlan:
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
    limits = entitlements["limits"]
    return SubscriptionPlan(
        slug=slug,
        name=spec["name"],
        description=spec["description"],
        tier=spec["tier"],
        stripe_product_id=product_id,
        stripe_price_id=price_id,
        price_monthly=spec["price_monthly"],
        price_yearly=spec["price_yearly"],
        included_minutes=spec["included_minutes"],
        included_calls=0,
        # Legacy columns, kept in step with the document for the admin editor.
        max_agents=limits[catalog.LIMIT_AGENTS],
        max_phone_numbers=limits[catalog.LIMIT_PHONE_NUMBERS],
        max_knowledge_bases=limits[catalog.LIMIT_KNOWLEDGE_BASES],
        overage_rate_per_minute=spec["overage_rate_per_minute"],
        overage_rate_per_call=Decimal("0"),
        features=spec["features"],
        entitlements={
            "features": dict(entitlements["features"]),
            "limits": dict(limits),
            "overage": dict(entitlements["overage"]),
        },
        trial_days=catalog.DEFAULT_TRIAL_DAYS,
        is_trialable=slug == TRIAL_PLAN_SLUG,
        sort_order=spec["sort_order"],
        is_active=True,
        is_public=True,
    )


def _retire_legacy_plan(plan: SubscriptionPlan) -> None:
    """Take a launch plan off sale without touching anyone subscribed to it.

    Subscribers resolve entitlements from this row, so it stays and keeps its
    document. ``is_active`` false keeps it out of checkout, change-plan and the
    trial; ``is_public`` false keeps it off every pricing page.
    """
    plan.is_active = False
    plan.is_public = False
    plan.is_trialable = False
    plan.sort_order = _LEGACY_SORT_ORDER + (plan.tier or 0)

    # Custom voices were never gated while these plans were on sale, so their
    # subscribers may rely on them; keep them working now that they are.
    document = dict(plan.entitlements or {})
    features = dict(document.get("features") or {})
    if features.get(catalog.CUSTOM_VOICE) is not True:
        features[catalog.CUSTOM_VOICE] = True
        document["features"] = features
        plan.entitlements = document


async def seed_default_plans(db: AsyncSession) -> int:
    """Create any current plan that is missing. Returns the number created.

    Also backfills existing rows, and — the first time the current plans are
    created on a database that has the launch plans — retires those.
    """
    result = await db.execute(select(SubscriptionPlan))
    existing = {plan.slug: plan for plan in result.scalars().all()}

    # Existing plans may predate entitlements or newer catalogue keys. Runs
    # before retirement so a retired plan still gets its missing keys.
    if existing:
        await backfill_plan_entitlements(db)

    missing = [spec for spec in DEFAULT_PLANS if spec["slug"] not in existing]
    if not missing:
        return 0

    stripe_service = await _stripe_for_seeding()
    for spec in missing:
        db.add(await _create_plan(spec, stripe_service))

    retired = []
    for slug in LEGACY_PLAN_SLUGS:
        plan = existing.get(slug)
        if plan is not None and (plan.is_active or plan.is_public):
            _retire_legacy_plan(plan)
            retired.append(plan.name)

    await db.commit()
    logger.info(f"Seeded {len(missing)} subscription plan(s)")
    if retired:
        logger.info(f"Retired launch plan(s) from sale: {', '.join(retired)}")
    return len(missing)
