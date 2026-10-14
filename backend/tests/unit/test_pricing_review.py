"""
Pricing review (14 Oct 2026): premium-model minutes, the overage rate from
the plan's settings, overage charged through Stripe/Polar, and provider cost
accuracy (Anthropic prompt caching, OpenAI cached tokens, per-call usage).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.core.config import Settings
from app.models.agent import Agent
from app.models.subscription import SOURCE_MANUAL, SOURCE_POLAR, UsageRecord
from app.services.billing import catalog, overage_billing, polar_service
from app.services.billing.seed_plans import seed_default_plans
from app.services.billing.usage_tracker import UsageTracker

from test_pricing_plans import (  # noqa: F401  (db and org are fixtures)
    db,
    finished_call,
    minute_records,
    org,
    plans_by_slug,
    subscribe,
)

pytestmark = [pytest.mark.unit, pytest.mark.billing]


async def agent_on(db, org, model: str, provider: str = "openai") -> Agent:
    agent = Agent(
        user_id=org.owner_id,
        organization_id=org.id,
        name=f"Agent {model}",
        llm_provider=provider,
        llm_model=model,
    )
    db.add(agent)
    await db.commit()
    return agent


async def call_by(db, org, agent: Agent | None, seconds: int):
    call = await finished_call(db, org, seconds=seconds)
    if agent is not None:
        call.agent_id = agent.id
        await db.commit()
    return call


@pytest.fixture
def no_provider_push(monkeypatch):
    """Record pushes instead of calling Stripe or Polar."""
    pushed = []

    async def fake_push_for_call(db, call_id):
        pushed.append(call_id)

    monkeypatch.setattr(overage_billing, "push_for_call", fake_push_for_call)
    return pushed


# ---------------------------------------------------------------------------
# Rates and the premium multiplier
# ---------------------------------------------------------------------------


class TestPremiumModels:
    @pytest.mark.parametrize(
        "provider,model,premium",
        [
            ("openai", "gpt-5.5", True),
            ("openai", "gpt-5.4", True),
            ("openai", "gpt-4o", True),
            ("openai", "gpt-4", True),
            ("openai", "gpt-5.4-mini", False),
            ("openai", "gpt-5.4-nano", False),
            ("openai", "gpt-4o-mini", False),
            ("openai", "o4-mini", False),
            ("anthropic", "claude-sonnet-5-5", True),
            ("anthropic", "claude-opus-5-5", True),
            ("anthropic", "claude-haiku-4-5", False),
            ("openrouter", "openai/gpt-5.5", True),
            ("openrouter", "openai/gpt-5.4-nano", False),
            ("custom", "my-local-llama", False),
            ("openai", None, False),
        ],
    )
    def test_which_models_are_premium(self, provider, model, premium):
        assert catalog.is_premium_model(provider, model) is premium

    def test_billable_minutes_round_up_after_the_multiplier(self):
        assert catalog.billable_minutes(3, 1.5, True) == 5  # 4.5 -> 5
        assert catalog.billable_minutes(4, 1.5, True) == 6
        assert catalog.billable_minutes(3, 1.5, False) == 3
        assert catalog.billable_minutes(3, 1.0, True) == 3
        assert catalog.billable_minutes(0, 1.5, True) == 0

    def test_every_plan_on_sale_carries_the_multiplier(self):
        for doc in (*catalog.PLAN_ENTITLEMENTS.values(), *catalog.PREPAID_PLAN_ENTITLEMENTS.values()):
            assert catalog.premium_multiplier(doc) == catalog.PREMIUM_MULTIPLIER == 1.5

    def test_a_multiplier_below_one_reads_as_one(self):
        assert catalog.premium_multiplier({"premium": {"multiplier": 0.5}}) == 1.0
        assert catalog.premium_multiplier({}) == 1.0  # legacy plans: off


class TestSubscriptionMinutes:
    async def test_a_premium_call_uses_the_allowance_faster(self, db, org, no_provider_push):
        await seed_default_plans(db)
        plans = await plans_by_slug(db)
        subscription = await subscribe(db, org, plans["growth"], minutes_used=0)
        agent = await agent_on(db, org, "gpt-5.5")
        call = await call_by(db, org, agent, seconds=180)

        await UsageTracker.record_call_usage(db, call.id, org.id)

        await db.refresh(subscription)
        assert subscription.current_period_minutes == 5  # 3 talk minutes x 1.5
        (record,) = await minute_records(db, call.id)
        assert record.quantity == 5
        assert record.stripe_metadata["talk_minutes"] == 3
        assert record.stripe_metadata["premium_model"] is True

    async def test_a_standard_call_counts_its_own_minutes(self, db, org, no_provider_push):
        await seed_default_plans(db)
        plans = await plans_by_slug(db)
        subscription = await subscribe(db, org, plans["growth"])
        agent = await agent_on(db, org, "gpt-5.4-nano")
        call = await call_by(db, org, agent, seconds=180)

        await UsageTracker.record_call_usage(db, call.id, org.id)

        await db.refresh(subscription)
        assert subscription.current_period_minutes == 3

    async def test_overage_is_priced_at_the_rate_set_on_the_plan(self, db, org, no_provider_push):
        await seed_default_plans(db)
        plans = await plans_by_slug(db)
        growth = plans["growth"]
        # What /admin/plans writes: the document, not only the column.
        growth.entitlements = {
            **growth.entitlements,
            "overage": {**growth.entitlements["overage"], "per_minute": 0.40},
        }
        await db.commit()
        await subscribe(db, org, growth, minutes_used=750)  # allowance used up
        call = await call_by(db, org, None, seconds=120)

        await UsageTracker.record_call_usage(db, call.id, org.id)

        (record,) = await minute_records(db, call.id)
        assert record.unit_price == Decimal("0.40")
        assert record.total_amount == Decimal("0.80")
        assert record.stripe_metadata["bill_overage"] is True
        assert record.stripe_metadata["overage_minutes"] == 2
        assert no_provider_push == [call.id]

    async def test_a_call_inside_the_allowance_is_not_sent_to_the_provider(self, db, org, no_provider_push):
        await seed_default_plans(db)
        plans = await plans_by_slug(db)
        await subscribe(db, org, plans["growth"], minutes_used=10)
        call = await call_by(db, org, None, seconds=120)

        await UsageTracker.record_call_usage(db, call.id, org.id)

        (record,) = await minute_records(db, call.id)
        assert record.stripe_metadata["bill_overage"] is False
        assert no_provider_push == []


# ---------------------------------------------------------------------------
# Overage charged at the provider
# ---------------------------------------------------------------------------


async def overage_record(db, org, *, source="stripe", minutes_used=750, seconds=120, **sub_fields):
    await seed_default_plans(db)
    plans = await plans_by_slug(db)
    subscription = await subscribe(db, org, plans["growth"], minutes_used=minutes_used)
    subscription.source = source
    for key, value in sub_fields.items():
        setattr(subscription, key, value)
    await db.commit()
    call = await call_by(db, org, None, seconds=seconds)
    return subscription, call


@pytest.fixture
def fake_stripe(monkeypatch):
    import stripe

    calls = []

    def create(**kwargs):
        calls.append(kwargs)
        if kwargs.get("fail"):
            raise RuntimeError("boom")
        return SimpleNamespace(id=f"ii_{len(calls)}")

    async def fake_service():
        return None

    monkeypatch.setattr(Settings, "stripe_configured", property(lambda self: True))
    monkeypatch.setattr(stripe.InvoiceItem, "create", staticmethod(create))
    monkeypatch.setattr(
        "app.services.billing.stripe_service.get_stripe_service", fake_service
    )
    return calls


class FakePolar:
    def __init__(self, *, has_meter=True):
        self.events = []
        self.has_meter = has_meter
        self.meters = []

    async def list_meters(self):
        return {"items": self.meters}

    async def create_meter(self, body):
        meter = {"id": "meter-1", **body}
        self.meters.append(meter)
        return meter

    async def get_subscription(self, subscription_id):
        prices = [{"amount_type": "fixed", "price_amount": 14900}]
        if self.has_meter:
            prices.append({"amount_type": "metered_unit", "meter_id": "meter-1"})
        return {"id": subscription_id, "prices": prices}

    async def ingest_events(self, events):
        self.events.extend(events)
        return {"inserted": len(events)}

    async def get_product(self, product_id):
        return {"id": product_id, "prices": [
            {"id": "price-fixed", "amount_type": "fixed"},
            {"id": "price-metered", "amount_type": "metered_unit", "meter_id": "meter-1"},
        ]}

    async def update_product(self, product_id, body):
        self.updated = (product_id, body)
        return {"id": product_id}


@pytest.fixture
def fake_polar(monkeypatch):
    client = FakePolar()
    monkeypatch.setattr(Settings, "polar_configured", property(lambda self: True))
    monkeypatch.setattr(polar_service, "get_polar_client", lambda: client)
    monkeypatch.setattr(polar_service, "_overage_meter_id", None)
    return client


class TestStripeOverage:
    async def test_overage_lands_on_the_next_stripe_invoice(self, db, org, fake_stripe):
        await overage_record(
            db, org, stripe_customer_id="cus_1", stripe_subscription_id="sub_1"
        )
        _, call = await overage_record_call(db, org)
        (record,) = await minute_records(db, call.id)

        assert record.reported_to_stripe is True
        assert record.stripe_usage_record_id == "ii_1"
        assert overage_billing.billing_state(record)["status"] == "billed"
        (item,) = fake_stripe
        assert item["customer"] == "cus_1" and item["subscription"] == "sub_1"
        assert item["amount"] == 44  # 2 minutes at $0.22
        assert item["idempotency_key"] == f"overage:{record.id}"

    async def test_a_billed_record_is_never_sent_again(self, db, org, fake_stripe):
        await overage_record(db, org, stripe_customer_id="cus_1", stripe_subscription_id="sub_1")
        _, call = await overage_record_call(db, org)
        (record,) = await minute_records(db, call.id)

        assert await overage_billing.push_record(db, record) == "billed"
        record.created_at = datetime.utcnow() - timedelta(minutes=10)
        await db.commit()
        assert await overage_billing.retry_pending(db) == 0
        assert len(fake_stripe) == 1

    async def test_a_failed_push_is_retried_by_the_sweep(self, db, org, fake_stripe, monkeypatch):
        import stripe

        await overage_record(db, org, stripe_customer_id="cus_1", stripe_subscription_id="sub_1")
        down = {"value": True}
        real = stripe.InvoiceItem.create

        def flaky(**kwargs):
            if down["value"]:
                raise RuntimeError("Stripe is down")
            return real(**kwargs)

        monkeypatch.setattr(stripe.InvoiceItem, "create", staticmethod(flaky))
        _, call = await overage_record_call(db, org)
        (record,) = await minute_records(db, call.id)
        assert overage_billing.billing_state(record)["status"] == "failed"
        assert record.reported_to_stripe is not True

        down["value"] = False
        record.created_at = datetime.utcnow() - timedelta(minutes=10)
        await db.commit()
        assert await overage_billing.retry_pending(db) == 1
        await db.refresh(record)
        assert record.reported_to_stripe is True

    async def test_overage_from_before_overage_billing_is_never_charged(self, db, org, fake_stripe):
        subscription, call = await overage_record(
            db, org, stripe_customer_id="cus_1", stripe_subscription_id="sub_1"
        )
        old = UsageRecord(
            subscription_id=subscription.id,
            organization_id=org.id,
            usage_type="minutes",
            quantity=10,
            unit_price=Decimal("0.25"),
            total_amount=Decimal("2.50"),
            resource_type="call",
            resource_id=call.id,
            period_start=subscription.current_period_start,
            period_end=subscription.current_period_end,
            stripe_metadata={"call_duration_seconds": 600},  # no bill_overage flag
            created_at=datetime.utcnow() - timedelta(days=2),
        )
        db.add(old)
        await db.commit()

        assert await overage_billing.retry_pending(db) == 0
        assert fake_stripe == []


async def overage_record_call(db, org, seconds=120):
    """Record one call for the org's (already created) subscription."""
    call = await call_by(db, org, None, seconds=seconds)
    await UsageTracker.record_call_usage(db, call.id, org.id)
    return None, call


class TestPolarOverage:
    async def test_overage_is_sent_to_polar_as_a_usage_event(self, db, org, fake_polar):
        await overage_record(
            db, org, source=SOURCE_POLAR, polar_subscription_id="psub_1", polar_customer_id="pcus_1"
        )
        _, call = await overage_record_call(db, org)
        (record,) = await minute_records(db, call.id)

        assert record.reported_to_stripe is True
        (event,) = fake_polar.events
        assert event["name"] == polar_service.OVERAGE_EVENT_NAME
        assert event["external_id"] == f"overage:{record.id}"
        assert event["customer_id"] == "pcus_1"
        assert event["metadata"]["amount_cents"] == 44
        # The meter is created on first use and sums those cents.
        (meter,) = fake_polar.meters
        assert meter["aggregation"] == {"func": "sum", "property": "amount_cents"}

    async def test_a_subscription_without_the_overage_price_is_flagged_not_charged(self, db, org, fake_polar):
        fake_polar.has_meter = False
        await overage_record(db, org, source=SOURCE_POLAR, polar_subscription_id="psub_1")
        _, call = await overage_record_call(db, org)
        (record,) = await minute_records(db, call.id)

        state = overage_billing.billing_state(record)
        assert state["status"] == "unbillable"
        assert "no overage price" in state["reason"]
        assert fake_polar.events == []

    async def test_a_price_change_keeps_the_overage_price(self, fake_polar):
        fake_polar.meters.append({"id": "meter-1", "metadata": {"voicecon": "voicecon_overage_cents"}})
        await polar_service.push_price("prod_1", Decimal("159"), "usd")

        product_id, body = fake_polar.updated
        assert product_id == "prod_1"
        assert body["prices"][0] == {"amount_type": "fixed", "price_amount": 15900, "price_currency": "usd"}
        assert body["prices"][1] == {"id": "price-metered"}


class TestManualSubscription:
    async def test_a_staff_billed_subscription_is_flagged_for_an_admin(self, db, org):
        await overage_record(db, org, source=SOURCE_MANUAL)
        _, call = await overage_record_call(db, org)
        (record,) = await minute_records(db, call.id)
        assert overage_billing.billing_state(record)["status"] == "unbillable"


# ---------------------------------------------------------------------------
# Provider cost accuracy
# ---------------------------------------------------------------------------


class TestAnthropicCaching:
    def _provider(self):
        from app.services.voice.providers.anthropic_llm import AnthropicLLM

        return AnthropicLLM.__new__(AnthropicLLM)

    def test_system_and_newest_message_are_marked_for_caching(self):
        from app.services.voice.providers.anthropic_llm import AnthropicLLM

        params = {
            "system": "You are Ava.",
            "messages": [
                {"role": "user", "content": "Hi"},
                {"role": "assistant", "content": "Hello!"},
                {"role": "user", "content": "Book me in"},
            ],
        }
        AnthropicLLM._apply_caching(params)

        assert params["system"] == [
            {"type": "text", "text": "You are Ava.", "cache_control": {"type": "ephemeral"}}
        ]
        assert params["messages"][-1]["content"] == [
            {"type": "text", "text": "Book me in", "cache_control": {"type": "ephemeral"}}
        ]
        # Earlier turns are untouched (they are part of the cached prefix).
        assert params["messages"][0]["content"] == "Hi"

    def test_tool_result_turns_are_marked_on_their_last_block(self):
        from app.services.voice.providers.anthropic_llm import AnthropicLLM

        blocks = [{"type": "tool_result", "tool_use_id": "t1", "content": "ok"}]
        params = {"messages": [{"role": "user", "content": blocks}]}
        AnthropicLLM._apply_caching(params)
        assert params["messages"][0]["content"][-1]["cache_control"] == {"type": "ephemeral"}
        assert "cache_control" not in blocks[0]  # the caller's list is not mutated

    def test_cached_tokens_are_priced_at_their_own_rates(self):
        llm = self._provider()
        # 1M uncached + 1M written + 1M read on Sonnet 4.6 ($3 input).
        cost = llm._calculate_cost("claude-sonnet-4-6", 1_000_000, 0, 1_000_000, 1_000_000)
        assert cost == pytest.approx(3.00 + 3.75 + 0.30)
        # Opus 5.5 reads are 0.05x.
        cost = llm._calculate_cost("claude-opus-5-5", 0, 0, 0, 1_000_000)
        assert cost == pytest.approx(0.20)

    def test_new_models_have_prices(self):
        llm = self._provider()
        assert llm._calculate_cost("claude-haiku-5-5", 1_000_000, 0) == pytest.approx(0.10)
        assert llm._calculate_cost("claude-sonnet-5-5", 1_000_000, 0) == pytest.approx(2.00)


class TestOpenAICost:
    def _provider(self):
        from app.services.voice.providers.openai_llm import OpenAILLM

        return OpenAILLM.__new__(OpenAILLM)

    def test_cached_prompt_tokens_are_discounted(self):
        llm = self._provider()
        # gpt-5.4-nano: $0.20 input; 1M prompt tokens of which 800k cached at 10%.
        cost = llm._calculate_cost("gpt-5.4-nano", 1_000_000, 0, cached_tokens=800_000)
        assert cost == pytest.approx(0.20 * 0.2 + 0.20 * 0.8 * 0.1)

    def test_an_unknown_model_is_priced_high_not_low(self):
        llm = self._provider()
        assert llm._calculate_cost("gpt-9-turbo", 1_000_000, 0) == pytest.approx(5.00)

    def test_gateway_ids_find_their_row(self):
        llm = self._provider()
        assert llm._calculate_cost("openai/gpt-5.4-nano", 1_000_000, 0) == pytest.approx(0.20)


class TestPerCallUsage:
    async def test_a_call_adds_up_only_its_own_usage(self):
        from app.services.voice.providers.base import LLMUsage, current_call_id
        from app.services.voice.llm_service import LLMService

        service = LLMService.__new__(LLMService)
        provider = SimpleNamespace(_usage_stats=[])
        provider.get_usage_stats = lambda: list(provider._usage_stats)
        service._active_providers = {"shared": provider}

        a, b = str(uuid.uuid4()), str(uuid.uuid4())
        for call_id, cost in ((a, 0.01), (b, 0.50), (a, 0.02)):
            token = current_call_id.set(call_id)
            provider._usage_stats.append(LLMUsage("openai", "gpt", 1, 1, 2, cost))
            current_call_id.reset(token)

        mine = await service.get_usage_stats(call_id=a)
        assert sum(u.cost for u in mine) == pytest.approx(0.03)

        service.forget_call_usage(a)
        assert [u.call_id for u in provider._usage_stats] == [b]
