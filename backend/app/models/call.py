"""
Call and telephony-related models.
"""
import uuid
from datetime import datetime
from typing import List, Optional
from decimal import Decimal
from sqlalchemy import Boolean, Column, DateTime, String, Text, ForeignKey, Integer, JSON, Numeric, Uuid
from sqlalchemy.orm import relationship, Mapped, mapped_column

from app.database import Base


class PhoneNumber(Base):
    """Phone number model."""

    __tablename__ = "phone_numbers"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    agent_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("agents.id")
    )

    phone_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    country_code: Mapped[Optional[str]] = mapped_column(String(10))
    area_code: Mapped[Optional[str]] = mapped_column(String(10))

    # Provider
    provider: Mapped[str] = mapped_column(String(50), default="twilio")
    provider_sid: Mapped[Optional[str]] = mapped_column(String(255))

    # Capabilities
    capabilities: Mapped[dict] = mapped_column(
        JSON, default={"voice": True, "sms": True}
    )

    # Status
    status: Mapped[str] = mapped_column(String(50), default="active")
    monthly_cost: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    user: Mapped["User"] = relationship("User")
    organization: Mapped["Organization"] = relationship("Organization")
    agent: Mapped[Optional["Agent"]] = relationship("Agent", back_populates="phone_numbers")
    calls: Mapped[List["Call"]] = relationship("Call", back_populates="phone_number")

    def __repr__(self) -> str:
        return f"<PhoneNumber(id={self.id}, number={self.phone_number})>"


class Call(Base):
    """Call record model."""

    __tablename__ = "calls"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    agent_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("agents.id")
    )
    squad_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("squads.id")
    )
    phone_number_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("phone_numbers.id")
    )

    # Call Details
    direction: Mapped[str] = mapped_column(String(20), nullable=False)  # inbound, outbound
    from_number: Mapped[str] = mapped_column(String(50), nullable=False)
    to_number: Mapped[str] = mapped_column(String(50), nullable=False)

    # Call Status
    status: Mapped[str] = mapped_column(String(50), default="initiated")

    # Timing
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    answered_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    duration_seconds: Mapped[Optional[int]] = mapped_column(Integer)
    billable_duration_seconds: Mapped[Optional[int]] = mapped_column(Integer)

    # Media
    recording_url: Mapped[Optional[str]] = mapped_column(Text)
    recording_duration: Mapped[Optional[int]] = mapped_column(Integer)

    # Transcript
    transcript: Mapped[Optional[str]] = mapped_column(Text)
    transcript_json: Mapped[Optional[dict]] = mapped_column(JSON)

    # Conversation summary (AI-generated recap of the call)
    summary: Mapped[Optional[str]] = mapped_column(Text)

    # Analysis
    sentiment_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(3, 2))
    sentiment_label: Mapped[Optional[str]] = mapped_column(String(50))
    emotions: Mapped[Optional[dict]] = mapped_column(JSON)
    intent: Mapped[Optional[str]] = mapped_column(String(255))
    topics: Mapped[List[str]] = mapped_column(JSON, default=list)

    # Costs
    cost_stt: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4))
    cost_llm: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4))
    cost_tts: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4))
    cost_telephony: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4))
    cost_total: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4))

    # Provider Details
    provider: Mapped[Optional[str]] = mapped_column(String(50))
    provider_call_sid: Mapped[Optional[str]] = mapped_column(String(255), unique=True)

    # Metadata
    call_metadata: Mapped[dict] = mapped_column(JSON, default=dict)
    tags: Mapped[List[str]] = mapped_column(JSON, default=list)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="calls")
    organization: Mapped["Organization"] = relationship("Organization", back_populates="calls")
    agent: Mapped[Optional["Agent"]] = relationship("Agent", back_populates="calls")
    squad: Mapped[Optional["Squad"]] = relationship("Squad")
    phone_number: Mapped[Optional["PhoneNumber"]] = relationship("PhoneNumber", back_populates="calls")
    logs: Mapped[List["CallLog"]] = relationship(
        "CallLog", back_populates="call", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Call(id={self.id}, status={self.status})>"


class CallLog(Base):
    """Call log for detailed event tracking."""

    __tablename__ = "call_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    call_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("calls.id", ondelete="CASCADE"), nullable=False, index=True
    )

    log_type: Mapped[str] = mapped_column(String(50), nullable=False)  # stt, llm, tts, function, etc.
    severity: Mapped[str] = mapped_column(String(20), default="info")  # debug, info, warning, error
    message: Mapped[str] = mapped_column(Text, nullable=False)
    details: Mapped[dict] = mapped_column(JSON, default=dict)

    # Performance tracking
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer)
    cost: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4))

    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    # Relationships
    call: Mapped["Call"] = relationship("Call", back_populates="logs")

    def __repr__(self) -> str:
        return f"<CallLog(id={self.id}, type={self.log_type})>"


# Forward references
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.user import User, Organization
    from app.models.agent import Agent, Squad
