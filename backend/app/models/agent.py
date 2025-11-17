"""
Agent and related models for voice AI configuration.
"""
import uuid
from datetime import datetime
from typing import List, Optional
from decimal import Decimal
from sqlalchemy import Boolean, Column, DateTime, String, Text, ForeignKey, Integer, ARRAY, JSON, Numeric
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, Mapped, mapped_column
from pgvector.sqlalchemy import Vector

from app.database import Base


class Agent(Base):
    """AI Voice Agent model."""

    __tablename__ = "agents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    type: Mapped[str] = mapped_column(String(50), default="assistant")  # assistant, squad

    # System Configuration
    system_prompt: Mapped[Optional[str]] = mapped_column(Text)
    first_message: Mapped[Optional[str]] = mapped_column(Text)

    # LLM Configuration
    llm_provider: Mapped[str] = mapped_column(String(50), default="openai")
    llm_model: Mapped[str] = mapped_column(String(100), default="gpt-4")
    llm_temperature: Mapped[Decimal] = mapped_column(Numeric(3, 2), default=Decimal("0.7"))
    llm_max_tokens: Mapped[int] = mapped_column(Integer, default=1000)
    llm_api_key_encrypted: Mapped[Optional[str]] = mapped_column(Text)

    # Voice Configuration (TTS)
    tts_provider: Mapped[str] = mapped_column(String(50), default="elevenlabs")
    tts_voice_id: Mapped[Optional[str]] = mapped_column(String(255))
    tts_speed: Mapped[Decimal] = mapped_column(Numeric(3, 2), default=Decimal("1.0"))
    tts_pitch: Mapped[Decimal] = mapped_column(Numeric(3, 2), default=Decimal("1.0"))
    tts_api_key_encrypted: Mapped[Optional[str]] = mapped_column(Text)

    # Speech Recognition (STT)
    stt_provider: Mapped[str] = mapped_column(String(50), default="deepgram")
    stt_language: Mapped[str] = mapped_column(String(10), default="en")
    stt_model: Mapped[Optional[str]] = mapped_column(String(100))
    stt_api_key_encrypted: Mapped[Optional[str]] = mapped_column(Text)

    # Conversation Settings
    interrupt_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    interrupt_sensitivity: Mapped[Decimal] = mapped_column(Numeric(3, 2), default=Decimal("0.5"))
    silence_timeout: Mapped[int] = mapped_column(Integer, default=3000)  # milliseconds
    max_call_duration: Mapped[int] = mapped_column(Integer, default=1800)  # seconds
    end_call_phrases: Mapped[List[str]] = mapped_column(ARRAY(Text), default=list)

    # Advanced Features
    sentiment_analysis_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    emotion_detection_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    background_noise_reduction: Mapped[bool] = mapped_column(Boolean, default=True)

    # Knowledge Base
    knowledge_base_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    knowledge_base_config: Mapped[dict] = mapped_column(JSON, default=dict)

    # Metadata
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_public: Mapped[bool] = mapped_column(Boolean, default=False)
    tags: Mapped[List[str]] = mapped_column(ARRAY(Text), default=list)
    version: Mapped[int] = mapped_column(Integer, default=1)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="agents")
    organization: Mapped["Organization"] = relationship("Organization", back_populates="agents")
    functions: Mapped[List["AgentFunction"]] = relationship(
        "AgentFunction", back_populates="agent", cascade="all, delete-orphan"
    )
    flows: Mapped[List["AgentFlow"]] = relationship(
        "AgentFlow", back_populates="agent", cascade="all, delete-orphan"
    )
    knowledge_documents: Mapped[List["KnowledgeBaseDocument"]] = relationship(
        "KnowledgeBaseDocument", back_populates="agent", cascade="all, delete-orphan"
    )
    calls: Mapped[List["Call"]] = relationship(
        "Call", back_populates="agent", cascade="all, delete-orphan"
    )
    phone_numbers: Mapped[List["PhoneNumber"]] = relationship(
        "PhoneNumber", back_populates="agent"
    )

    def __repr__(self) -> str:
        return f"<Agent(id={self.id}, name={self.name})>"


class AgentFunction(Base):
    """Agent function/tool configuration."""

    __tablename__ = "agent_functions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    parameters: Mapped[dict] = mapped_column(JSON, nullable=False)  # JSON Schema

    # Webhook configuration
    webhook_url: Mapped[Optional[str]] = mapped_column(Text)
    http_method: Mapped[str] = mapped_column(String(10), default="POST")
    headers: Mapped[dict] = mapped_column(JSON, default=dict)
    timeout: Mapped[int] = mapped_column(Integer, default=5000)  # milliseconds
    retry_count: Mapped[int] = mapped_column(Integer, default=3)

    # Settings
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    execution_order: Mapped[int] = mapped_column(Integer, default=0)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    agent: Mapped["Agent"] = relationship("Agent", back_populates="functions")

    def __repr__(self) -> str:
        return f"<AgentFunction(id={self.id}, name={self.name})>"


class Squad(Base):
    """Squad model for multi-agent orchestration."""

    __tablename__ = "squads"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    initial_agent_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agents.id")
    )

    # Transfer rules (JSONB for complex logic)
    transfer_rules: Mapped[List[dict]] = mapped_column(JSON, default=list)

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    user: Mapped["User"] = relationship("User")
    organization: Mapped["Organization"] = relationship("Organization")
    initial_agent: Mapped[Optional["Agent"]] = relationship("Agent", foreign_keys=[initial_agent_id])
    members: Mapped[List["SquadMember"]] = relationship(
        "SquadMember", back_populates="squad", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Squad(id={self.id}, name={self.name})>"


class SquadMember(Base):
    """Squad member relationship."""

    __tablename__ = "squad_members"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    squad_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("squads.id", ondelete="CASCADE"), nullable=False
    )
    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False
    )

    role: Mapped[Optional[str]] = mapped_column(String(100))
    transfer_conditions: Mapped[dict] = mapped_column(JSON, default=dict)
    execution_order: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    squad: Mapped["Squad"] = relationship("Squad", back_populates="members")
    agent: Mapped["Agent"] = relationship("Agent")

    def __repr__(self) -> str:
        return f"<SquadMember(squad={self.squad_id}, agent={self.agent_id})>"


class KnowledgeBaseDocument(Base):
    """Knowledge base document with vector embeddings."""

    __tablename__ = "knowledge_base_documents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False
    )

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_type: Mapped[Optional[str]] = mapped_column(String(50))  # text, url, pdf, docx
    source_url: Mapped[Optional[str]] = mapped_column(Text)

    metadata: Mapped[dict] = mapped_column(JSON, default=dict)

    # Vector embedding for similarity search (pgvector)
    embedding_vector = Column(Vector(1536))  # OpenAI embedding dimension

    # Chunking support
    chunk_index: Mapped[Optional[int]] = mapped_column(Integer)
    parent_document_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("knowledge_base_documents.id")
    )

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    agent: Mapped["Agent"] = relationship("Agent", back_populates="knowledge_documents")
    parent: Mapped[Optional["KnowledgeBaseDocument"]] = relationship(
        "KnowledgeBaseDocument", remote_side=[id]
    )

    def __repr__(self) -> str:
        return f"<KnowledgeBaseDocument(id={self.id}, title={self.title})>"


class AgentFlow(Base):
    """Agent flow configuration (visual flow builder)."""

    __tablename__ = "agent_flows"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    flow_data: Mapped[dict] = mapped_column(JSON, nullable=False)  # Complete flow configuration

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    version: Mapped[int] = mapped_column(Integer, default=1)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    agent: Mapped["Agent"] = relationship("Agent", back_populates="flows")

    def __repr__(self) -> str:
        return f"<AgentFlow(id={self.id}, name={self.name})>"


# Forward references
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.user import User, Organization
    from app.models.call import Call, PhoneNumber
