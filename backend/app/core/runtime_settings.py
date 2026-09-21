"""
Operator-managed configuration layered over the environment.

The platform admin dashboard stores provider keys and tunables in the
``platform_settings`` table. This module overlays those rows onto the global
``settings`` object, so the ~150 existing ``settings.X`` reads across the
codebase pick up a dashboard change without being rewritten.

Precedence, per key: **database row → environment variable → code default.**
Deleting a row restores the environment value. A deployment with no rows
behaves exactly as it did before this module existed.

What is deliberately *not* manageable here (see ``BOOTSTRAP_ONLY``): the
secrets that protect the database's contents and the addresses needed to reach
the database at all. Those have to exist before a row can be read, and storing
the encryption key next to the data it encrypts would defeat it.

Freshness across processes: every API process and Celery worker keeps its own
copy of the overlay. A change is applied immediately in the process that made
it, and every other process notices within ``POLL_INTERVAL_SECONDS`` by
comparing a cheap fingerprint (row count + latest ``updated_at``).

Consumers that build long-lived clients (LLM/STT/TTS provider caches, the
Twilio singleton) key those caches on the credential they were built with, so
a rotated key produces a fresh client rather than reusing the old one.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import UserFacingError

logger = logging.getLogger(__name__)

#: How often each process checks for changes made elsewhere.
POLL_INTERVAL_SECONDS = 15

#: Never stored in the database, whatever the admin API is asked.
BOOTSTRAP_ONLY = frozenset(
    {
        "SECRET_KEY",
        "ENCRYPTION_SECRET_KEY",
        "ENCRYPTION_SALT",
        "DATABASE_URL",
        "REDIS_URL",
        "CELERY_BROKER_URL",
        "CELERY_RESULT_BACKEND",
        "ENVIRONMENT",
        "DEBUG",
        "EGRESS_ALLOW_PRIVATE",
        "ALGORITHM",
        "BACKEND_CORS_ORIGINS",
        "PLATFORM_ADMIN_EMAILS",
    }
)


# ---------------------------------------------------------------------------
# Catalogue
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SettingSpec:
    key: str
    label: str
    group: str
    #: ``secret`` | ``string`` | ``text`` | ``url`` | ``bool`` | ``int`` | ``choice``
    kind: str = "string"
    description: str = ""
    choices: Tuple[str, ...] = ()
    #: Provider id understood by ``services/admin/provider_checks``.
    test: Optional[str] = None
    placeholder: str = ""

    @property
    def is_secret(self) -> bool:
        return self.kind == "secret"


@dataclass(frozen=True)
class SettingGroup:
    id: str
    label: str
    description: str
    icon: str
    test: Optional[str] = None
    docs_url: Optional[str] = None


GROUPS: Tuple[SettingGroup, ...] = (
    SettingGroup("openai", "OpenAI", "Language model for agents, chat, workflows and knowledge-base embeddings.", "sparkles", "openai", "https://platform.openai.com/api-keys"),
    SettingGroup("anthropic", "Anthropic", "Claude models for agents configured to use Anthropic.", "brain", "anthropic", "https://console.anthropic.com/settings/keys"),
    SettingGroup("deepgram", "Deepgram", "Speech-to-text for live calls and agent test sessions.", "mic", "deepgram", "https://console.deepgram.com/"),
    SettingGroup("elevenlabs", "ElevenLabs", "Text-to-speech voices for agents.", "audio", "elevenlabs", "https://elevenlabs.io/app/settings/api-keys"),
    SettingGroup("twilio", "Twilio", "Platform telephony account: number purchases, calls and webhook signatures.", "phone", "twilio", "https://console.twilio.com/"),
    SettingGroup("stripe", "Stripe", "Subscriptions, checkout and billing webhooks.", "card", "stripe", "https://dashboard.stripe.com/apikeys"),
    SettingGroup("email", "Email delivery", "How transactional email (verification codes, invites, billing notices) is sent.", "mail", "email"),
    SettingGroup("storage", "File storage (S3)", "Recordings, avatars and knowledge-base uploads.", "database", "storage"),
    SettingGroup("social_login", "Sign-in providers", "Google and Apple sign-in. The Google app is also used for Calendar, Sheets and Drive.", "key"),
    SettingGroup("integration_apps", "Integration OAuth apps", "Client credentials for the integrations customers connect with one click.", "plug"),
    SettingGroup("security", "Security & limits", "Sign-up verification and API rate limits. Applied on the next request.", "shield"),
    SettingGroup("urls", "Public URLs", "Addresses Twilio and emails use to reach this deployment. A wrong value breaks inbound calls and email links.", "globe"),
)

_S = SettingSpec

SPECS: Tuple[SettingSpec, ...] = (
    # AI
    _S("OPENAI_API_KEY", "API key", "openai", "secret", placeholder="sk-..."),
    _S("OPENAI_ORG_ID", "Organization ID", "openai", description="Optional."),
    _S("OPENAI_BASE_URL", "Base URL", "openai", "url", "Leave empty for api.openai.com. Set to use an OpenAI-compatible gateway such as OpenRouter."),
    _S("ANTHROPIC_API_KEY", "API key", "anthropic", "secret", placeholder="sk-ant-..."),
    # Voice
    _S("DEEPGRAM_API_KEY", "API key", "deepgram", "secret"),
    _S("ELEVENLABS_API_KEY", "API key", "elevenlabs", "secret"),
    # Telephony
    _S("TWILIO_ACCOUNT_SID", "Account SID", "twilio", placeholder="AC..."),
    _S("TWILIO_AUTH_TOKEN", "Auth token", "twilio", "secret"),
    _S("TWILIO_PHONE_NUMBER", "Default phone number", "twilio", placeholder="+15551234567"),
    _S("TWILIO_VALIDATE_WEBHOOKS", "Verify webhook signatures", "twilio", "bool", "Reject inbound Twilio webhooks without a valid signature. Keep on in production."),
    # Payments
    _S("STRIPE_SECRET_KEY", "Secret key", "stripe", "secret", placeholder="sk_live_..."),
    _S("STRIPE_PUBLISHABLE_KEY", "Publishable key", "stripe", placeholder="pk_live_..."),
    _S("STRIPE_WEBHOOK_SECRET", "Webhook signing secret", "stripe", "secret", placeholder="whsec_..."),
    # Email
    _S("EMAIL_PROVIDER", "Provider", "email", "choice", "auto picks SMTP, then SendGrid, then logs to console.", choices=("auto", "smtp", "sendgrid", "console")),
    _S("EMAIL_FROM", "From address", "email", placeholder="noreply@voicecon.ai"),
    _S("EMAIL_FROM_NAME", "From name", "email", placeholder="Voicecon"),
    _S("SMTP_HOST", "SMTP host", "email"),
    _S("SMTP_PORT", "SMTP port", "email", "int"),
    _S("SMTP_USERNAME", "SMTP username", "email"),
    _S("SMTP_PASSWORD", "SMTP password", "email", "secret"),
    _S("SMTP_USE_TLS", "Use STARTTLS", "email", "bool", "For port 587."),
    _S("SMTP_USE_SSL", "Use implicit TLS", "email", "bool", "For port 465. Do not enable together with STARTTLS."),
    _S("SENDGRID_API_KEY", "SendGrid API key", "email", "secret", placeholder="SG...."),
    _S("SENDGRID_FROM_EMAIL", "SendGrid from address", "email"),
    # Storage
    _S("AWS_ACCESS_KEY_ID", "Access key ID", "storage"),
    _S("AWS_SECRET_ACCESS_KEY", "Secret access key", "storage", "secret"),
    _S("AWS_S3_BUCKET", "Bucket", "storage"),
    _S("AWS_REGION", "Region", "storage", placeholder="us-east-1"),
    _S("AWS_ENDPOINT_URL", "Endpoint URL", "storage", "url", "For S3-compatible stores (R2, MinIO). Empty for AWS."),
    _S("AWS_PUBLIC_URL", "Public URL", "storage", "url", "Base URL files are served from, if different from the bucket URL."),
    # Social login
    _S("GOOGLE_CLIENT_ID", "Google client ID", "social_login"),
    _S("GOOGLE_CLIENT_SECRET", "Google client secret", "social_login", "secret"),
    _S("APPLE_CLIENT_ID", "Apple Services ID", "social_login", placeholder="com.voicecon.web"),
    _S("APPLE_TEAM_ID", "Apple team ID", "social_login"),
    _S("APPLE_KEY_ID", "Apple key ID", "social_login"),
    _S("APPLE_PRIVATE_KEY", "Apple private key", "social_login", "secret", "Contents of the .p8 file."),
    # Integration OAuth apps
    _S("HUBSPOT_CLIENT_ID", "HubSpot client ID", "integration_apps"),
    _S("HUBSPOT_CLIENT_SECRET", "HubSpot client secret", "integration_apps", "secret"),
    _S("SALESFORCE_CLIENT_ID", "Salesforce client ID", "integration_apps"),
    _S("SALESFORCE_CLIENT_SECRET", "Salesforce client secret", "integration_apps", "secret"),
    _S("SLACK_CLIENT_ID", "Slack client ID", "integration_apps"),
    _S("SLACK_CLIENT_SECRET", "Slack client secret", "integration_apps", "secret"),
    _S("NOTION_CLIENT_ID", "Notion client ID", "integration_apps"),
    _S("NOTION_CLIENT_SECRET", "Notion client secret", "integration_apps", "secret"),
    _S("CLICKUP_CLIENT_ID", "ClickUp client ID", "integration_apps"),
    _S("CLICKUP_CLIENT_SECRET", "ClickUp client secret", "integration_apps", "secret"),
    _S("CALENDLY_CLIENT_ID", "Calendly client ID", "integration_apps"),
    _S("CALENDLY_CLIENT_SECRET", "Calendly client secret", "integration_apps", "secret"),
    _S("MONDAY_CLIENT_ID", "Monday.com client ID", "integration_apps"),
    _S("MONDAY_CLIENT_SECRET", "Monday.com client secret", "integration_apps", "secret"),
    _S("TRELLO_API_KEY", "Trello API key", "integration_apps", "secret"),
    # Security & limits
    _S("REQUIRE_EMAIL_VERIFICATION", "Require email verification at sign-up", "security", "bool", "Turning this off lets anyone register an address they do not own."),
    _S("RATE_LIMIT_ENABLED", "Rate limiting enabled", "security", "bool"),
    _S("RATE_LIMIT_READ_PER_MINUTE", "Reads per minute (per user)", "security", "int"),
    _S("RATE_LIMIT_WRITE_PER_MINUTE", "Writes per minute (per user)", "security", "int"),
    _S("RATE_LIMIT_AUTH_PER_MINUTE", "Auth requests per minute (per IP)", "security", "int"),
    _S("RATE_LIMIT_LOGIN_ATTEMPTS", "Failed logins before lockout", "security", "int"),
    _S("RATE_LIMIT_LOGIN_LOCKOUT_SECONDS", "Lockout duration (seconds)", "security", "int"),
    # Public URLs
    _S("FRONTEND_URL", "Frontend URL", "urls", "url", "Used to build invite, verification and OAuth links.", placeholder="https://app.voicecon.ai"),
    _S("API_BASE_URL", "API base URL", "urls", "url", "Public HTTPS address Twilio sends voice webhooks to.", placeholder="https://api.voicecon.ai"),
    _S("WEBSOCKET_URL", "WebSocket URL", "urls", "url", "Public WSS address for Twilio media streams.", placeholder="wss://api.voicecon.ai"),
    _S("TWILIO_PUBLIC_BASE_URL", "Twilio signature base URL", "urls", "url", "Only needed when the URL Twilio signs differs from the API base URL."),
)

SPEC_BY_KEY: Dict[str, SettingSpec] = {s.key: s for s in SPECS}
GROUP_BY_ID: Dict[str, SettingGroup] = {g.id: g for g in GROUPS}

assert not (set(SPEC_BY_KEY) & BOOTSTRAP_ONLY), "bootstrap settings must not be manageable"


# ---------------------------------------------------------------------------
# Value handling
# ---------------------------------------------------------------------------

class InvalidSettingValue(UserFacingError, ValueError):
    """The submitted value cannot be used for this setting. Every raise site
    passes a hand-written sentence, so it is safe to show."""


_TRUE = {"1", "true", "yes", "on"}
_FALSE = {"0", "false", "no", "off"}


def normalise(spec: SettingSpec, raw: Any) -> str:
    """Validate a submitted value and return its canonical stored string."""
    if raw is None:
        raise InvalidSettingValue("A value is required. Use reset to fall back to the environment.")

    if spec.kind == "bool":
        if isinstance(raw, bool):
            return "true" if raw else "false"
        text = str(raw).strip().lower()
        if text in _TRUE:
            return "true"
        if text in _FALSE:
            return "false"
        raise InvalidSettingValue("Must be true or false.")

    text = str(raw)
    if spec.kind != "text" and spec.kind != "secret":
        text = text.strip()
    if spec.kind == "secret":
        # Surrounding whitespace in a pasted key is never intended; interior
        # newlines are (PEM private keys).
        text = text.strip()

    if text == "":
        raise InvalidSettingValue("Value cannot be empty. Use reset to fall back to the environment.")

    if spec.kind == "int":
        try:
            number = int(text)
        except ValueError:
            raise InvalidSettingValue("Must be a whole number.")
        if number < 0:
            raise InvalidSettingValue("Must not be negative.")
        return str(number)

    if spec.kind == "choice":
        if text not in spec.choices:
            raise InvalidSettingValue(f"Must be one of: {', '.join(spec.choices)}.")
        return text

    if spec.kind == "url":
        if not text.startswith(("http://", "https://", "ws://", "wss://")):
            raise InvalidSettingValue("Must start with http://, https://, ws:// or wss://.")
        return text.rstrip("/")

    if len(text) > 10_000:
        raise InvalidSettingValue("Value is too long.")
    return text


def coerce(spec: SettingSpec, stored: Optional[str]) -> Any:
    """Turn a stored string into the type the rest of the app expects."""
    if stored is None:
        return None
    if spec.kind == "bool":
        return stored.strip().lower() in _TRUE
    if spec.kind == "int":
        return int(stored)
    return stored


def key_fingerprint(value: Optional[str]) -> str:
    """Short, non-reversible identity for a credential, for cache keys.

    Lets a cache tell two keys apart without holding either in its key.
    """
    if not value:
        return "none"
    return hashlib.sha256(str(value).encode()).hexdigest()[:12]


def mask(value: Optional[str]) -> Optional[str]:
    """A hint that identifies a secret without revealing it."""
    if not value:
        return None
    value = str(value)
    if len(value) <= 8:
        return "••••"
    return f"••••{value[-4:]}"


# ---------------------------------------------------------------------------
# Overlay state
# ---------------------------------------------------------------------------

@dataclass
class _State:
    #: Environment/code value of every managed key, captured before the first
    #: overlay so a deleted row can restore it.
    baseline: Optional[Dict[str, Any]] = None
    #: key -> coerced value currently applied from the database.
    applied: Dict[str, Any] = field(default_factory=dict)
    #: key -> reason, for rows that exist but could not be applied.
    errors: Dict[str, str] = field(default_factory=dict)
    fingerprint: Optional[Tuple[int, Optional[datetime]]] = None
    loaded_at: Optional[datetime] = None
    #: Last time this process compared its copy with the table.
    checked_at: Optional[datetime] = None


_state = _State()
_poll_task: Optional[asyncio.Task] = None


def _ensure_baseline() -> Dict[str, Any]:
    if _state.baseline is None:
        _state.baseline = {spec.key: getattr(settings, spec.key, None) for spec in SPECS}
    return _state.baseline


def baseline_value(key: str) -> Any:
    """The value this key would have with no database override."""
    return _ensure_baseline().get(key)


def db_errors() -> Dict[str, str]:
    return dict(_state.errors)


def status() -> Dict[str, Any]:
    return {
        "overrides_applied": len(_state.applied),
        "errors": dict(_state.errors),
        "loaded_at": _state.loaded_at.isoformat() if _state.loaded_at else None,
        "checked_at": _state.checked_at.isoformat() if _state.checked_at else None,
        "poll_interval_seconds": POLL_INTERVAL_SECONDS,
    }


def apply_overrides(values: Dict[str, Any]) -> List[str]:
    """Set ``values`` on ``settings``; restore the baseline for keys no longer overridden.

    ``values`` maps key -> already-coerced value. Returns the keys whose
    effective value changed.
    """
    baseline = _ensure_baseline()
    changed: List[str] = []
    # Only keys the database overrides now, or overrode before, are touched.
    # Anything else is left exactly as found, so this can never undo a value
    # some other code path set at runtime.
    for key in set(values) | set(_state.applied):
        target = values[key] if key in values else baseline.get(key)
        current = getattr(settings, key, None)
        if current != target:
            setattr(settings, key, target)
            changed.append(key)
    _state.applied = dict(values)
    return changed


async def _fingerprint(db: AsyncSession) -> Tuple[int, Optional[datetime]]:
    from app.models.platform import PlatformSetting

    row = (
        await db.execute(select(func.count(PlatformSetting.key), func.max(PlatformSetting.updated_at)))
    ).one()
    return int(row[0] or 0), row[1]


def _decrypt(ciphertext: str) -> str:
    from app.services.integrations.credential_manager import get_credential_manager

    return get_credential_manager().decrypt(ciphertext)


def encrypt_secret(plaintext: str) -> str:
    """Encrypt a secret for storage. Raises ``CredentialEncryptionError`` when
    the deployment has no encryption key configured."""
    from app.services.integrations.credential_manager import get_credential_manager

    return get_credential_manager().encrypt(plaintext)


async def refresh(db: AsyncSession, *, force: bool = False) -> bool:
    """Re-read the table if it changed since the last load. Returns whether it did."""
    from app.models.platform import PlatformSetting

    fingerprint = await _fingerprint(db)
    _state.checked_at = datetime.utcnow()
    if not force and fingerprint == _state.fingerprint:
        return False

    rows = (await db.execute(select(PlatformSetting))).scalars().all()
    values: Dict[str, Any] = {}
    errors: Dict[str, str] = {}
    for row in rows:
        spec = SPEC_BY_KEY.get(row.key)
        if spec is None:
            # A key this build no longer manages (or never did). Ignored rather
            # than applied: nothing outside the catalogue may be overridden.
            continue
        try:
            raw = _decrypt(row.value_encrypted) if row.is_secret else row.value
            if raw is None:
                continue
            values[row.key] = coerce(spec, raw)
        except Exception as exc:  # undecryptable or corrupt: keep the env value
            errors[row.key] = f"{type(exc).__name__}: could not be applied; using the environment value."
            logger.error(f"Platform setting {row.key} could not be applied: {exc}")

    changed = apply_overrides(values)
    _state.errors = errors
    _state.fingerprint = fingerprint
    _state.loaded_at = datetime.utcnow()
    if changed:
        logger.info(f"Platform settings applied; changed: {', '.join(sorted(changed))}")
    return True


async def refresh_quietly(db: AsyncSession) -> None:
    """``refresh`` for callers that must never fail because of it (Celery
    tasks, the poll loop). A missing table — a deploy mid-migration — is not
    an error worth more than a debug line."""
    try:
        await refresh(db)
    except Exception as exc:
        logger.debug(f"Platform settings refresh skipped: {exc}")
        try:
            await db.rollback()
        except Exception:
            pass


async def _poll_forever() -> None:
    from app.database import AsyncSessionLocal

    while True:
        try:
            async with AsyncSessionLocal() as db:
                await refresh_quietly(db)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug(f"Platform settings poll failed: {exc}")
        await asyncio.sleep(POLL_INTERVAL_SECONDS)


async def start_polling() -> None:
    """Load once now, then keep this process in step with the table."""
    global _poll_task
    from app.database import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        await refresh_quietly(db)
    if _poll_task is None or _poll_task.done():
        _poll_task = asyncio.create_task(_poll_forever())


async def stop_polling() -> None:
    global _poll_task
    if _poll_task is not None:
        _poll_task.cancel()
        try:
            await _poll_task
        except (asyncio.CancelledError, Exception):
            pass
        _poll_task = None


def reset_for_tests() -> None:
    """Restore every managed key to its baseline and forget loaded state."""
    if _state.baseline is not None:
        apply_overrides({})
    _state.applied = {}
    _state.errors = {}
    _state.fingerprint = None
    _state.loaded_at = None
    _state.checked_at = None
