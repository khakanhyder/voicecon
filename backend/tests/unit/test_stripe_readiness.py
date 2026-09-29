"""
Stripe readiness and resilience: which keys make checkout "configured", how a
test/live key mix is reported, how plans whose Stripe product belongs to the
other mode are repaired, and how Stripe errors reach the customer.

Production 2026-09-30: a live restricted key (rk_live_…) passed "Test
connection" but checkout answered "Payments are not available" because only
sk_ keys were accepted, and the publishable key saved beside it was pk_test_.
"""

import uuid
from types import SimpleNamespace

import pytest
import stripe
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.services.billing import providers
from app.services.billing.stripe_service import StripeService

pytestmark = [pytest.mark.unit, pytest.mark.billing]


def _keys(monkeypatch, secret, publishable="pk_live_abc", webhook="whsec_abc"):
    monkeypatch.setattr(settings, "STRIPE_SECRET_KEY", secret)
    monkeypatch.setattr(settings, "STRIPE_API_KEY", None)
    monkeypatch.setattr(settings, "STRIPE_PUBLISHABLE_KEY", publishable)
    monkeypatch.setattr(settings, "STRIPE_WEBHOOK_SECRET", webhook)


class TestReadiness:
    @pytest.mark.parametrize("secret", ["sk_live_abc", "rk_live_abc"])
    def test_standard_and_restricted_live_keys_are_ready(self, monkeypatch, secret):
        _keys(monkeypatch, secret)
        assert settings.stripe_configured
        assert providers.is_ready(providers.STRIPE)

    def test_placeholder_key_is_not_configured(self, monkeypatch):
        _keys(monkeypatch, "sk_live_...")
        assert not settings.stripe_configured
        assert not providers.is_ready(providers.STRIPE)

    def test_live_secret_with_test_publishable_is_not_ready(self, monkeypatch):
        _keys(monkeypatch, "rk_live_abc", publishable="pk_test_abc")
        assert settings.stripe_configured
        assert not providers.is_ready(providers.STRIPE)
        problem = providers.problem(providers.STRIPE)
        assert "live-mode publishable key" in problem
        assert "test-mode" in problem

    def test_matching_test_keys_are_ready(self, monkeypatch):
        _keys(monkeypatch, "sk_test_abc", publishable="pk_test_abc")
        assert providers.is_ready(providers.STRIPE)

    def test_missing_webhook_secret_is_not_ready(self, monkeypatch):
        _keys(monkeypatch, "sk_live_abc", webhook=None)
        assert not providers.is_ready(providers.STRIPE)


class TestEnsureProduct:
    def _plan(self, product_id):
        return SimpleNamespace(
            id=uuid.uuid4(), slug="scale", name="Scale", description="d", stripe_product_id=product_id
        )

    @pytest.mark.asyncio
    async def test_product_from_other_mode_is_recreated(self, monkeypatch):
        def missing(_pid):
            raise stripe.error.InvalidRequestError("No such product", "id", code="resource_missing")

        created = []
        monkeypatch.setattr(stripe.Product, "retrieve", staticmethod(missing))
        monkeypatch.setattr(
            stripe.Product, "create", staticmethod(lambda **kw: created.append(kw) or SimpleNamespace(id="prod_new"))
        )
        plan = self._plan("prod_testmode")
        service = StripeService(api_key="", webhook_secret="", configure_sdk=False)

        assert await service.ensure_stripe_product(plan) == "prod_new"
        assert plan.stripe_product_id == "prod_new"
        assert created and created[0]["metadata"]["plan_id"] == str(plan.id)

    @pytest.mark.asyncio
    async def test_existing_active_product_is_kept(self, monkeypatch):
        monkeypatch.setattr(stripe.Product, "retrieve", staticmethod(lambda pid: {"id": pid, "active": True}))
        monkeypatch.setattr(stripe.Product, "create", staticmethod(lambda **kw: pytest.fail("must not create")))
        plan = self._plan("prod_live")
        service = StripeService(api_key="", webhook_secret="", configure_sdk=False)
        assert await service.ensure_stripe_product(plan) == "prod_live"

    @pytest.mark.asyncio
    async def test_placeholder_product_is_created(self, monkeypatch):
        monkeypatch.setattr(stripe.Product, "create", staticmethod(lambda **kw: SimpleNamespace(id="prod_new")))
        plan = self._plan("local_scale")
        service = StripeService(api_key="", webhook_secret="", configure_sdk=False)
        assert await service.ensure_stripe_product(plan) == "prod_new"

    @pytest.mark.asyncio
    async def test_other_stripe_errors_propagate(self, monkeypatch):
        def denied(_pid):
            raise stripe.error.PermissionError("restricted key lacks product read")

        monkeypatch.setattr(stripe.Product, "retrieve", staticmethod(denied))
        service = StripeService(api_key="", webhook_secret="", configure_sdk=False)
        with pytest.raises(stripe.error.PermissionError):
            await service.ensure_stripe_product(self._plan("prod_live"))


class TestStripeErrorResponses:
    async def _call(self, exc):
        from app.main import stripe_exception_handler

        app = FastAPI()
        app.add_exception_handler(stripe.error.StripeError, stripe_exception_handler)

        @app.post("/pay")
        async def pay():
            raise exc

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
            return await client.post("/pay")

    @pytest.mark.asyncio
    async def test_card_error_is_402_with_stripe_wording(self):
        exc = stripe.error.CardError("Your card was declined.", "card", "card_declined")
        exc._message = "Your card was declined."
        response = await self._call(exc)
        assert response.status_code == 402
        assert "declined" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_other_errors_are_503_without_internals(self):
        response = await self._call(stripe.error.PermissionError("rk key lacks subscriptions write"))
        assert response.status_code == 503
        assert "rk key" not in response.json()["detail"]


class TestAdminConnectionCheck:
    @pytest.mark.asyncio
    async def test_mixed_modes_are_reported_not_ok(self, monkeypatch):
        from app.services.admin import provider_checks

        async def accepted(*args, **kwargs):
            return provider_checks.CheckResult("ok", "Secret key accepted.", 100)

        monkeypatch.setattr(provider_checks, "_http_check", accepted)
        _keys(monkeypatch, "rk_live_abc", publishable="pk_test_abc")

        result = await provider_checks.check_stripe()
        assert result.status == "incomplete"
        assert "live mode" in result.message
        assert "Checkout is still off" in result.message

    @pytest.mark.asyncio
    async def test_complete_live_setup_is_ok(self, monkeypatch):
        from app.services.admin import provider_checks

        async def accepted(*args, **kwargs):
            return provider_checks.CheckResult("ok", "Secret key accepted.", 100)

        monkeypatch.setattr(provider_checks, "_http_check", accepted)
        _keys(monkeypatch, "rk_live_abc", publishable="pk_live_abc")

        result = await provider_checks.check_stripe()
        assert result.status == "ok"
