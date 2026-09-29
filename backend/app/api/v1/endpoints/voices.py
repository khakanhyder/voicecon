"""
Voice library API: preview any voice, and manage a workspace's custom voices.

Provider keys only ever travel inward. A key typed into the "add custom voice"
form is used for that request and, on save, stored encrypted; no response
carries one.
"""
import logging
import uuid
from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import and_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.entitlement_guard import require_entitlement
from app.services.billing import catalog
from app.core.dependencies import get_current_active_user, get_current_org_id
from app.database import get_db
from app.models.agent import Agent
from app.models.user import User
from app.models.voice import CustomVoice
from app.schemas.voice import (
    CustomVoiceCreate,
    CustomVoiceResponse,
    VoiceCheckResponse,
    VoiceLibraryResponse,
    VoiceProviderInfo,
    VoiceRef,
)
from app.services.voice import voice_library
from app.services.voice.providers.base import (
    AuthenticationError,
    ProviderError,
    RateLimitError,
)

logger = logging.getLogger(__name__)
router = APIRouter()


def _to_response(voice: CustomVoice) -> CustomVoiceResponse:
    return CustomVoiceResponse(
        id=voice.id,
        provider=voice.provider,
        voice_id=voice.voice_id,
        name=voice.name,
        category=voice.category,
        description=voice.description,
        labels=voice.labels or {},
        uses_own_key=bool(voice.api_key_encrypted),
        created_at=voice.created_at,
    )


def _http_error(error: ProviderError, own_key: bool) -> HTTPException:
    """Turn a provider failure into something the person can act on."""
    if isinstance(error, voice_library.UnsupportedVoiceProvider):
        return HTTPException(status.HTTP_400_BAD_REQUEST, "That voice provider is not supported yet.")
    if isinstance(error, voice_library.InvalidVoiceId):
        return HTTPException(status.HTTP_400_BAD_REQUEST, str(error))
    if isinstance(error, voice_library.VoiceNotFound):
        hint = (
            "Check the Voice ID and that it belongs to the account this API key is from."
            if own_key
            else "Check the Voice ID. If the voice is in your own provider account, add that account's API key."
        )
        return HTTPException(status.HTTP_404_NOT_FOUND, f"We couldn't find that voice. {hint}")
    if isinstance(error, RateLimitError):
        return HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "The voice provider is busy. Please try again in a moment.",
        )
    if isinstance(error, AuthenticationError) and "payment" in str(error).lower():
        # The provider answers an unpaid account the same way as a bad key.
        whose = "the account that API key belongs to" if own_key else "the voice provider account"
        return HTTPException(
            status.HTTP_402_PAYMENT_REQUIRED if own_key else status.HTTP_502_BAD_GATEWAY,
            f"The voice could not be played because {whose} has an unpaid invoice.",
        )
    if isinstance(error, AuthenticationError) and own_key:
        return HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "The voice provider rejected that API key. Check that it is correct and allowed to use text to speech.",
        )
    logger.error(f"Voice provider error: {error}")
    return HTTPException(
        status.HTTP_502_BAD_GATEWAY,
        "The voice provider could not be reached. Please try again.",
    )


async def _saved_key(db: AsyncSession, org_id: uuid.UUID, ref: VoiceRef) -> "str | None":
    """The key to use for a request: the one typed in, else the one saved with
    the workspace's custom voice, else None (the platform's)."""
    if ref.api_key and ref.api_key.strip():
        return ref.api_key.strip()
    return await voice_library.resolve_tts_api_key(db, org_id, ref.provider, ref.voice_id.strip())


@router.get("", response_model=VoiceLibraryResponse)
async def get_voice_library(
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db),
):
    """The workspace's custom voices, and the providers one can be added from."""
    result = await db.execute(
        select(CustomVoice)
        .where(CustomVoice.organization_id == org_id)
        .order_by(CustomVoice.created_at.desc())
    )
    return VoiceLibraryResponse(
        providers=[
            VoiceProviderInfo(
                slug=adapter.slug,
                label=adapter.label,
                fields=[asdict(f) for f in adapter.fields],
            )
            for adapter in voice_library.ADAPTERS.values()
        ],
        custom_voices=[_to_response(v) for v in result.scalars().all()],
    )


@router.post("/preview")
async def preview_voice(
    ref: VoiceRef,
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db),
):
    """A short spoken sample of the voice, as MP3. Works for built-in voices,
    saved custom voices, and a custom voice that is still being added."""
    key = await _saved_key(db, org_id, ref)
    try:
        result = await voice_library.preview_voice(ref.provider, ref.voice_id, key)
    except ProviderError as e:
        raise _http_error(e, own_key=bool(key))
    return Response(
        content=result.audio_data,
        media_type="audio/mpeg",
        headers={"Cache-Control": "private, max-age=3600"},
    )


@router.post("/custom/check", response_model=VoiceCheckResponse)
async def check_custom_voice(
    ref: VoiceRef,
    current_user: User = Depends(get_current_active_user),
):
    """Confirm a voice id exists and can be used, before it is saved."""
    try:
        info = await voice_library.inspect_voice(ref.provider, ref.voice_id, ref.api_key)
    except ProviderError as e:
        raise _http_error(e, own_key=bool(ref.api_key and ref.api_key.strip()))
    return VoiceCheckResponse(**asdict(info))


@router.post(
    "/custom",
    response_model=CustomVoiceResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[
        Depends(
            require_entitlement(
                feature=catalog.CUSTOM_VOICE, limit=catalog.LIMIT_CUSTOM_VOICES
            )
        )
    ],
)
async def add_custom_voice(
    body: CustomVoiceCreate,
    current_user: User = Depends(get_current_active_user),
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db),
):
    """Validate a voice against its provider and save it to the library."""
    try:
        info = await voice_library.inspect_voice(body.provider, body.voice_id, body.api_key)
    except ProviderError as e:
        raise _http_error(e, own_key=bool(body.api_key and body.api_key.strip()))

    name = (body.name or "").strip() or info.name
    if not name:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Please give this voice a name. Its provider did not share one.",
        )

    existing = await db.execute(
        select(CustomVoice.id).where(
            and_(
                CustomVoice.organization_id == org_id,
                CustomVoice.provider == info.provider,
                CustomVoice.voice_id == info.voice_id,
            )
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status.HTTP_409_CONFLICT, "This voice is already in your library.")

    voice = CustomVoice(
        organization_id=org_id,
        created_by=current_user.id,
        provider=info.provider,
        voice_id=info.voice_id,
        name=name,
        category=info.category,
        description=info.description,
        labels=info.labels,
        api_key_encrypted=voice_library.encrypt_api_key(body.api_key),
    )
    db.add(voice)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "This voice is already in your library.")
    await db.refresh(voice)
    return _to_response(voice)


@router.delete("/custom/{custom_voice_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_custom_voice(
    custom_voice_id: uuid.UUID,
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db),
):
    """Remove a custom voice. Refused while an agent still speaks with it."""
    result = await db.execute(
        select(CustomVoice).where(
            and_(CustomVoice.id == custom_voice_id, CustomVoice.organization_id == org_id)
        )
    )
    voice = result.scalar_one_or_none()
    if not voice:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Voice not found")

    in_use = await db.execute(
        select(Agent.name).where(
            and_(
                Agent.organization_id == org_id,
                Agent.tts_provider == voice.provider,
                Agent.tts_voice_id == voice.voice_id,
                Agent.deleted_at.is_(None),
            )
        )
    )
    agent_names = [name for name in in_use.scalars().all()]
    if agent_names:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "This voice is used by: " + ", ".join(agent_names[:5])
            + ". Choose another voice for those assistants first.",
        )

    await db.delete(voice)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
