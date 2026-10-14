"""
What a customer is shown about the price of a call.

A call carries two kinds of money:

* ``cost_stt`` / ``cost_llm`` / ``cost_tts`` / ``cost_telephony`` /
  ``cost_total`` — what the providers charge *Voicecon*. Internal: only the
  platform admin console shows them.
* ``billed_amount`` — what the *customer* was charged: the Pay As You Go wallet
  debit, at the per-minute rate set on the plan in /admin/plans when the call
  ended (``UsageTracker.record_call_usage``).

Only a Pay As You Go workspace pays per call, so only it is shown a price. A
subscription workspace pays for its plan, and its calls show no amount at all.
Customer endpoints keep the ``cost_total`` field name for the price so the
existing screens and CSV column keep working; the provider breakdown is always
blanked.
"""

from __future__ import annotations

import uuid
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.call import Call

#: The column customer-facing totals sum. Never ``Call.cost_total``.
PRICE_COLUMN = Call.billed_amount

_PROVIDER_COST_FIELDS = ("cost_stt", "cost_llm", "cost_tts", "cost_telephony")


async def shows_call_prices(db: AsyncSession, organization_id: uuid.UUID) -> bool:
    """Does this workspace pay per call (and so see what each call cost)?"""
    from app.services.billing.entitlements import resolve_entitlements

    try:
        ent = await resolve_entitlements(db, organization_id)
    except Exception:
        # Showing nothing is the safe failure: never leak internal costs.
        return False
    return bool(ent.is_prepaid)


def customer_price(call: Any, show: bool) -> Optional[float]:
    """The price of one call as the customer sees it, or ``None``."""
    if not show:
        return None
    amount = getattr(call, "billed_amount", None)
    return None if amount is None else float(amount)


def present_call(response: Any, call: Any, show: bool) -> Any:
    """Rewrite a ``CallResponse`` so it carries the price, not our costs."""
    for field in _PROVIDER_COST_FIELDS:
        setattr(response, field, None)
    response.cost_total = customer_price(call, show)
    return response


def present_total(value: Any, show: bool) -> Optional[float]:
    """A summed price for a summary card; ``None`` when prices are hidden."""
    if not show:
        return None
    return float(value or 0)
