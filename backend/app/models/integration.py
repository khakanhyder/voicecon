"""
Integration and workflow models.
"""
import uuid
from datetime import datetime
from typing import List, Optional
from decimal import Decimal
from sqlalchemy import Boolean, Column, DateTime, String, Text, ForeignKey, Integer, ARRAY, JSON, Numeric, Date
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, Mapped, mapped_column

from app.database import Base


class IntegrationConnector(Base):
    """Available integration connectors (e.g., Salesforce, HubSpot)."""

    __tablename__ = "integration_connectors"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    category: Mapped[Optional[str]] = mapped_column(String(100))  # crm, marketing, calendar, etc.
    description: Mapped[Optional[str]] = mapped_column(Text)
    logo_url: Mapped[Optional[str]] = mapped_column(Text)

    # API Configuration
    base_url: Mapped[Optional[str]] = mapped_column(Text)
    api_version: Mapped[Optional[str]] = mapped_column(String(50))
    auth_type: Mapped[str] = mapped_column(String(50), nullable=False)  # oauth2, api_key, basic, jwt
    auth_config: Mapped[dict] = mapped_column(JSON, default=dict)

    # Capabilities
    supports_triggers: Mapped[bool] = mapped_column(Boolean, default=False)
    supports_actions: Mapped[bool] = mapped_column(Boolean, default=True)
    supports_realtime: Mapped[bool] = mapped_column(Boolean, default=False)
    supports_webhooks: Mapped[bool] = mapped_column(Boolean, default=False)

    # Rate Limiting
    rate_limit_per_minute: Mapped[Optional[int]] = mapped_column(Integer)
    rate_limit_per_hour: Mapped[Optional[int]] = mapped_column(Integer)
    rate_limit_per_day: Mapped[Optional[int]] = mapped_column(Integer)

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_beta: Mapped[bool] = mapped_column(Boolean, default=False)
    is_premium: Mapped[bool] = mapped_column(Boolean, default=False)

    # Documentation
    documentation_url: Mapped[Optional[str]] = mapped_column(Text)
    setup_instructions: Mapped[Optional[str]] = mapped_column(Text)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    connections: Mapped[List["IntegrationConnection"]] = relationship(
        "IntegrationConnection", back_populates="connector", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<IntegrationConnector(id={self.id}, slug={self.slug})>"


class IntegrationConnection(Base):
    """User's connected integration account."""

    __tablename__ = "integration_connections"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    connector_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("integration_connectors.id", ondelete="CASCADE"), nullable=False, index=True
    )

    name: Mapped[Optional[str]] = mapped_column(String(255))  # User-given name

    # Authentication (encrypted)
    auth_data_encrypted: Mapped[Optional[str]] = mapped_column(Text)
    access_token_encrypted: Mapped[Optional[str]] = mapped_column(Text)
    refresh_token_encrypted: Mapped[Optional[str]] = mapped_column(Text)
    token_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # Configuration
    config: Mapped[dict] = mapped_column(JSON, default=dict)

    # Status
    status: Mapped[str] = mapped_column(String(50), default="active", index=True)
    last_sync_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    last_error: Mapped[Optional[str]] = mapped_column(Text)
    error_count: Mapped[int] = mapped_column(Integer, default=0)

    # Metadata
    metadata: Mapped[dict] = mapped_column(JSON, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    user: Mapped["User"] = relationship("User")
    organization: Mapped["Organization"] = relationship("Organization")
    connector: Mapped["IntegrationConnector"] = relationship(
        "IntegrationConnector", back_populates="connections"
    )

    def __repr__(self) -> str:
        return f"<IntegrationConnection(id={self.id}, connector={self.connector_id})>"


class Workflow(Base):
    """Workflow automation model."""

    __tablename__ = "workflows"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)

    # Trigger Configuration
    trigger_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    trigger_config: Mapped[dict] = mapped_column(JSON, nullable=False)

    # Workflow Definition
    workflow_steps: Mapped[dict] = mapped_column(JSON, nullable=False)

    # Settings
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    execution_mode: Mapped[str] = mapped_column(String(50), default="async")
    error_handling: Mapped[str] = mapped_column(String(50), default="continue")
    max_retries: Mapped[int] = mapped_column(Integer, default=3)
    retry_delay: Mapped[int] = mapped_column(Integer, default=60)

    # Execution Stats
    total_executions: Mapped[int] = mapped_column(Integer, default=0)
    successful_executions: Mapped[int] = mapped_column(Integer, default=0)
    failed_executions: Mapped[int] = mapped_column(Integer, default=0)
    last_executed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # Versioning
    version: Mapped[int] = mapped_column(Integer, default=1)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Relationships
    user: Mapped["User"] = relationship("User")
    organization: Mapped["Organization"] = relationship("Organization")
    executions: Mapped[List["WorkflowExecution"]] = relationship(
        "WorkflowExecution", back_populates="workflow", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Workflow(id={self.id}, name={self.name})>"


class WorkflowExecution(Base):
    """Workflow execution history."""

    __tablename__ = "workflow_executions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    workflow_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False, index=True
    )

    trigger_data: Mapped[Optional[dict]] = mapped_column(JSON)

    # Execution Details
    status: Mapped[str] = mapped_column(String(50), default="running", index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer)

    # Results
    steps_executed: Mapped[int] = mapped_column(Integer, default=0)
    steps_successful: Mapped[int] = mapped_column(Integer, default=0)
    steps_failed: Mapped[int] = mapped_column(Integer, default=0)

    result_data: Mapped[Optional[dict]] = mapped_column(JSON)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    error_details: Mapped[Optional[dict]] = mapped_column(JSON)

    # Cost tracking
    cost: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4))

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    workflow: Mapped["Workflow"] = relationship("Workflow", back_populates="executions")

    def __repr__(self) -> str:
        return f"<WorkflowExecution(id={self.id}, status={self.status})>"


class IntegrationLog(Base):
    """Integration API call logs."""

    __tablename__ = "integration_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    connection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("integration_connections.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Request details
    method: Mapped[str] = mapped_column(String(10), nullable=False)
    endpoint: Mapped[str] = mapped_column(Text, nullable=False)
    request_headers: Mapped[Optional[dict]] = mapped_column(JSON)
    request_body: Mapped[Optional[dict]] = mapped_column(JSON)

    # Response details
    status_code: Mapped[Optional[int]] = mapped_column(Integer)
    response_body: Mapped[Optional[dict]] = mapped_column(JSON)
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer)

    # Status
    success: Mapped[bool] = mapped_column(Boolean, default=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    def __repr__(self) -> str:
        return f"<IntegrationLog(id={self.id}, method={self.method}, success={self.success})>"


# Forward references
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.user import User, Organization
