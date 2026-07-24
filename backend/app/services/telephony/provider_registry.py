"""
Resolve which telephony carrier a user can buy numbers from.

A user buys numbers on their *own* carrier account, which they connect under
Integrations. This module turns those connections into ready-to-use
`NumberProvider` instances:

- `list_available_providers` — what to show in the provider picker.
- `resolve_provider` — the provider to actually use for a search/purchase.
- `resolve_provider_for_number` — the provider that owns an existing number,
  so releases and webhook updates go back to the right carrier.

If no carrier integration is connected but the server has Twilio credentials in
its environment, Twilio is still offered as a "platform" provider. That keeps
single-tenant and demo deployments working exactly as they did before.
"""
import base64
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.integration import IntegrationConnection, IntegrationConnector
from app.models.user import User
from app.services.integrations.credential_manager import get_credential_manager
from app.services.telephony.providers import (
    PROVIDER_CLASSES,
    TELEPHONY_PROVIDER_SLUGS,
    NumberProvider,
    NumberProviderError,
)

logger = logging.getLogger(__name__)

#: Marker used instead of a connection id when the provider is backed by
#: server-level credentials rather than a user's integration.
PLATFORM_SOURCE = "platform"
INTEGRATION_SOURCE = "integration"


class NoTelephonyProviderError(Exception):
    """Raised when the user has no carrier available to buy numbers from."""


class AmbiguousProviderError(Exception):
    """Raised when several carriers are connected and none was chosen."""


@dataclass
class ProviderOption:
    """A carrier the user can buy numbers from."""

    slug: str
    name: str
    source: str
    connection_id: Optional[str] = None
    connection_name: Optional[str] = None

    def as_dict(self) -> Dict[str, Any]:
        return {
            "slug": self.slug,
            "name": self.name,
            "source": self.source,
            "connection_id": self.connection_id,
            "connection_name": self.connection_name,
        }


@dataclass
class ResolvedProvider:
    """A provider instance plus the connection it was built from."""

    provider: NumberProvider
    option: ProviderOption

    @property
    def slug(self) -> str:
        return self.option.slug

    @property
    def connection_uuid(self) -> Optional[UUID]:
        if not self.option.connection_id:
            return None
        try:
            return UUID(self.option.connection_id)
        except (TypeError, ValueError):
            return None


async def list_available_providers(db: AsyncSession, user: User) -> List[ProviderOption]:
    """
    List the carriers this user can currently buy numbers from.

    Only active connections to a telephony connector are returned, so a carrier
    the user has not connected never shows up in the picker.
    """
    result = await db.execute(
        select(IntegrationConnection, IntegrationConnector)
        .join(
            IntegrationConnector,
            IntegrationConnector.id == IntegrationConnection.connector_id,
        )
        .where(
            IntegrationConnection.user_id == user.id,
            IntegrationConnection.is_active.is_(True),
            IntegrationConnection.status == "active",
            IntegrationConnector.slug.in_(TELEPHONY_PROVIDER_SLUGS),
        )
        .order_by(IntegrationConnection.created_at.asc())
    )

    options: List[ProviderOption] = []
    for connection, connector in result.all():
        options.append(
            ProviderOption(
                slug=connector.slug,
                name=connector.name,
                source=INTEGRATION_SOURCE,
                connection_id=str(connection.id),
                connection_name=connection.name or connector.name,
            )
        )

    # Server-level Twilio credentials keep working when nothing is connected.
    has_twilio = any(option.slug == "twilio" for option in options)
    if not has_twilio and settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN:
        options.append(
            ProviderOption(
                slug="twilio",
                name="Twilio",
                source=PLATFORM_SOURCE,
                connection_name="Platform credentials",
            )
        )

    return options


async def resolve_provider(
    db: AsyncSession,
    user: User,
    slug: Optional[str] = None,
    connection_id: Optional[str] = None,
) -> ResolvedProvider:
    """
    Pick the carrier to use for a search or purchase.

    With one carrier available it is used automatically; with several, the
    caller must say which one (by `slug`, or by `connection_id` when the same
    carrier is connected more than once).

    Raises:
        NoTelephonyProviderError: nothing connected, or the requested carrier
            is not connected.
        AmbiguousProviderError: several carriers available and none chosen.
    """
    options = await list_available_providers(db, user)

    if not options:
        raise NoTelephonyProviderError(
            "No phone provider is connected. Connect Twilio or Telnyx under "
            "Integrations to buy phone numbers."
        )

    if connection_id:
        match = next((o for o in options if o.connection_id == connection_id), None)
        if not match:
            raise NoTelephonyProviderError(
                "That phone provider connection is not available. It may have "
                "been disconnected."
            )
    elif slug:
        matches = [o for o in options if o.slug == slug]
        if not matches:
            available = ", ".join(sorted({o.name for o in options})) or "none"
            raise NoTelephonyProviderError(
                f"{slug.title()} is not connected. Connect it under Integrations "
                f"first. Currently available: {available}."
            )
        match = matches[0]
    else:
        distinct_slugs = {o.slug for o in options}
        if len(distinct_slugs) > 1:
            raise AmbiguousProviderError(
                "Several phone providers are connected "
                f"({', '.join(sorted(distinct_slugs))}). Choose which one to use."
            )
        match = options[0]

    return ResolvedProvider(provider=await _build_provider(db, match), option=match)


async def resolve_provider_for_number(
    db: AsyncSession,
    user: User,
    provider_slug: str,
    connection_id: Optional[UUID] = None,
) -> ResolvedProvider:
    """
    Rebuild the provider that owns an already-purchased number.

    Prefers the exact connection the number was bought on; falls back to any
    active connection for the same carrier, which covers numbers bought before
    the connection was recorded (and numbers bought on platform credentials).
    """
    options = await list_available_providers(db, user)

    match = None
    if connection_id:
        match = next(
            (o for o in options if o.connection_id == str(connection_id)), None
        )
    if match is None:
        match = next((o for o in options if o.slug == provider_slug), None)

    if match is None:
        raise NoTelephonyProviderError(
            f"No active {provider_slug.title()} connection is available to manage "
            f"this number. Reconnect {provider_slug.title()} under Integrations."
        )

    return ResolvedProvider(provider=await _build_provider(db, match), option=match)


async def _build_provider(db: AsyncSession, option: ProviderOption) -> NumberProvider:
    """Instantiate the carrier client behind a provider option."""
    provider_class = PROVIDER_CLASSES.get(option.slug)
    if not provider_class:
        raise NoTelephonyProviderError(f"Unsupported phone provider: {option.slug}")

    if option.source == PLATFORM_SOURCE:
        credentials = _platform_credentials(option.slug)
    else:
        connection = await db.get(IntegrationConnection, UUID(option.connection_id))
        if not connection:
            raise NoTelephonyProviderError(
                "That phone provider connection no longer exists."
            )
        credentials = _connection_credentials(option.slug, connection)

    return provider_class(credentials)


def _platform_credentials(slug: str) -> Dict[str, Any]:
    """Credentials taken from server configuration rather than a connection."""
    if slug == "twilio":
        return {
            "account_sid": settings.TWILIO_ACCOUNT_SID,
            "auth_token": settings.TWILIO_AUTH_TOKEN,
        }
    return {}


def _connection_credentials(
    slug: str, connection: IntegrationConnection
) -> Dict[str, Any]:
    """
    Decrypt an integration connection into the credential shape its provider
    expects.

    Twilio connections store a Base64 `AccountSID:AuthToken` pair in the API key
    field (matching `TwilioConnector`); Telnyx stores a plain API key.
    """
    credential_manager = get_credential_manager()

    if not connection.api_key_encrypted:
        raise NumberProviderError(
            f"The {slug.title()} connection has no stored credentials. "
            f"Reconnect it under Integrations."
        )

    secret = credential_manager.decrypt(connection.api_key_encrypted)

    auth_data: Dict[str, Any] = {}
    if connection.auth_data_encrypted:
        try:
            auth_data = credential_manager.decrypt_dict(connection.auth_data_encrypted)
        except Exception as e:  # pragma: no cover - defensive
            logger.warning(f"Could not decrypt auth data for connection {connection.id}: {e}")

    if slug == "twilio":
        account_sid = auth_data.get("account_sid")
        auth_token = auth_data.get("auth_token")

        # The canonical storage format is Base64("SID:TOKEN") in the API key.
        if not (account_sid and auth_token):
            try:
                decoded = base64.b64decode(secret).decode()
                if ":" in decoded:
                    decoded_sid, decoded_token = decoded.split(":", 1)
                    account_sid = account_sid or decoded_sid
                    auth_token = auth_token or decoded_token
            except Exception:
                logger.debug("Twilio API key is not a Base64 SID:token pair")

        return {"account_sid": account_sid, "auth_token": auth_token}

    if slug == "telnyx":
        return {"api_key": secret}

    return {"api_key": secret}
