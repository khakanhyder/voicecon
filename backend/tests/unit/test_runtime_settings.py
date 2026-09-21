"""Unit tests for the admin-managed settings overlay (app.core.runtime_settings)."""
import pytest

from app.core import runtime_settings as rs
from app.core.config import settings


@pytest.fixture(autouse=True)
def _clean():
    rs.reset_for_tests()
    yield
    rs.reset_for_tests()


def test_overlay_applies_and_restores_baseline():
    baseline = rs.baseline_value("DEEPGRAM_API_KEY")
    rs.apply_overrides({"DEEPGRAM_API_KEY": "dg-from-db"})
    assert settings.DEEPGRAM_API_KEY == "dg-from-db"
    rs.apply_overrides({})
    assert settings.DEEPGRAM_API_KEY == baseline


def test_overlay_leaves_unmanaged_runtime_values_alone(monkeypatch):
    # A value set elsewhere at runtime (tests, other code) must survive a reload
    # that never overrode it.
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", False)
    rs.apply_overrides({"DEEPGRAM_API_KEY": "x"})
    rs.apply_overrides({})
    assert settings.RATE_LIMIT_ENABLED is False


def test_undeclared_integration_keys_reach_env_value():
    from app.core.config import env_value

    rs.apply_overrides({"HUBSPOT_CLIENT_ID": "hub-123"})
    assert env_value("HUBSPOT_CLIENT_ID") == "hub-123"


@pytest.mark.parametrize(
    "key,raw,expected",
    [
        ("SMTP_PORT", " 587 ", "587"),
        ("SMTP_USE_TLS", True, "true"),
        ("SMTP_USE_TLS", "off", "false"),
        ("EMAIL_PROVIDER", "smtp", "smtp"),
        ("API_BASE_URL", "https://api.example.com/", "https://api.example.com"),
        ("OPENAI_API_KEY", "  sk-abc  ", "sk-abc"),
    ],
)
def test_normalise_accepts(key, raw, expected):
    assert rs.normalise(rs.SPEC_BY_KEY[key], raw) == expected


@pytest.mark.parametrize(
    "key,raw",
    [
        ("SMTP_PORT", "abc"),
        ("SMTP_PORT", "-1"),
        ("SMTP_USE_TLS", "maybe"),
        ("EMAIL_PROVIDER", "pigeon"),
        ("API_BASE_URL", "api.example.com"),
        ("OPENAI_API_KEY", "   "),
        ("OPENAI_API_KEY", None),
    ],
)
def test_normalise_rejects(key, raw):
    with pytest.raises(rs.InvalidSettingValue):
        rs.normalise(rs.SPEC_BY_KEY[key], raw)


def test_bootstrap_secrets_are_not_in_the_catalogue():
    for key in ("SECRET_KEY", "ENCRYPTION_SECRET_KEY", "ENCRYPTION_SALT", "DATABASE_URL"):
        assert key not in rs.SPEC_BY_KEY


def test_mask_never_reveals_short_values():
    assert rs.mask("abcd") == "••••"
    assert rs.mask("sk-1234567890") == "••••7890"
    assert rs.mask(None) is None


def test_llm_provider_cache_rebuilds_on_key_rotation():
    from app.services.voice.llm_service import LLMService

    service = LLMService()
    first = service.get_provider("openai", api_key="sk-first-key-000000")
    again = service.get_provider("openai", api_key="sk-first-key-000000")
    rotated = service.get_provider("openai", api_key="sk-rotated-key-11111")
    assert first is again
    assert rotated is not first


def test_twilio_singleton_rebuilds_on_credential_change(monkeypatch):
    from app.services.telephony import twilio_service as ts

    monkeypatch.setattr(ts, "_twilio_service", None)
    monkeypatch.setattr(settings, "TWILIO_ACCOUNT_SID", "AC" + "1" * 32)
    monkeypatch.setattr(settings, "TWILIO_AUTH_TOKEN", "token-one")
    first = ts.get_twilio_service()
    assert ts.get_twilio_service() is first
    monkeypatch.setattr(settings, "TWILIO_AUTH_TOKEN", "token-two")
    second = ts.get_twilio_service()
    assert second is not first
    assert second.auth_token == "token-two"
