"""
Card checkout when the bank wants the cardholder to approve the payment.

Most cards outside the US need 3-D Secure on a first subscription payment.
Checkout used to treat that as a decline ("try a different card"), so those
customers could never pay. It is now a three-step flow, and these tests pin
each step against a fake Stripe:

- ``/checkout`` hands the browser a client secret and changes nothing;
- ``/checkout/confirm`` activates only what Stripe says was paid, only for the
  workspace that started it, and clears up a payment that was not approved;
- the webhook activates a paid checkout whose browser never came back.

Also here: the message an admin gets for pressing Upgrade, which only the
workspace owner may do.
"""
import json
import uuid
from datetime import datetime, timedelta

import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.api.v1.endpoints import billing
from app.core import permissions as perms
from app.core.workspace import WorkspaceContext
from app.database import Base
from app.models.subscription import (
    SOURCE_STRIPE,
    SOURCE_TRIAL,
    STATUS_ACTIVE,
    STATUS_TRIALING,
    Subscription,
    SubscriptionEvent,
    SubscriptionPlan,
)
from app.models.user import Organization, OrganizationMember, User

pytestmark = [pytest.mark.unit, pytest.mark.billing]


class Obj(dict):
    """A stand-in for a StripeObject: attribute and item access on one dict."""

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)


def stripe_subscription(org_id, plan_id, *, sub_status, intent_status, decline=None, sub_id=None):
    now = int(datetime.utcnow().timestamp())
    return Obj(
        id=sub_id or f"sub_{uuid.uuid4().hex[:12]}",
        status=sub_status,
        customer="cus_test",
        current_period_start=now,
        current_period_end=now + 30 * 86400,
        metadata={"organization_id": str(org_id), "plan_id": str(plan_id)},
        items={"data": [{"price": {"recurring": {"interval": "month"}}}]},
        latest_invoice=Obj(
            id="in_test",
            payment_intent=Obj(
                status=intent_status,
                client_secret="pi_secret_test",
                last_payment_error=Obj(message=decline) if decline else None,
            ),
        ),
    )


class FakeStripe:
    """What the Stripe SDK would hold: one subscription per id, and what was deleted."""

    def __init__(self):
        self.subscriptions = {}
        self.deleted = []

    def add(self, subscription):
        self.subscriptions[subscription.id] = subscription
        return subscription

    def retrieve(self, sub_id, **_):
        import stripe

        if sub_id not in self.subscriptions:
            raise stripe.error.InvalidRequestError("No such subscription", "id")
        return self.subscriptions[sub_id]

    def delete(self, sub_id, **_):
        self.deleted.append(sub_id)


class FakeStripeService:
    synced_invoices: list

    def __init__(self):
        self.synced_invoices = []

    async def create_customer(self, **_):
        return "cus_test"

    async def ensure_stripe_price(self, **_):
        return "price_test"

    async def record_affiliate_commission(self, *_):
        return None

    async def sync_invoice(self, db, invoice_id):
        self.synced_invoices.append(invoice_id)


@pytest_asyncio.fixture
async def db() -> AsyncSession:
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


@pytest_asyncio.fixture
async def owner(db) -> User:
    user = User(
        email=f"owner-{uuid.uuid4().hex[:8]}@example.com",
        hashed_password="x",
        full_name="Owner",
        is_active=True,
    )
    db.add(user)
    await db.commit()
    return user


async def make_org(db, owner, name="Acme") -> Organization:
    organization = Organization(
        name=name, slug=f"acme-{uuid.uuid4().hex[:8]}", owner_id=owner.id
    )
    db.add(organization)
    await db.flush()
    db.add(OrganizationMember(organization_id=organization.id, user_id=owner.id, role="owner"))
    await db.commit()
    return organization


@pytest_asyncio.fixture
async def org(db, owner) -> Organization:
    return await make_org(db, owner)


@pytest_asyncio.fixture
async def plan(db) -> SubscriptionPlan:
    subscription_plan = SubscriptionPlan(
        slug="growth",
        name="Growth",
        tier=2,
        stripe_product_id=f"prod_{uuid.uuid4().hex[:10]}",
        stripe_price_id=f"price_{uuid.uuid4().hex[:10]}",
        price_monthly=179,
        trial_days=30,
        is_trialable=True,
    )
    db.add(subscription_plan)
    await db.commit()
    return subscription_plan


@pytest_asyncio.fixture
async def trial(db, org, plan) -> Subscription:
    start = datetime.utcnow() - timedelta(days=3)
    subscription = Subscription(
        organization_id=org.id,
        plan_id=plan.id,
        status=STATUS_TRIALING,
        source=SOURCE_TRIAL,
        billing_period="monthly",
        current_period_start=start,
        current_period_end=start + timedelta(days=30),
        trial_start=start,
        trial_end=start + timedelta(days=30),
    )
    db.add(subscription)
    await db.commit()
    return subscription


@pytest.fixture
def fake_stripe(monkeypatch):
    fake = FakeStripe()
    service = FakeStripeService()
    fake.service = service

    async def get_service():
        return service

    async def no_email(**_):
        return None

    monkeypatch.setattr(billing, "get_stripe_service", get_service)
    monkeypatch.setattr(billing, "_require_checkout_provider", lambda provider: None)
    monkeypatch.setattr("stripe.PaymentMethod.attach", lambda *a, **k: None)
    monkeypatch.setattr("stripe.Customer.modify", lambda *a, **k: None)
    monkeypatch.setattr("stripe.Subscription.retrieve", fake.retrieve)
    monkeypatch.setattr("stripe.Subscription.delete", fake.delete)
    monkeypatch.setattr(
        "app.services.email.service.email_service.send_subscription_confirmation", no_email
    )
    return fake


async def events_of(db, org) -> list:
    result = await db.execute(
        select(SubscriptionEvent.event_type).where(SubscriptionEvent.organization_id == org.id)
    )
    return list(result.scalars().all())


async def start_checkout(db, monkeypatch, fake, org, plan, owner, **subscription_kwargs):
    created = fake.add(stripe_subscription(org.id, plan.id, **subscription_kwargs))
    monkeypatch.setattr("stripe.Subscription.create", lambda **_: created)
    request = billing.CheckoutRequest(plan_id=plan.id, payment_method_id="pm_test")
    return created, await billing.checkout(request, current_user=owner, org_id=org.id, db=db)


async def confirm(db, org, owner, sub_id):
    return await billing.confirm_checkout(
        billing.CheckoutConfirmRequest(stripe_subscription_id=sub_id),
        current_user=owner,
        org_id=org.id,
        db=db,
    )


class TestCheckoutAsksForAuthentication:
    async def test_a_card_needing_approval_is_handed_to_the_browser(
        self, db, monkeypatch, fake_stripe, org, plan, owner, trial
    ):
        created, response = await start_checkout(
            db, monkeypatch, fake_stripe, org, plan, owner,
            sub_status="incomplete", intent_status="requires_action",
        )

        assert response.status_code == 202
        assert json.loads(response.body) == {
            "requires_action": True,
            "client_secret": "pi_secret_test",
            "stripe_subscription_id": created.id,
        }
        # Not a failure: the Stripe subscription must survive for the bank prompt.
        assert fake_stripe.deleted == []

    async def test_the_trial_is_untouched_until_the_payment_is_approved(
        self, db, monkeypatch, fake_stripe, org, plan, owner, trial
    ):
        await start_checkout(
            db, monkeypatch, fake_stripe, org, plan, owner,
            sub_status="incomplete", intent_status="requires_action",
        )

        await db.refresh(trial)
        assert trial.status == STATUS_TRIALING
        assert trial.source == SOURCE_TRIAL
        assert trial.stripe_subscription_id is None

    async def test_a_declined_card_says_why_and_leaves_nothing_behind(
        self, db, monkeypatch, fake_stripe, org, plan, owner, trial
    ):
        with pytest.raises(HTTPException) as refused:
            await start_checkout(
                db, monkeypatch, fake_stripe, org, plan, owner,
                sub_status="incomplete", intent_status="requires_payment_method",
                decline="Your card has insufficient funds.",
            )

        assert refused.value.status_code == 402
        assert "insufficient funds" in refused.value.detail
        assert "not charged" in refused.value.detail
        assert len(fake_stripe.deleted) == 1
        await db.refresh(trial)
        assert trial.status == STATUS_TRIALING

    async def test_a_card_that_needs_no_approval_activates_straight_away(
        self, db, monkeypatch, fake_stripe, org, plan, owner, trial
    ):
        created, response = await start_checkout(
            db, monkeypatch, fake_stripe, org, plan, owner,
            sub_status="active", intent_status="succeeded",
        )

        assert response.status == STATUS_ACTIVE
        await db.refresh(trial)
        assert trial.source == SOURCE_STRIPE
        assert trial.stripe_subscription_id == created.id


class TestConfirmAfterAuthentication:
    async def test_an_approved_payment_converts_the_trial_in_place(
        self, db, fake_stripe, org, plan, owner, trial
    ):
        paid = fake_stripe.add(
            stripe_subscription(org.id, plan.id, sub_status="active", intent_status="succeeded")
        )

        response = await confirm(db, org, owner, paid.id)

        assert response.status == STATUS_ACTIVE
        assert response.id == trial.id  # the same row, not a second subscription
        await db.refresh(trial)
        assert trial.source == SOURCE_STRIPE
        assert trial.stripe_subscription_id == paid.id
        assert trial.billing_period == "monthly"
        assert await events_of(db, org) == ["trial_converted"]

    async def test_a_payment_that_was_not_approved_changes_nothing(
        self, db, fake_stripe, org, plan, owner, trial
    ):
        unpaid = fake_stripe.add(
            stripe_subscription(
                org.id, plan.id, sub_status="incomplete", intent_status="requires_action"
            )
        )

        with pytest.raises(HTTPException) as refused:
            await confirm(db, org, owner, unpaid.id)

        assert refused.value.status_code == 402
        assert "verification was not completed" in refused.value.detail
        assert fake_stripe.deleted == [unpaid.id]
        await db.refresh(trial)
        assert trial.status == STATUS_TRIALING
        assert trial.stripe_subscription_id is None

    async def test_another_workspaces_payment_cannot_be_claimed(
        self, db, fake_stripe, org, plan, owner, trial
    ):
        other = await make_org(db, owner, name="Someone Else")
        theirs = fake_stripe.add(
            stripe_subscription(other.id, plan.id, sub_status="active", intent_status="succeeded")
        )

        with pytest.raises(HTTPException) as refused:
            await confirm(db, org, owner, theirs.id)

        assert refused.value.status_code == 404
        assert fake_stripe.deleted == []  # and it must not be cancelled either
        await db.refresh(trial)
        assert trial.status == STATUS_TRIALING

    async def test_an_unknown_subscription_is_a_404(self, db, fake_stripe, org, owner, trial):
        with pytest.raises(HTTPException) as refused:
            await confirm(db, org, owner, "sub_does_not_exist")

        assert refused.value.status_code == 404

    async def test_confirming_twice_applies_it_once(
        self, db, fake_stripe, org, plan, owner, trial
    ):
        paid = fake_stripe.add(
            stripe_subscription(org.id, plan.id, sub_status="active", intent_status="succeeded")
        )

        await confirm(db, org, owner, paid.id)
        await confirm(db, org, owner, paid.id)

        assert await events_of(db, org) == ["trial_converted"]


class TestWebhookActivatesAnOrphanedPayment:
    """The customer approved the payment, then the tab closed."""

    def event(self, sub_id, event_type="invoice.paid"):
        data = (
            {"id": "in_test", "subscription": sub_id}
            if event_type == "invoice.paid"
            else {"id": sub_id}
        )
        return {"type": event_type, "data": {"object": data}}

    async def test_a_paid_checkout_with_no_row_is_activated(
        self, db, fake_stripe, org, plan, owner, trial
    ):
        paid = fake_stripe.add(
            stripe_subscription(org.id, plan.id, sub_status="active", intent_status="succeeded")
        )

        await billing.adopt_paid_stripe_subscription(db, self.event(paid.id))

        await db.refresh(trial)
        assert trial.status == STATUS_ACTIVE
        assert trial.source == SOURCE_STRIPE
        assert trial.stripe_subscription_id == paid.id
        assert fake_stripe.service.synced_invoices == ["in_test"]

    async def test_the_late_confirm_call_then_changes_nothing(
        self, db, fake_stripe, org, plan, owner, trial
    ):
        paid = fake_stripe.add(
            stripe_subscription(org.id, plan.id, sub_status="active", intent_status="succeeded")
        )
        await billing.adopt_paid_stripe_subscription(db, self.event(paid.id))

        response = await confirm(db, org, owner, paid.id)

        assert response.status == STATUS_ACTIVE
        assert await events_of(db, org) == ["trial_converted"]

    async def test_an_unpaid_subscription_is_left_alone(
        self, db, fake_stripe, org, plan, owner, trial
    ):
        unpaid = fake_stripe.add(
            stripe_subscription(
                org.id, plan.id, sub_status="incomplete", intent_status="requires_action"
            )
        )

        await billing.adopt_paid_stripe_subscription(
            db, self.event(unpaid.id, "customer.subscription.updated")
        )

        await db.refresh(trial)
        assert trial.status == STATUS_TRIALING

    async def test_a_subscription_that_is_not_ours_is_ignored(
        self, db, fake_stripe, org, plan, owner, trial
    ):
        foreign = stripe_subscription(org.id, plan.id, sub_status="active", intent_status="succeeded")
        foreign["metadata"] = {}
        fake_stripe.add(foreign)

        await billing.adopt_paid_stripe_subscription(db, self.event(foreign.id))

        await db.refresh(trial)
        assert trial.status == STATUS_TRIALING

    async def test_a_stripe_failure_never_escapes(self, db, fake_stripe, org, trial):
        # Unknown to the fake: retrieve raises. The webhook must still answer 200.
        await billing.adopt_paid_stripe_subscription(db, self.event("sub_missing"))


class TestOnlyTheOwnerManagesBilling:
    def context(self, role):
        organization = Organization(id=uuid.uuid4(), name="Diamant Versatile", slug="dv")
        return WorkspaceContext(
            user=User(id=uuid.uuid4(), email="a@example.com"),
            organization=organization,
            membership=OrganizationMember(role=role),
        )

    def test_an_admin_is_told_who_can(self):
        with pytest.raises(HTTPException) as refused:
            self.context("admin").require(perms.BILLING_MANAGE)

        assert refused.value.status_code == 403
        assert "Only the owner of Diamant Versatile" in refused.value.detail
        assert "role" not in refused.value.detail

    def test_the_owner_passes(self):
        self.context("owner").require(perms.BILLING_MANAGE)

    def test_an_admin_can_still_read_billing(self):
        self.context("admin").require(perms.BILLING_READ)
