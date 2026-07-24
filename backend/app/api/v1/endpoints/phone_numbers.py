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

from app.core.config import settings
from app.database import get_db
from app.models.call import PhoneNumber
from app.models.agent import Agent
from app.models.user import User
from app.services.telephony.provider_registry import (
    AmbiguousProviderError,
    NoTelephonyProviderError,
    list_available_providers,
    resolve_provider,
    resolve_provider_for_number,
)
from app.services.telephony.providers import NumberProviderError
from app.core.dependencies import get_current_active_user

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
    """A carrier the user can buy numbers from."""
    slug: str
    name: str
    source: str = Field(description="'integration' (user-connected) or 'platform' (server credentials)")
    connection_id: Optional[str] = None
    connection_name: Optional[str] = None


def _webhook_base_url() -> str:
    """Public base URL that carriers should call back on."""
    return (settings.API_BASE_URL or f"https://{settings.SERVER_HOST}").rstrip("/")


def _voice_webhook_url(provider_slug: str, agent_id: str) -> str:
    """Inbound-call webhook for an agent on a given carrier."""
    return f"{_webhook_base_url()}/api/v1/telephony/{provider_slug}/voice/{agent_id}"


def _status_webhook_url(provider_slug: str) -> str:
    """Call-status callback for a carrier."""
    return f"{_webhook_base_url()}/api/v1/telephony/{provider_slug}/status"


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
    return HTTPException(status_code=500, detail=str(e))


@router.get("/providers", response_model=List[TelephonyProviderResponse])
async def list_phone_number_providers(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    List the carriers this user can buy phone numbers from.

    Only carriers the user has actually connected under Integrations are
    returned, so the purchase UI can show just those. An empty list means the
    user needs to connect Twilio or Telnyx first.
    """
    try:
        options = await list_available_providers(db, current_user)
        return [TelephonyProviderResponse(**option.as_dict()) for option in options]

    except Exception as e:
        logger.error(f"Error listing phone number providers: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list phone providers: {str(e)}"
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
    db: AsyncSession = Depends(get_db),
):
    """
    Search a connected carrier for available phone numbers.

    The carrier is chosen explicitly with `provider`; when the user has only one
    connected it is selected automatically.
    """
    try:
        resolved = await resolve_provider(
            db, current_user, slug=provider, connection_id=connection_id
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
            detail=f"Failed to search phone numbers: {str(e)}"
        )


@router.post("/provision", response_model=PhoneNumberResponse, status_code=status.HTTP_201_CREATED)
async def provision_phone_number(
    provision_request: PhoneNumberProvision,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Purchase a phone number from a connected carrier and wire it to an agent.
    """
    # Verify agent belongs to user
    agent_result = await db.execute(
        select(Agent).where(
            Agent.id == provision_request.agent_id,
            Agent.user_id == current_user.id,
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
        resolved = await resolve_provider(
            db,
            current_user,
            slug=provision_request.provider,
            connection_id=provision_request.connection_id,
        )
    except (NoTelephonyProviderError, AmbiguousProviderError, NumberProviderError) as e:
        raise _provider_http_error(e)

    try:
        purchased = await resolved.provider.purchase_number(
            phone_number=provision_request.phone_number,
            voice_url=_voice_webhook_url(resolved.slug, str(agent.id)),
            status_callback_url=_status_webhook_url(resolved.slug),
            label=f"Voicecon Agent {agent.name}"[:255],
        )
    except NumberProviderError as e:
        logger.error(f"Purchase failed on {resolved.slug}: {e}")
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        logger.error(f"Error provisioning phone number: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to provision phone number: {str(e)}"
        )

    # The number is bought at this point — persist it even if some optional
    # detail is missing, so the user never pays for an untracked number.
    try:
        phone_number_record = PhoneNumber(
            phone_number=purchased.phone_number,
            country_code=provision_request.country_code,
            area_code=provision_request.area_code,
            provider=purchased.provider,
            provider_sid=purchased.provider_sid,
            integration_connection_id=resolved.connection_uuid,
            provider_metadata=purchased.provider_metadata or {},
            agent_id=agent.id,
            user_id=agent.user_id,
            organization_id=agent.organization_id,
            capabilities=purchased.capabilities or {"voice": True},
            # Neither carrier quotes a price on purchase, so fall back to the
            # price the user was shown when they picked the number.
            monthly_cost=purchased.monthly_cost
            if purchased.monthly_cost is not None
            else provision_request.monthly_cost,
            status="active",
        )

        db.add(phone_number_record)
        await db.commit()
        await db.refresh(phone_number_record)

    except Exception as e:
        await db.rollback()
        logger.error(
            f"Purchased {purchased.phone_number} on {resolved.slug} but failed to "
            f"record it: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail=(
                f"{purchased.phone_number} was purchased on "
                f"{resolved.option.name} but could not be saved. Contact support "
                f"before buying another number."
            ),
        )

    logger.info(
        f"Provisioned {purchased.phone_number} on {resolved.slug} "
        f"(record {phone_number_record.id})"
    )
    return _to_response(phone_number_record)


@router.get("", response_model=List[PhoneNumberResponse])
async def list_phone_numbers(
    agent_id: Optional[UUID] = Query(default=None, description="Filter by agent ID"),
    status: Optional[str] = Query(default=None, description="Filter by status"),
    current_user: User = Depends(get_current_active_user),
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
            PhoneNumber.user_id == current_user.id
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
            detail=f"Failed to list phone numbers: {str(e)}"
        )


@router.get("/{phone_number_id}", response_model=PhoneNumberResponse)
async def get_phone_number(
    phone_number_id: UUID,
    current_user: User = Depends(get_current_active_user),
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
                PhoneNumber.user_id == current_user.id,
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
            detail=f"Failed to get phone number: {str(e)}"
        )


@router.patch("/{phone_number_id}", response_model=PhoneNumberResponse)
async def update_phone_number(
    phone_number_id: UUID,
    update_request: PhoneNumberUpdate,
    current_user: User = Depends(get_current_active_user),
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
            PhoneNumber.user_id == current_user.id,
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
                    Agent.user_id == current_user.id,
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
                    current_user,
                    provider_slug=phone_number.provider,
                    connection_id=phone_number.integration_connection_id,
                )
                metadata = await resolved.provider.update_voice_webhook(
                    provider_sid=phone_number.provider_sid,
                    voice_url=_voice_webhook_url(resolved.slug, str(agent.id)),
                    phone_number=phone_number.phone_number,
                    status_callback_url=_status_webhook_url(resolved.slug),
                    provider_metadata=phone_number.provider_metadata or {},
                )
                phone_number.provider_metadata = metadata or phone_number.provider_metadata
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
            detail=f"Failed to update phone number: {str(e)}"
        )


@router.delete("/{phone_number_id}", status_code=status.HTTP_204_NO_CONTENT)
async def release_phone_number(
    phone_number_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Release (delete) a phone number back to the carrier it was bought from.
    """
    result = await db.execute(
        select(PhoneNumber).where(
            PhoneNumber.id == phone_number_id,
            PhoneNumber.user_id == current_user.id,
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
            current_user,
            provider_slug=phone_number.provider,
            connection_id=phone_number.integration_connection_id,
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
            detail=f"Failed to release phone number: {str(e)}"
        )

    try:
        await db.delete(phone_number)
        await db.commit()
    except Exception as e:
        await db.rollback()
        logger.error(f"Error deleting phone number record: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to release phone number: {str(e)}"
        )

    logger.info(f"Released phone number: {phone_number_id}")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
