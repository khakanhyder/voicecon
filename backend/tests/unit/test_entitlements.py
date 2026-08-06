"""
Entitlement resolution — the logic every gate in the product depends on.

These are deliberately DB-free: the questions being asked ("has this trial
ended?", "does this plan include campaigns?", "is there headroom left?") are
pure functions of a subscription row and a clock, and testing them that way
means the clock can be moved without freezing time globally.

The lifecycle tests that need real rows live in
``tests/unit/test_subscription_lifecycle.py``.
"""

import uuid
from datetime import datetime, timedelta

import pytest

from app.core.entitlement_guard import (
    EntitlementError,
    REASON_FEATURE,
    REASON_INACTIVE,
    REASON_LIMIT,
    assert_feature,
    assert_live,
    assert_within_limit,
)
from app.models.subscription import (
    SOURCE_STRIPE,
    SOURCE_TRIAL,
    STATUS_ACTIVE,
    STATUS_CANCELED,
    STATUS_EXPIRED,
    STATUS_GRACE,
    STATUS_PAST_DUE,
    STATUS_TRIALING,
    Subscription,
)
from app.services.billing import catalog
from app.services.billing.entitlements import (
    TRIAL_GRACE_DAYS,
    Entitlements,
    effective_grace_end,
    effective_status,
)

NOW = datetime(2026, 8, 5, 12, 0, 0)


def make_subscription(**overrides) -> Subscription:
    """A subscription row with sensible defaults, not persisted."""
    defaults = dict(
        organization_id=uuid.uuid4(),
        plan_id=uuid.uuid4(),
        status=STATUS_TRIALING,
        source=SOURCE_TRIAL,
        billing_period="monthly",
        current_period_start=NOW - timedelta(days=1),
        current_period_end=NOW + timedelta(days=6),
        trial_start=NOW - timedelta(days=1),
        trial_end=NOW + timedelta(days=6),
        current_period_minutes=0,
        current_period_calls=0,
        current_period_sms=0,
        current_period_emails=0,
        cancel_at_period_end=False,
    )
    defaults.update(overrides)
    return Subscription(**defaults)


def make_entitlements(**overrides) -> Entitlements:
    document = overrides.pop("document", catalog.TRIAL_ENTITLEMENTS)
    defaults = dict(
        organization_id=uuid.uuid4(),
        status=STATUS_TRIALING,
        source=SOURCE_TRIAL,
        plan_slug="voice-ai",
        plan_name="Voice AI",
        features=frozenset(
            key for key, on in document["features"].items() if on
        ),
        limits=dict(document["limits"]),
        usage={},
        overage_allowed=bool(document["overage"].get("allowed")),
    )
    defaults.update(overrides)
    return Entitlements(**defaults)


# ==================== effective_status ====================


@pytest.mark.unit
@pytest.mark.billing
class TestEffectiveStatus:
    """Expiry is derived from the clock, never read off the stored status.

    This is the whole defence against "the reconciler didn't run": a trial that
    ended overnight must read as ended on the very next request.
    """

    def test_running_trial_is_trialing(self):
        sub = make_subscription(trial_end=NOW + timedelta(days=3))
        assert effective_status(sub, NOW) == STATUS_TRIALING

    def test_trial_past_its_end_falls_into_grace(self):
        # Still stored as `trialing` — the reconciler has not run yet.
        sub = make_subscription(trial_end=NOW - timedelta(hours=1))
        assert effective_status(sub, NOW) == STATUS_GRACE

    def test_trial_past_grace_is_expired(self):
        sub = make_subscription(
            trial_end=NOW - timedelta(days=TRIAL_GRACE_DAYS + 1)
        )
        assert effective_status(sub, NOW) == STATUS_EXPIRED

    def test_trial_that_ended_months_ago_is_expired(self):
        """The exact bug this feature exists to fix.

        Rows like this were sitting in the database reading as `trialing`
        forever, which meant a permanently free account.
        """
        sub = make_subscription(
            status=STATUS_TRIALING, trial_end=NOW - timedelta(days=90)
        )
        assert effective_status(sub, NOW) == STATUS_EXPIRED

    def test_grace_window_still_runs(self):
        sub = make_subscription(
            status=STATUS_GRACE, grace_period_end=NOW + timedelta(days=1)
        )
        assert effective_status(sub, NOW) == STATUS_GRACE

    def test_grace_window_elapsed_is_expired(self):
        sub = make_subscription(
            status=STATUS_GRACE, grace_period_end=NOW - timedelta(minutes=1)
        )
        assert effective_status(sub, NOW) == STATUS_EXPIRED

    def test_past_due_keeps_working_during_dunning(self):
        """Stripe retries for ~2 weeks; most failures resolve themselves."""
        sub = make_subscription(
            status=STATUS_PAST_DUE,
            source=SOURCE_STRIPE,
            grace_period_end=NOW + timedelta(days=5),
        )
        assert effective_status(sub, NOW) == STATUS_PAST_DUE

    def test_past_due_expires_once_dunning_is_exhausted(self):
        sub = make_subscription(
            status=STATUS_PAST_DUE,
            source=SOURCE_STRIPE,
            grace_period_end=NOW - timedelta(hours=1),
        )
        assert effective_status(sub, NOW) == STATUS_EXPIRED

    def test_cancelled_but_paid_up_still_has_access(self):
        """They paid for the period; cancelling does not claw it back."""
        sub = make_subscription(
            status=STATUS_CANCELED,
            source=SOURCE_STRIPE,
            current_period_end=NOW + timedelta(days=10),
        )
        assert effective_status(sub, NOW) == STATUS_ACTIVE

    def test_cancelled_and_period_over_is_expired(self):
        sub = make_subscription(
            status=STATUS_CANCELED,
            source=SOURCE_STRIPE,
            current_period_end=NOW - timedelta(days=1),
        )
        assert effective_status(sub, NOW) == STATUS_EXPIRED

    def test_active_past_period_end_is_left_alone(self):
        """Fail *open* for payers.

        An active subscription past its period end almost always means a missed
        Stripe webhook, not a customer who stopped paying. Locking them out over
        our own delivery problem costs far more than a few hours of usage.
        """
        sub = make_subscription(
            status=STATUS_ACTIVE,
            source=SOURCE_STRIPE,
            current_period_end=NOW - timedelta(days=3),
        )
        assert effective_status(sub, NOW) == STATUS_ACTIVE

    def test_no_subscription_is_expired(self):
        assert effective_status(None, NOW) == STATUS_EXPIRED


@pytest.mark.unit
@pytest.mark.billing
class TestEffectiveGraceEnd:
    """The grace deadline has to exist before the reconciler writes it.

    Otherwise the banner in the window between "trial lapsed" and "next sweep"
    can't tell the user how long they have to keep their phone number.
    """

    def test_derived_when_the_column_is_still_empty(self):
        trial_end = NOW - timedelta(hours=2)
        sub = make_subscription(trial_end=trial_end, grace_period_end=None)

        assert effective_grace_end(sub, NOW) == trial_end + timedelta(
            days=TRIAL_GRACE_DAYS
        )

    def test_stored_value_wins_once_written(self):
        stored = NOW + timedelta(days=1)
        sub = make_subscription(
            status=STATUS_GRACE, trial_end=NOW - timedelta(days=1), grace_period_end=stored
        )
        assert effective_grace_end(sub, NOW) == stored

    def test_none_while_the_trial_is_still_running(self):
        assert effective_grace_end(make_subscription(), NOW) is None

    def test_grace_days_remaining_is_reported_before_reconciliation(self):
        """The end-to-end symptom this exists to fix."""
        trial_end = datetime.utcnow() - timedelta(hours=1)
        ent = make_entitlements(
            status=STATUS_GRACE,
            grace_period_end=trial_end + timedelta(days=TRIAL_GRACE_DAYS),
        )
        assert ent.grace_days_remaining == TRIAL_GRACE_DAYS


# ==================== Entitlements ====================


@pytest.mark.unit
@pytest.mark.billing
class TestEntitlements:
    def test_live_statuses_allow_runtime(self):
        for status in (STATUS_TRIALING, STATUS_ACTIVE, STATUS_PAST_DUE, STATUS_GRACE):
            assert make_entitlements(status=status).is_live, status

    def test_expired_is_read_only(self):
        ent = make_entitlements(
            status=STATUS_EXPIRED, document=catalog.EXPIRED_ENTITLEMENTS
        )
        assert not ent.is_live
        assert ent.is_read_only

    def test_expired_account_has_no_features(self):
        ent = make_entitlements(
            status=STATUS_EXPIRED, document=catalog.EXPIRED_ENTITLEMENTS
        )
        assert not ent.has(catalog.INBOUND_CALLS)
        assert not ent.has(catalog.OUTBOUND_CALLS)

    def test_feature_in_plan_but_account_dead_is_still_denied(self):
        """`has()` is state *and* plan — an expired Voice AI trial runs nothing."""
        ent = make_entitlements(status=STATUS_EXPIRED)  # trial feature set
        assert catalog.LEAD_SCORING in ent.features
        assert not ent.has(catalog.LEAD_SCORING)

    def test_days_remaining_rounds_up(self):
        ent = make_entitlements(trial_end=datetime.utcnow() + timedelta(hours=30))
        assert ent.days_remaining == 2

    def test_days_remaining_never_negative(self):
        ent = make_entitlements(trial_end=datetime.utcnow() - timedelta(days=5))
        assert ent.days_remaining == 0

    def test_days_remaining_is_none_when_not_trialing(self):
        assert make_entitlements(status=STATUS_ACTIVE).days_remaining is None

    def test_expiring_soon_within_three_days(self):
        soon = make_entitlements(trial_end=datetime.utcnow() + timedelta(days=2))
        later = make_entitlements(trial_end=datetime.utcnow() + timedelta(days=6))
        assert soon.trial_expiring_soon
        assert not later.trial_expiring_soon

    def test_within_respects_headroom(self):
        ent = make_entitlements(usage={catalog.LIMIT_AGENTS: 0})
        assert ent.within(catalog.LIMIT_AGENTS)  # trial allows 1

        at_cap = make_entitlements(usage={catalog.LIMIT_AGENTS: 1})
        assert not at_cap.within(catalog.LIMIT_AGENTS)

    def test_unlimited_is_always_within(self):
        ent = make_entitlements(
            status=STATUS_ACTIVE,
            document=catalog.PLAN_ENTITLEMENTS["voice-ai"],
            usage={catalog.LIMIT_WORKFLOWS: 9999},
        )
        assert ent.is_unlimited(catalog.LIMIT_WORKFLOWS)
        assert ent.within(catalog.LIMIT_WORKFLOWS)
        assert ent.remaining(catalog.LIMIT_WORKFLOWS) is None

    def test_dead_account_is_within_nothing(self):
        ent = make_entitlements(
            status=STATUS_EXPIRED, document=catalog.EXPIRED_ENTITLEMENTS
        )
        assert not ent.within(catalog.LIMIT_AGENTS)


# ==================== The catalogue ====================


@pytest.mark.unit
@pytest.mark.billing
class TestCatalog:
    def test_trial_unlocks_the_premium_features(self):
        """Trials convert on feature discovery, so capability is generous."""
        features = catalog.TRIAL_ENTITLEMENTS["features"]
        assert features[catalog.LEAD_SCORING]
        assert features[catalog.VIRTUAL_MEETINGS]
        assert features[catalog.OUTBOUND_CAMPAIGNS]

    def test_trial_caps_consumption_hard(self):
        limits = catalog.TRIAL_ENTITLEMENTS["limits"]
        assert limits[catalog.LIMIT_MINUTES] <= 120
        assert limits[catalog.LIMIT_CALLS] <= 50
        assert limits[catalog.LIMIT_AGENTS] == 1

    def test_trial_never_allows_overage(self):
        """No card on file means metered overage is an unbounded liability."""
        assert catalog.TRIAL_ENTITLEMENTS["overage"]["allowed"] is False

    def test_paid_plans_allow_overage(self):
        for slug, doc in catalog.PLAN_ENTITLEMENTS.items():
            assert doc["overage"]["allowed"] is True, slug

    def test_expired_grants_nothing(self):
        assert not any(catalog.EXPIRED_ENTITLEMENTS["features"].values())
        assert all(v == 0 for v in catalog.EXPIRED_ENTITLEMENTS["limits"].values())

    def test_voice_ai_is_a_superset_of_sales_chatbot(self):
        cheap = catalog.PLAN_ENTITLEMENTS["sales-chatbot"]["features"]
        rich = catalog.PLAN_ENTITLEMENTS["voice-ai"]["features"]
        for key, enabled in cheap.items():
            if enabled:
                assert rich[key], f"voice-ai is missing {key}"

    def test_plans_offering_points_at_the_upgrade(self):
        assert catalog.plans_offering(catalog.OUTBOUND_CAMPAIGNS) == ["voice-ai"]
        assert set(catalog.plans_offering(catalog.INBOUND_CALLS)) == {
            "sales-chatbot",
            "voice-ai",
        }

    def test_plans_allowing_accounts_for_unlimited(self):
        assert "voice-ai" in catalog.plans_allowing(catalog.LIMIT_WORKFLOWS, 500)
        assert "sales-chatbot" not in catalog.plans_allowing(catalog.LIMIT_AGENTS, 3)

    def test_unknown_slug_under_grants(self):
        """A typo in a slug must never hand out the expensive plan."""
        assert catalog.entitlements_for_plan("nonsense") is catalog.PLAN_ENTITLEMENTS[
            "sales-chatbot"
        ]

    def test_override_merge_is_shallow_per_section(self):
        merged = catalog.merge_entitlements(
            catalog.PLAN_ENTITLEMENTS["sales-chatbot"],
            {"features": {catalog.LEAD_SCORING: True}},
        )
        assert merged["features"][catalog.LEAD_SCORING] is True
        # The rest of the plan survives the override.
        assert merged["features"][catalog.INBOUND_CALLS] is True
        assert merged["limits"][catalog.LIMIT_AGENTS] == 1


# ==================== The guard ====================


@pytest.mark.unit
@pytest.mark.billing
class TestGuard:
    def test_live_account_passes(self):
        assert_live(make_entitlements())  # does not raise

    def test_expired_account_raises_402_with_a_reason(self):
        ent = make_entitlements(
            status=STATUS_EXPIRED, document=catalog.EXPIRED_ENTITLEMENTS
        )
        with pytest.raises(EntitlementError) as exc:
            assert_live(ent)
        assert exc.value.status_code == 402
        assert exc.value.payload["reason"] == REASON_INACTIVE

    def test_expired_trial_says_so(self):
        ent = make_entitlements(
            status=STATUS_EXPIRED,
            source=SOURCE_TRIAL,
            document=catalog.EXPIRED_ENTITLEMENTS,
        )
        with pytest.raises(EntitlementError) as exc:
            assert_live(ent)
        assert "trial" in exc.value.payload["detail"].lower()

    def test_missing_feature_names_the_plan_that_has_it(self):
        ent = make_entitlements(
            status=STATUS_ACTIVE,
            plan_slug="sales-chatbot",
            document=catalog.PLAN_ENTITLEMENTS["sales-chatbot"],
        )
        with pytest.raises(EntitlementError) as exc:
            assert_feature(ent, catalog.OUTBOUND_CAMPAIGNS)
        payload = exc.value.payload
        assert payload["reason"] == REASON_FEATURE
        assert payload["feature"] == catalog.OUTBOUND_CAMPAIGNS
        assert payload["required_plans"] == ["voice-ai"]
        assert payload["upgrade_url"]

    def test_resource_limit_blocks_and_reports_the_numbers(self):
        ent = make_entitlements(usage={catalog.LIMIT_AGENTS: 1})
        with pytest.raises(EntitlementError) as exc:
            assert_within_limit(ent, catalog.LIMIT_AGENTS)
        payload = exc.value.payload
        assert payload["reason"] == REASON_LIMIT
        assert payload["used"] == 1
        assert payload["cap"] == 1

    def test_trial_stops_dead_at_its_usage_allowance(self):
        """No card on file, so there is nothing to bill the overage to."""
        cap = catalog.TRIAL_ENTITLEMENTS["limits"][catalog.LIMIT_CALLS]
        ent = make_entitlements(usage={catalog.LIMIT_CALLS: cap})
        with pytest.raises(EntitlementError):
            assert_within_limit(ent, catalog.LIMIT_CALLS)

    def test_paid_plan_bills_past_its_usage_allowance(self):
        """Metered billing working as designed — going over costs, not blocks."""
        doc = catalog.PLAN_ENTITLEMENTS["voice-ai"]
        cap = doc["limits"][catalog.LIMIT_CALLS]
        ent = make_entitlements(
            status=STATUS_ACTIVE,
            source=SOURCE_STRIPE,
            document=doc,
            usage={catalog.LIMIT_CALLS: cap + 50},
        )
        assert_within_limit(ent, catalog.LIMIT_CALLS)  # does not raise

    def test_resource_caps_never_overflow_even_on_a_paid_plan(self):
        """"One more agent, billed as overage" is not a thing."""
        doc = catalog.PLAN_ENTITLEMENTS["voice-ai"]
        ent = make_entitlements(
            status=STATUS_ACTIVE,
            source=SOURCE_STRIPE,
            document=doc,
            usage={catalog.LIMIT_AGENTS: doc["limits"][catalog.LIMIT_AGENTS]},
        )
        with pytest.raises(EntitlementError):
            assert_within_limit(ent, catalog.LIMIT_AGENTS)
