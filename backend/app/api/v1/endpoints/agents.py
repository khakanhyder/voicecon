"""
Agent API endpoints.

Handles agent CRUD, configuration, testing, and templates.
"""
import logging
import uuid
import asyncio
import base64
from typing import Optional, List, Dict, Any
from datetime import datetime
import re
import json
from fastapi import APIRouter, Depends, HTTPException, Query, status, UploadFile, File, WebSocket, WebSocketDisconnect
from fastapi.responses import Response, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func
from pydantic import BaseModel, Field

from app.database import get_db
from app.core.dependencies import get_current_active_user
from app.models.user import User, OrganizationMember
from app.models.agent import Agent, AgentFunction
from app.schemas.agent import (
    AgentCreate,
    AgentUpdate,
    AgentResponse,
    AgentListResponse,
    AgentFunctionCreate,
    AgentFunctionUpdate,
    AgentFunctionResponse,
    AgentTestRequest,
    AgentTestResponse,
    AgentCloneRequest,
)
from app.services.agent_service import get_agent_service
from app.services.voice.llm_service import get_llm_service, ChatMessage
from app.services.voice.tts_service import get_tts_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
async def create_agent(
    agent_data: AgentCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new agent.

    Args:
        agent_data: Agent creation data
        current_user: Current authenticated user
        db: Database session

    Returns:
        Created agent
    """
    try:
        # Get user's organization
        org_result = await db.execute(
            select(OrganizationMember)
            .where(OrganizationMember.user_id == current_user.id)
            .limit(1)
        )
        org_member = org_result.scalar_one_or_none()

        if not org_member:
            raise HTTPException(
                status_code=400,
                detail="User is not associated with any organization"
            )

        agent_service = get_agent_service()

        agent = await agent_service.create_agent(
            agent_data=agent_data,
            user_id=current_user.id,
            organization_id=org_member.organization_id,
            db=db,
        )

        return agent

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating agent: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create agent: {str(e)}"
        )


@router.get("", response_model=AgentListResponse)
async def list_agents(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    search: Optional[str] = Query(default=None, description="Search by name/description"),
    tags: Optional[List[str]] = Query(default=None, description="Filter by tags"),
    is_active: Optional[bool] = Query(default=None, description="Filter by active status"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    List user's agents.

    Args:
        skip: Number of records to skip
        limit: Maximum records to return
        search: Search query
        tags: Filter by tags
        is_active: Filter by active status
        current_user: Current authenticated user
        db: Database session

    Returns:
        List of agents
    """
    try:
        # Build query
        query = select(Agent).where(
            and_(
                Agent.user_id == current_user.id,
                Agent.deleted_at.is_(None),
            )
        )

        if search:
            search_filter = or_(
                Agent.name.ilike(f"%{search}%"),
                Agent.description.ilike(f"%{search}%"),
            )
            query = query.where(search_filter)

        if tags:
            # Filter by any matching tag
            query = query.where(Agent.tags.overlap(tags))

        if is_active is not None:
            query = query.where(Agent.is_active == is_active)

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await db.execute(count_query)
        total = total_result.scalar()

        # Get agents
        query = query.order_by(Agent.created_at.desc()).offset(skip).limit(limit)
        result = await db.execute(query)
        agents = result.scalars().all()

        return AgentListResponse(
            agents=agents,
            total=total,
            skip=skip,
            limit=limit,
        )

    except Exception as e:
        logger.error(f"Error listing agents: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list agents: {str(e)}"
        )


@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(
    agent_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get agent by ID.

    Args:
        agent_id: Agent ID
        current_user: Current authenticated user
        db: Database session

    Returns:
        Agent details
    """
    try:
        result = await db.execute(
            select(Agent).where(
                and_(
                    Agent.id == agent_id,
                    Agent.user_id == current_user.id,
                    Agent.deleted_at.is_(None),
                )
            )
        )
        agent = result.scalar_one_or_none()

        if not agent:
            raise HTTPException(
                status_code=404,
                detail="Agent not found"
            )

        return agent

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting agent: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get agent: {str(e)}"
        )


@router.patch("/{agent_id}", response_model=AgentResponse)
async def update_agent(
    agent_id: uuid.UUID,
    agent_data: AgentUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Update an agent.

    Args:
        agent_id: Agent ID
        agent_data: Update data
        current_user: Current authenticated user
        db: Database session

    Returns:
        Updated agent
    """
    try:
        agent_service = get_agent_service()

        agent = await agent_service.update_agent(
            agent_id=agent_id,
            agent_data=agent_data,
            user_id=current_user.id,
            db=db,
        )

        if not agent:
            raise HTTPException(
                status_code=404,
                detail="Agent not found"
            )

        return agent

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating agent: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update agent: {str(e)}"
        )


@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent(
    agent_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Delete an agent (soft delete).

    Args:
        agent_id: Agent ID
        current_user: Current authenticated user
        db: Database session
    """
    try:
        agent_service = get_agent_service()

        deleted = await agent_service.delete_agent(
            agent_id=agent_id,
            user_id=current_user.id,
            db=db,
            soft_delete=True,
        )

        if not deleted:
            raise HTTPException(
                status_code=404,
                detail="Agent not found"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting agent: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete agent: {str(e)}"
        )


@router.post("/{agent_id}/clone", response_model=AgentResponse)
async def clone_agent(
    agent_id: uuid.UUID,
    clone_request: AgentCloneRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Clone an existing agent.

    Args:
        agent_id: Agent ID to clone
        clone_request: Clone configuration
        current_user: Current authenticated user
        db: Database session

    Returns:
        Cloned agent
    """
    try:
        agent_service = get_agent_service()

        agent = await agent_service.clone_agent(
            agent_id=agent_id,
            new_name=clone_request.name,
            user_id=current_user.id,
            organization_id=current_user.organizations[0].id,
            db=db,
            include_functions=clone_request.include_functions,
        )

        if not agent:
            raise HTTPException(
                status_code=404,
                detail="Agent not found"
            )

        return agent

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cloning agent: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to clone agent: {str(e)}"
        )


@router.post("/{agent_id}/test", response_model=AgentTestResponse)
async def test_agent(
    agent_id: uuid.UUID,
    test_request: AgentTestRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Test an agent with a sample message.

    Args:
        agent_id: Agent ID
        test_request: Test configuration
        current_user: Current authenticated user
        db: Database session

    Returns:
        Test results
    """
    try:
        # Get agent
        result = await db.execute(
            select(Agent).where(
                and_(
                    Agent.id == agent_id,
                    Agent.user_id == current_user.id,
                )
            )
        )
        agent = result.scalar_one_or_none()

        if not agent:
            raise HTTPException(
                status_code=404,
                detail="Agent not found"
            )

        # Run test
        start_time = datetime.utcnow()

        # Test LLM
        llm_service = get_llm_service()
        messages = []

        if agent.system_prompt:
            messages.append(ChatMessage(role="system", content=agent.system_prompt))

        messages.append(ChatMessage(role="user", content=test_request.test_message))

        # Generate response
        response_text = ""
        async for chunk in llm_service.chat_stream(
            messages=messages,
            provider=agent.llm_provider,
            model=agent.llm_model,
            temperature=float(agent.llm_temperature),
            max_tokens=agent.llm_max_tokens,
        ):
            response_text += chunk

        # Calculate latency
        end_time = datetime.utcnow()
        latency_ms = int((end_time - start_time).total_seconds() * 1000)

        # Get usage stats
        llm_stats = await llm_service.get_usage_stats(provider=agent.llm_provider)
        last_usage = llm_stats[-1] if llm_stats else None

        costs = {
            "llm": float(last_usage.cost) if last_usage else 0,
            "total": float(last_usage.cost) if last_usage else 0,
        }

        # Test TTS if requested
        if test_request.test_mode == "audio":
            tts_service = get_tts_service()

            # Synthesize (don't stream for test)
            tts_result = await tts_service.synthesize(
                text=response_text[:200],  # Limit for testing
                provider=agent.tts_provider,
                voice_id=agent.tts_voice_id or "rachel",
            )

            tts_stats = await tts_service.get_usage_stats(provider=agent.tts_provider)
            last_tts = tts_stats[-1] if tts_stats else None

            costs["tts"] = float(last_tts.cost) if last_tts else 0
            costs["total"] += costs["tts"]

        return AgentTestResponse(
            success=True,
            test_id=uuid.uuid4(),
            agent_response=response_text,
            latency_ms=latency_ms,
            costs=costs,
            metadata={
                "agent_id": str(agent_id),
                "test_message": test_request.test_message,
                "test_mode": test_request.test_mode,
                "model": agent.llm_model,
                "provider": agent.llm_provider,
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error testing agent: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to test agent: {str(e)}"
        )


class SpeakRequest(BaseModel):
    """Request to synthesize speech for an agent response."""
    text: str = Field(..., description="Text to convert to speech")


@router.post("/{agent_id}/speak")
async def agent_speak(
    agent_id: uuid.UUID,
    request: SpeakRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Convert text to speech using the agent's configured TTS provider.
    Returns base64-encoded MP3 audio.
    """
    try:
        result = await db.execute(
            select(Agent).where(
                and_(Agent.id == agent_id, Agent.user_id == current_user.id)
            )
        )
        agent = result.scalar_one_or_none()
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")

        tts_service = get_tts_service()
        tts_result = await tts_service.synthesize(
            text=request.text,
            provider=agent.tts_provider,
            voice_id=agent.tts_voice_id or "21m00Tcm4TlvDq8ikWAM",
        )

        audio_b64 = base64.b64encode(tts_result.audio_data).decode("utf-8")
        return {
            "audio_base64": audio_b64,
            "audio_format": tts_result.format or "mp3",
            "duration_seconds": tts_result.duration,
            "text": request.text,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error synthesizing speech: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"TTS failed: {str(e)}")


class RespondRequest(BaseModel):
    message: str
    history: list = []


@router.post("/{agent_id}/respond")
async def agent_respond(
    agent_id: uuid.UUID,
    request: RespondRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Low-latency combined LLM + TTS endpoint.
    Streams sentences as SSE: each event contains sentence text + base64 audio.
    Sentences are synthesized as they arrive from the LLM — no waiting for full response.
    """
    result = await db.execute(
        select(Agent).where(and_(Agent.id == agent_id, Agent.user_id == current_user.id))
    )
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    # Gather agent conversation config
    end_call_phrases = list(agent.end_call_phrases or [])
    interrupt_enabled = bool(agent.interrupt_enabled)
    max_tokens_cap = min(agent.llm_max_tokens or 150, 150)

    async def generate():
        # Yield a keepalive SSE comment immediately so the HTTP response opens
        # before any blocking LLM/TTS work begins.
        yield ": keepalive\n\n"
        try:
            llm_service = get_llm_service()
            tts_service = get_tts_service()

            messages = []
            system_text = (agent.system_prompt or "You are a helpful voice assistant.")
            system_text += (
                "\n\nIMPORTANT: You are speaking in a live voice call. "
                "Keep every reply SHORT (1-2 sentences max). "
                "Never use lists, bullet points, or markdown. "
                "Speak naturally and conversationally."
            )
            if end_call_phrases:
                phrases_str = ", ".join(f'"{p}"' for p in end_call_phrases)
                system_text += (
                    f"\n\nWhen the user wants to end the conversation or says goodbye, "
                    f"respond warmly and use one of these exact phrases to end: {phrases_str}."
                )
            messages.append(ChatMessage(role="system", content=system_text))
            for h in request.history[-10:]:
                raw_role = h.get("role", "user")
                role = "assistant" if raw_role == "agent" else raw_role
                messages.append(ChatMessage(role=role, content=h.get("text", "")))
            messages.append(ChatMessage(role="user", content=request.message))

            full_response = ""
            sentence_buffer = ""
            # Queue of in-flight TTS tasks — started immediately when a sentence is
            # detected, running concurrently while the LLM keeps streaming tokens.
            pending_tts: list[asyncio.Task] = []

            # Use the fastest model for voice; upgrade slow legacy defaults silently.
            llm_model = agent.llm_model
            if not llm_model or llm_model in ("gpt-4-turbo-preview", "gpt-4-turbo", "gpt-4o-mini", "gpt-4.1-nano"):
                llm_model = "gpt-5.4-nano"

            def _start_tts(text: str) -> "asyncio.Task | None":
                """Fire-and-forget TTS task — never blocks the LLM loop."""
                text = text.strip()
                if len(text) < 2:
                    return None

                async def _synth() -> "str | None":
                    try:
                        tts_result = await asyncio.wait_for(
                            tts_service.synthesize(
                                text=text,
                                provider=agent.tts_provider,
                                voice_id=agent.tts_voice_id or "21m00Tcm4TlvDq8ikWAM",
                                model="eleven_flash_v2_5",
                            ),
                            timeout=5.0,
                        )
                        audio_b64 = base64.b64encode(tts_result.audio_data).decode()
                        return json.dumps({
                            "type": "sentence",
                            "text": text,
                            "audio_base64": audio_b64,
                            "audio_format": tts_result.format or "mp3",
                        })
                    except Exception as e:
                        logger.warning(f"TTS error (text-only fallback): {e}")
                        return json.dumps({"type": "sentence", "text": text, "audio_base64": None})

                return asyncio.create_task(_synth())

            async for chunk in llm_service.chat_stream(
                messages=messages,
                provider=agent.llm_provider,
                model=llm_model,
                temperature=float(agent.llm_temperature),
                max_tokens=max_tokens_cap,
            ):
                full_response += chunk
                sentence_buffer += chunk

                flush_chunks = []
                while True:
                    m = re.search(r'(?<=[.!?])\s+', sentence_buffer)
                    if m:
                        flush_chunks.append(sentence_buffer[:m.start() + 1])
                        sentence_buffer = sentence_buffer[m.end():]
                        continue
                    if len(sentence_buffer) >= 25:
                        m2 = re.search(r'(?<=[,;])\s+', sentence_buffer)
                        if m2:
                            flush_chunks.append(sentence_buffer[:m2.start() + 1])
                            sentence_buffer = sentence_buffer[m2.end():]
                            continue
                    break

                # Launch TTS for each new sentence — non-blocking
                for fc in flush_chunks:
                    task = _start_tts(fc)
                    if task:
                        pending_tts.append(task)

                # Immediately drain any tasks that already finished (preserving order)
                while pending_tts and pending_tts[0].done():
                    payload = await pending_tts.pop(0)
                    if payload:
                        yield f"data: {payload}\n\n"

            # Flush remaining sentence buffer
            if sentence_buffer.strip():
                task = _start_tts(sentence_buffer.strip())
                if task:
                    pending_tts.append(task)

            # Drain remaining TTS tasks in order
            for task in pending_tts:
                payload = await task
                if payload:
                    yield f"data: {payload}\n\n"

            # Fallback when LLM returned nothing
            if not full_response.strip():
                fallback = "I'm sorry, I didn't get a response. Could you try again?"
                task = _start_tts(fallback)
                if task:
                    payload = await task
                    if payload:
                        yield f"data: {payload}\n\n"
                full_response = fallback

            # End-call phrase detection
            end_call_triggered = False
            if end_call_phrases:
                full_lower = full_response.lower()
                for phrase in end_call_phrases:
                    if phrase.lower() in full_lower:
                        end_call_triggered = True
                        break

            yield f"data: {json.dumps({'type': 'done', 'full_text': full_response, 'end_call': end_call_triggered})}\n\n"

        except Exception as e:
            logger.error(f"Error in respond stream: {e}", exc_info=True)
            err_msg = "I'm having a technical issue right now. Please try again."
            if "quota" in str(e).lower() or "429" in str(e):
                err_msg = "The AI service is temporarily unavailable. Please try again shortly."
            elif "rate" in str(e).lower():
                err_msg = "I'm receiving too many requests. Please wait a moment and try again."
            yield f"data: {json.dumps({'type': 'sentence', 'text': err_msg, 'audio_base64': None})}\n\n"
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
            yield f"data: {json.dumps({'type': 'done', 'full_text': err_msg, 'end_call': False})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


class SessionLogRequest(BaseModel):
    """Request to log a completed web test session as a call record."""
    started_at: datetime
    duration_seconds: int = Field(ge=0)
    messages: list = Field(default_factory=list)  # [{"role": "user"|"agent", "text": "..."}]


@router.post("/{agent_id}/log-session")
async def log_agent_session(
    agent_id: uuid.UUID,
    request: SessionLogRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Log a completed web-based test call session to the call history.
    Called by the frontend at the end of each test call.
    """
    from app.models.call import Call
    from sqlalchemy import select, and_

    result = await db.execute(
        select(Agent).where(and_(Agent.id == agent_id, Agent.user_id == current_user.id))
    )
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    # Build plain-text transcript
    transcript_lines = [
        f"{m.get('role', 'user').upper()}: {m.get('text', '')}"
        for m in request.messages
        if m.get('text', '').strip()
    ]
    transcript = "\n".join(transcript_lines)

    from datetime import timedelta
    ended_at = request.started_at + timedelta(seconds=request.duration_seconds)

    call = Call(
        user_id=current_user.id,
        organization_id=agent.organization_id,
        agent_id=agent.id,
        direction="test",
        from_number="web-test",
        to_number="web-test",
        status="completed",
        started_at=request.started_at,
        ended_at=ended_at,
        duration_seconds=request.duration_seconds,
        billable_duration_seconds=request.duration_seconds,
        transcript=transcript,
        transcript_json={"messages": request.messages},
        call_metadata={"source": "web_test", "agent_name": agent.name},
    )

    db.add(call)
    try:
        await db.commit()
        await db.refresh(call)
        logger.info(f"Logged web test session for agent {agent_id}: {call.id} ({request.duration_seconds}s, {len(request.messages)} messages)")
        return {"id": str(call.id), "status": "logged"}
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to log session: {e}")
        raise HTTPException(status_code=500, detail="Failed to log session")


@router.post("/{agent_id}/calls/{call_id}/recording")
async def upload_call_recording(
    agent_id: uuid.UUID,
    call_id: uuid.UUID,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Save a browser-recorded audio file for a test call."""
    import os
    from app.models.call import Call

    result = await db.execute(
        select(Call).where(and_(
            Call.id == call_id,
            Call.user_id == current_user.id,
            Call.agent_id == agent_id,
        ))
    )
    call = result.scalar_one_or_none()
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")

    recordings_dir = os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', 'recordings')
    os.makedirs(recordings_dir, exist_ok=True)

    filename = f"{call_id}.webm"
    filepath = os.path.join(recordings_dir, filename)
    contents = await file.read()
    with open(filepath, 'wb') as f:
        f.write(contents)

    call.recording_url = f"/recordings/{filename}"
    call.recording_duration = call.duration_seconds
    await db.commit()

    logger.info(f"Saved recording for call {call_id}: {len(contents)} bytes")
    return {"recording_url": call.recording_url}


@router.websocket("/{agent_id}/stt")
async def agent_stt_websocket(
    websocket: WebSocket,
    agent_id: uuid.UUID,
    token: str = Query(default=""),
):
    """
    Real-time Deepgram STT WebSocket proxy.
    Client sends raw audio bytes (WebM/Opus); server forwards to Deepgram and returns
    transcript events as JSON. Auth via 'token' query param (browser WS can't set headers).
    """
    await websocket.accept()

    # Authenticate
    from app.core.security import decode_token
    from app.database import AsyncSessionLocal
    from app.models.user import User

    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        await websocket.close(code=4001)
        return

    user_id = payload.get("sub")

    async with AsyncSessionLocal() as db:
        user_result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
        user = user_result.scalar_one_or_none()
        if not user:
            await websocket.close(code=4001)
            return

        result = await db.execute(
            select(Agent).where(and_(Agent.id == agent_id, Agent.user_id == user.id))
        )
        agent = result.scalar_one_or_none()
        if not agent:
            await websocket.close(code=4004)
            return

        stt_model = getattr(agent, "stt_model", None) or "nova-3"
        stt_language = getattr(agent, "stt_language", None) or "en"

    from app.core.config import settings

    if not getattr(settings, "DEEPGRAM_API_KEY", None):
        await websocket.send_json({"type": "error", "message": "Deepgram API key not configured"})
        await websocket.close()
        return

    dg_url = (
        f"wss://api.deepgram.com/v1/listen"
        f"?model={stt_model}"
        f"&language={stt_language}"
        f"&interim_results=true"
        f"&smart_format=false"
        f"&no_delay=true"
        f"&endpointing=300"
        f"&utterance_end_ms=1000"
    )

    try:
        import aiohttp

        async with aiohttp.ClientSession() as session:
            async with session.ws_connect(
                dg_url,
                headers={"Authorization": f"Token {settings.DEEPGRAM_API_KEY}"},
            ) as dg_ws:
                await websocket.send_json({"type": "ready"})

                async def relay_client_to_deepgram():
                    try:
                        async for data in websocket.iter_bytes():
                            if not dg_ws.closed:
                                await dg_ws.send_bytes(data)
                    except WebSocketDisconnect:
                        pass
                    except Exception:
                        pass
                    finally:
                        try:
                            await dg_ws.close()
                        except Exception:
                            pass

                async def relay_deepgram_to_client():
                    try:
                        async for msg in dg_ws:
                            if msg.type == aiohttp.WSMsgType.TEXT:
                                data = json.loads(msg.data)
                                msg_type = data.get("type")
                                if msg_type == "Results":
                                    alts = data.get("channel", {}).get("alternatives", [{}])
                                    transcript = alts[0].get("transcript", "") if alts else ""
                                    if transcript:
                                        await websocket.send_json({
                                            "type": "transcript",
                                            "text": transcript,
                                            "is_final": data.get("is_final", False),
                                            "speech_final": data.get("speech_final", False),
                                        })
                                elif msg_type == "UtteranceEnd":
                                    await websocket.send_json({"type": "utterance_end"})
                            elif msg.type in (aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.ERROR):
                                break
                    except Exception:
                        pass

                await asyncio.gather(relay_client_to_deepgram(), relay_deepgram_to_client())

    except Exception as e:
        logger.error(f"STT WebSocket error: {e}")
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
            await websocket.close()
        except Exception:
            pass


@router.post("/{agent_id}/transcribe")
async def agent_transcribe(
    agent_id: uuid.UUID,
    audio: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Transcribe audio file to text using agent's configured STT provider (Deepgram).
    Accepts WAV/WebM audio upload, returns transcript text.
    """
    try:
        result = await db.execute(
            select(Agent).where(
                and_(Agent.id == agent_id, Agent.user_id == current_user.id)
            )
        )
        agent = result.scalar_one_or_none()
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")

        # Read audio bytes
        audio_bytes = await audio.read()
        if not audio_bytes:
            raise HTTPException(status_code=400, detail="Empty audio file")

        # Use Deepgram HTTPS API (non-streaming for test mode)
        import aiohttp
        from app.core.config import settings

        url = "https://api.deepgram.com/v1/listen"
        params = {
            "language": agent.stt_language or "en",
            "model": agent.stt_model or "nova-2",
            "punctuate": "true",
            "smart_format": "true",
        }
        headers = {
            "Authorization": f"Token {settings.DEEPGRAM_API_KEY}",
            "Content-Type": audio.content_type or "audio/webm",
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, params=params, data=audio_bytes) as resp:
                if resp.status == 401:
                    raise HTTPException(status_code=500, detail="Invalid Deepgram API key")
                if resp.status != 200:
                    body = await resp.text()
                    raise HTTPException(status_code=500, detail=f"Deepgram error: {body}")
                data = await resp.json()

        # Extract transcript
        try:
            transcript = data["results"]["channels"][0]["alternatives"][0]["transcript"]
        except (KeyError, IndexError):
            transcript = ""

        return {
            "transcript": transcript,
            "language": agent.stt_language or "en",
            "confidence": data.get("results", {}).get("channels", [{}])[0]
                          .get("alternatives", [{}])[0].get("confidence", 0),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error transcribing audio: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")


@router.get("/templates/list")
async def list_templates(
    current_user: User = Depends(get_current_active_user),
):
    """
    List available agent templates.

    Args:
        current_user: Current authenticated user

    Returns:
        List of templates
    """
    try:
        agent_service = get_agent_service()
        templates = agent_service.get_templates()

        return {
            "templates": templates,
            "total": len(templates),
        }

    except Exception as e:
        logger.error(f"Error listing templates: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list templates: {str(e)}"
        )


@router.post("/templates/{template_id}/create", response_model=AgentResponse)
async def create_from_template(
    template_id: str,
    custom_name: Optional[str] = Query(default=None),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Create agent from template.

    Args:
        template_id: Template ID
        custom_name: Optional custom name
        current_user: Current authenticated user
        db: Database session

    Returns:
        Created agent
    """
    try:
        agent_service = get_agent_service()

        agent = await agent_service.create_from_template(
            template_id=template_id,
            user_id=current_user.id,
            organization_id=current_user.organizations[0].id,
            db=db,
            custom_name=custom_name,
        )

        if not agent:
            raise HTTPException(
                status_code=404,
                detail="Template not found"
            )

        return agent

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating from template: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create from template: {str(e)}"
        )


# Agent Functions endpoints


@router.post("/{agent_id}/functions", response_model=AgentFunctionResponse)
async def create_agent_function(
    agent_id: uuid.UUID,
    function_data: AgentFunctionCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a function for an agent.

    Args:
        agent_id: Agent ID
        function_data: Function data
        current_user: Current authenticated user
        db: Database session

    Returns:
        Created function
    """
    try:
        # Verify agent ownership
        result = await db.execute(
            select(Agent).where(
                and_(
                    Agent.id == agent_id,
                    Agent.user_id == current_user.id,
                )
            )
        )
        agent = result.scalar_one_or_none()

        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")

        # Create function
        function = AgentFunction(
            agent_id=agent_id,
            name=function_data.name,
            description=function_data.description,
            parameters=function_data.parameters,
            webhook_url=function_data.webhook_url,
            http_method=function_data.http_method,
            headers=function_data.headers,
            timeout=function_data.timeout,
            retry_count=function_data.retry_count,
            is_active=function_data.is_active,
            execution_order=function_data.execution_order,
        )

        db.add(function)
        await db.commit()
        await db.refresh(function)

        return function

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating function: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{agent_id}/functions", response_model=List[AgentFunctionResponse])
async def list_agent_functions(
    agent_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    List agent's functions.

    Args:
        agent_id: Agent ID
        current_user: Current authenticated user
        db: Database session

    Returns:
        List of functions
    """
    try:
        # Verify agent ownership
        result = await db.execute(
            select(Agent).where(
                and_(
                    Agent.id == agent_id,
                    Agent.user_id == current_user.id,
                )
            )
        )
        agent = result.scalar_one_or_none()

        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")

        # Get functions
        result = await db.execute(
            select(AgentFunction)
            .where(AgentFunction.agent_id == agent_id)
            .order_by(AgentFunction.execution_order)
        )
        functions = result.scalars().all()

        return functions

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing functions: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{agent_id}/functions/{function_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent_function(
    agent_id: uuid.UUID,
    function_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Delete an agent function.

    Args:
        agent_id: Agent ID
        function_id: Function ID
        current_user: Current authenticated user
        db: Database session
    """
    try:
        # Verify agent ownership
        result = await db.execute(
            select(Agent).where(
                and_(
                    Agent.id == agent_id,
                    Agent.user_id == current_user.id,
                )
            )
        )
        agent = result.scalar_one_or_none()

        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")

        # Delete function
        result = await db.execute(
            select(AgentFunction).where(
                and_(
                    AgentFunction.id == function_id,
                    AgentFunction.agent_id == agent_id,
                )
            )
        )
        function = result.scalar_one_or_none()

        if not function:
            raise HTTPException(status_code=404, detail="Function not found")

        await db.delete(function)
        await db.commit()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting function: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# Function Testing Endpoint
class FunctionTestRequest(BaseModel):
    """Function test request."""
    parameters: Dict[str, Any] = Field(..., description="Function parameters to test")


class FunctionTestResponse(BaseModel):
    """Function test response."""
    success: bool
    function_name: str
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    execution_time_ms: int
    formatted_result: str


@router.post("/{agent_id}/functions/{function_id}/test", response_model=FunctionTestResponse)
async def test_function(
    agent_id: str,
    function_id: str,
    test_request: FunctionTestRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Test a function with sample parameters.

    Args:
        agent_id: Agent ID
        function_id: Function ID
        test_request: Test request with parameters
        current_user: Current authenticated user
        db: Database session

    Returns:
        Function test result
    """
    try:
        # Verify agent ownership
        result = await db.execute(
            select(Agent).where(
                and_(
                    Agent.id == agent_id,
                    Agent.user_id == current_user.id,
                )
            )
        )
        agent = result.scalar_one_or_none()

        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")

        # Get function
        result = await db.execute(
            select(AgentFunction).where(
                and_(
                    AgentFunction.id == function_id,
                    AgentFunction.agent_id == agent_id,
                )
            )
        )
        function = result.scalar_one_or_none()

        if not function:
            raise HTTPException(status_code=404, detail="Function not found")

        # Execute function
        from app.services.function_executor import get_function_executor

        executor = get_function_executor()

        execution_result = await executor.execute_function(
            function=function,
            parameters=test_request.parameters,
            call_id=None,  # No call ID for testing
            db=None,  # Don't log test executions
        )

        # Format result for display
        formatted_result = executor.format_for_llm(function, execution_result)

        return FunctionTestResponse(
            success=execution_result["success"],
            function_name=execution_result["function_name"],
            result=execution_result.get("result"),
            error=execution_result.get("error"),
            execution_time_ms=execution_result["execution_time_ms"],
            formatted_result=formatted_result,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error testing function: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
