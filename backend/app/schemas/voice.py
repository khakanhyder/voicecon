"""Schemas for the voice library."""
import uuid
from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field
from app.core.time import UTCDatetime


class VoiceRef(BaseModel):
    """A voice, and optionally the caller's own provider key for reaching it."""
    provider: str = Field(default="elevenlabs", max_length=50)
    voice_id: str = Field(..., min_length=1, max_length=255)
    api_key: Optional[str] = Field(default=None, max_length=500)


class CustomVoiceCreate(VoiceRef):
    # Defaults to the name the provider gives the voice.
    name: Optional[str] = Field(default=None, max_length=255)


class VoiceCheckResponse(BaseModel):
    provider: str
    voice_id: str
    name: Optional[str]
    category: Optional[str]
    description: Optional[str]
    labels: Dict[str, str]


class CustomVoiceResponse(BaseModel):
    id: uuid.UUID
    provider: str
    voice_id: str
    name: str
    category: Optional[str]
    description: Optional[str]
    labels: Dict[str, str]
    # Whether the voice is spoken with the workspace's own provider key. The
    # key itself is never returned.
    uses_own_key: bool
    created_at: UTCDatetime


class VoiceProviderField(BaseModel):
    key: str
    label: str
    required: bool
    secret: bool
    placeholder: str
    help: str


class VoiceProviderInfo(BaseModel):
    slug: str
    label: str
    fields: List[VoiceProviderField]


class VoiceLibraryResponse(BaseModel):
    # Providers a custom voice can be added from.
    providers: List[VoiceProviderInfo]
    custom_voices: List[CustomVoiceResponse]
