"""
Call-related Pydantic schemas.
"""
import uuid
from typing import Optional, Dict, Any, List
from datetime import datetime
from pydantic import BaseModel, Field, validator


# Phone Number Schemas

class PhoneNumberBase(BaseModel):
    """Base phone number schema."""
    phone_number: str = Field(..., description="Phone number in E.164 format")


class PhoneNumberCreate(PhoneNumberBase):
    """Schema for creating a phone number."""
    pass


class PhoneNumberResponse(PhoneNumberBase):
    """Schema for phone number response."""
    id: uuid.UUID
    user_id: uuid.UUID
    organization_id: Optional[uuid.UUID] = None
    provider: str
    provider_number_id: Optional[str] = None
    capabilities: Dict[str, Any] = Field(default_factory=dict)
    status: str = "active"
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Call Schemas

class CallBase(BaseModel):
    """Base call schema."""
    to_number: str = Field(..., description="Destination phone number")


class CallCreate(CallBase):
    """Schema for creating a call."""
    agent_id: uuid.UUID = Field(..., description="ID of the agent handling the call")
    from_number_id: Optional[uuid.UUID] = Field(None, description="ID of the phone number to call from")


class CallResponse(BaseModel):
    """Schema for call response."""
    id: uuid.UUID
    agent_id: Optional[uuid.UUID] = None
    user_id: uuid.UUID
    organization_id: Optional[uuid.UUID] = None
    phone_number_id: Optional[uuid.UUID] = None
    from_number: str
    to_number: str
    direction: str
    status: str
    started_at: Optional[datetime] = None
    answered_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    duration_seconds: Optional[int] = None
    recording_url: Optional[str] = None
    recording_duration: Optional[int] = None
    transcript: Optional[str] = None
    transcript_json: Optional[Any] = None
    summary: Optional[str] = None
    sentiment_score: Optional[float] = None
    sentiment_label: Optional[str] = None
    cost_stt: Optional[float] = None
    cost_llm: Optional[float] = None
    cost_tts: Optional[float] = None
    cost_telephony: Optional[float] = None
    cost_total: Optional[float] = None
    tags: List[str] = Field(default_factory=list)
    call_metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CallListResponse(BaseModel):
    """Schema for paginated call list."""
    calls: List[CallResponse]
    total: int
    skip: int
    limit: int


class CallLogResponse(BaseModel):
    """Schema for call log entry."""
    id: uuid.UUID
    call_id: uuid.UUID
    timestamp: datetime
    event_type: str
    metadata: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        from_attributes = True


# WebSocket Message Schemas

class TranscriptionMessage(BaseModel):
    """WebSocket message for transcription."""
    type: str = "transcription"
    text: str
    is_final: bool
    confidence: Optional[float] = None
    timestamp: datetime


class AgentMessage(BaseModel):
    """WebSocket message for agent response."""
    type: str = "agent_message"
    text: str
    timestamp: datetime


class AgentResponseMessage(BaseModel):
    """WebSocket message for agent response."""
    type: str = "agent_response"
    text: str
    timestamp: datetime


class ErrorMessage(BaseModel):
    """WebSocket error message."""
    type: str = "error"
    message: str
    code: Optional[str] = None


class ControlMessage(BaseModel):
    """WebSocket control message."""
    type: str
    data: Optional[Dict[str, Any]] = None
