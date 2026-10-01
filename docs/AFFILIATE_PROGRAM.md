# Affiliate program

Partners refer customers by link or coupon and earn a commission on those
customers' payments — on **annual plans, monthly plans or both**, chosen per
affiliate with a separate rate for each. Staff run it from the admin console
(Growth → Affiliates); partners use their own portal at `/affiliate`.

## How it works

| Step | What happens |
|---|---|
| Request (optional) | A visitor applies with the form at `/affiliate-program` (linked from the website footer). The request appears under Growth → Affiliate Requests, and every platform admin gets a notification in the console's bell and an email. An admin opens it and clicks **Create affiliate** — the normal affiliate form with the applicant filled in — or rejects it. Creating the affiliate approves the request. |
| Invite | Admin creates the affiliate (email, name, commission %, optional coupon), from a request or directly with **New affiliate**. They get an invite link to set a password. The console shows the link too, in case the email doesn't arrive. |
| Link | `https://voicecon.ai/?ref=CODE` (or `app.voicecon.ai/register?ref=CODE`). The code is stored for `cookie_days` in a cookie on `.voicecon.ai`, so it survives the hop from the landing site to the app. |
| Attribution | A **new** account created with a stored code is credited to that affiliate. A coupon applied in onboarding or at checkout credits a workspace that isn't referred yet. **First touch wins**, and it's once per workspace. Self-referral and existing paying customers are refused. |
| Coupon | Percent off, for annual plans only or for all plans, applied to the first payment, every payment, or N months. Stripe gets a coupon on the subscription; Polar gets a discount on the hosted checkout. New customers only. |
| Commission | Earned when a referred workspace pays an invoice or order whose billing period the affiliate earns on: **annual only** (default), **monthly only**, or **both**. Each has its own rate (monthly rate blank = same as annual). It is calculated on what was paid after the discount and before tax. Payments on a billing type the affiliate doesn't earn on are skipped. |
| Hold | New commissions are `pending` for `hold_days` (the refund window), then become `approved`. The billing scheduler moves them. |
| Refund | Before payout, a refund shrinks or reverses the commission. After payout, a negative clawback is taken off the next payout. |
| Payout | Admin clicks **Pay** on the affiliate. This sends one Stripe Connect transfer for the whole approved balance, or records a manual payment with its reference. |

Admin-set rules (Program rules page):
- default commission %
- hold days
- minimum payout
- cookie days
- referral window: the first annual payment must come within N days of sign-up
- number of commissioned **annual** payments per customer (1 = first only, blank = every renewal) and, separately, commissioned **monthly** payments per customer (default 12 = first year, blank = every month); each affiliate can override both
- eligible plans

## Before going live

1. **Stripe secret key must be set, even while Polar takes payments.** Payouts are Stripe Connect transfers from VoiceCon's Stripe balance. With Polar as the checkout provider, that balance only holds what you top up. A transfer that fails for low balance is marked failed, and its commissions return to the payable pool.
2. **Enable Connect** in the Stripe dashboard (Express accounts). For partners outside the platform's country, the account uses the *recipient* service agreement, which only works where Stripe supports cross-border payouts.
3. A **restricted key** (`rk_`) additionally needs write access to Coupons, Connected accounts (Accounts, Account links, Login links) and Transfers.
4. Add **`charge.refunded`** to the Stripe webhook's events. Polar's `order.refunded` is already handled. The Polar token needs `discounts:write`.
5. Optional: `LANDING_URL` sets the base of referral links. Without it, the base is `FRONTEND_URL` minus its `app.` prefix.
6. Migrations `0030_affiliate_program`, `0031_affiliate_billing_periods` and `0033_affiliate_applications` run on deploy (`start.sh`). 0031 keeps existing affiliates on annual-only.
7. Request emails go to every active platform admin's own address, so at least one admin must have a mailbox that is read. `FRONTEND_URL` is the base of the "Review the request" link.

## Requests from the website form

- The form is public and anonymous. Limits: 5 requests per IP address per hour (counted per backend process), a hidden honeypot field, and the general write rate limit.
- Applying again while a request is still pending updates that request and does not notify the admins a second time. After a rejection, a new application is a new request.
- The form gives the same answer to everyone, so it cannot be used to find out who is already an affiliate. In the console, a request from an existing affiliate's address is flagged and cannot be turned into a second affiliate.
- The applicant gets no automatic email on submit or on rejection. On approval they get the normal portal invite. A rejected request can be reopened.
- Staff notifications are kept out of the customer app's bell: the console reads `/admin/notifications`, and `/notifications` skips those types (`ADMIN_NOTIFICATION_TYPES`).

## Not verified yet

- Nothing has run against a real Stripe Connect account or a real Polar discount. Before launch, do one sandbox run covering: connect → yearly checkout with coupon → commission → approve early → Stripe payout → refund → clawback.
- The Polar `refunded_amount` is assumed to exclude tax (Polar reports `refunded_tax_amount` separately).
- Stripe: if the webhook endpoint uses an API version where `charge.invoice` no longer exists (basil and later), refunds cannot be matched to an invoice, and are logged and skipped.

## Where the code is

- Models: `backend/app/models/affiliate.py`
- Rules: `backend/app/services/affiliates/` (`commissions.py` has the eligibility list)
- Admin API: `backend/app/api/v1/endpoints/admin/affiliates.py`; requests in `admin/affiliate_applications.py`; the console bell in `admin/notifications.py`
- Portal API: `backend/app/api/v1/endpoints/affiliate_portal.py` (also the public `POST /affiliate-public/apply`)
- Requests: `backend/app/services/affiliates/applications.py`
- Webhook hooks: `stripe_service.record_affiliate_commission` and `_on_charge_refunded`; `polar_service._record_affiliate_commission` and `_reverse_affiliate_commission`
- Portal sign-in: `/auth/affiliate/*`. Its sessions carry scope `affiliate` and only reach `/api/v1/affiliate` (see `_enforce_session_scope`)
- Frontend: `src/app/affiliate-program/` (public form), `src/app/admin/affiliates/requests/`, `src/components/admin/AdminNotificationBell.tsx`, `src/app/affiliate/`, `src/app/admin/affiliates/`, `src/lib/referral.ts`, `src/components/billing/CouponField.tsx`
- Tests: `backend/tests/unit/test_affiliates.py`

## Local testing

`backend/scripts/simulate_affiliate_payment.py` runs the webhook commission code for a referred customer without a payment provider:
`pay <email> [--period monthly|yearly] [--reason subscription_cycle]`, `refund <email> --fraction 0.5`, `mature`.
Never run it against production.
