"""
Telephony webhook endpoints for Twilio integration.

Handles:
- Inbound call webhooks
- Call status callbacks
- WebSocket media stream handling
"""
import logging
from datetime import datetime
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

    The query string is part of what Twilio signs, so it has to be kept: our
    outbound answer and status callback URLs both carry a ``?call_id=``, and
    dropping it made every one of those signatures fail to verify.
    """
    # Path *and* query — see the note above.
    target = request.url.path
    if request.url.query:
        target = f"{target}?{request.url.query}"

    forwarded_proto = request.headers.get("x-forwarded-proto", request.url.scheme)

    if settings.TWILIO_PUBLIC_BASE_URL:
        base = settings.TWILIO_PUBLIC_BASE_URL.rstrip("/")
        # Twilio signs the URL it actually requested. If the configured base
        # says http:// but the call arrived over https, every signature is
        # computed against the wrong string and *all* webhooks fail — which
        # looks like a credentials problem, not a one-character config typo.
        # The scheme is observable, so trust it over the static setting rather
        # than failing the call.
        scheme, sep, remainder = base.partition("://")
        if sep and scheme != forwarded_proto:
            logger.warning(
                "TWILIO_PUBLIC_BASE_URL is configured as %s:// but this webhook "
                "arrived over %s://. Using %s:// to match what Twilio signed — "
                "correct the setting to silence this.",
                scheme,
                forwarded_proto,
                forwarded_proto,
            )
            base = f"{forwarded_proto}://{remainder}"
        return f"{base}{target}"

    host = request.headers.get("x-forwarded-host") or request.headers.get("host")
    if host:
        return f"{forwarded_proto}://{host}{target}"
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

    Returns True (allow) when validation is disabled, or — **outside production
    only** — when no auth token can be found, so local and credential-less
    environments are unaffected. Otherwise the signature must match the account
    that owns the number the call is for.

    The "no token" case used to allow the request everywhere, which made these
    endpoints unauthenticated in production whenever a webhook named a number
    absent from ``phone_numbers``, or whose stored credentials failed to
    decrypt. They are also exempt from rate limiting, on the stated grounds
    that they carry their own authentication — so when this fell through, they
    carried none at all. Forged status callbacks could then write call records,
    durations and billed minutes.
    """
    if not settings.TWILIO_VALIDATE_WEBHOOKS:
        return True

    tokens = await _candidate_auth_tokens(db, form_data)
    if not tokens:
        if settings.is_production:
            logger.error(
                "Rejecting webhook: no Twilio auth token available for this "
                "number and no TWILIO_AUTH_TOKEN configured, so the signature "
                "cannot be verified. Set TWILIO_AUTH_TOKEN, or connect the "
                "number's Twilio account."
            )
            return False
        logger.warning(
            "Twilio webhook signature not validated: no auth token available for "
            "this number and no TWILIO_AUTH_TOKEN configured (allowed outside "
            "production only)"
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


#: Carrier status strings mapped onto the canonical states the rest of the app
#: queries on (see ``CallState`` in app.services.voice.call_manager). Twilio and
#: Telnyx both report ``in-progress`` with a hyphen; stored raw it matched no
#: filter, so "In Progress" on the calls page and the active-call analytics
#: count were permanently empty.
_PROVIDER_CALL_STATUS = {
    "queued": "initiated",
    "initiated": "initiated",
    "ringing": "ringing",
    "answered": "in_progress",
    "in-progress": "in_progress",
    "in_progress": "in_progress",
    "completed": "completed",
    "busy": "missed",
    "no-answer": "missed",
    "no_answer": "missed",
    "failed": "failed",
    "canceled": "failed",
    "cancelled": "failed",
}

#: Per-minute carrier rates used when the provider does not price the call for us.
_TELEPHONY_RATE_PER_MINUTE = {"inbound": 0.0085, "outbound": 0.0140}

#: Ceiling on a duration reconstructed from timestamps. A late or duplicated
#: final callback would otherwise measure "row created until now" and bill a
#: multi-day call; past this the span is not a real conversation, so it is
#: dropped rather than guessed at.
_MAX_RECONSTRUCTED_DURATION_SECONDS = 24 * 60 * 60


def normalize_call_status(call_status: Optional[str]) -> Optional[str]:
    """
    Translate a carrier status into the canonical value stored on ``Call.status``.

    Unknown statuses are passed through lowercased rather than dropped, so a new
    carrier state still lands somewhere visible instead of silently becoming the
    previous value.

    Args:
        call_status: Carrier-reported status, e.g. Twilio's ``in-progress``

    Returns:
        Canonical status, or None when nothing was reported
    """
    if not call_status:
        return None
    key = call_status.strip().lower()
    return _PROVIDER_CALL_STATUS.get(key, key)


def _apply_telephony_cost(call: Call) -> None:
    """
    Price the carrier leg from the billable duration and refresh the total.

    Args:
        call: Call record to price
    """
    if not call.duration_seconds:
        return

    rate = _TELEPHONY_RATE_PER_MINUTE.get(call.direction, _TELEPHONY_RATE_PER_MINUTE["outbound"])
    call.cost_telephony = round((call.duration_seconds / 60) * rate, 4)
    call.cost_total = round(
        float(call.cost_stt or 0)
        + float(call.cost_llm or 0)
        + float(call.cost_tts or 0)
        + float(call.cost_telephony or 0),
        4,
    )


def _apply_call_timing(
    call: Call,
    canonical_status: Optional[str],
    call_duration: Optional[str] = None,
) -> None:
    """
    Stamp the lifecycle timestamps a status callback implies.

    ``started_at`` is filled on *any* callback that finds it missing, not only on
    ``ringing``. Carriers do not guarantee that event — an inbound number is
    subscribed to ``completed`` alone by default, and an early outbound callback
    can arrive before the row carries its SID — and the previous if/elif chain
    meant a missed ``ringing`` left the column NULL forever, which the UI then
    rendered as the epoch (Jan 1, 1970).

    Args:
        call: Call record to update
        canonical_status: Normalized status for this callback
        call_duration: Carrier-reported duration in seconds, when present
    """
    now = datetime.utcnow()

    # Any sign of life means the call had started by now at the latest.
    if not call.started_at:
        call.started_at = call.created_at or now

    if canonical_status == "in_progress" and not call.answered_at:
        call.answered_at = now

    if canonical_status in ("completed", "failed", "missed"):
        if not call.ended_at:
            call.ended_at = now

        if call_duration:
            try:
                call.duration_seconds = int(float(call_duration))
            except (TypeError, ValueError):
                logger.warning(f"Unparseable call duration from carrier: {call_duration!r}")

        # Carriers occasionally omit the duration on the final callback; the
        # timestamps we just stamped are enough to reconstruct it.
        # Only for a call that actually connected. Reconstructing a span for a
        # busy/no-answer call would turn ring time into billable duration.
        if call.duration_seconds is None and canonical_status == "completed":
            opened = call.answered_at or call.started_at
            if opened and call.ended_at and call.ended_at > opened:
                span = int((call.ended_at - opened).total_seconds())
                if span <= _MAX_RECONSTRUCTED_DURATION_SECONDS:
                    call.duration_seconds = span
                else:
                    logger.warning(
                        f"Refusing to reconstruct a {span}s duration for call {call.id}; "
                        "leaving it unset rather than billing a guess"
                    )

        if call.duration_seconds is not None and call.billable_duration_seconds is None:
            call.billable_duration_seconds = call.duration_seconds

        _apply_telephony_cost(call)


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


async def _find_call_for_status(
    db: AsyncSession,
    *,
    call_id: Optional[str],
    call_sid: Optional[str],
) -> Optional[Call]:
    """
    Find the Call a status callback belongs to.

    Prefers our own id — carried on the status callback URL for calls we dialled
    — because the carrier can fire ``initiated``/``ringing`` before the dial
    response was committed, leaving ``provider_call_sid`` still empty.

    Args:
        db: Database session
        call_id: Our own Call id, when the callback URL carried one
        call_sid: Carrier call identifier

    Returns:
        The matching Call, or None
    """
    if call_id:
        try:
            found = (
                await db.execute(select(Call).where(Call.id == UUID(call_id)))
            ).scalar_one_or_none()
        except ValueError:
            logger.warning(f"Status callback carried a malformed call_id {call_id!r}")
            found = None
        if found is not None:
            return found
        logger.warning(f"Status callback named unknown call_id {call_id}")

    if call_sid:
        return (
            await db.execute(select(Call).where(Call.provider_call_sid == call_sid))
        ).scalar_one_or_none()

    return None


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
            existing.status = normalize_call_status(call_status) or existing.status
        if not existing.started_at:
            existing.started_at = existing.created_at or datetime.utcnow()
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
        status=normalize_call_status(call_status) or "initiated",
        # Stamped here rather than waiting on a `ringing` callback that a carrier
        # may never send: by the time the answer webhook runs, the call is live.
        started_at=datetime.utcnow(),
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

        # Match on our own id first. The early callbacks of an outbound call can
        # land before the dial response committed the SID, and a SID-only lookup
        # dropped them — which is how a call ended up with no start time at all.
        call = await _find_call_for_status(db, call_id=request.query_params.get("call_id"), call_sid=call_sid)

        if not call:
            logger.warning(f"Call not found: {call_sid}")
            return Response(status_code=200)

        if call_sid and not call.provider_call_sid:
            call.provider_call_sid = call_sid

        canonical_status = normalize_call_status(call_status)
        if canonical_status:
            call.status = canonical_status

        _apply_call_timing(call, canonical_status, call_duration)
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
            started_at=datetime.utcnow(),
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
        call.status = normalize_call_status(call_details["status"]) or call.status
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

        call = await _find_call_for_status(db, call_id=request.query_params.get("call_id"), call_sid=call_sid)

        if not call:
            logger.warning(f"Call not found: {call_sid}")
            return Response(status_code=200)

        if call_sid and not call.provider_call_sid:
            call.provider_call_sid = call_sid

        canonical_status = normalize_call_status(call_status)
        if canonical_status:
            call.status = canonical_status

        _apply_call_timing(call, canonical_status, call_duration)
        _record_status_metadata(call, call_status)

        await db.commit()

        logger.info(f"Updated call status: {call.id} -> {call_status}")

        return Response(status_code=200)

    except Exception as e:
        logger.error(f"Error handling Telnyx call status: {e}", exc_info=True)
        return Response(status_code=200)
