# Free Trial & Subscription — Feature Overview

A plain-language description of how the trial and subscription experience should
work. No implementation detail — see `SUBSCRIPTION_AND_TRIAL_PLAN.md` for that.

---

## The idea in one line

A new user can skip payment and start a **7-day free trial with full access to
the product**. When the trial ends, the account stays alive but stops making
calls, and the user is asked to pick a plan to continue.

---

## The user journey

```
  Sign up  →  Company info  →  Pricing page
                                    │
                       ┌────────────┴────────────┐
                       │                         │
              "Start Free Trial"           "Choose a plan"
                       │                         │
                       ▼                         ▼
              7 days, full access          Paid subscription
                       │                         │
          ┌────────────┴────────────┐            │
          │                         │            │
   Upgrades during trial      Trial ends         │
          │                         │            │
          └────────────► Paid subscription ◄─────┘
                                    │
                            Renews every month
```

---

## What happens in each stage

### 1. Starting the trial

The user clicks **"Start Free Trial"** on the pricing screen. No credit card, no
payment details. They land straight in the dashboard and can start building.

The trial runs for **7 days** from that moment.

### 2. During the trial (days 1–7)

**The user gets the full product.** Every feature is unlocked — agents,
phone number, inbound and outbound calls, workflows, CRM integrations,
knowledge base, analytics, everything.

The only thing we limit is **how much they can use**, so the trial doesn't cost
us real money in call charges:

- 1 AI agent
- 1 phone number (provided by us)
- A small allowance of call minutes and calls

A small bar at the top of the dashboard shows **"Trial · 5 days left · Upgrade"**
at all times, so they always know where they stand.

### 3. Trial about to end (last 2–3 days)

The banner turns amber and becomes more direct: *"Your trial ends Friday. Add a
payment method to keep your phone number and agents running."*

We also send reminder emails — one a few days before, one on the last day.

### 4. Trial ends

The account **is not deleted and is not locked out.** What changes:

| Still works | Stops working |
|---|---|
| Log in | Answering incoming calls |
| See all their agents, prompts, workflows | Making outgoing calls |
| See call history, recordings, transcripts | Running agents or workflows |
| Download / export their data | Editing agents and workflows |
| Billing page and upgrading | Sending SMS / emails |
| Invite or manage team | |

So the product goes **read-only**. Everything they built is still there, they
just can't run it.

A red banner across the top says: *"Your trial has ended. Your agents are
paused. Upgrade to resume."* On the main pages (Agents, Calls) we show an
upgrade screen instead of the normal content.

We give them a **3-day grace period** after the trial ends before phone numbers
are released, so a trial expiring on a Friday doesn't become a crisis.

We keep their data for **60 days** after the trial ends. If they come back and
pay within that window, everything is restored exactly as they left it.

### 5. Upgrading

The user picks a plan, enters card details, and everything switches back on
immediately — same agents, same settings, same history. Nothing to rebuild.

They can upgrade at any point, including during the trial.

### 6. Paid subscription

Renews monthly (or yearly). If a payment fails, we don't cut them off straight
away — the card gets retried over about two weeks and the account keeps working
during that time, with a banner asking them to update their card.

Users can cancel anytime. They keep access until the end of the period they've
already paid for.

---

## Locked features during a paid plan

The same idea applies between the two paid plans. If someone on **Sales Chatbot
($119)** opens a Voice AI feature — say lead scoring or campaigns — we don't hide
it. We show it greyed out with a small lock and *"Available on Voice AI"*, plus
an upgrade button.

Hiding a feature means nobody knows it exists. Showing it locked is free
advertising for the higher plan.

---

## What the user can do, at a glance

| | Free Trial (7 days) | Sales Chatbot $119 | Voice AI $359 | After trial ends |
|---|---|---|---|---|
| Make & receive calls | ✅ limited allowance | ✅ 1,000 min | ✅ 3,000 min | ❌ |
| AI agents | 1 | 1 | 5 | View only |
| Phone numbers | 1 (ours) | 1 | 5 | View only |
| Workflows & integrations | ✅ | ✅ | ✅ | View only |
| Campaigns, lead scoring, meetings | ✅ (to try) | ❌ | ✅ | ❌ |
| View past calls & transcripts | ✅ | ✅ | ✅ | ✅ |
| Export their data | ✅ | ✅ | ✅ | ✅ |
| Billing & upgrade | ✅ | ✅ | ✅ | ✅ |

---

## Why this approach

- **Full access during the trial** is what actually sells the product. If we
  hide the expensive features, nobody has a reason to pick the $359 plan.
- **Usage caps instead of feature caps** protect us on cost. Calls cost us real
  money; showing a feature doesn't.
- **Read-only instead of a hard lockout** keeps the door open. The person
  trialling often isn't the person who approves the spend — they need to be able
  to log in and show it to their boss. And deleting someone's work guarantees
  they never come back.
- **Nothing is lost on expiry**, so upgrading later is one click, not a rebuild.

---

## Decisions we need from the business

1. **Trial length** — 7 days is what's built. 14 days is more common in B2B and
   usually converts better, since a week isn't much time to set up a phone
   system and see results.
2. **How much usage** the trial includes (suggested: ~60 minutes / 25 calls).
3. **Do we ask for a card up front?** No card = more signups, lower conversion.
   Card required = fewer signups, much higher conversion. Current build asks for
   no card.
4. **Which features belong to each paid plan** — the table above is a proposal
   based on the pricing page copy, worth confirming.
5. **One trial per company, or per user?** Per workspace *and* per user, both
   enforced. Per email *domain* is detected but allowed through by default, so
   a second team at a large company is not refused — flip
   `BLOCK_REPEAT_TRIALS_BY_DOMAIN` in `endpoints/billing.py` to tighten it.

---

## Current status

**Built and working.** The whole flow described above is implemented: the trial
starts, runs for 7 days, ends on time, drops into a 3-day grace period, then
turns the workspace read-only — and the user can upgrade at any point and pick
up exactly where they left off.

What changed from the previous state:

| Before | Now |
|---|---|
| Trials never ended — an expired trial kept full access forever | Trials end on the clock; access is re-checked on every request |
| Plan limits were stored but never checked | Agents, numbers, knowledge bases, workflows, seats and API keys all enforced |
| A trial user could not pay — checkout rejected them | Trials convert to paid in one step, keeping all their data |
| Nothing stopped signing up again for another trial | One trial per workspace *and* per user, enforced; the UI hides the button once it's spent |
| No banners, no upgrade prompts | Status banner, locked-feature UI, and an upgrade dialog on every blocked action |

Design decisions worth knowing:

* The trial runs on the **Voice AI** plan, not the cheaper one, so people see
  what they'd be buying. Usage is what's capped, not features.
* A trial **cannot** run up an overage bill — with no card on file it stops at
  its limit rather than billing us for the excess.
* Expiry is checked **on every request**, so a trial ends on time even if the
  background job is down. The job handles the emails and cleanup.
* Paying customers **fail open**: if a payment webhook goes missing we log it
  and leave them working, rather than locking out someone who has paid.

Still deferred, none of it blocking:

* Releasing pooled phone numbers at the carrier. They're suspended at grace end
  and flagged for an operator — releasing a number is irreversible, so it should
  not be a background job's decision.
* The day-3 nudge and day-14 win-back emails. The reminder and expiry emails do
  send.
* A staff UI for comping an account. The data model and resolver support it; the
  screen doesn't exist.
* Stripe's hosted Customer Portal, which is a business decision — see
  `SUBSCRIPTION_AND_TRIAL_PLAN.md`.

See `SUBSCRIPTION_AND_TRIAL_PLAN.md` for the technical detail.
