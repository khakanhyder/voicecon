"""
Voice library: looking up, previewing and resolving credentials for voices.

The TTS providers in ``providers/`` know how to *speak*. This module knows how
to answer the questions the voice picker asks: does this voice id exist, what
is it called, what does it sound like, and which API key reaches it.

Each provider that supports bring-your-own voices has a
:class:`VoiceProviderAdapter` registered in ``ADAPTERS``. Adding a provider
means writing its TTS class, registering it in ``TTSService.PROVIDERS`` and
adding an adapter here; the endpoints and the UI are driven by the registry.
"""
import logging
import re
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import httpx
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.voice import CustomVoice
from app.services.integrations.credential_manager import get_credential_manager
from app.services.voice.providers.base import (
    AuthenticationError,
    ProviderError,
    RateLimitError,
    SynthesisResult,
)
from app.services.voice.tts_service import get_tts_service

logger = logging.getLogger(__name__)

# Spoken by every preview, so voices are compared on the same words.
PREVIEW_TEXT = "Hello! This is how I will sound when I speak with your callers."


class UnsupportedVoiceProvider(ProviderError):
    """No adapter is registered for the provider."""


class InvalidVoiceId(ProviderError):
    """The voice id is not in the shape the provider uses."""


class VoiceNotFound(ProviderError):
    """The provider has no such voice, or the key in use cannot reach it."""


class VoiceLookupUnavailable(ProviderError):
    """The key may speak but is not allowed to read voice details."""


class ProviderNotConfigured(ProviderError):
    """Neither the caller nor the platform has a key for the provider."""


@dataclass
class VoiceInfo:
    provider: str
    voice_id: str
    # None when the provider would not tell us (see VoiceLookupUnavailable).
    name: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    labels: Dict[str, str] = field(default_factory=dict)


@dataclass
class ConfigField:
    """One input of the "add custom voice" form, described for the frontend."""
    key: str
    label: str
    required: bool
    secret: bool = False
    placeholder: str = ""
    help: str = ""


class VoiceProviderAdapter(ABC):
    slug: str
    label: str
    fields: List[ConfigField]

    @abstractmethod
    def clean_voice_id(self, voice_id: str) -> str:
        """Return the normalised id, or raise InvalidVoiceId."""

    @abstractmethod
    async def lookup(self, voice_id: str, api_key: str) -> VoiceInfo:
        """Fetch the voice's details. Raises VoiceNotFound, AuthenticationError
        or VoiceLookupUnavailable."""

    @abstractmethod
    def is_missing_voice(self, error: ProviderError) -> bool:
        """Whether a synthesis error means "no such voice"."""


class ElevenLabsVoices(VoiceProviderAdapter):
    slug = "elevenlabs"
    label = "ElevenLabs"
    fields = [
        ConfigField(
            key="voice_id",
            label="Voice ID",
            required=True,
            placeholder="e.g. 21m00Tcm4TlvDq8ikWAM",
            help="In ElevenLabs, open Voices, then choose the voice's menu and Copy voice ID.",
        ),
        ConfigField(
            key="api_key",
            label="ElevenLabs API key",
            required=False,
            secret=True,
            placeholder="sk_...",
            help=(
                "Needed for voices in your own ElevenLabs account, such as cloned voices. "
                "It is stored encrypted and never shown again."
            ),
        ),
    ]

    BASE_URL = "https://api.elevenlabs.io/v1"
    # The id is placed in a URL path, so nothing but the id's own alphabet.
    _VOICE_ID = re.compile(r"^[A-Za-z0-9]{16,40}$")

    def __init__(self, transport: Optional[httpx.AsyncBaseTransport] = None):
        self._transport = transport

    def clean_voice_id(self, voice_id: str) -> str:
        cleaned = (voice_id or "").strip()
        if not self._VOICE_ID.match(cleaned):
            raise InvalidVoiceId(
                "That doesn't look like an ElevenLabs Voice ID. "
                "It is about 20 letters and numbers, with no spaces."
            )
        return cleaned

    async def lookup(self, voice_id: str, api_key: str) -> VoiceInfo:
        try:
            async with httpx.AsyncClient(
                base_url=self.BASE_URL, timeout=15.0, transport=self._transport
            ) as client:
                response = await client.get(
                    f"/voices/{voice_id}", headers={"xi-api-key": api_key}
                )
        except httpx.HTTPError as e:
            raise ProviderError(f"Network error: {e}")

        if response.status_code == 200:
            data = response.json()
            labels = data.get("labels") or {}
            return VoiceInfo(
                provider=self.slug,
                voice_id=data.get("voice_id") or voice_id,
                name=data.get("name"),
                category=data.get("category"),
                description=data.get("description"),
                labels={str(k): str(v) for k, v in labels.items() if v},
            )

        status_code = self._error_status(response)
        if response.status_code == 401:
            if status_code == "missing_permissions":
                raise VoiceLookupUnavailable("Key cannot read voice details")
            raise AuthenticationError("ElevenLabs rejected the API key")
        if response.status_code == 429:
            raise RateLimitError("ElevenLabs rate limit exceeded")
        if response.status_code in (400, 404, 422):
            raise VoiceNotFound(f"ElevenLabs has no voice {voice_id} for this key")
        raise ProviderError(f"ElevenLabs returned {response.status_code}")

    def is_missing_voice(self, error: ProviderError) -> bool:
        text = str(error).lower()
        return "voice_not_found" in text or "voice_does_not_exist" in text

    @staticmethod
    def _error_status(response: httpx.Response) -> Optional[str]:
        try:
            detail = response.json().get("detail")
        except ValueError:
            return None
        return detail.get("status") if isinstance(detail, dict) else None


ADAPTERS: Dict[str, VoiceProviderAdapter] = {
    ElevenLabsVoices.slug: ElevenLabsVoices(),
}


def get_adapter(provider: str) -> VoiceProviderAdapter:
    adapter = ADAPTERS.get((provider or "").strip().lower())
    if adapter is None:
        raise UnsupportedVoiceProvider(f"Custom voices are not supported for {provider}")
    return adapter


def _key_for(provider: str, api_key: Optional[str]) -> str:
    key = (api_key or "").strip() or get_tts_service()._get_api_key(provider)
    if not key:
        raise ProviderNotConfigured(f"No API key is configured for {provider}")
    return key


async def preview_voice(
    provider: str, voice_id: str, api_key: Optional[str] = None
) -> SynthesisResult:
    """Speak the sample sentence with the voice. ``api_key`` is the caller's
    own provider key; without it the platform's key is used."""
    adapter = get_adapter(provider)
    voice_id = adapter.clean_voice_id(voice_id)
    key = _key_for(adapter.slug, api_key)
    try:
        return await get_tts_service().synthesize(
            text=PREVIEW_TEXT,
            provider=adapter.slug,
            api_key=key,
            voice_id=voice_id,
        )
    except ProviderError as e:
        if adapter.is_missing_voice(e):
            raise VoiceNotFound(str(e))
        raise


async def inspect_voice(
    provider: str, voice_id: str, api_key: Optional[str] = None
) -> VoiceInfo:
    """Confirm the voice exists and is usable with the key, and describe it.

    Some keys are scoped to speech only and may not read voice details. For
    those the voice is proven by speaking with it, and comes back unnamed.
    """
    adapter = get_adapter(provider)
    voice_id = adapter.clean_voice_id(voice_id)
    try:
        return await adapter.lookup(voice_id, _key_for(adapter.slug, api_key))
    except VoiceLookupUnavailable:
        await preview_voice(adapter.slug, voice_id, api_key)
        return VoiceInfo(provider=adapter.slug, voice_id=voice_id)


def encrypt_api_key(api_key: Optional[str]) -> Optional[str]:
    key = (api_key or "").strip()
    return get_credential_manager().encrypt(key) if key else None


async def resolve_tts_api_key(
    db: AsyncSession,
    organization_id: uuid.UUID,
    provider: Optional[str],
    voice_id: Optional[str],
) -> Optional[str]:
    """The key an agent's voice must be spoken with, or None for the platform's.

    Returns a key only when the voice is one of the workspace's custom voices
    and was saved with the workspace's own provider key.
    """
    if not provider or not voice_id:
        return None
    try:
        result = await db.execute(
            select(CustomVoice.api_key_encrypted).where(
                and_(
                    CustomVoice.organization_id == organization_id,
                    CustomVoice.provider == provider,
                    CustomVoice.voice_id == voice_id,
                )
            )
        )
        encrypted = result.scalar_one_or_none()
        if not encrypted:
            return None
        return get_credential_manager().decrypt(encrypted) or None
    except Exception as e:
        # A call should still be attempted with the platform key rather than
        # die here; if the voice needs the custom key, synthesis reports it.
        logger.error(f"Could not resolve custom voice key for org {organization_id}: {e}")
        return None
