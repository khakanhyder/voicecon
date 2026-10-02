# Pay As You Go

A prepaid plan beside the four subscriptions. No monthly fee: the workspace owner adds credit
to a wallet and each call minute is deducted from it. Built 2 October 2026.

## How it works for the customer

1. **Trial first (unchanged).** A new workspace still starts on the 14-day free trial.
2. **Choosing the plan.** Pay As You Go is a card on the landing page, the onboarding pricing
   step and Settings → Billing. Choosing it opens "Add credit"; the first top-up is what starts
   the plan. A trial, a lapsed account or a new workspace switches at once.
3. **Calls.** Each call is charged per started minute when it ends. A call cannot start unless
   the balance covers a minute, and a live call is ended politely when the credit set aside
   for it runs out.
4. **Balance card.** Settings → Billing shows the balance, what it buys, auto-recharge and the
   full history of top-ups, call charges, phone number fees, refunds and adjustments.
5. **Notices.** One email and in-app notification when the balance runs low, one when it runs
   out. A dashboard banner says the same.
6. **Switching.** Subscription → Pay As You Go takes effect when the paid period ends (and can
   be undone until then). Pay As You Go → subscription takes effect at checkout. Credit is
   kept across both.

## Defaults (all editable in Admin → Plans & Pricing → Pay As You Go)

| Setting | Default |
| --- | --- |
| Price per call minute | $0.35 |
| Phone number, per 30 days | $2.00 |
| Top-up amounts | $10, $25, $50, $100 |
| Smallest / largest top-up | $10 / $1,000 |
| Low-balance warning | below $5 |
| Features and limits | Same as Starter; 2 calls at once |

Credit does not expire. There is no self-service refund; staff can add or remove credit under
Admin → Organizations → (organization) → Pay As You Go balance, with a reason.

## Where the code is

| Area | File |
| --- | --- |
| Plan definition and rate | `backend/app/services/billing/catalog.py` (`PAYG_BILLING`) |
| Wallet, ledger, call reservations | `backend/app/services/billing/wallet.py` |
| Top-ups, refunds, auto-recharge | `backend/app/services/billing/wallet_topups.py` |
| Plan activation, scheduled switch, number fees | `backend/app/services/billing/prepaid.py` |
| Call charge | `backend/app/services/billing/usage_tracker.py` |
| Call start / in-call stop | `billing/call_credit.py`, `websocket/voice_session.py` (`_balance_guard`) |
| Customer API | `backend/app/api/v1/endpoints/wallet.py` (`/billing/wallet/*`) |
| Admin API | `backend/app/api/v1/endpoints/admin/wallet.py` |
| Tables | `wallets`, `wallet_transactions` (migration `0036_payg_wallet`) |
| Screens | `frontend/src/components/billing/{WalletCard,TopUpModal,PaygPlanCard}.tsx` |

Rules the code keeps:

- The balance only changes together with a ledger row (`wallet.apply`). The reconciler checks
  every 15 minutes that each balance equals the sum of its ledger and logs any mismatch.
- Every credit and charge has a unique idempotency key (the payment id, the call id), so a
  repeated webhook or carrier callback cannot apply twice.
- The wallet is credited only when the provider confirms payment, never from the browser's
  return page.

## Deploying

1. Deploy the backend before the frontend. `start.sh` runs `alembic upgrade head`, which
   creates the two tables; the plan row is seeded on startup.
2. **Polar** (the active provider): in Admin → Plans & Pricing, press **Create in Polar** on
   the Pay As You Go card. This creates the one-time "call credit" product top-ups are sold as.
   Until it exists, the Add credit dialog says payments are not available.
3. **Stripe** (if it becomes the provider): add these events to the webhook endpoint:
   `payment_intent.succeeded`, `charge.refunded`, `charge.dispute.created`,
   `charge.dispute.funds_withdrawn`, `charge.dispute.closed`. A restricted key also needs write
   access to PaymentIntents.
4. Marketing pages are cached for 60 seconds per route; load `/` and `/pricing` twice after the
   deploy to see the new card.

## Provider differences

| | Stripe | Polar |
| --- | --- | --- |
| Top-up | Card form in the app, with 3-D Secure | Hosted checkout, amount fixed by us |
| Sales tax | Not added | Added by Polar on top; only the net amount becomes credit |
| Auto-recharge | Yes (saved card, charged off-session) | No: Polar cannot charge a saved card later |

## Not verified against real providers

Local keys are placeholders. Verified with tests and a live run against the local API and
database, with this side playing the provider:

- Polar: signed `order.paid` / `order.refunded` webhooks were sent to the real endpoint. The
  hosted checkout call itself and Polar's real payload were not exercised.
- Stripe: PaymentIntent creation, 3-D Secure, off-session auto-recharge, refunds and disputes
  were tested with a fake Stripe only.
- The in-call stop was not tested on a live phone call.

Run a sandbox top-up, a refund and one short real call on each provider before launch.

## Not included

- Subscription overage is still priced but not charged (unchanged).
- Affiliates earn no commission on top-ups.
- The chat widget and browser test conversations are not metered on any plan, including this one.
