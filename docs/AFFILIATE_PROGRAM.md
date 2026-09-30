# Affiliate program

Partners refer customers by link or coupon and earn a commission on those
customers' **annual** payments. Staff run it from the admin console
(Growth → Affiliates); partners use their own portal at `/affiliate`.

## How it works

| Step | What happens |
|---|---|
| Invite | Admin creates the affiliate (email, name, commission %, optional coupon). They get an invite link to set a password. The console shows the link too, in case the email doesn't arrive. |
| Link | `https://voicecon.ai/?ref=CODE` (or `app.voicecon.ai/register?ref=CODE`). The code is stored for `cookie_days` in a cookie on `.voicecon.ai`, so it survives the hop from the landing site to the app. |
| Attribution | A **new** account created with a stored code is credited to that affiliate. A coupon applied in onboarding or at checkout credits a workspace that isn't referred yet. **First touch wins**, and it's once per workspace. Self-referral and existing paying customers are refused. |
| Coupon | Percent off, for annual plans only or for all plans, applied to the first payment, every payment, or N months. Stripe gets a coupon on the subscription; Polar gets a discount on the hosted checkout. New customers only. |
| Commission | Earned when a referred workspace pays a **yearly** invoice or order. Monthly payments never earn (a fixed rule). It is calculated on what was paid after the discount and before tax. |
| Hold | New commissions are `pending` for `hold_days` (the refund window), then become `approved`. The billing scheduler moves them. |
| Refund | Before payout, a refund shrinks or reverses the commission. After payout, a negative clawback is taken off the next payout. |
| Payout | Admin clicks **Pay** on the affiliate. This sends one Stripe Connect transfer for the whole approved balance, or records a manual payment with its reference. |

Admin-set rules (Program rules page):
- default commission %
- hold days
- minimum payout
- cookie days
- referral window: the first annual payment must come within N days of sign-up
- number of commissioned annual payments per customer: 1 = first only, blank = every renewal; each affiliate can override this
- eligible plans

## Before going live

1. **Stripe secret key must be set, even while Polar takes payments.** Payouts are Stripe Connect transfers from VoiceCon's Stripe balance. With Polar as the checkout provider, that balance only holds what you top up. A transfer that fails for low balance is marked failed, and its commissions return to the payable pool.
2. **Enable Connect** in the Stripe dashboard (Express accounts). For partners outside the platform's country, the account uses the *recipient* service agreement, which only works where Stripe supports cross-border payouts.
3. A **restricted key** (`rk_`) additionally needs write access to Coupons, Connected accounts (Accounts, Account links, Login links) and Transfers.
4. Add **`charge.refunded`** to the Stripe webhook's events. Polar's `order.refunded` is already handled. The Polar token needs `discounts:write`.
5. Optional: `LANDING_URL` sets the base of referral links. Without it, the base is `FRONTEND_URL` minus its `app.` prefix.
6. Migration `0030_affiliate_program` runs on deploy (`start.sh`).

## Not verified yet

- Nothing has run against a real Stripe Connect account or a real Polar discount. Before launch, do one sandbox run covering: connect → yearly checkout with coupon → commission → approve early → Stripe payout → refund → clawback.
- The Polar `refunded_amount` is assumed to exclude tax (Polar reports `refunded_tax_amount` separately).
- Stripe: if the webhook endpoint uses an API version where `charge.invoice` no longer exists (basil and later), refunds cannot be matched to an invoice, and are logged and skipped.

## Where the code is

- Models: `backend/app/models/affiliate.py`
- Rules: `backend/app/services/affiliates/` (`commissions.py` has the eligibility list)
- Admin API: `backend/app/api/v1/endpoints/admin/affiliates.py`
- Portal API: `backend/app/api/v1/endpoints/affiliate_portal.py`
- Webhook hooks: `stripe_service.record_affiliate_commission` and `_on_charge_refunded`; `polar_service._record_affiliate_commission` and `_reverse_affiliate_commission`
- Portal sign-in: `/auth/affiliate/*`. Its sessions carry scope `affiliate` and only reach `/api/v1/affiliate` (see `_enforce_session_scope`)
- Frontend: `src/app/affiliate/`, `src/app/admin/affiliates/`, `src/lib/referral.ts`, `src/components/billing/CouponField.tsx`
- Tests: `backend/tests/unit/test_affiliates.py`
