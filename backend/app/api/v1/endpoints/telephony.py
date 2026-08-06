"""
Telephony webhook endpoints for Twilio integration.

Handles:
- Inbound call webhooks
- Call status callbacks
- WebSocket media stream handling
"""
import logging
from typing import Dict, Any, List, Optional
from uuid import UUID
from urllib.parse import urljoin
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import case, select
from twilio.request_validator import RequestValidator

from app.core.config import settings
from app.database import get_db
from app.models.call import Call, PhoneNumber
from app.models.agent import Agent
from app.services.telephony.provider_registry import credentials_for_number
from app.services.telephony.twilio_service import (
    build_twiml_error,
    build_twiml_for_websocket,
    get_twilio_service_for_number,
)
from app.core.dependencies import get_current_user, get_current_active_user, get_current_org_id
from app.core.entitlement_guard import require_entitlement
from app.models.user import User
from app.services.billing import catalog
from app.services.billing.entitlements import runtime_allows

logger = logging.getLogger(__name__)

router = APIRouter()

#: Routes that must stay reachable without a workspace context — carrier and
#: payment-provider webhooks, and the public embed surfaces. They live on their
#: own router so the authenticated router can carry a blanket permission guard
#: (see app.api.v1.api) without accidentally locking these out.
public_router = APIRouter()


def _public_webhook_url(request: Request) -> str:
    """
    Reconstruct the exact public URL Twilio signed.

    Behind a TLS-terminating proxy the internal scheme/host differ from what
    Twilio called, and the signature is computed over the public URL. Prefer an
    explicitly configured public base URL; otherwise honour forwarded headers.
    """
    if settings.TWILIO_PUBLIC_BASE_URL:
        base = settings.TWILIO_PUBLIC_BASE_URL.rstrip("/")
        return f"{base}{request.url.path}"
    proto = request.headers.get("x-forwarded-proto", request.url.scheme)
    host = request.headers.get("x-forwarded-host") or request.headers.get("host")
    if host:
        return f"{proto}://{host}{request.url.path}"
    return str(request.url)


async def _candidate_auth_tokens(db: AsyncSession, form_data) -> List[str]:
    """
    Auth tokens that could legitimately have signed this webhook.

    A number bought on a user's own Twilio account is signed with *their* auth
    token, not the platform one, so the token is looked up from the account the
    number lives on. The platform token is always included as well, since the
    platform account signs webhooks for numbers bought on it.
    """
    tokens: List[str] = []

    # Inbound webhooks name our number in `To`; outbound ones in `From`.
    numbers = {
        str(form_data.get(field))
        for field in ("To", "From", "Called", "Caller")
        if form_data.get(field)
    }

    if numbers:
        result = await db.execute(
            select(PhoneNumber).where(
                PhoneNumber.phone_number.in_(numbers),
                PhoneNumber.provider == "twilio",
            )
        )
        for number in result.scalars().all():
            credentials = await credentials_for_number(
                db,
                "twilio",
                connection_id=number.integration_connection_id,
                provider_metadata=number.provider_metadata or {},
            )
            token = credentials.get("auth_token")
            if token:
                tokens.append(token)

    if settings.TWILIO_AUTH_TOKEN:
        tokens.append(settings.TWILIO_AUTH_TOKEN)

    seen = set()
    return [t for t in tokens if not (t in seen or seen.add(t))]


async def validate_twilio_request(request: Request, form_data, db: AsyncSession) -> bool:
    """
    Validate the X-Twilio-Signature on a webhook request.

    Returns True (allow) when validation is disabled or no auth token can be
    found — there is nothing to validate against in that case, so local and
    credential-less environments are unaffected. Otherwise the signature must
    match the account that owns the number the call is for.
    """
    if not settings.TWILIO_VALIDATE_WEBHOOKS:
        return True

    tokens = await _candidate_auth_tokens(db, form_data)
    if not tokens:
        logger.warning(
            "Twilio webhook signature not validated: no auth token available for "
            "this number and no TWILIO_AUTH_TOKEN configured"
        )
        return True

    signature = request.headers.get("X-Twilio-Signature", "")
    if not signature:
        logger.error("Rejecting webhook: missing X-Twilio-Signature header")
        return False

    url = _public_webhook_url(request)
    post_vars = {k: str(v) for k, v in form_data.items()}

    for token in tokens:
        if RequestValidator(token).validate(url, post_vars, signature):
            return True

    logger.error(f"Rejecting webhook: invalid Twilio signature for {url}")
    return False


def _record_status_metadata(call: Call, call_status: Optional[str]) -> None:
    """
    Note the latest carrier status on the call record.

    Writes ``call_metadata`` — the model's actual column. ``call.metadata`` is
    SQLAlchemy's own :class:`MetaData` on the declarative class, so reading it
    raised ``AttributeError`` and writing it went nowhere.

    A new dict is assigned rather than mutated in place: the column is a plain
    ``JSON``, so SQLAlchemy only notices a change on reassignment.

    Args:
        call: Call record to update
        call_status: Carrier-reported status for this callback
    """
    current = call.call_metadata or {}
    call.call_metadata = {
        **current,
        "last_status": call_status,
        "status_callback_count": current.get("status_callback_count", 0) + 1,
    }


async def _resolve_call_record(
    db: AsyncSession,
    *,
    provider: str,
    agent: Agent,
    call_sid: Optional[str],
    from_number: Optional[str],
    to_number: Optional[str],
    call_status: Optional[str],
    call_id: Optional[str] = None,
) -> Call:
    """
    Find the Call this answer webhook belongs to, or create one for an inbound call.

    Only inbound calls are new here. An outbound call already has a row — written
    when we asked the carrier to dial — and the carrier fetches this same answer
    URL once the callee picks up. Inserting again would collide on the unique
    ``provider_call_sid`` and drop the call, so an existing row is reused and
    keeps its ``outbound`` direction.

    The row is matched by ``call_id`` (which we put on the outbound answer URL)
    first, falling back to the SID for carriers or paths that don't carry it.

    Args:
        db: Database session
        provider: Carrier slug, e.g. "twilio" or "telnyx"
        agent: Agent handling the call
        call_sid: Carrier call identifier
        from_number: Caller number
        to_number: Called number
        call_status: Carrier-reported status
        call_id: Our own Call id, when the answer URL carried one

    Returns:
        The Call record the media stream should attach to
    """
    existing: Optional[Call] = None

    if call_id:
        existing = (
            await db.execute(select(Call).where(Call.id == call_id))
        ).scalar_one_or_none()
        if existing is None:
            logger.warning(f"Answer webhook named unknown call_id {call_id}")

    if existing is None and call_sid:
        existing = (
            await db.execute(select(Call).where(Call.provider_call_sid == call_sid))
        ).scalar_one_or_none()

    if existing is not None:
        # Bind the SID on first contact: for an outbound call this webhook may
        # arrive before the dial response was committed.
        if call_sid and not existing.provider_call_sid:
            existing.provider_call_sid = call_sid
        if call_status:
            existing.status = call_status
        await db.commit()
        await db.refresh(existing)
        logger.info(
            f"Answer webhook matched existing {existing.direction} call {existing.id}"
        )
        return existing

    phone_number = (
        await db.execute(
            select(PhoneNumber).where(
                PhoneNumber.phone_number == to_number,
                PhoneNumber.agent_id == agent.id,
            )
        )
    ).scalar_one_or_none()

    call = Call(
        user_id=agent.user_id,
        organization_id=agent.organization_id,
        agent_id=agent.id,
        phone_number_id=phone_number.id if phone_number else None,
        direction="inbound",
        from_number=from_number,
        to_number=to_number,
        status=call_status or "initiated",
        provider=provider,
        provider_call_sid=call_sid,
        # `call_metadata`, not `metadata`: the latter is SQLAlchemy's own
        # attribute, so assigning it silently discards the value.
        call_metadata={
            f"{provider}_call_sid": call_sid,
            "call_status": call_status,
        },
    )

    db.add(call)
    await db.commit()
    await db.refresh(call)

    logger.info(f"Created inbound call record: {call.id}")
    return call


@public_router.post("/twilio/voice/{agent_id}")
async def handle_inbound_call(
    agent_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Handle the answer webhook from Twilio and return TwiML connecting the call
    to the media-streaming WebSocket.

    Twilio fetches this URL for *both* directions: on an inbound call it is the
    number's voice_url, and on an outbound one it is the answer URL we passed to
    the dial request. Only the inbound case creates a Call row — see
    :func:`_resolve_call_record`.

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

        # Validate the Twilio webhook signature against the account that owns
        # this number — the platform account, or the user's own connected one.
        if not await validate_twilio_request(request, form_data, db):
            raise HTTPException(status_code=403, detail="Invalid Twilio signature")

        # Get agent from database
        agent_result = await db.execute(
            select(Agent).where(Agent.id == agent_id)
        )
        agent = agent_result.scalar_one_or_none()

        if not agent:
            logger.error(f"Agent not found: {agent_id}")
            twiml = build_twiml_error("We're sorry, the agent is not available.")
            return Response(content=twiml, media_type="application/xml")

        # An inbound call is the most expensive thing this product does — it
        # spins up STT, an LLM and TTS on a live carrier leg — and it arrives on
        # a webhook, so no HTTP dependency has gated it. Check here, before any
        # of that starts, or an expired account keeps calling on our money.
        allowed, reason = await runtime_allows(
            db, agent.organization_id, catalog.INBOUND_CALLS
        )
        if not allowed:
            logger.info(
                f"Declining inbound call for org {agent.organization_id}: {reason}"
            )
            twiml = build_twiml_error(
                "We're sorry, this number is not currently taking calls. "
                "Please try again later."
            )
            return Response(content=twiml, media_type="application/xml")

        # Reuse the row an outbound dial already created; create one only for a
        # genuinely inbound call.
        call = await _resolve_call_record(
            db,
            provider="twilio",
            agent=agent,
            call_sid=call_sid,
            from_number=from_number,
            to_number=to_number,
            call_status=call_status,
            call_id=request.query_params.get("call_id"),
        )

        # Generate WebSocket URL for media streaming
        # The WebSocket endpoint will be at /api/v1/voice/stream/{call_id}
        websocket_url = urljoin(
            settings.WEBSOCKET_URL or f"wss://{request.headers.get('host')}",
            f"/api/v1/voice/stream/{call.id}"
        )

        logger.info(f"WebSocket URL: {websocket_url}")

        # "connecting you with X" only makes sense to someone who dialled us.
        # On an outbound call the agent's own first_message does the greeting.
        twiml = build_twiml_for_websocket(
            websocket_url=websocket_url,
            agent_name=agent.name if call.direction == "inbound" else None,
        )

        logger.info(f"Generated TwiML for call: {call_sid}")

        return Response(content=twiml, media_type="application/xml")

    except HTTPException:
        # Signature-rejection (403) and similar must propagate, not be masked
        # as a friendly TwiML error.
        raise
    except Exception as e:
        logger.error(f"Error handling inbound call: {e}", exc_info=True)

        # Return error TwiML
        twiml = build_twiml_error(
            "We're sorry, an error occurred. Please try again later."
        )
        return Response(content=twiml, media_type="application/xml")


@public_router.post("/twilio/status")
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

        # Validate the webhook signature (auto-skips without an auth token).
        if not await validate_twilio_request(request, form_data, db):
            raise HTTPException(status_code=403, detail="Invalid Twilio signature")

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

        _record_status_metadata(call, call_status)

        await db.commit()

        logger.info(f"Updated call status: {call.id} -> {call_status}")

        return Response(status_code=200)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error handling call status: {e}", exc_info=True)
        return Response(status_code=200)  # Return 200 to avoid Twilio retries


@router.post(
    "/twilio/voice-outbound",
    dependencies=[
        Depends(
            require_entitlement(
                feature=catalog.OUTBOUND_CALLS, limit=catalog.LIMIT_CALLS
            )
        )
    ],
)
async def initiate_outbound_call(
    to_number: str,
    agent_id: str,
    from_number: Optional[str] = None,
    current_user: User = Depends(get_current_active_user),
    org_id: UUID = Depends(get_current_org_id),
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
                Agent.organization_id == org_id,
            )
        )
        agent = agent_result.scalar_one_or_none()

        if not agent:
            raise HTTPException(
                status_code=404,
                detail="Agent not found or access denied"
            )

        # Resolve the number to dial from, always inside the caller's workspace:
        # an unscoped lookup would let one tenant place calls from another's
        # number. A named number is preferred, then one assigned to this agent.
        number_query = select(PhoneNumber).where(
            PhoneNumber.organization_id == org_id,
            PhoneNumber.status == "active",
        )
        if from_number:
            number_query = number_query.where(PhoneNumber.phone_number == from_number)
        else:
            number_query = number_query.order_by(
                case((PhoneNumber.agent_id == agent.id, 0), else_=1)
            )

        phone_number = (await db.execute(number_query)).scalars().first()

        if not phone_number:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Phone number not found in this workspace"
                    if from_number
                    else "No active phone number available to call from"
                ),
            )

        from_number = phone_number.phone_number

        # The row is written before dialling so the answer webhook — which can
        # fire the instant the callee picks up — has something to attach to.
        call = Call(
            user_id=agent.user_id,
            organization_id=agent.organization_id,
            agent_id=agent.id,
            phone_number_id=phone_number.id,
            direction="outbound",
            from_number=from_number,
            to_number=to_number,
            status="initiated",
            provider="twilio",
        )

        db.add(call)
        await db.commit()
        await db.refresh(call)

        # Dial out from the account that owns the number, not necessarily the
        # platform one.
        twilio_service = await get_twilio_service_for_number(db, from_number)

        webhook_base_url = settings.API_BASE_URL or f"https://{settings.SERVER_HOST}"

        try:
            call_details = await twilio_service.make_outbound_call(
                to_number=to_number,
                from_number=from_number,
                agent_id=str(agent_id),
                webhook_base_url=webhook_base_url,
                call_id=str(call.id),
            )
        except Exception:
            await db.rollback()
            failed = await db.get(Call, call.id)
            if failed:
                failed.status = "failed"
                await db.commit()
            raise

        call.provider_call_sid = call_details["call_sid"]
        call.status = call_details["status"]
        call.call_metadata = {
            "twilio_call_sid": call_details["call_sid"],
            "direction_type": call_details["direction"],
        }
        await db.commit()

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
    org_id: UUID = Depends(get_current_org_id),
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
                Call.organization_id == org_id,
            )
        )
        call = call_result.scalar_one_or_none()

        if not call:
            raise HTTPException(
                status_code=404,
                detail="Call not found or access denied"
            )

        # Details live in the account the call was placed on.
        own_number = call.from_number if call.direction == "outbound" else call.to_number
        twilio_service = await get_twilio_service_for_number(db, own_number)
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


# ============================================================================
# Telnyx — TeXML webhooks
#
# Numbers bought on Telnyx are attached to a TeXML application whose voice_url
# points here. TeXML speaks the same XML dialect as TwiML and posts the same
# form fields (CallSid, From, To, CallStatus), so the handling mirrors the
# Twilio path — only the media-stream frames on the WebSocket differ.
# ============================================================================


@public_router.post("/telnyx/voice/{agent_id}")
async def handle_telnyx_inbound_call(
    agent_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Handle an inbound call webhook from a Telnyx TeXML application.

    Returns TeXML that connects the call to the media-stream WebSocket.

    Args:
        agent_id: Agent ID to handle the call
        request: FastAPI request object
        db: Database session

    Returns:
        TeXML response connecting to the WebSocket
    """
    from app.services.telephony.texml import build_error_response, build_stream_response

    try:
        form_data = await request.form()

        call_sid = form_data.get("CallSid")
        from_number = form_data.get("From")
        to_number = form_data.get("To")
        call_status = form_data.get("CallStatus")

        logger.info(
            f"Inbound Telnyx call: CallSid={call_sid}, From={from_number}, "
            f"To={to_number}, Status={call_status}, Agent={agent_id}"
        )

        agent_result = await db.execute(select(Agent).where(Agent.id == agent_id))
        agent = agent_result.scalar_one_or_none()

        if not agent:
            logger.error(f"Agent not found: {agent_id}")
            return Response(
                content=build_error_response("We're sorry, the agent is not available."),
                media_type="application/xml",
            )

        # Same gate as the Twilio path: stop before the agent runtime starts, or
        # a lapsed account keeps burning carrier and model spend on our account.
        allowed, reason = await runtime_allows(
            db, agent.organization_id, catalog.INBOUND_CALLS
        )
        if not allowed:
            logger.info(
                f"Declining inbound Telnyx call for org {agent.organization_id}: {reason}"
            )
            return Response(
                content=build_error_response(
                    "We're sorry, this number is not currently taking calls. "
                    "Please try again later."
                ),
                media_type="application/xml",
            )

        call = await _resolve_call_record(
            db,
            provider="telnyx",
            agent=agent,
            call_sid=call_sid,
            from_number=from_number,
            to_number=to_number,
            call_status=call_status,
            call_id=request.query_params.get("call_id"),
        )

        websocket_url = urljoin(
            settings.WEBSOCKET_URL or f"wss://{request.headers.get('host')}",
            f"/api/v1/voice/stream/{call.id}",
        )

        return Response(
            content=build_stream_response(
                websocket_url,
                agent.name if call.direction == "inbound" else None,
            ),
            media_type="application/xml",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error handling Telnyx inbound call: {e}", exc_info=True)
        return Response(
            content=build_error_response(
                "We're sorry, an error occurred. Please try again later."
            ),
            media_type="application/xml",
        )


@public_router.post("/telnyx/status")
async def handle_telnyx_call_status(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Handle a call-status callback from a Telnyx TeXML application.

    Args:
        request: FastAPI request object
        db: Database session

    Returns:
        Empty 200 response
    """
    try:
        form_data = await request.form()

        call_sid = form_data.get("CallSid")
        call_status = form_data.get("CallStatus")
        call_duration = form_data.get("CallDuration")

        logger.info(
            f"Telnyx call status: CallSid={call_sid}, Status={call_status}, "
            f"Duration={call_duration}"
        )

        call_result = await db.execute(
            select(Call).where(Call.provider_call_sid == call_sid)
        )
        call = call_result.scalar_one_or_none()

        if not call:
            logger.warning(f"Call not found: {call_sid}")
            return Response(status_code=200)

        from datetime import datetime

        call.status = call_status

        if call_status == "ringing" and not call.started_at:
            call.started_at = datetime.utcnow()

        elif call_status == "in-progress" and not call.answered_at:
            call.answered_at = datetime.utcnow()

        elif call_status == "completed":
            call.ended_at = datetime.utcnow()

            if call_duration:
                call.duration_seconds = int(call_duration)
                call.billable_duration_seconds = int(call_duration)

        _record_status_metadata(call, call_status)

        await db.commit()

        logger.info(f"Updated call status: {call.id} -> {call_status}")

        return Response(status_code=200)

    except Exception as e:
        logger.error(f"Error handling Telnyx call status: {e}", exc_info=True)
        return Response(status_code=200)
