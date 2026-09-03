"""
Phone number management endpoints.

Handles:
- Listing the carriers a user can buy numbers from
- Searching available phone numbers
- Provisioning/purchasing phone numbers
- Listing user's phone numbers
- Updating phone number configuration
- Releasing phone numbers

Numbers are bought on whichever carrier the user has connected under
Integrations (Twilio, Telnyx). The carrier used for a number is recorded on the
row so releases and webhook changes go back to the same account.
"""
import logging
from typing import Any, Dict, List, Optional
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
from app.core.dependencies import get_current_active_user, get_current_org_id

logger = logging.getLogger(__name__)

router = APIRouter()


# Schemas
class PhoneNumberProvision(BaseModel):
    """Phone number provisioning request."""
    phone_number: str = Field(..., description="Phone number to purchase (E.164 format)")
    agent_id: UUID = Field(..., description="Agent ID to associate with the number")
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
    """Serialise a phone number row."""
    return PhoneNumberResponse(
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
    )


def _provider_http_error(e: Exception) -> HTTPException:
    """Translate provider-resolution failures into meaningful HTTP errors."""
    if isinstance(e, NoTelephonyProviderError):
        return HTTPException(status_code=400, detail=str(e))
    if isinstance(e, AmbiguousProviderError):
        return HTTPException(status_code=400, detail=str(e))
    if isinstance(e, NumberProviderError):
        return HTTPException(status_code=502, detail=str(e))
    return HTTPException(status_code=500, detail="An internal error occurred. Please try again.")


@router.get("/providers", response_model=List[TelephonyProviderResponse])
async def list_phone_number_providers(
    current_user: User = Depends(get_current_active_user),
    org_id: UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db),
):
    """
    List the carrier accounts this user can buy phone numbers from.

    Includes the Voicecon platform Twilio account (when the server is configured
    for it) alongside any carrier the user connected under Integrations, so the
    purchase UI can offer both. The first entry is the default — the user's own
    Twilio if they connected one, otherwise the platform Twilio.

    An empty list means the server has no platform Twilio configured and the
    user has connected nothing.
    """
    try:
        options = await list_available_providers(db, org_id)
        return [
            TelephonyProviderResponse(**option.as_dict(), is_default=(index == 0))
            for index, option in enumerate(options)
        ]

    except Exception as e:
        logger.error(f"Error listing phone number providers: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="An internal error occurred. Please try again."
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
    current_user: User = Depends(get_current_active_user),
    org_id: UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db),
):
    """
    Search a connected carrier for available phone numbers.

    The carrier is chosen explicitly with `provider`; when the user has only one
    connected it is selected automatically.
    """
    try:
        resolved = await resolve_provider(
            db, org_id, slug=provider, connection_id=connection_id
        )
    except (NoTelephonyProviderError, AmbiguousProviderError, NumberProviderError) as e:
        raise _provider_http_error(e)

    try:
        results = await resolved.provider.search_numbers(
            country_code=country_code,
            area_code=area_code,
            contains=contains,
            limit=limit,
        )
        return [AvailablePhoneNumber(**number.as_dict()) for number in results]

    except NumberProviderError as e:
        logger.error(f"Carrier search failed on {resolved.slug}: {e}")
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        logger.error(f"Error searching phone numbers: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="An internal error occurred. Please try again."
        )


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
            detail="Phone number already provisioned"
        )

    try:
        phone_number_record, _ = await purchase_number_for_agent(
            db,
            current_user,
            agent,
            phone_number=provision_request.phone_number,
            provider=provision_request.provider,
            connection_id=provision_request.connection_id,
            country_code=provision_request.country_code,
            area_code=provision_request.area_code,
            monthly_cost=provision_request.monthly_cost,
        )
    except (NoTelephonyProviderError, AmbiguousProviderError) as e:
        raise _provider_http_error(e)
    except NumberProviderError as e:
        logger.error(f"Purchase failed for {provision_request.phone_number}: {e}")
        raise HTTPException(status_code=502, detail=str(e))
    except WebhookUrlNotConfigured as e:
        raise HTTPException(status_code=500, detail="An internal error occurred. Please try again.")
    except NumberNotRecordedError as e:
        raise HTTPException(status_code=500, detail="An internal error occurred. Please try again.")
    except Exception as e:
        logger.error(f"Error provisioning phone number: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="An internal error occurred. Please try again."
        )

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
            detail="An internal error occurred. Please try again."
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
            detail="An internal error occurred. Please try again."
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
        # Update agent association
        if update_request.agent_id is not None:
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
            except WebhookUrlNotConfigured as e:
                raise HTTPException(status_code=500, detail="An internal error occurred. Please try again.")
            except (NoTelephonyProviderError, NumberProviderError) as e:
                raise _provider_http_error(e)

            phone_number.agent_id = update_request.agent_id

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
            detail="An internal error occurred. Please try again."
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
    except (NoTelephonyProviderError, NumberProviderError) as e:
        raise _provider_http_error(e)
    except Exception as e:
        logger.error(f"Error releasing phone number at carrier: {e}", exc_info=True)
        raise HTTPException(
            status_code=502,
            detail="An internal error occurred. Please try again."
        )

    try:
        await db.delete(phone_number)
        await db.commit()
    except Exception as e:
        await db.rollback()
        logger.error(f"Error deleting phone number record: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="An internal error occurred. Please try again."
        )

    logger.info(f"Released phone number: {phone_number_id}")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
