"""
Phone number management endpoints.

Handles:
- Listing the carriers a user can buy numbers from
- Searching available phone numbers
- Provisioning/purchasing phone numbers
- Listing user's phone numbers
- Updating phone number configuration
- Releasing phone numbers

Two purchase flows share these endpoints (see
``services/telephony/purchase_account``):

- ``source=voicecon`` — a Voicecon number, bought on Voicecon's own carrier
  account. The carrier is never named in responses or errors for these.
- ``source=own`` — a number on a carrier account the workspace connected
  under Integrations (Twilio, Telnyx).

The account a number was bought on is recorded on the row so releases and
webhook changes go back to it. Errors never carry carrier, transport or
internal detail; that stays in the log.
"""
import logging
from typing import Any, Dict, List, Literal, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, Field

from app.core.entitlement_guard import require_entitlement
from app.database import get_db
from app.models.call import PhoneNumber
from app.services.billing import catalog
from app.models.agent import Agent
from app.models.user import User
from app.services.telephony.number_provisioning import (
    NumberNotRecordedError,
    WebhookUrlNotConfigured,
    purchase_number_for_agent,
    status_webhook_url,
    voice_webhook_url,
)
from app.services.telephony.provider_registry import (
    CREDENTIAL_SOURCE_KEY,
    AmbiguousProviderError,
    NoTelephonyProviderError,
    list_available_providers,
    resolve_provider,
    resolve_provider_for_number,
)
from app.services.telephony.providers import NumberProviderError
from app.services.telephony.purchase_account import (
    OWN_PROVIDER_CATALOG,
    SOURCE_OWN,
    SOURCE_VOICECON,
    is_voicecon_number,
    mask_provider,
    public_error,
    public_source,
    resolve_account,
)
from app.core.dependencies import get_current_active_user, get_current_org_id

logger = logging.getLogger(__name__)

router = APIRouter()


# Schemas
PurchaseSource = Literal["voicecon", "own"]


class PhoneNumberProvision(BaseModel):
    """Phone number provisioning request."""
    phone_number: str = Field(..., description="Phone number to purchase (E.164 format)")
    agent_id: UUID = Field(..., description="Agent ID to associate with the number")
    source: Optional[PurchaseSource] = Field(
        default=None,
        description=(
            "'voicecon' for a Voicecon number, 'own' for your own connected provider "
            "(then connection_id picks which one). Omit to choose by provider/connection_id."
        ),
    )
    provider: Optional[str] = Field(
        default=None,
        description="Carrier to buy from (twilio, telnyx). Required when more than one is connected.",
    )
    connection_id: Optional[str] = Field(
        default=None,
        description="Specific carrier connection to use, when the same carrier is connected more than once",
    )
    country_code: Optional[str] = Field(default=None, description="Country code of the number")
    area_code: Optional[str] = Field(default=None, description="Area code of the number")
    monthly_cost: Optional[float] = Field(
        default=None,
        ge=0,
        description=(
            "Monthly price quoted for this number at search time. Display only — "
            "neither carrier returns a price on purchase, so it is echoed back "
            "from the search result the user accepted."
        ),
    )


class PhoneNumberUpdate(BaseModel):
    """Phone number update request."""
    agent_id: Optional[UUID] = Field(default=None, description="Update agent association")
    status: Optional[str] = Field(default=None, description="Update status (active, inactive)")


class PhoneNumberResponse(BaseModel):
    """Phone number response."""
    id: UUID
    phone_number: str
    country_code: Optional[str]
    area_code: Optional[str]
    provider: str
    provider_sid: Optional[str]
    agent_id: Optional[UUID]
    capabilities: dict
    status: str
    monthly_cost: Optional[float]
    created_at: str
    source: str = Field(
        default=SOURCE_VOICECON,
        description="'voicecon' (a Voicecon number) or 'own' (your own connected provider)",
    )

    class Config:
        from_attributes = True


class AvailablePhoneNumber(BaseModel):
    """Available phone number from a carrier."""
    phone_number: str
    friendly_name: str
    provider: str
    locality: Optional[str] = None
    region: Optional[str] = None
    capabilities: dict = Field(default_factory=dict)
    monthly_cost: Optional[float] = None
    setup_cost: Optional[float] = None
    currency: Optional[str] = None


class OwnProviderOption(BaseModel):
    """A carrier the workspace may connect for the "your own provider" flow."""
    slug: str
    name: str
    description: str
    connected: bool


class PurchaseOptionsResponse(BaseModel):
    """What the purchase screen can offer this workspace."""
    voicecon_available: bool = Field(description="Whether Voicecon numbers can be bought")
    own_providers: List["TelephonyProviderResponse"] = Field(
        description="Carrier accounts the workspace connected itself"
    )
    supported_providers: List[OwnProviderOption] = Field(
        description="Carriers that can be connected for the own-provider flow"
    )


class TelephonyProviderResponse(BaseModel):
    """A carrier account the user can buy numbers from."""
    slug: str
    name: str
    source: str = Field(description="'integration' (user-connected) or 'platform' (Voicecon's own account)")
    connection_id: Optional[str] = None
    connection_name: Optional[str] = None
    is_default: bool = Field(
        default=False,
        description="Pre-selected in the purchase UI when the user makes no choice",
    )


def _to_response(phone_number: PhoneNumber) -> PhoneNumberResponse:
    """Serialise a phone number row. A Voicecon number never names its carrier."""
    voicecon = is_voicecon_number(phone_number)
    return PhoneNumberResponse(**mask_provider(dict(
        id=phone_number.id,
        phone_number=phone_number.phone_number,
        country_code=phone_number.country_code,
        area_code=phone_number.area_code,
        provider=phone_number.provider,
        provider_sid=phone_number.provider_sid,
        agent_id=phone_number.agent_id,
        capabilities=phone_number.capabilities or {},
        status=phone_number.status,
        monthly_cost=float(phone_number.monthly_cost) if phone_number.monthly_cost else None,
        created_at=phone_number.created_at.isoformat(),
        source=SOURCE_VOICECON if voicecon else SOURCE_OWN,
    ), voicecon=voicecon))


@router.get("/providers", response_model=List[TelephonyProviderResponse])
async def list_phone_number_providers(
    current_user: User = Depends(get_current_active_user),
    org_id: UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db),
):
    """
    List the carrier accounts this workspace connected itself.

    Voicecon's own account is not listed: buying a Voicecon number doesn't
    involve choosing a carrier (see ``GET /phone-numbers/purchase-options``).
    """
    try:
        options = [o for o in await list_available_providers(db, org_id) if o.source != "platform"]
        return [
            TelephonyProviderResponse(**option.as_dict(), is_default=(index == 0))
            for index, option in enumerate(options)
        ]
    except Exception as e:
        logger.error(f"Error listing phone number providers: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="We couldn't load your connected providers right now. Please try again.",
        )


@router.get("/purchase-options", response_model=PurchaseOptionsResponse)
async def get_purchase_options(
    current_user: User = Depends(get_current_active_user),
    org_id: UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db),
):
    """
    What the purchase screen can offer: Voicecon numbers (without naming the
    carrier behind them), and the workspace's own connected carriers.
    """
    try:
        options = await list_available_providers(db, org_id)
    except Exception as e:
        logger.error(f"Error loading phone number purchase options: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="We couldn't load phone number options right now. Please try again.",
        )
    own = [o for o in options if o.source != "platform"]
    connected_slugs = {o.slug for o in own}
    return PurchaseOptionsResponse(
        voicecon_available=any(o.source == "platform" for o in options),
        own_providers=[
            TelephonyProviderResponse(**o.as_dict(), is_default=(i == 0))
            for i, o in enumerate(own)
        ],
        supported_providers=[
            OwnProviderOption(**p, connected=p["slug"] in connected_slugs)
            for p in OWN_PROVIDER_CATALOG
        ],
    )


@router.get("/search", response_model=List[AvailablePhoneNumber])
async def search_phone_numbers(
    country_code: str = Query(default="US", description="Country code"),
    area_code: Optional[str] = Query(default=None, description="Area code"),
    contains: Optional[str] = Query(default=None, description="Pattern to search for"),
    limit: int = Query(default=10, ge=1, le=50, description="Max results"),
    provider: Optional[str] = Query(
        default=None, description="Carrier to search (twilio, telnyx)"
    ),
    connection_id: Optional[str] = Query(
        default=None, description="Specific carrier connection to search on"
    ),
    source: Optional[PurchaseSource] = Query(
        default=None,
        description="'voicecon' for Voicecon numbers, 'own' for your own connected provider",
    ),
    current_user: User = Depends(get_current_active_user),
    org_id: UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db),
):
    """
    Search for available phone numbers — Voicecon numbers (`source=voicecon`)
    or numbers on one of the workspace's own providers (`source=own`).
    """
    # Carriers reject a malformed North American area code with a generic
    # 400, which reads as a carrier outage. Say what is wrong instead.
    area_code = (area_code or "").strip() or None
    if (
        area_code
        and country_code.upper() in ("US", "CA")
        and not (area_code.isdigit() and len(area_code) == 3)
    ):
        raise HTTPException(
            status_code=400,
            detail="US and Canadian area codes are 3 digits, for example 415.",
        )

    contains = (contains or "").strip() or None
    if contains and not contains.replace("*", "").isdigit():
        raise HTTPException(
            status_code=400,
            detail="“Contains” should be digits only, for example 555.",
        )

    voicecon = source == SOURCE_VOICECON
    try:
        provider, connection_id = await resolve_account(
            db, org_id, source=source, provider=provider, connection_id=connection_id
        )
        resolved = await resolve_provider(
            db, org_id, slug=provider, connection_id=connection_id
        )
        voicecon = resolved.option.source == "platform"
        results = await resolved.provider.search_numbers(
            country_code=country_code,
            area_code=area_code,
            contains=contains,
            limit=limit,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise public_error(e, action="search", voicecon=voicecon)

    return [
        AvailablePhoneNumber(**mask_provider(number.as_dict(), voicecon=voicecon))
        for number in results
    ]


@router.post(
    "/provision",
    response_model=PhoneNumberResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[
        # Buying is gated on the *feature* before the *limit*: a trial has no
        # allowance to check, it simply may not buy. The feature check also
        # covers a user's own connected carrier, because the gate is on the
        # action rather than on whose credentials the carrier bills.
        Depends(require_entitlement(feature=catalog.PHONE_NUMBER_PURCHASE)),
        Depends(require_entitlement(limit=catalog.LIMIT_PHONE_NUMBERS)),
    ],
)
async def provision_phone_number(
    provision_request: PhoneNumberProvision,
    current_user: User = Depends(get_current_active_user),
    org_id: UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db),
):
    """
    Purchase a phone number from a connected carrier and wire it to an agent.
    """
    # Verify agent belongs to user
    agent_result = await db.execute(
        select(Agent).where(
            Agent.id == provision_request.agent_id,
            Agent.organization_id == org_id,
        )
    )
    agent = agent_result.scalar_one_or_none()

    if not agent:
        raise HTTPException(
            status_code=404,
            detail="Agent not found or access denied"
        )

    # Check if number already exists
    existing_result = await db.execute(
        select(PhoneNumber).where(
            PhoneNumber.phone_number == provision_request.phone_number
        )
    )
    if existing_result.scalar_one_or_none():
        raise HTTPException(
            status_code=400,
            detail="That number is already in use. Please choose another one."
        )

    voicecon = provision_request.source == SOURCE_VOICECON
    try:
        provider, connection_id = await resolve_account(
            db,
            org_id,
            source=provision_request.source,
            provider=provision_request.provider,
            connection_id=provision_request.connection_id,
        )
        # Pin the exact account up front, so an error is worded for the
        # account actually used (a Voicecon purchase never names the carrier).
        account = await resolve_provider(db, org_id, slug=provider, connection_id=connection_id)
        voicecon = account.option.source == "platform"
        phone_number_record, resolved = await purchase_number_for_agent(
            db,
            current_user,
            agent,
            phone_number=provision_request.phone_number,
            provider=account.option.slug,
            connection_id=account.option.connection_id,
            country_code=provision_request.country_code,
            area_code=provision_request.area_code,
            monthly_cost=provision_request.monthly_cost,
        )
    except HTTPException:
        raise
    except Exception as e:
        # WebhookUrlNotConfigured / NumberNotRecordedError / anything else land
        # here too: logged in full, shown as the plain purchase message.
        raise public_error(e, action="purchase", voicecon=voicecon)

    return _to_response(phone_number_record)


@router.get("", response_model=List[PhoneNumberResponse])
async def list_phone_numbers(
    agent_id: Optional[UUID] = Query(default=None, description="Filter by agent ID"),
    status: Optional[str] = Query(default=None, description="Filter by status"),
    current_user: User = Depends(get_current_active_user),
    org_id: UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db),
):
    """
    List user's phone numbers.

    Args:
        agent_id: Optional agent ID filter
        status: Optional status filter
        current_user: Current authenticated user
        db: Database session

    Returns:
        List of phone numbers
    """
    try:
        # Build query
        query = select(PhoneNumber).where(
            PhoneNumber.organization_id == org_id
        )

        if agent_id:
            query = query.where(PhoneNumber.agent_id == agent_id)

        if status:
            query = query.where(PhoneNumber.status == status)

        # Execute query
        result = await db.execute(query.order_by(PhoneNumber.created_at.desc()))
        phone_numbers = result.scalars().all()

        return [_to_response(pn) for pn in phone_numbers]

    except Exception as e:
        logger.error(f"Error listing phone numbers: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="We couldn't load your phone numbers right now. Please try again."
        )


@router.get("/{phone_number_id}", response_model=PhoneNumberResponse)
async def get_phone_number(
    phone_number_id: UUID,
    current_user: User = Depends(get_current_active_user),
    org_id: UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db),
):
    """
    Get phone number details.

    Args:
        phone_number_id: Phone number ID
        current_user: Current authenticated user
        db: Database session

    Returns:
        Phone number details
    """
    try:
        result = await db.execute(
            select(PhoneNumber).where(
                PhoneNumber.id == phone_number_id,
                PhoneNumber.organization_id == org_id,
            )
        )
        phone_number = result.scalar_one_or_none()

        if not phone_number:
            raise HTTPException(
                status_code=404,
                detail="Phone number not found or access denied"
            )

        return _to_response(phone_number)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting phone number: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="We couldn't load this phone number right now. Please try again."
        )


@router.patch("/{phone_number_id}", response_model=PhoneNumberResponse)
async def update_phone_number(
    phone_number_id: UUID,
    update_request: PhoneNumberUpdate,
    current_user: User = Depends(get_current_active_user),
    org_id: UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db),
):
    """
    Update phone number configuration.

    Reassigning the number to a different agent also re-points the carrier's
    voice webhook at that agent.
    """
    result = await db.execute(
        select(PhoneNumber).where(
            PhoneNumber.id == phone_number_id,
            PhoneNumber.organization_id == org_id,
        )
    )
    phone_number = result.scalar_one_or_none()

    if not phone_number:
        raise HTTPException(
            status_code=404,
            detail="Phone number not found or access denied"
        )

    try:
        # Update agent association. Picking the agent it already has is a
        # no-op: nothing to tell the carrier.
        if update_request.agent_id is not None and update_request.agent_id != phone_number.agent_id:
            # Verify agent belongs to user
            agent_result = await db.execute(
                select(Agent).where(
                    Agent.id == update_request.agent_id,
                    Agent.organization_id == org_id,
                )
            )
            agent = agent_result.scalar_one_or_none()

            if not agent:
                raise HTTPException(
                    status_code=404,
                    detail="Agent not found or access denied"
                )
            if not agent.is_active:
                raise HTTPException(
                    status_code=400,
                    detail=f"{agent.name} is turned off. Turn it on before it can answer this number.",
                )

            try:
                resolved = await resolve_provider_for_number(
                    db,
                    org_id,
                    provider_slug=phone_number.provider,
                    connection_id=phone_number.integration_connection_id,
                    provider_metadata=phone_number.provider_metadata or {},
                )
                metadata = await resolved.provider.update_voice_webhook(
                    provider_sid=phone_number.provider_sid,
                    voice_url=voice_webhook_url(resolved.slug, str(agent.id)),
                    phone_number=phone_number.phone_number,
                    status_callback_url=status_webhook_url(resolved.slug),
                    provider_metadata=phone_number.provider_metadata or {},
                )
                # Merge rather than replace: the carrier only returns its own
                # bookkeeping, and the account the number lives on must survive.
                phone_number.provider_metadata = {
                    **(phone_number.provider_metadata or {}),
                    **(metadata or {}),
                    CREDENTIAL_SOURCE_KEY: resolved.option.source,
                }
            except Exception as e:
                raise public_error(e, action="update", voicecon=is_voicecon_number(phone_number))

            previous_agent_id = phone_number.agent_id
            phone_number.agent_id = update_request.agent_id
            logger.info(
                f"Reassigned {phone_number.phone_number} from agent "
                f"{previous_agent_id} to {update_request.agent_id}"
            )

        # Update status
        if update_request.status is not None:
            phone_number.status = update_request.status

        await db.commit()
        await db.refresh(phone_number)

        logger.info(f"Updated phone number: {phone_number_id}")

        return _to_response(phone_number)

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Error updating phone number: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="We couldn't update this number right now. Please try again."
        )


@router.delete("/{phone_number_id}", status_code=status.HTTP_204_NO_CONTENT)
async def release_phone_number(
    phone_number_id: UUID,
    current_user: User = Depends(get_current_active_user),
    org_id: UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db),
):
    """
    Release (delete) a phone number back to the carrier it was bought from.
    """
    result = await db.execute(
        select(PhoneNumber).where(
            PhoneNumber.id == phone_number_id,
            PhoneNumber.organization_id == org_id,
        )
    )
    phone_number = result.scalar_one_or_none()

    if not phone_number:
        raise HTTPException(
            status_code=404,
            detail="Phone number not found or access denied"
        )

    try:
        resolved = await resolve_provider_for_number(
            db,
            org_id,
            provider_slug=phone_number.provider,
            connection_id=phone_number.integration_connection_id,
            provider_metadata=phone_number.provider_metadata or {},
        )
        await resolved.provider.release_number(
            provider_sid=phone_number.provider_sid,
            phone_number=phone_number.phone_number,
            provider_metadata=phone_number.provider_metadata or {},
        )
    except Exception as e:
        raise public_error(e, action="release", voicecon=is_voicecon_number(phone_number))

    try:
        await db.delete(phone_number)
        await db.commit()
    except Exception as e:
        await db.rollback()
        logger.error(f"Error deleting phone number record: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="We couldn't release this number right now. Please try again or contact support."
        )

    logger.info(f"Released phone number: {phone_number_id}")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
