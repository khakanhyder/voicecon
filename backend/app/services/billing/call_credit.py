"""
Setting credit aside for a call on the prepaid (Pay As You Go) plan.

A thin layer over ``wallet.reserve_for_call`` for the three places a call
starts — the carrier's answer webhook and the two dial endpoints — so they all
treat a wallet that cannot pay the same way. For a workspace on a subscription
or a trial every function here does nothing.
"""
from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.billing import wallet as wallet_service

logger = logging.getLogger(__name__)

#: The shortest "longest call" credit is ever reserved against.
_MIN_CALL_SECONDS = 60
#: An agent with no maximum set runs for at most this long.
_DEFAULT_CALL_SECONDS = 1800

#: How long before its reserved credit runs out a live call starts saying
#: goodbye, so the goodbye and the hang-up fit inside minutes already paid for.
END_MARGIN_SECONDS = 12


def max_call_seconds(agent) -> int:
    return max(int(getattr(agent, "max_call_duration", None) or _DEFAULT_CALL_SECONDS), _MIN_CALL_SECONDS)


async def reserve(db: AsyncSession, call, agent) -> bool:
    """Reserve credit for ``call``. ``False`` means the wallet cannot pay for a
    first minute and the call must not go ahead; the call row is closed out so
    it does not count as live.

    An unexpected error lets the call through: a fault in the meter should not
    take a phone line down, and the call is still charged when it ends.
    """
    try:
        await wallet_service.reserve_for_call(db, call.id, max_seconds=max_call_seconds(agent))
        return True
    except wallet_service.InsufficientBalance:
        logger.info(
            f"Declining {call.direction} call {call.id} for org {call.organization_id}: "
            "insufficient_balance"
        )
        call.status = "missed" if call.direction == "inbound" else "failed"
        call.ended_at = datetime.utcnow()
        call.call_metadata = {
            **(call.call_metadata or {}),
            "declined_reason": "insufficient_balance",
        }
        await db.commit()
        return False
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Could not reserve credit for call {call.id}: {exc}", exc_info=True)
        try:
            # A rollback expires what the caller has loaded; load it again so
            # the request can carry on with these objects.
            await db.rollback()
            await db.refresh(call)
            await db.refresh(agent)
        except Exception:  # pragma: no cover - defensive
            pass
        return True


async def reserve_or_refuse(db: AsyncSession, call, agent) -> None:
    """:func:`reserve`, raising the 402 the dashboard turns into "Add credit"."""
    if await reserve(db, call, agent):
        return
    from app.core.entitlement_guard import REASON_BALANCE, EntitlementError
    from app.services.billing.entitlements import resolve_entitlements

    raise EntitlementError(
        message=wallet_service.INSUFFICIENT_BALANCE,
        reason=REASON_BALANCE,
        entitlements=await resolve_entitlements(db, call.organization_id),
    )


async def extend(call_id, *, max_seconds: int) -> int:
    """Ask for more credit for a call that is about to run out of it.

    Returns the new total the call may run for, in seconds, or ``0`` when
    there is nothing more (or the wallet could not be read — a call that cannot
    be shown to be paid for ends). Opens its own database session: the live
    call's session is busy with the call.
    """
    from app.database import get_db_session

    try:
        async with get_db_session() as db:
            total = await wallet_service.reserve_for_call(
                db, call_id, max_seconds=max_seconds, extend=True
            )
            return int(total or 0)
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Could not extend the credit reserved for call {call_id}: {exc}")
        return 0
