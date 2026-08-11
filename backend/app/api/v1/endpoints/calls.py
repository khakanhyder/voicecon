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
from sqlalchemy import select, and_, func, case, desc

from app.database import get_db
from app.core.dependencies import get_current_user, get_current_org_id
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
from app.services.telephony.twilio_service import get_twilio_service_for_number
from app.core.config import settings
from app.core.entitlement_guard import require_entitlement
from app.services.billing import catalog

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


@router.post("", response_model=CallResponse, status_code=status.HTTP_201_CREATED)
async def create_call(
    call_data: CallCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org_id: uuid.UUID = Depends(get_current_org_id),
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
                Agent.organization_id == org_id,
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
                    PhoneNumber.organization_id == org_id
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
        # No number named: dial from any active number assigned to this agent,
        # else any active number in the workspace. Something has to be dialled
        # *from*, and the carrier rejects a number the account doesn't own.
        result = await db.execute(
            select(PhoneNumber)
            .where(
                and_(
                    PhoneNumber.organization_id == org_id,
                    PhoneNumber.status == "active",
                )
            )
            .order_by(case((PhoneNumber.agent_id == agent.id, 0), else_=1))
        )
        phone_number = result.scalars().first()

        if not phone_number:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No active phone number available to call from",
            )

        from_number = phone_number.phone_number

    # Create call record
    call = Call(
        agent_id=agent.id,
        user_id=current_user.id,
        organization_id=agent.organization_id,
        phone_number_id=phone_number.id,
        from_number=from_number,
        to_number=call_data.to_number,
        direction="outbound",
        status="initiated",
        provider="twilio",
        started_at=datetime.utcnow(),
    )

    db.add(call)
    await db.commit()
    await db.refresh(call)

    # Integrate with Twilio to initiate call
    try:
        # Credentials follow the number: platform-bought numbers dial on the
        # platform account, numbers bought on a user's own Twilio dial on theirs.
        twilio_service = await get_twilio_service_for_number(db, from_number)
        webhook_base_url = settings.API_BASE_URL or f"https://{settings.SERVER_HOST}"

        call_details = await twilio_service.make_outbound_call(
            to_number=call_data.to_number,
            from_number=from_number,
            agent_id=str(agent.id),
            webhook_base_url=webhook_base_url,
            # Named on the answer URL so the webhook updates this row instead of
            # inserting a second one for the same call.
            call_id=str(call.id),
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
        # The dial failed mid-transaction, so the session may be unusable; roll
        # back before recording the failure or the status write is lost too.
        await db.rollback()
        call = await db.get(Call, call.id)
        if call:
            call.status = "failed"
            await db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initiate call: {str(e)}",
        )

    return call


@router.get("", response_model=CallListResponse)
async def list_calls(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    agent_id: Optional[uuid.UUID] = None,
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org_id: uuid.UUID = Depends(get_current_org_id),
):
    """
    List calls for the current user.

    Supports filtering by agent and status.
    """
    # Outer join: a call outlives the agent that handled it, and losing those
    # rows from the log would be worse than showing one without a name.
    query = (
        select(Call, Agent.name)
        .outerjoin(Agent, Agent.id == Call.agent_id)
        .where(Call.organization_id == org_id)
    )
    count_query = select(func.count()).select_from(Call).where(
        Call.organization_id == org_id
    )

    # Apply filters
    if agent_id:
        query = query.where(Call.agent_id == agent_id)
        count_query = count_query.where(Call.agent_id == agent_id)
    if status:
        query = query.where(Call.status == status)
        count_query = count_query.where(Call.status == status)

    # Order by most recent. `nullslast` matters because Postgres sorts NULLs
    # first on DESC, which floated calls with no start time to the top.
    query = query.order_by(Call.started_at.desc().nullslast(), Call.created_at.desc())

    total = (await db.execute(count_query)).scalar_one()

    # Get paginated results
    query = query.offset(skip).limit(limit)
    rows = (await db.execute(query)).all()

    calls = []
    for call, agent_name in rows:
        call.agent_name = agent_name
        calls.append(call)

    return {
        "calls": calls,
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.get("/stats")
async def get_call_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org_id: uuid.UUID = Depends(get_current_org_id),
):
    """
    Get call statistics for the current user.
    """
    from sqlalchemy import func

    total_calls_result = await db.execute(
        select(func.count(Call.id)).where(Call.organization_id == org_id)
    )
    total_calls = total_calls_result.scalar()

    completed_calls_result = await db.execute(
        select(func.count(Call.id)).where(
            and_(
                Call.organization_id == org_id,
                Call.status == "completed"
            )
        )
    )
    completed_calls = completed_calls_result.scalar()

    duration_result = await db.execute(
        select(func.sum(Call.duration_seconds)).where(Call.organization_id == org_id)
    )
    total_duration = duration_result.scalar() or 0

    cost_result = await db.execute(
        select(func.sum(Call.cost_total)).where(Call.organization_id == org_id)
    )
    total_cost = cost_result.scalar() or 0

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


# Phone Number Management

@router.post(
    "/phone-numbers",
    response_model=PhoneNumberResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[
        # Attaching a number is gated exactly like buying one. This route does
        # not call a carrier, but it is still a way to end up with a working
        # number on a trial account, and a restriction with a side door is not
        # a restriction.
        Depends(require_entitlement(feature=catalog.PHONE_NUMBER_PURCHASE)),
        Depends(require_entitlement(limit=catalog.LIMIT_PHONE_NUMBERS)),
    ],
)
async def create_phone_number(
    phone_data: PhoneNumberCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org_id: uuid.UUID = Depends(get_current_org_id),
):
    """
    Register a new phone number.
    """
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

    phone_number = PhoneNumber(
        user_id=current_user.id,
        organization_id=org_id,
        phone_number=phone_data.phone_number,
        provider="twilio",
        capabilities={"voice": True, "sms": True},
        status="active",
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
    org_id: uuid.UUID = Depends(get_current_org_id),
):
    """
    List all phone numbers for the current user.
    """
    result = await db.execute(
        select(PhoneNumber).where(
            and_(
                PhoneNumber.organization_id == org_id,
                PhoneNumber.status == "active"
            )
        ).order_by(PhoneNumber.created_at.desc())
    )
    phone_numbers = result.scalars().all()

    return phone_numbers


# Caller / Contact History
#
# A "contact" is the external party on a call — the person who dialled the
# agent (inbound) or was dialled by it (outbound). Calls are grouped by that
# number so the analytics dashboard can show per-caller history.

def _contact_expr():
    """SQL expression for the external party's phone number on a call."""
    return case(
        (Call.direction == "inbound", Call.from_number),
        else_=Call.to_number,
    )


@router.get("/contacts")
async def list_call_contacts(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org_id: uuid.UUID = Depends(get_current_org_id),
):
    """
    List distinct callers (contacts) with aggregated call history.

    Each contact is the external phone number that interacted with an agent,
    along with call counts, duration, cost, sentiment and last-activity time.
    """
    contact = _contact_expr().label("contact")

    query = (
        select(
            contact,
            func.count(Call.id).label("total_calls"),
            func.sum(case((Call.status == "completed", 1), else_=0)).label("completed_calls"),
            func.sum(func.coalesce(Call.duration_seconds, 0)).label("total_duration"),
            func.sum(func.coalesce(Call.cost_total, 0)).label("total_cost"),
            func.avg(Call.sentiment_score).label("avg_sentiment"),
            func.max(Call.started_at).label("last_call_at"),
        )
        .where(Call.organization_id == org_id)
        .group_by(contact)
        .order_by(desc(func.max(Call.started_at)))
    )

    result = await db.execute(query)
    rows = result.all()

    contacts = [
        {
            "contact_number": row.contact,
            "total_calls": row.total_calls or 0,
            "completed_calls": row.completed_calls or 0,
            "total_duration_seconds": int(row.total_duration or 0),
            "total_cost": float(row.total_cost or 0),
            "avg_sentiment_score": float(row.avg_sentiment) if row.avg_sentiment is not None else None,
            "last_call_at": row.last_call_at.isoformat() if row.last_call_at else None,
        }
        for row in rows
        if row.contact  # skip blank / system numbers
    ]

    return {"contacts": contacts, "total": len(contacts)}


@router.get("/contacts/{contact_number}/calls", response_model=CallListResponse)
async def get_contact_calls(
    contact_number: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org_id: uuid.UUID = Depends(get_current_org_id),
):
    """
    List all calls for a specific caller (contact), most recent first.
    """
    contact = _contact_expr()

    base_filter = and_(
        Call.organization_id == org_id,
        contact == contact_number,
    )

    total_result = await db.execute(select(func.count()).select_from(Call).where(base_filter))
    total = total_result.scalar() or 0

    result = await db.execute(
        select(Call)
        .where(base_filter)
        .order_by(Call.started_at.desc())
        .offset(skip)
        .limit(limit)
    )
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
    org_id: uuid.UUID = Depends(get_current_org_id),
):
    """
    Get a specific call by ID.
    """
    result = await db.execute(
        select(Call, Agent.name)
        .outerjoin(Agent, Agent.id == Call.agent_id)
        .where(
            and_(
                Call.id == call_id,
                Call.organization_id == org_id
            )
        )
    )
    row = result.first()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Call not found",
        )

    call, agent_name = row
    call.agent_name = agent_name

    return call


@router.delete("/{call_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_call(
    call_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org_id: uuid.UUID = Depends(get_current_org_id),
):
    """
    Delete a call record.
    """
    result = await db.execute(
        select(Call).where(
            and_(
                Call.id == call_id,
                Call.organization_id == org_id
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


