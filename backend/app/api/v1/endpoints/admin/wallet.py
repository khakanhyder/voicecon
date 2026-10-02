"""Prepaid wallets (Pay As You Go): a workspace's balance, its ledger, and
adding or removing credit by hand."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.admin import audit, require_platform_admin
from app.database import get_db
from app.models.user import Organization
from app.models.wallet import WalletTransaction
from app.services.billing import wallet as wallet_service
from app.services.billing import wallet_topups
from app.services.billing.entitlements import invalidate_entitlements, resolve_entitlements

from ._common import PageParams, iso, paginated, parse_uuid

router = APIRouter()

#: The most credit one adjustment may add or remove. A typo guard, not a
#: policy: anything larger is almost certainly a misplaced decimal point.
MAX_ADJUSTMENT = 10_000


async def _org_or_404(db: AsyncSession, org_id: str) -> Organization:
    org = await db.get(Organization, parse_uuid(org_id, "organization"))
    if org is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    return org


def _transaction_view(row: WalletTransaction) -> dict:
    details = row.details or {}
    return {
        "id": str(row.id),
        "type": row.type,
        "amount": wallet_service.from_cents(row.amount_cents),
        "balance_after": wallet_service.from_cents(row.balance_after_cents),
        "description": row.description,
        "reference_type": row.reference_type,
        "reference_id": row.reference_id,
        "actor_type": row.actor_type,
        "reason": details.get("reason"),
        "admin_email": details.get("admin_email"),
        "created_at": iso(row.created_at),
    }


@router.get("/organizations/{org_id}/wallet")
async def get_organization_wallet(
    org_id: str,
    params: PageParams = Depends(),
    db: AsyncSession = Depends(get_db),
    _admin=Depends(require_platform_admin),
):
    """A workspace's balance and ledger, newest first."""
    org = await _org_or_404(db, org_id)
    wallet = await wallet_service.get_wallet(db, org.id)
    ent = await resolve_entitlements(db, org.id, fresh=True)
    billing = await wallet_service.billing_for_org(db, org.id)

    filters = [WalletTransaction.organization_id == org.id]
    total = int(
        (await db.execute(select(func.count(WalletTransaction.id)).where(*filters))).scalar() or 0
    )
    rows = (
        await db.execute(
            select(WalletTransaction)
            .where(*filters)
            .order_by(WalletTransaction.created_at.desc(), WalletTransaction.id.desc())
            .offset(params.offset)
            .limit(params.page_size)
        )
    ).scalars().all()
    ledger_total = int(
        (
            await db.execute(
                select(func.coalesce(func.sum(WalletTransaction.amount_cents), 0)).where(*filters)
            )
        ).scalar()
        or 0
    )
    balance = int(wallet.balance_cents) if wallet else 0
    return {
        "exists": wallet is not None,
        "prepaid": ent.is_prepaid,
        "balance": wallet_service.from_cents(balance),
        "held": wallet_service.from_cents(await wallet_service.held_cents(db, org.id)),
        "currency": (wallet.currency if wallet else None) or "usd",
        "per_minute": float(billing.get("per_minute") or 0),
        #: False means the balance and the ledger disagree — see the reconciler.
        "ledger_matches": ledger_total == balance,
        "auto_recharge": {
            "enabled": bool(wallet and wallet.auto_recharge_enabled),
            "threshold": wallet_service.from_cents(wallet.auto_recharge_threshold_cents)
            if wallet and wallet.auto_recharge_threshold_cents is not None
            else None,
            "amount": wallet_service.from_cents(wallet.auto_recharge_amount_cents)
            if wallet and wallet.auto_recharge_amount_cents is not None
            else None,
            "card_brand": wallet.card_brand if wallet else None,
            "card_last4": wallet.card_last4 if wallet else None,
            "failures": int(wallet.auto_recharge_failures or 0) if wallet else 0,
        },
        "transactions": paginated([_transaction_view(r) for r in rows], total, params),
    }


class AdjustBody(BaseModel):
    #: Positive adds credit, negative removes it. In the wallet's currency.
    amount: float
    reason: str = Field(..., min_length=3, max_length=500)


@router.post("/organizations/{org_id}/wallet/adjust")
async def adjust_organization_wallet(
    org_id: str,
    body: AdjustBody,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_platform_admin),
):
    """Add or remove credit by hand, with a reason.

    Written to the wallet's ledger as its own row and to the admin audit log,
    in one transaction. The balance may be taken below zero on purpose (to
    claw back credit given in error); that blocks calls until it is made good.
    """
    org = await _org_or_404(db, org_id)
    if not body.amount or abs(body.amount) > MAX_ADJUSTMENT:
        raise HTTPException(
            status_code=422,
            detail=f"Enter an amount between -{MAX_ADJUSTMENT:,} and {MAX_ADJUSTMENT:,}, other than zero.",
        )
    amount_cents = wallet_service.to_cents(body.amount)
    try:
        movement = await wallet_topups.adjust(
            db, org.id, amount_cents=amount_cents, reason=body.reason, admin=admin
        )
    except wallet_service.WalletError as exc:
        raise HTTPException(status_code=422, detail=exc.public_message)

    audit(
        db, admin, "wallet.adjust", target_type="organization", target_id=org.id,
        summary=(
            f"{'Added' if amount_cents > 0 else 'Removed'} "
            f"{wallet_service.format_money(abs(amount_cents))} of credit "
            f"{'to' if amount_cents > 0 else 'from'} {org.name}"
        ),
        details={
            "amount": wallet_service.from_cents(amount_cents),
            "balance_after": wallet_service.from_cents(movement.balance_cents),
            "reason": body.reason,
        },
        request=request,
    )
    await db.commit()
    invalidate_entitlements(org.id)

    # Added credit may be what a number on hold was waiting for.
    if amount_cents > 0:
        try:
            from app.services.telephony.number_reclaim import restore_numbers

            await restore_numbers(db, org.id)
        except Exception:  # noqa: BLE001 — the credit is in; the sweep will restore
            await db.rollback()

    return {
        "balance": wallet_service.from_cents(movement.balance_cents),
        "transaction": _transaction_view(movement.transaction),
    }
