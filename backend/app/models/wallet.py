"""
The prepaid wallet behind the Pay As You Go plan.

Two tables, and they have different jobs:

* :class:`Wallet` — one row per organization, holding the *current* balance and
  the workspace's wallet settings (auto-recharge, the saved card).
* :class:`WalletTransaction` — the ledger. Every credit and debit is one row,
  and rows are only ever inserted. The balance on the wallet is a materialised
  sum of this table; the reconciler checks that the two still agree.

Money is whole minor units (cents) in integers. Nothing here is a float.
"""

from datetime import datetime
from typing import Optional
import uuid

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

# ---- Transaction types ----
# What moved the balance. The sign lives on ``amount_cents``; the type says why.
TXN_TOPUP = "topup"              # the customer paid in
TXN_USAGE = "usage"              # call minutes
TXN_NUMBER_FEE = "number_fee"    # monthly rent of a Voicecon phone number
TXN_REFUND = "refund"            # a top-up refunded or charged back at the provider
TXN_ADJUSTMENT = "adjustment"    # staff added or removed credit, with a reason

TRANSACTION_TYPES = (TXN_TOPUP, TXN_USAGE, TXN_NUMBER_FEE, TXN_REFUND, TXN_ADJUSTMENT)

# ---- Low-balance notice levels ----
# Which notice the owners have already had, so a notice is sent when a
# threshold is crossed and not again on every call after it.
NOTICE_NONE = "none"
NOTICE_LOW = "low"
NOTICE_EMPTY = "empty"


class Wallet(Base):
    """An organization's prepaid balance."""

    __tablename__ = "wallets"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("organizations.id"), unique=True, nullable=False
    )

    #: Current balance in minor units. May dip slightly below zero (a call that
    #: ran a few seconds past what was reserved, a refund of spent credit); a
    #: balance at or below zero blocks new calls.
    balance_cents: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="usd", nullable=False)

    # Auto-recharge: when the balance falls below the threshold, charge the
    # saved card for the amount. Only where the provider can charge a saved
    # card without the customer present (Stripe).
    auto_recharge_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    auto_recharge_threshold_cents: Mapped[Optional[int]] = mapped_column(Integer)
    auto_recharge_amount_cents: Mapped[Optional[int]] = mapped_column(Integer)
    #: When the last automatic charge was started. Doubles as the "one at a
    #: time" guard: a second attempt is not started while one is recent.
    auto_recharge_attempted_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    #: Consecutive failed automatic charges. Auto-recharge switches itself off
    #: after a few, rather than hammering a card the bank keeps declining.
    auto_recharge_failures: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # The card saved for auto-recharge. Only ids and what is printed on a
    # receipt — card numbers never reach this app.
    stripe_customer_id: Mapped[Optional[str]] = mapped_column(String(255))
    stripe_payment_method_id: Mapped[Optional[str]] = mapped_column(String(255))
    card_brand: Mapped[Optional[str]] = mapped_column(String(30))
    card_last4: Mapped[Optional[str]] = mapped_column(String(4))

    #: none | low | empty — see the NOTICE_* constants.
    notice_level: Mapped[str] = mapped_column(String(10), default=NOTICE_NONE, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    def __repr__(self):
        return f"<Wallet org={self.organization_id} balance={self.balance_cents}>"


class WalletTransaction(Base):
    """One movement of a wallet's balance.

    Append-only: rows are never updated or deleted. A mistake is corrected by a
    new row in the other direction, so the history always explains the balance.
    """

    __tablename__ = "wallet_transactions"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    wallet_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("wallets.id"), nullable=False
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("organizations.id"), nullable=False
    )

    #: See TRANSACTION_TYPES.
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    #: Signed: positive adds credit, negative spends it.
    amount_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    #: The wallet's balance once this row was applied.
    balance_after_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="usd", nullable=False)

    #: A sentence for the customer's history, e.g. "Call to +1 415 555 0100, 3 min".
    description: Mapped[Optional[str]] = mapped_column(String(255))

    #: What this row is about: ``call`` + the call id, ``stripe_payment_intent``
    #: + ``pi_…``, ``polar_order`` + the order id, ``phone_number`` + its id.
    reference_type: Mapped[Optional[str]] = mapped_column(String(40))
    reference_id: Mapped[Optional[str]] = mapped_column(String(255))
    #: Our own id for a top-up, set when the checkout is created, so the
    #: return page can ask "has this one landed yet?".
    client_ref: Mapped[Optional[str]] = mapped_column(String(64), index=True)

    #: The exactly-once guard. Unique, so a repeated webhook or a repeated
    #: carrier callback cannot credit or charge twice: the second insert fails.
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(255), unique=True)

    #: user | system | stripe | polar | admin
    actor_type: Mapped[str] = mapped_column(String(20), default="system", nullable=False)
    actor_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid(as_uuid=True))

    #: Anything else worth keeping: minutes and rate for usage, the receipt
    #: link for a top-up, the reason for an adjustment.
    details: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    def __repr__(self):
        return f"<WalletTransaction {self.type} {self.amount_cents}>"


Index("idx_wallet_txn_org_created", WalletTransaction.organization_id, WalletTransaction.created_at)
Index("idx_wallet_txn_wallet", WalletTransaction.wallet_id)
Index("idx_wallet_txn_reference", WalletTransaction.reference_type, WalletTransaction.reference_id)
