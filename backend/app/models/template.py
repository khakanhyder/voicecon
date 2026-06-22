"""
Template marketplace models for agents and workflows.
"""

from datetime import datetime
from typing import Optional
import uuid

from sqlalchemy import String, Integer, Text, ForeignKey, DateTime, Boolean, Numeric, Index, JSON, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class AgentTemplate(Base):
    """Pre-built agent templates for the marketplace."""
    __tablename__ = "agent_templates"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # Basic Information
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    long_description: Mapped[Optional[str]] = mapped_column(Text)

    # Categorization
    category: Mapped[str] = mapped_column(String(100), nullable=False)  # customer_support, sales, etc.
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)

    # Template Configuration
    version: Mapped[str] = mapped_column(String(50), nullable=False, default="1.0.0")
    agent_config: Mapped[dict] = mapped_column(JSON, nullable=False)  # Agent configuration
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    first_message: Mapped[Optional[str]] = mapped_column(Text)
    functions: Mapped[Optional[list]] = mapped_column(JSON)  # Pre-configured functions

    # Visual Assets
    icon: Mapped[Optional[str]] = mapped_column(String(500))  # Icon URL or emoji
    banner_image: Mapped[Optional[str]] = mapped_column(String(500))
    screenshots: Mapped[Optional[list]] = mapped_column(JSON)  # Array of screenshot URLs

    # Author Information
    author_name: Mapped[str] = mapped_column(String(255), nullable=False)
    author_organization: Mapped[Optional[str]] = mapped_column(String(255))
    is_official: Mapped[bool] = mapped_column(Boolean, default=False)  # Official Voicecon template

    # Publishing
    status: Mapped[str] = mapped_column(String(50), default="draft")  # draft, published, archived
    is_featured: Mapped[bool] = mapped_column(Boolean, default=False)
    is_free: Mapped[bool] = mapped_column(Boolean, default=True)
    price: Mapped[Optional[float]] = mapped_column(Numeric(10, 2))

    # Statistics
    install_count: Mapped[int] = mapped_column(Integer, default=0)
    average_rating: Mapped[float] = mapped_column(Numeric(3, 2), default=0.0)
    review_count: Mapped[int] = mapped_column(Integer, default=0)

    # Customization Options
    customizable_fields: Mapped[Optional[list]] = mapped_column(JSON)  # Fields users can customize
    required_integrations: Mapped[Optional[list[str]]] = mapped_column(JSON)  # Required integration types

    # Documentation
    setup_guide: Mapped[Optional[str]] = mapped_column(Text)  # Markdown setup instructions
    use_cases: Mapped[Optional[list]] = mapped_column(JSON)  # Example use cases
    demo_url: Mapped[Optional[str]] = mapped_column(String(500))

    # Metadata
    template_metadata: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)

    # Timestamps
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    installations: Mapped[list["TemplateInstallation"]] = relationship(
        "TemplateInstallation", back_populates="agent_template", cascade="all, delete-orphan"
    )
    reviews: Mapped[list["TemplateReview"]] = relationship(
        "TemplateReview", back_populates="agent_template", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<AgentTemplate {self.name} v{self.version}>"


class WorkflowTemplate(Base):
    """Pre-built workflow templates for the marketplace."""
    __tablename__ = "workflow_templates"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # Basic Information
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    long_description: Mapped[Optional[str]] = mapped_column(Text)

    # Categorization
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)

    # Workflow Configuration
    version: Mapped[str] = mapped_column(String(50), nullable=False, default="1.0.0")
    workflow_definition: Mapped[dict] = mapped_column(JSON, nullable=False)  # Complete workflow
    trigger_config: Mapped[dict] = mapped_column(JSON, nullable=False)  # Trigger configuration

    # Visual Assets
    icon: Mapped[Optional[str]] = mapped_column(String(500))
    banner_image: Mapped[Optional[str]] = mapped_column(String(500))
    screenshots: Mapped[Optional[list]] = mapped_column(JSON)

    # Author Information
    author_name: Mapped[str] = mapped_column(String(255), nullable=False)
    author_organization: Mapped[Optional[str]] = mapped_column(String(255))
    is_official: Mapped[bool] = mapped_column(Boolean, default=False)

    # Publishing
    status: Mapped[str] = mapped_column(String(50), default="draft")
    is_featured: Mapped[bool] = mapped_column(Boolean, default=False)
    is_free: Mapped[bool] = mapped_column(Boolean, default=True)
    price: Mapped[Optional[float]] = mapped_column(Numeric(10, 2))

    # Statistics
    install_count: Mapped[int] = mapped_column(Integer, default=0)
    average_rating: Mapped[float] = mapped_column(Numeric(3, 2), default=0.0)
    review_count: Mapped[int] = mapped_column(Integer, default=0)

    # Requirements
    required_integrations: Mapped[Optional[list[str]]] = mapped_column(JSON)
    compatible_agents: Mapped[Optional[list[str]]] = mapped_column(JSON)  # Agent template slugs

    # Documentation
    setup_guide: Mapped[Optional[str]] = mapped_column(Text)
    use_cases: Mapped[Optional[list]] = mapped_column(JSON)

    # Metadata
    template_metadata: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)

    # Timestamps
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    installations: Mapped[list["TemplateInstallation"]] = relationship(
        "TemplateInstallation", back_populates="workflow_template", cascade="all, delete-orphan"
    )
    reviews: Mapped[list["TemplateReview"]] = relationship(
        "TemplateReview", back_populates="workflow_template", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<WorkflowTemplate {self.name} v{self.version}>"


class TemplateInstallation(Base):
    """Track template installations by users."""
    __tablename__ = "template_installations"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("organizations.id"), nullable=False
    )

    # Template References (one of these will be set)
    agent_template_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("agent_templates.id")
    )
    workflow_template_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("workflow_templates.id")
    )

    # Installation Details
    installed_version: Mapped[str] = mapped_column(String(50), nullable=False)
    customizations: Mapped[Optional[dict]] = mapped_column(JSON)  # User customizations

    # Created Resources
    created_agent_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("agents.id")
    )
    created_workflow_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("workflows.id")
    )

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    uninstalled_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # Metadata
    installation_metadata: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)

    # Timestamps
    installed_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    # Relationships
    agent_template: Mapped[Optional["AgentTemplate"]] = relationship(
        "AgentTemplate", back_populates="installations"
    )
    workflow_template: Mapped[Optional["WorkflowTemplate"]] = relationship(
        "WorkflowTemplate", back_populates="installations"
    )

    def __repr__(self):
        template_type = "Agent" if self.agent_template_id else "Workflow"
        return f"<TemplateInstallation {template_type} for org {self.organization_id}>"


class TemplateReview(Base):
    """User reviews and ratings for templates."""
    __tablename__ = "template_reviews"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("organizations.id"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False
    )

    # Template References (one of these will be set)
    agent_template_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("agent_templates.id")
    )
    workflow_template_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("workflow_templates.id")
    )

    # Review Content
    rating: Mapped[int] = mapped_column(Integer, nullable=False)  # 1-5 stars
    title: Mapped[Optional[str]] = mapped_column(String(255))
    review_text: Mapped[Optional[str]] = mapped_column(Text)

    # Review Metadata
    verified_installation: Mapped[bool] = mapped_column(Boolean, default=False)  # User actually installed it
    helpful_count: Mapped[int] = mapped_column(Integer, default=0)  # Number of users who found helpful

    # Moderation
    is_approved: Mapped[bool] = mapped_column(Boolean, default=True)
    is_flagged: Mapped[bool] = mapped_column(Boolean, default=False)
    moderation_notes: Mapped[Optional[str]] = mapped_column(Text)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    agent_template: Mapped[Optional["AgentTemplate"]] = relationship(
        "AgentTemplate", back_populates="reviews"
    )
    workflow_template: Mapped[Optional["WorkflowTemplate"]] = relationship(
        "WorkflowTemplate", back_populates="reviews"
    )

    def __repr__(self):
        return f"<TemplateReview {self.rating}★ by user {self.user_id}>"


class TemplateVersion(Base):
    """Version history for templates."""
    __tablename__ = "template_versions"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # Template References (one of these will be set)
    agent_template_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("agent_templates.id")
    )
    workflow_template_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("workflow_templates.id")
    )

    # Version Information
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    changelog: Mapped[str] = mapped_column(Text, nullable=False)

    # Configuration Snapshot
    config_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)

    # Release Information
    is_breaking_change: Mapped[bool] = mapped_column(Boolean, default=False)
    migration_guide: Mapped[Optional[str]] = mapped_column(Text)

    # Timestamps
    released_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    def __repr__(self):
        return f"<TemplateVersion {self.version}>"


# Indexes for performance
Index("idx_agent_template_category", AgentTemplate.category)
Index("idx_agent_template_status", AgentTemplate.status)
Index("idx_agent_template_featured", AgentTemplate.is_featured)
Index("idx_agent_template_slug", AgentTemplate.slug)

Index("idx_workflow_template_category", WorkflowTemplate.category)
Index("idx_workflow_template_status", WorkflowTemplate.status)
Index("idx_workflow_template_slug", WorkflowTemplate.slug)

Index("idx_installation_org", TemplateInstallation.organization_id)
Index("idx_installation_agent", TemplateInstallation.agent_template_id)
Index("idx_installation_workflow", TemplateInstallation.workflow_template_id)

Index("idx_review_agent", TemplateReview.agent_template_id)
Index("idx_review_workflow", TemplateReview.workflow_template_id)
Index("idx_review_user", TemplateReview.user_id)
Index("idx_review_approved", TemplateReview.is_approved)

Index("idx_version_agent", TemplateVersion.agent_template_id)
Index("idx_version_workflow", TemplateVersion.workflow_template_id)
