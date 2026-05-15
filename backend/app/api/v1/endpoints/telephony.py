"""
Telephony webhook endpoints for Twilio integration.

Handles:
- Inbound call webhooks
- Call status callbacks
- WebSocket media stream handling
"""
import logging
from typing import Dict, Any, Optional
from urllib.parse import urljoin
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.database import get_db
from app.models.call import Call, PhoneNumber
from app.models.agent import Agent
from app.services.telephony.twilio_service import get_twilio_service
from app.core.dependencies import get_current_user, get_current_active_user
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter()


def validate_twilio_request(request: Request, url: str) -> bool:
    """
    Validate Twilio webhook request signature.

    Args:
        request: FastAPI request object
        url: Full URL of the webhook

    Returns:
        True if signature is valid
    """
    twilio_service = get_twilio_service()

    # Get signature from headers
    signature = request.headers.get("X-Twilio-Signature", "")

    if not signature:
        logger.warning("Missing Twilio signature")
        return False

    # Get POST parameters
    # For form data, FastAPI doesn't have it in request at this point
    # We'll need to parse it manually or trust for now
    # In production, implement proper signature validation

    return True  # Simplified for now


@router.post("/twilio/voice/{agent_id}")
async def handle_inbound_call(
    agent_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Handle inbound call webhook from Twilio.

    This endpoint receives the initial call webhook and returns TwiML
    to connect the call to a WebSocket for media streaming.

    Args:
        agent_id: Agent ID to handle the call
        request: FastAPI request object
        db: Database session

    Returns:
        TwiML response to connect to WebSocket
    """
    try:
        # Get form data from Twilio
        form_data = await request.form()

        call_sid = form_data.get("CallSid")
        from_number = form_data.get("From")
        to_number = form_data.get("To")
        call_status = form_data.get("CallStatus")

        logger.info(
            f"Inbound call: CallSid={call_sid}, From={from_number}, "
            f"To={to_number}, Status={call_status}, Agent={agent_id}"
        )

        # Validate Twilio signature (simplified)
        # In production, implement proper validation
        # url = str(request.url)
        # if not validate_twilio_request(request, url):
        #     logger.error("Invalid Twilio signature")
        #     raise HTTPException(status_code=403, detail="Invalid signature")

        # Get agent from database
        agent_result = await db.execute(
            select(Agent).where(Agent.id == agent_id)
        )
        agent = agent_result.scalar_one_or_none()

        if not agent:
            logger.error(f"Agent not found: {agent_id}")
            twilio_service = get_twilio_service()
            twiml = twilio_service.generate_twiml_error(
                "We're sorry, the agent is not available."
            )
            return Response(content=twiml, media_type="application/xml")

        # Get phone number record
        phone_result = await db.execute(
            select(PhoneNumber).where(
                PhoneNumber.phone_number == to_number,
                PhoneNumber.agent_id == agent_id,
            )
        )
        phone_number = phone_result.scalar_one_or_none()

        # Create call record
        call = Call(
            user_id=agent.user_id,
            organization_id=agent.organization_id,
            agent_id=agent.id,
            phone_number_id=phone_number.id if phone_number else None,
            direction="inbound",
            from_number=from_number,
            to_number=to_number,
            status=call_status or "initiated",
            provider="twilio",
            provider_call_sid=call_sid,
            metadata={
                "twilio_call_sid": call_sid,
                "call_status": call_status,
            },
        )

        db.add(call)
        await db.commit()
        await db.refresh(call)

        logger.info(f"Created call record: {call.id}")

        # Generate WebSocket URL for media streaming
        # The WebSocket endpoint will be at /api/v1/voice/stream/{call_id}
        websocket_url = urljoin(
            settings.WEBSOCKET_URL or f"wss://{request.headers.get('host')}",
            f"/api/v1/voice/stream/{call.id}"
        )

        logger.info(f"WebSocket URL: {websocket_url}")

        # Generate TwiML response
        twilio_service = get_twilio_service()
        twiml = twilio_service.generate_twiml_for_websocket(
            websocket_url=websocket_url,
            agent_name=agent.name,
        )

        logger.info(f"Generated TwiML for call: {call_sid}")

        return Response(content=twiml, media_type="application/xml")

    except Exception as e:
        logger.error(f"Error handling inbound call: {e}", exc_info=True)

        # Return error TwiML
        twilio_service = get_twilio_service()
        twiml = twilio_service.generate_twiml_error(
            "We're sorry, an error occurred. Please try again later."
        )
        return Response(content=twiml, media_type="application/xml")


@router.post("/twilio/status")
async def handle_call_status(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Handle call status callback from Twilio.

    This endpoint receives status updates throughout the call lifecycle:
    - initiated
    - ringing
    - answered
    - completed

    Args:
        request: FastAPI request object
        db: Database session

    Returns:
        Empty response
    """
    try:
        # Get form data from Twilio
        form_data = await request.form()

        call_sid = form_data.get("CallSid")
        call_status = form_data.get("CallStatus")
        call_duration = form_data.get("CallDuration")
        from_number = form_data.get("From")
        to_number = form_data.get("To")

        logger.info(
            f"Call status update: CallSid={call_sid}, Status={call_status}, "
            f"Duration={call_duration}"
        )

        # Find call by provider_call_sid
        call_result = await db.execute(
            select(Call).where(Call.provider_call_sid == call_sid)
        )
        call = call_result.scalar_one_or_none()

        if not call:
            logger.warning(f"Call not found: {call_sid}")
            return Response(status_code=200)

        # Update call status
        call.status = call_status

        # Update timing based on status
        if call_status == "ringing" and not call.started_at:
            from datetime import datetime
            call.started_at = datetime.utcnow()

        elif call_status == "in-progress" and not call.answered_at:
            from datetime import datetime
            call.answered_at = datetime.utcnow()

        elif call_status == "completed":
            from datetime import datetime
            call.ended_at = datetime.utcnow()

            if call_duration:
                call.duration_seconds = int(call_duration)
                call.billable_duration_seconds = int(call_duration)

            # Calculate telephony cost (Twilio pricing)
            # Inbound: $0.0085/min, Outbound: $0.0140/min
            if call.duration_seconds:
                minutes = call.duration_seconds / 60
                if call.direction == "inbound":
                    cost = minutes * 0.0085
                else:
                    cost = minutes * 0.0140

                call.cost_telephony = round(cost, 4)

                # Update total cost
                call.cost_total = (
                    (call.cost_stt or 0) +
                    (call.cost_llm or 0) +
                    (call.cost_tts or 0) +
                    (call.cost_telephony or 0)
                )

        # Update metadata
        if not call.metadata:
            call.metadata = {}

        call.metadata.update({
            "last_status": call_status,
            "status_callback_count": call.metadata.get("status_callback_count", 0) + 1,
        })

        await db.commit()

        logger.info(f"Updated call status: {call.id} -> {call_status}")

        return Response(status_code=200)

    except Exception as e:
        logger.error(f"Error handling call status: {e}", exc_info=True)
        return Response(status_code=200)  # Return 200 to avoid Twilio retries


@router.post("/twilio/voice-outbound")
async def initiate_outbound_call(
    to_number: str,
    agent_id: str,
    from_number: Optional[str] = None,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Initiate an outbound call.

    Args:
        to_number: Destination phone number (E.164 format)
        agent_id: Agent ID to handle the call
        from_number: Optional specific phone number to call from
        current_user: Current authenticated user
        db: Database session

    Returns:
        Call details
    """
    try:
        # Get agent
        agent_result = await db.execute(
            select(Agent).where(
                Agent.id == agent_id,
                Agent.user_id == current_user.id,
            )
        )
        agent = agent_result.scalar_one_or_none()

        if not agent:
            raise HTTPException(
                status_code=404,
                detail="Agent not found or access denied"
            )

        # Get phone number if not specified
        if not from_number:
            phone_result = await db.execute(
                select(PhoneNumber).where(
                    PhoneNumber.agent_id == agent_id,
                    PhoneNumber.status == "active",
                )
            )
            phone_number = phone_result.first()

            if not phone_number:
                raise HTTPException(
                    status_code=400,
                    detail="No active phone number found for agent"
                )

            from_number = phone_number[0].phone_number

        # Initiate call via Twilio
        twilio_service = get_twilio_service()

        webhook_base_url = settings.API_BASE_URL or f"https://{settings.SERVER_HOST}"

        call_details = await twilio_service.make_outbound_call(
            to_number=to_number,
            from_number=from_number,
            agent_id=str(agent_id),
            webhook_base_url=webhook_base_url,
        )

        # Create call record
        call = Call(
            user_id=agent.user_id,
            organization_id=agent.organization_id,
            agent_id=agent.id,
            direction="outbound",
            from_number=from_number,
            to_number=to_number,
            status=call_details["status"],
            provider="twilio",
            provider_call_sid=call_details["call_sid"],
            metadata={
                "twilio_call_sid": call_details["call_sid"],
                "direction_type": call_details["direction"],
            },
        )

        db.add(call)
        await db.commit()
        await db.refresh(call)

        logger.info(f"Initiated outbound call: {call.id}")

        return {
            "call_id": str(call.id),
            "call_sid": call_details["call_sid"],
            "status": call_details["status"],
            "from": from_number,
            "to": to_number,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error initiating outbound call: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to initiate call: {str(e)}"
        )


@router.get("/twilio/call/{call_sid}/details")
async def get_call_details(
    call_sid: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get call details from Twilio.

    Args:
        call_sid: Twilio call SID
        current_user: Current authenticated user
        db: Database session

    Returns:
        Call details from Twilio
    """
    try:
        # Verify user has access to this call
        call_result = await db.execute(
            select(Call).where(
                Call.provider_call_sid == call_sid,
                Call.user_id == current_user.id,
            )
        )
        call = call_result.scalar_one_or_none()

        if not call:
            raise HTTPException(
                status_code=404,
                detail="Call not found or access denied"
            )

        # Get details from Twilio
        twilio_service = get_twilio_service()
        details = await twilio_service.get_call_details(call_sid)

        return details

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching call details: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch call details: {str(e)}"
        )
