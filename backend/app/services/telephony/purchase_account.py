"""
Which account a number is bought on, as the *user* sees it.

Users choose between two flows, and only the second one is about carriers:

- **Voicecon numbers** (``source="voicecon"``) — bought on Voicecon's own
  carrier account. The carrier behind it is infrastructure: it is never named
  in API responses or error messages for these numbers.
- **Your own provider** (``source="own"``) — bought on a carrier account the
  workspace connected under Integrations (Twilio, Telnyx, …). Here the carrier
  is the user's own, so its name appears freely.

Every error the phone-number endpoints return goes through
:func:`public_error`, which keeps carrier, transport and internal detail in the
log and gives the user a plain sentence.
"""
import logging
from typing import Any, Dict, Optional, Tuple
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.telephony.provider_registry import (
    CREDENTIAL_SOURCE_KEY,
    INTEGRATION_SOURCE,
    PLATFORM_CONNECTION_PREFIX,
    PLATFORM_SOURCE,
    AmbiguousProviderError,
    NoTelephonyProviderError,
    list_available_providers,
)
from app.services.telephony.providers import NumberProviderError

logger = logging.getLogger(__name__)

SOURCE_VOICECON = "voicecon"
SOURCE_OWN = "own"
SOURCES = (SOURCE_VOICECON, SOURCE_OWN)

#: What API responses say instead of the carrier's name for a Voicecon number.
VOICECON_PROVIDER_LABEL = "voicecon"

#: Carriers a workspace may connect itself, for the "Connect your own
#: provider" flow. Slugs match ``TELEPHONY_PROVIDER_SLUGS`` and the connector
#: pages under Integrations.
OWN_PROVIDER_CATALOG = (
    {"slug": "twilio", "name": "Twilio", "description": "Use numbers and calling on your own Twilio account."},
    {"slug": "telnyx", "name": "Telnyx", "description": "Use numbers and calling on your own Telnyx account."},
)

VOICECON_UNAVAILABLE = (
    "Voicecon numbers aren't available right now. Please try again later, "
    "or connect your own provider."
)
CHOOSE_OWN_PROVIDER = "Choose which of your connected providers to use."

# Plain-language messages per action, used for every Voicecon-number failure
# and as the fallback for a user's own provider.
MESSAGES = {
    "search": "We couldn't load available numbers right now. Please try again.",
    "purchase": "Unable to complete the purchase. Please try again or contact support.",
    "release": "We couldn't release this number right now. Please try again or contact support.",
    "update": "We couldn't update this number right now. Please try again.",
    "list_own": "We couldn't load the numbers on your account right now. Please try again.",
    "import": "We couldn't add this number right now. Please try again.",
}
NUMBER_TAKEN = "That number is no longer available. Please choose another one."


def is_voicecon_number(phone_number: Any) -> bool:
    """True when the number lives on Voicecon's own carrier account."""
    source = (getattr(phone_number, "provider_metadata", None) or {}).get(CREDENTIAL_SOURCE_KEY)
    if source == PLATFORM_SOURCE:
        return True
    if source == INTEGRATION_SOURCE:
        return False
    # Rows from before the source was recorded: own-provider numbers always
    # carry the connection they were bought on.
    return getattr(phone_number, "integration_connection_id", None) is None


def public_source(option_source: str) -> str:
    return SOURCE_VOICECON if option_source == PLATFORM_SOURCE else SOURCE_OWN


async def voicecon_available(db: AsyncSession, org_id: UUID) -> bool:
    options = await list_available_providers(db, org_id)
    return any(o.source == PLATFORM_SOURCE for o in options)


async def resolve_account(
    db: AsyncSession,
    org_id: UUID,
    *,
    source: Optional[str],
    provider: Optional[str],
    connection_id: Optional[str],
) -> Tuple[Optional[str], Optional[str]]:
    """Turn the user's choice into the ``(provider, connection_id)`` to buy on.

    ``source=None`` keeps the older API behaviour (carrier/connection chosen
    directly) for existing API clients.
    """
    if source is None:
        return provider, connection_id
    if source not in SOURCES:
        raise HTTPException(status_code=400, detail="Choose Voicecon numbers or your own provider.")

    options = await list_available_providers(db, org_id)
    if source == SOURCE_VOICECON:
        platform = next((o for o in options if o.source == PLATFORM_SOURCE), None)
        if platform is None:
            raise NoTelephonyProviderError(VOICECON_UNAVAILABLE)
        return None, platform.connection_id

    own = [o for o in options if o.source == INTEGRATION_SOURCE]
    if connection_id:
        if connection_id.startswith(PLATFORM_CONNECTION_PREFIX) or not any(
            o.connection_id == connection_id for o in own
        ):
            raise NoTelephonyProviderError(
                "That provider isn't connected any more. Reconnect it under Integrations."
            )
        return None, connection_id
    if len(own) == 1:
        return None, own[0].connection_id
    if not own:
        raise NoTelephonyProviderError(
            "You haven't connected a phone provider yet. Connect one under Integrations first."
        )
    raise AmbiguousProviderError(CHOOSE_OWN_PROVIDER)


def public_error(e: Exception, *, action: str, voicecon: bool) -> HTTPException:
    """The HTTP error to show for a failed phone-number operation.

    The full exception is logged here; the response carries only a sentence
    written for the user. For Voicecon numbers it never names the carrier.
    """
    fallback = MESSAGES.get(action, "Something went wrong. Please try again.")

    if isinstance(e, (NoTelephonyProviderError, AmbiguousProviderError)):
        # These messages are written for users. For Voicecon they are ours
        # (see resolve_account); an own-provider one may name their carrier.
        message = e.public_message
        if voicecon and message != VOICECON_UNAVAILABLE:
            message = VOICECON_UNAVAILABLE
        return HTTPException(status_code=400, detail=message)

    if isinstance(e, NumberProviderError):
        logger.error("Phone number %s failed (voicecon=%s): %s", action, voicecon, e)
        status_code = getattr(e, "status_code", None)
        rejected = status_code is not None and 400 <= status_code < 500 and status_code not in (401, 403, 429)
        if action == "purchase" and rejected:
            return HTTPException(status_code=409, detail=NUMBER_TAKEN)
        if voicecon:
            return HTTPException(status_code=502, detail=fallback)
        return HTTPException(status_code=502, detail=e.public_message or fallback)

    logger.error("Unexpected phone number %s failure: %s", action, e, exc_info=True)
    return HTTPException(status_code=500, detail=fallback)


def mask_provider(data: Dict[str, Any], *, voicecon: bool) -> Dict[str, Any]:
    """Hide carrier identity (name and carrier-side id) on a Voicecon number."""
    if voicecon:
        data = {**data, "provider": VOICECON_PROVIDER_LABEL}
        if "provider_sid" in data:
            data["provider_sid"] = None
    return data
