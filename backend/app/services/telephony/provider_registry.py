"""
Resolve which telephony carrier a user can buy numbers from.

Twilio is the default carrier. Numbers can be bought two ways:

- **Platform** — on Voicecon's own Twilio account, from the server's
  `TWILIO_ACCOUNT_SID` / `TWILIO_AUTH_TOKEN`. Always offered when those are
  configured, so a user can buy a number without connecting anything.
- **Integration** — on the user's *own* carrier account (Twilio or Telnyx),
  connected under Integrations.

Both are offered side by side, so a user who has connected their own Twilio can
still pick either account. This module turns them into ready-to-use
`NumberProvider` instances:

- `list_available_providers` — what to show in the provider picker, Twilio first.
- `resolve_provider` — the provider to actually use for a search/purchase.
- `resolve_provider_for_number` — the provider that owns an existing number,
  so releases and webhook updates go back to the right account.
- `credentials_for_number` — raw credentials for the account a number lives on,
  used for webhook signature checks and outbound calls.
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

#: Carrier used when the caller does not name one. Twilio is the product
#: default: it is the carrier the platform account runs on.
DEFAULT_PROVIDER_SLUG = "twilio"

#: Platform providers have no `IntegrationConnection` row, so they get a
#: synthetic connection id instead. It keeps the platform account addressable
#: and distinct from a user's own connection to the same carrier — without it,
#: "buy on Twilio" would be ambiguous for a user who connected their own.
PLATFORM_CONNECTION_PREFIX = "platform:"

#: Label shown for the platform account in the provider picker.
PLATFORM_CONNECTION_NAME = "Voicecon shared account"

#: `provider_metadata` key recording which account a number was bought on, so
#: it can be routed back there once the picker offers both.
CREDENTIAL_SOURCE_KEY = "credential_source"


def platform_connection_id(slug: str) -> str:
    """Synthetic connection id identifying a carrier's platform credentials."""
    return f"{PLATFORM_CONNECTION_PREFIX}{slug}"


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


def _platform_options() -> List[ProviderOption]:
    """
    Carriers the server itself holds credentials for.

    Today that is Twilio only — the platform account users buy on when they
    have not brought their own.
    """
    if not (settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN):
        return []

    return [
        ProviderOption(
            slug="twilio",
            name="Twilio",
            source=PLATFORM_SOURCE,
            connection_id=platform_connection_id("twilio"),
            connection_name=PLATFORM_CONNECTION_NAME,
        )
    ]


async def list_available_providers(db: AsyncSession, org_id: UUID) -> List[ProviderOption]:
    """
    List the accounts this workspace can currently buy numbers from.

    Returns the workspace's connected carriers *and* the platform Twilio account
    (when the server has credentials), so a team who connected their own Twilio
    can still choose between the two. Scoped to the workspace, not the
    individual, so a carrier one teammate connected is usable by the whole team.

    Ordered so the first entry is the sensible default: the user's own Twilio if
    they connected one, otherwise the platform Twilio, with other carriers last.
    """
    result = await db.execute(
        select(IntegrationConnection, IntegrationConnector)
        .join(
            IntegrationConnector,
            IntegrationConnector.id == IntegrationConnection.connector_id,
        )
        .where(
            IntegrationConnection.organization_id == org_id,
            IntegrationConnection.is_active.is_(True),
            IntegrationConnection.status == "active",
            IntegrationConnector.slug.in_(TELEPHONY_PROVIDER_SLUGS),
        )
        .order_by(IntegrationConnection.created_at.asc())
    )

    connected: List[ProviderOption] = []
    for connection, connector in result.all():
        connected.append(
            ProviderOption(
                slug=connector.slug,
                name=connector.name,
                source=INTEGRATION_SOURCE,
                connection_id=str(connection.id),
                connection_name=connection.name or connector.name,
            )
        )

    default_connected = [o for o in connected if o.slug == DEFAULT_PROVIDER_SLUG]
    other_connected = [o for o in connected if o.slug != DEFAULT_PROVIDER_SLUG]

    return [*default_connected, *_platform_options(), *other_connected]


async def resolve_provider(
    db: AsyncSession,
    org_id: UUID,
    slug: Optional[str] = None,
    connection_id: Optional[str] = None,
) -> ResolvedProvider:
    """
    Pick the account to use for a search or purchase.

    `connection_id` selects an exact account — a user's own connection, or the
    platform account via its synthetic `platform:<slug>` id. `slug` selects a
    carrier, preferring the user's own account over the platform one. With
    neither, Twilio is used when available, since it is the default carrier.

    Raises:
        NoTelephonyProviderError: no account available, or the requested one is
            not available.
        AmbiguousProviderError: several carriers available, none of them the
            default, and none chosen.
    """
    options = await list_available_providers(db, org_id)

    if not options:
        raise NoTelephonyProviderError(
            "No phone provider is available. Connect Twilio or Telnyx under "
            "Integrations to buy phone numbers."
        )

    if connection_id:
        match = next((o for o in options if o.connection_id == connection_id), None)
        if not match:
            raise NoTelephonyProviderError(
                "That phone provider account is not available. It may have been "
                "disconnected."
            )
    elif slug:
        # Options are ordered own-account-first, so this prefers the user's own
        # carrier account over the platform one for the same carrier.
        matches = [o for o in options if o.slug == slug]
        if not matches:
            available = ", ".join(sorted({o.name for o in options})) or "none"
            raise NoTelephonyProviderError(
                f"{slug.title()} is not available. Connect it under Integrations "
                f"first. Currently available: {available}."
            )
        match = matches[0]
    else:
        distinct_slugs = {o.slug for o in options}
        default_match = next(
            (o for o in options if o.slug == DEFAULT_PROVIDER_SLUG), None
        )
        if len(distinct_slugs) > 1 and default_match is None:
            raise AmbiguousProviderError(
                "Several phone providers are connected "
                f"({', '.join(sorted(distinct_slugs))}). Choose which one to use."
            )
        match = default_match or options[0]

    return ResolvedProvider(provider=await _build_provider(db, match), option=match)


async def resolve_provider_for_number(
    db: AsyncSession,
    org_id: UUID,
    provider_slug: str,
    connection_id: Optional[UUID] = None,
    provider_metadata: Optional[Dict[str, Any]] = None,
) -> ResolvedProvider:
    """
    Rebuild the provider that owns an already-purchased number.

    A number lives in exactly one account, so releases and webhook changes must
    go back to that account:

    1. the connection it was bought on, when one was recorded;
    2. the platform account, when the number was bought on platform credentials
       (recorded in `provider_metadata`) — never the user's own account, which
       does not own the number;
    3. otherwise any account for the same carrier, which covers numbers bought
       before the source was recorded.
    """
    options = await list_available_providers(db, org_id)

    match = None
    if connection_id:
        match = next(
            (o for o in options if o.connection_id == str(connection_id)), None
        )

    if match is None and (provider_metadata or {}).get(CREDENTIAL_SOURCE_KEY) == PLATFORM_SOURCE:
        match = next(
            (
                o
                for o in options
                if o.slug == provider_slug and o.source == PLATFORM_SOURCE
            ),
            None,
        )
        if match is None:
            raise NoTelephonyProviderError(
                f"This number was bought on the Voicecon {provider_slug.title()} "
                f"account, which is no longer configured on the server. Contact "
                f"support to manage it."
            )

    if match is None:
        match = next((o for o in options if o.slug == provider_slug), None)

    if match is None:
        raise NoTelephonyProviderError(
            f"No active {provider_slug.title()} account is available to manage "
            f"this number. Reconnect {provider_slug.title()} under Integrations."
        )

    return ResolvedProvider(provider=await _build_provider(db, match), option=match)


async def credentials_for_number(
    db: AsyncSession,
    provider_slug: str,
    connection_id: Optional[UUID] = None,
    provider_metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Credentials for the carrier account a number lives on.

    Used where a `NumberProvider` is not what is needed — validating the webhook
    signature on an inbound call, or dialling out from the number — both of
    which must use the account that actually owns it. Returns `{}` when the
    account cannot be resolved, so callers can fall back rather than fail.
    """
    if connection_id:
        connection = await db.get(IntegrationConnection, connection_id)
        if connection:
            try:
                return _connection_credentials(provider_slug, connection)
            except NumberProviderError as e:
                logger.warning(f"Could not read credentials for {connection_id}: {e}")
        return {}

    if (provider_metadata or {}).get(CREDENTIAL_SOURCE_KEY) == INTEGRATION_SOURCE:
        # Bought on a user connection that has since been removed.
        return {}

    return _platform_credentials(provider_slug)


async def _build_provider(db: AsyncSession, option: ProviderOption) -> NumberProvider:
    """Instantiate the carrier client behind a provider option."""
    provider_class = PROVIDER_CLASSES.get(option.slug)
    if not provider_class:
        raise NoTelephonyProviderError(f"Unsupported phone provider: {option.slug}")

    if option.source == PLATFORM_SOURCE:
        credentials = _platform_credentials(option.slug)
        if not credentials or not all(credentials.values()):
            raise NoTelephonyProviderError(
                f"The Voicecon {option.name} account is not configured on this "
                f"server. Connect your own {option.name} account under "
                f"Integrations to buy numbers."
            )
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
