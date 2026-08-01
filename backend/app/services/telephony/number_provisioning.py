"""
Buying a phone number and recording it against an agent.

Shared by the dashboard's Phone Numbers page and the onboarding flow, so both
buy on the same account (Twilio by default — Voicecon's shared account, or the
user's own when they have connected one), point the carrier at the same webhook
URLs, and record the same provenance on the row.
"""
import logging
from typing import Any, Dict, Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.agent import Agent
from app.models.call import PhoneNumber
from app.models.user import User
from app.services.telephony.provider_registry import (
    CREDENTIAL_SOURCE_KEY,
    ResolvedProvider,
    resolve_provider,
)

logger = logging.getLogger(__name__)


class WebhookUrlNotConfigured(Exception):
    """The server has no public URL, so a bought number could never be reached."""


class NumberNotRecordedError(Exception):
    """The number was bought at the carrier but could not be saved locally."""

    def __init__(self, phone_number: str, account_name: str):
        self.phone_number = phone_number
        self.account_name = account_name
        super().__init__(
            f"{phone_number} was purchased on {account_name} but could not be "
            f"saved. Contact support before buying another number."
        )


def webhook_base_url() -> str:
    """
    Public base URL that carriers should call back on.

    Refuses to guess: a number bought with an unreachable webhook is billed to
    the buyer every month and can never take a call, so it is better to fail
    before the purchase than to sell a dead number.
    """
    base = (
        settings.API_BASE_URL
        or settings.TWILIO_PUBLIC_BASE_URL
        or (f"https://{settings.SERVER_HOST}" if settings.SERVER_HOST else "")
    ).rstrip("/")

    if not base:
        raise WebhookUrlNotConfigured(
            "This server has no public URL configured, so a purchased number "
            "would have nowhere to send calls. Set API_BASE_URL to the public "
            "HTTPS URL of this API and try again."
        )

    return base


def voice_webhook_url(provider_slug: str, agent_id: str) -> str:
    """Inbound-call webhook for an agent on a given carrier."""
    return f"{webhook_base_url()}/api/v1/telephony/{provider_slug}/voice/{agent_id}"


def status_webhook_url(provider_slug: str) -> str:
    """Call-status callback for a carrier."""
    return f"{webhook_base_url()}/api/v1/telephony/{provider_slug}/status"


async def purchase_number_for_agent(
    db: AsyncSession,
    user: User,
    agent: Agent,
    phone_number: str,
    provider: Optional[str] = None,
    connection_id: Optional[str] = None,
    country_code: Optional[str] = None,
    area_code: Optional[str] = None,
    monthly_cost: Optional[float] = None,
) -> Tuple[PhoneNumber, ResolvedProvider]:
    """
    Buy `phone_number` on the chosen account and wire it to `agent`.

    With no `provider`/`connection_id` the default account is used: the user's
    own Twilio if they connected one, otherwise Voicecon's shared Twilio.

    Raises:
        NoTelephonyProviderError / AmbiguousProviderError: no usable account.
        NumberProviderError: the carrier refused the purchase.
        WebhookUrlNotConfigured: the server has no public URL.
        NumberNotRecordedError: bought, but the local row could not be written.
    """
    resolved = await resolve_provider(
        db, user, slug=provider, connection_id=connection_id
    )

    purchased = await resolved.provider.purchase_number(
        phone_number=phone_number,
        voice_url=voice_webhook_url(resolved.slug, str(agent.id)),
        status_callback_url=status_webhook_url(resolved.slug),
        label=f"Voicecon Agent {agent.name}"[:255],
    )

    # Remember which account the number was bought on. Platform purchases have
    # no connection row, so without this a release could be aimed at the user's
    # own account — which does not own the number.
    provider_metadata: Dict[str, Any] = dict(purchased.provider_metadata or {})
    provider_metadata[CREDENTIAL_SOURCE_KEY] = resolved.option.source

    # The number is bought at this point — persist it even if some optional
    # detail is missing, so the user never pays for an untracked number.
    try:
        record = PhoneNumber(
            phone_number=purchased.phone_number,
            country_code=country_code,
            area_code=area_code,
            provider=purchased.provider,
            provider_sid=purchased.provider_sid,
            integration_connection_id=resolved.connection_uuid,
            provider_metadata=provider_metadata,
            agent_id=agent.id,
            user_id=agent.user_id,
            organization_id=agent.organization_id,
            capabilities=purchased.capabilities or {"voice": True},
            # Neither carrier quotes a price on purchase, so fall back to the
            # price the user was shown when they picked the number.
            monthly_cost=purchased.monthly_cost
            if purchased.monthly_cost is not None
            else monthly_cost,
            status="active",
        )

        db.add(record)
        await db.commit()
        await db.refresh(record)

    except Exception as e:
        await db.rollback()
        logger.error(
            f"Purchased {purchased.phone_number} on {resolved.slug} but failed to "
            f"record it: {e}",
            exc_info=True,
        )
        raise NumberNotRecordedError(purchased.phone_number, resolved.option.name)

    logger.info(
        f"Provisioned {purchased.phone_number} on {resolved.slug} "
        f"({resolved.option.source}, record {record.id})"
    )
    return record, resolved
