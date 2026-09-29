"""Which payment provider new checkouts use, and whether it can take payments.

The admin console sets ``PAYMENT_PROVIDER`` (``stripe`` or ``polar``). It only
routes *new* checkouts: a subscription always stays with the provider it was
created on, so cancel, change-plan, reactivate and the billing portal dispatch
on ``Subscription.source``, never on this setting.
"""
from __future__ import annotations

from typing import List, Optional

from app.core.config import settings

STRIPE = "stripe"
POLAR = "polar"
PROVIDERS = (STRIPE, POLAR)
LABELS = {STRIPE: "Stripe", POLAR: "Polar"}

#: Keys each provider needs before it can be made active. The admin console
#: refuses to switch to a provider with any of these missing, and refuses to
#: remove one while its provider is active.
REQUIRED_KEYS = {
    STRIPE: ("STRIPE_SECRET_KEY", "STRIPE_PUBLISHABLE_KEY", "STRIPE_WEBHOOK_SECRET"),
    POLAR: ("POLAR_ACCESS_TOKEN", "POLAR_WEBHOOK_SECRET"),
}


def active_provider() -> str:
    return settings.payment_provider


def stripe_key_mode(key: Optional[str]) -> Optional[str]:
    """``live`` or ``test`` for a Stripe secret/restricted/publishable key."""
    key = (key or "").strip()
    for prefix in ("sk_", "rk_", "pk_"):
        if key.startswith(prefix + "live_"):
            return "live"
        if key.startswith(prefix + "test_"):
            return "test"
    return None


def stripe_mode_mismatch() -> Optional[str]:
    """Why the Stripe keys cannot work together, or None.

    The card is tokenised in the browser with the publishable key and charged
    on the server with the secret key. Keys from different modes live in
    different Stripe worlds, so every checkout would fail with "No such
    PaymentMethod" after the customer had typed their card.
    """
    secret = stripe_key_mode(settings.stripe_secret_key)
    publishable = stripe_key_mode(settings.STRIPE_PUBLISHABLE_KEY)
    if secret and publishable and secret != publishable:
        return (
            f"a {secret}-mode publishable key (pk_{secret}_…) to match the "
            f"{secret}-mode secret key; the publishable key saved is {publishable}-mode"
        )
    return None


def missing_for(provider: str) -> List[str]:
    """Human labels of what ``provider`` still needs. Empty means ready."""
    missing: List[str] = []
    if provider == STRIPE:
        if not settings.stripe_configured:
            missing.append("Stripe secret key (sk_… or rk_…)")
        if not settings.STRIPE_PUBLISHABLE_KEY:
            missing.append("Stripe publishable key")
        if not settings.STRIPE_WEBHOOK_SECRET:
            missing.append("Stripe webhook signing secret")
        mismatch = stripe_mode_mismatch()
        if mismatch:
            missing.append(mismatch)
    elif provider == POLAR:
        if not settings.polar_configured:
            missing.append("Polar access token")
        if not settings.POLAR_WEBHOOK_SECRET:
            missing.append("Polar webhook signing secret")
    else:
        missing.append(f"a known provider (got '{provider}')")
    return missing


def problem(provider: str) -> Optional[str]:
    missing = missing_for(provider)
    if not missing:
        return None
    return f"{LABELS.get(provider, provider)} is missing: {', '.join(missing)}."


def is_ready(provider: Optional[str] = None) -> bool:
    return not missing_for(provider or active_provider())
