"""
Call API endpoints.

Handles voice call operations including WebSocket connections for real-time audio.
"""
import logging
import uuid
from typing import Optional
from datetime import datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.call import Call, PhoneNumber
from app.models.agent import Agent
from app.services.voice.call_manager import get_call_manager, CallSession
from app.schemas.call import (
    CallCreate,
    CallResponse,
    CallListResponse,
    PhoneNumberCreate,
    PhoneNumberResponse,
)
from app.services.telephony.twilio_service import get_twilio_service
from app.core.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)


@router.websocket("/ws/{agent_id}")
async def call_websocket(
    websocket: WebSocket,
    agent_id: uuid.UUID,
    phone_number: str = Query(..., description="Caller's phone number"),
    db: AsyncSession = Depends(get_db),
):
    """
    WebSocket endpoint for real-time voice calls.

    Handles bidirectional audio streaming:
    - Receives audio chunks from client
    - Sends transcriptions and agent responses back

    Args:
        websocket: WebSocket connection
        agent_id: ID of the agent handling the call
        phone_number: Caller's phone number
        db: Database session
    """
    await websocket.accept()
    logger.info(f"WebSocket connection accepted for agent: {agent_id}")

    call_manager = get_call_manager()
    call_session: Optional[CallSession] = None

    try:
        # Verify agent exists and is active
        result = await db.execute(
            select(Agent).where(
                and_(
                    Agent.id == agent_id,
                    Agent.is_active == True
                )
            )
        )
        agent = result.scalar_one_or_none()

        if not agent:
            await websocket.send_json({
                "type": "error",
                "message": "Agent not found or inactive",
            })
            await websocket.close(code=4004)
            return

        # Create call session
        call_session = await call_manager.create_call(
            agent_id=agent_id,
            phone_number=phone_number,
            websocket=websocket,
            db=db,
        )

        # Initialize and start the call
        await call_session.initialize()
        await call_session.start()

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for agent: {agent_id}")
    except Exception as e:
        logger.error(f"Error in call WebSocket: {e}")
        try:
            await websocket.send_json({
                "type": "error",
                "message": str(e),
            })
        except:
            pass
    finally:
        # Clean up
        if call_session:
            await call_session.cleanup()
            await call_manager.remove_call(call_session.call_id)


@router.post("/", response_model=CallResponse, status_code=status.HTTP_201_CREATED)
async def create_call(
    call_data: CallCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create a new outbound call.

    Initiates a call through the telephony provider.
    """
    # Verify agent belongs to user
    result = await db.execute(
        select(Agent).where(
            and_(
                Agent.id == call_data.agent_id,
                Agent.user_id == current_user.id,
                Agent.is_active == True
            )
        )
    )
    agent = result.scalar_one_or_none()

    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found or inactive",
        )

    # Verify phone number belongs to user
    if call_data.from_number_id:
        result = await db.execute(
            select(PhoneNumber).where(
                and_(
                    PhoneNumber.id == call_data.from_number_id,
                    PhoneNumber.user_id == current_user.id
                )
            )
        )
        phone_number = result.scalar_one_or_none()

        if not phone_number:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Phone number not found",
            )

        from_number = phone_number.phone_number
    else:
        # Use agent's default number
        from_number = "system"

    # Create call record
    call = Call(
        agent_id=agent.id,
        user_id=current_user.id,
        organization_id=agent.organization_id,
        from_number=from_number,
        to_number=call_data.to_number,
        direction="outbound",
        status="initiated",
        start_time=datetime.utcnow(),
    )

    db.add(call)
    await db.commit()
    await db.refresh(call)

    # Integrate with Twilio to initiate call
    try:
        twilio_service = get_twilio_service()
        webhook_base_url = settings.API_BASE_URL or f"https://{settings.SERVER_HOST}"

        call_details = await twilio_service.make_outbound_call(
            to_number=call_data.to_number,
            from_number=from_number if from_number != "system" else phone_number.phone_number,
            agent_id=str(agent.id),
            webhook_base_url=webhook_base_url,
        )

        # Update call with Twilio details
        call.provider = "twilio"
        call.provider_call_sid = call_details["call_sid"]
        call.status = call_details["status"]

        await db.commit()
        await db.refresh(call)

        logger.info(f"Call created and initiated via Twilio: {call.id} (SID: {call_details['call_sid']})")

    except Exception as e:
        logger.error(f"Failed to initiate call via Twilio: {e}")
        call.status = "failed"
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initiate call: {str(e)}",
        )

    return call


@router.get("/", response_model=CallListResponse)
async def list_calls(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    agent_id: Optional[uuid.UUID] = None,
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List calls for the current user.

    Supports filtering by agent and status.
    """
    query = select(Call).where(Call.user_id == current_user.id)

    # Apply filters
    if agent_id:
        query = query.where(Call.agent_id == agent_id)
    if status:
        query = query.where(Call.status == status)

    # Order by most recent
    query = query.order_by(Call.start_time.desc())

    # Get total count
    count_query = select(Call).where(Call.user_id == current_user.id)
    if agent_id:
        count_query = count_query.where(Call.agent_id == agent_id)
    if status:
        count_query = count_query.where(Call.status == status)

    total_result = await db.execute(count_query)
    total = len(total_result.all())

    # Get paginated results
    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    calls = result.scalars().all()

    return {
        "calls": calls,
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.get("/{call_id}", response_model=CallResponse)
async def get_call(
    call_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get a specific call by ID.
    """
    result = await db.execute(
        select(Call).where(
            and_(
                Call.id == call_id,
                Call.user_id == current_user.id
            )
        )
    )
    call = result.scalar_one_or_none()

    if not call:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Call not found",
        )

    return call


@router.delete("/{call_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_call(
    call_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Delete a call record.

    Note: This only deletes the record, it cannot cancel an active call.
    """
    result = await db.execute(
        select(Call).where(
            and_(
                Call.id == call_id,
                Call.user_id == current_user.id
            )
        )
    )
    call = result.scalar_one_or_none()

    if not call:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Call not found",
        )

    await db.delete(call)
    await db.commit()


# Phone Number Management

@router.post("/phone-numbers", response_model=PhoneNumberResponse, status_code=status.HTTP_201_CREATED)
async def create_phone_number(
    phone_data: PhoneNumberCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Register a new phone number.

    TODO: Integrate with telephony provider to provision number.
    """
    # Check if number already exists
    result = await db.execute(
        select(PhoneNumber).where(
            PhoneNumber.phone_number == phone_data.phone_number
        )
    )
    existing = result.scalar_one_or_none()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Phone number already registered",
        )

    # Create phone number record
    phone_number = PhoneNumber(
        user_id=current_user.id,
        organization_id=current_user.organizations[0].id if current_user.organizations else None,
        phone_number=phone_data.phone_number,
        provider="twilio",  # TODO: Make configurable
        capabilities={"voice": True, "sms": True},
        is_active=True,
    )

    db.add(phone_number)
    await db.commit()
    await db.refresh(phone_number)

    logger.info(f"Phone number created: {phone_number.id} ({phone_data.phone_number})")

    return phone_number


@router.get("/phone-numbers", response_model=list[PhoneNumberResponse])
async def list_phone_numbers(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List all phone numbers for the current user.
    """
    result = await db.execute(
        select(PhoneNumber).where(
            and_(
                PhoneNumber.user_id == current_user.id,
                PhoneNumber.is_active == True
            )
        ).order_by(PhoneNumber.created_at.desc())
    )
    phone_numbers = result.scalars().all()

    return phone_numbers


@router.get("/stats")
async def get_call_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get call statistics for the current user.
    """
    from sqlalchemy import func

    # Total calls
    total_calls_result = await db.execute(
        select(func.count(Call.id)).where(Call.user_id == current_user.id)
    )
    total_calls = total_calls_result.scalar()

    # Completed calls
    completed_calls_result = await db.execute(
        select(func.count(Call.id)).where(
            and_(
                Call.user_id == current_user.id,
                Call.status == "completed"
            )
        )
    )
    completed_calls = completed_calls_result.scalar()

    # Total duration (in minutes)
    duration_result = await db.execute(
        select(func.sum(Call.duration)).where(Call.user_id == current_user.id)
    )
    total_duration = duration_result.scalar() or 0

    # Total cost
    cost_result = await db.execute(
        select(func.sum(Call.cost)).where(Call.user_id == current_user.id)
    )
    total_cost = cost_result.scalar() or 0

    # Active calls count
    call_manager = get_call_manager()
    active_calls = await call_manager.get_active_calls_count()

    return {
        "total_calls": total_calls,
        "completed_calls": completed_calls,
        "active_calls": active_calls,
        "total_duration_seconds": total_duration,
        "total_duration_minutes": round(total_duration / 60, 2),
        "total_cost": float(total_cost),
        "average_duration_seconds": round(total_duration / total_calls, 2) if total_calls > 0 else 0,
        "completion_rate": round(completed_calls / total_calls * 100, 2) if total_calls > 0 else 0,
    }
