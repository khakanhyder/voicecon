"""
Phone number management endpoints.

Handles:
- Searching available phone numbers
- Provisioning/purchasing phone numbers
- Listing user's phone numbers
- Updating phone number configuration
- Releasing phone numbers
"""
import logging
from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, Field

from app.core.config import settings
from app.database import get_db
from app.models.call import PhoneNumber
from app.models.agent import Agent
from app.models.user import User
from app.services.telephony.twilio_service import get_twilio_service
from app.core.dependencies import get_current_active_user

logger = logging.getLogger(__name__)

router = APIRouter()


# Schemas
class PhoneNumberSearch(BaseModel):
    """Phone number search criteria."""
    country_code: str = Field(default="US", description="Country code (US, GB, CA, etc.)")
    area_code: Optional[str] = Field(default=None, description="Area code to search in")
    contains: Optional[str] = Field(default=None, description="Pattern the number should contain")
    limit: int = Field(default=10, ge=1, le=50, description="Maximum numbers to return")


class PhoneNumberProvision(BaseModel):
    """Phone number provisioning request."""
    phone_number: str = Field(..., description="Phone number to purchase (E.164 format)")
    agent_id: UUID = Field(..., description="Agent ID to associate with the number")


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
    """Available phone number from provider."""
    phone_number: str
    friendly_name: str
    locality: Optional[str]
    region: Optional[str]
    capabilities: dict


@router.get("/search", response_model=List[AvailablePhoneNumber])
async def search_phone_numbers(
    country_code: str = Query(default="US", description="Country code"),
    area_code: Optional[str] = Query(default=None, description="Area code"),
    contains: Optional[str] = Query(default=None, description="Pattern to search for"),
    limit: int = Query(default=10, ge=1, le=50, description="Max results"),
    current_user: User = Depends(get_current_active_user),
):
    """
    Search for available phone numbers.

    Args:
        country_code: Country code (US, GB, CA, etc.)
        area_code: Optional area code filter
        contains: Optional pattern the number should contain
        limit: Maximum numbers to return
        current_user: Current authenticated user

    Returns:
        List of available phone numbers
    """
    try:
        twilio_service = get_twilio_service()

        results = await twilio_service.search_phone_numbers(
            country_code=country_code,
            area_code=area_code,
            contains=contains,
            limit=limit,
        )

        return results

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
    Purchase and provision a phone number.

    Args:
        provision_request: Provisioning details
        current_user: Current authenticated user
        db: Database session

    Returns:
        Provisioned phone number details
    """
    try:
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
        existing = existing_result.scalar_one_or_none()

        if existing:
            raise HTTPException(
                status_code=400,
                detail="Phone number already provisioned"
            )

        # Provision via Twilio
        twilio_service = get_twilio_service()
        webhook_base_url = settings.API_BASE_URL or f"https://{settings.SERVER_HOST}"

        phone_number = await twilio_service.provision_phone_number(
            phone_number=provision_request.phone_number,
            agent_id=str(provision_request.agent_id),
            db=db,
            webhook_base_url=webhook_base_url,
        )

        logger.info(f"Provisioned phone number: {phone_number.id}")

        return PhoneNumberResponse(
            id=phone_number.id,
            phone_number=phone_number.phone_number,
            country_code=phone_number.country_code,
            area_code=phone_number.area_code,
            provider=phone_number.provider,
            provider_sid=phone_number.provider_sid,
            agent_id=phone_number.agent_id,
            capabilities=phone_number.capabilities,
            status=phone_number.status,
            monthly_cost=float(phone_number.monthly_cost) if phone_number.monthly_cost else None,
            created_at=phone_number.created_at.isoformat(),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error provisioning phone number: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to provision phone number: {str(e)}"
        )


@router.get("/", response_model=List[PhoneNumberResponse])
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

        return [
            PhoneNumberResponse(
                id=pn.id,
                phone_number=pn.phone_number,
                country_code=pn.country_code,
                area_code=pn.area_code,
                provider=pn.provider,
                provider_sid=pn.provider_sid,
                agent_id=pn.agent_id,
                capabilities=pn.capabilities,
                status=pn.status,
                monthly_cost=float(pn.monthly_cost) if pn.monthly_cost else None,
                created_at=pn.created_at.isoformat(),
            )
            for pn in phone_numbers
        ]

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

        return PhoneNumberResponse(
            id=phone_number.id,
            phone_number=phone_number.phone_number,
            country_code=phone_number.country_code,
            area_code=phone_number.area_code,
            provider=phone_number.provider,
            provider_sid=phone_number.provider_sid,
            agent_id=phone_number.agent_id,
            capabilities=phone_number.capabilities,
            status=phone_number.status,
            monthly_cost=float(phone_number.monthly_cost) if phone_number.monthly_cost else None,
            created_at=phone_number.created_at.isoformat(),
        )

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

    Args:
        phone_number_id: Phone number ID
        update_request: Update details
        current_user: Current authenticated user
        db: Database session

    Returns:
        Updated phone number details
    """
    try:
        # Get phone number
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

            phone_number.agent_id = update_request.agent_id

            # Update Twilio webhook
            twilio_service = get_twilio_service()
            webhook_base_url = settings.API_BASE_URL or f"https://{settings.SERVER_HOST}"
            voice_url = f"{webhook_base_url}/api/v1/telephony/twilio/voice/{agent.id}"

            await twilio_service.update_phone_number_webhook(
                phone_number_sid=phone_number.provider_sid,
                voice_url=voice_url,
            )

        # Update status
        if update_request.status is not None:
            phone_number.status = update_request.status

        await db.commit()
        await db.refresh(phone_number)

        logger.info(f"Updated phone number: {phone_number_id}")

        return PhoneNumberResponse(
            id=phone_number.id,
            phone_number=phone_number.phone_number,
            country_code=phone_number.country_code,
            area_code=phone_number.area_code,
            provider=phone_number.provider,
            provider_sid=phone_number.provider_sid,
            agent_id=phone_number.agent_id,
            capabilities=phone_number.capabilities,
            status=phone_number.status,
            monthly_cost=float(phone_number.monthly_cost) if phone_number.monthly_cost else None,
            created_at=phone_number.created_at.isoformat(),
        )

    except HTTPException:
        raise
    except Exception as e:
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
    Release (delete) a phone number.

    Args:
        phone_number_id: Phone number ID
        current_user: Current authenticated user
        db: Database session

    Returns:
        No content
    """
    try:
        # Get phone number
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

        # Release from Twilio
        twilio_service = get_twilio_service()
        await twilio_service.release_phone_number(phone_number.provider_sid)

        # Delete from database
        await db.delete(phone_number)
        await db.commit()

        logger.info(f"Released phone number: {phone_number_id}")

        return Response(status_code=status.HTTP_204_NO_CONTENT)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error releasing phone number: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to release phone number: {str(e)}"
        )
