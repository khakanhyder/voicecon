"""
Analytics and metrics models.
"""
import uuid
from datetime import datetime, date
from typing import Optional
from decimal import Decimal
from sqlalchemy import (
    Boolean, Column, DateTime, String, Text, ForeignKey, Integer,
    JSON, Numeric, Date, Index, func
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, Mapped, mapped_column

from app.database import Base


class CallMetrics(Base):
    """
    Pre-aggregated call metrics for performance.
    Aggregated hourly and daily for faster queries.
    """

    __tablename__ = "call_metrics"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    agent_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE")
    )

    # Time dimension
    metric_date: Mapped[date] = mapped_column(Date, nullable=False)
    metric_hour: Mapped[Optional[int]] = mapped_column(Integer)  # 0-23, null for daily
    granularity: Mapped[str] = mapped_column(String(20), default="daily")  # hourly, daily

    # Call volume metrics
    total_calls: Mapped[int] = mapped_column(Integer, default=0)
    completed_calls: Mapped[int] = mapped_column(Integer, default=0)
    failed_calls: Mapped[int] = mapped_column(Integer, default=0)
    missed_calls: Mapped[int] = mapped_column(Integer, default=0)

    # Duration metrics (in seconds)
    total_duration: Mapped[int] = mapped_column(Integer, default=0)
    avg_duration: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))
    max_duration: Mapped[Optional[int]] = mapped_column(Integer)
    min_duration: Mapped[Optional[int]] = mapped_column(Integer)

    # Cost metrics
    total_cost: Mapped[Decimal] = mapped_column(Numeric(10, 4), default=0)
    avg_cost_per_call: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4))

    # Quality metrics
    avg_sentiment_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(3, 2))
    positive_sentiment_count: Mapped[int] = mapped_column(Integer, default=0)
    negative_sentiment_count: Mapped[int] = mapped_column(Integer, default=0)
    neutral_sentiment_count: Mapped[int] = mapped_column(Integer, default=0)

    # Success metrics
    success_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))  # percentage

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Indexes for fast queries
    __table_args__ = (
        Index('idx_call_metrics_org_date', 'organization_id', 'metric_date'),
        Index('idx_call_metrics_agent_date', 'agent_id', 'metric_date'),
        Index('idx_call_metrics_granularity', 'granularity', 'metric_date'),
    )


class AgentMetrics(Base):
    """
    Pre-aggregated agent performance metrics.
    """

    __tablename__ = "agent_metrics"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False
    )

    # Time dimension
    metric_date: Mapped[date] = mapped_column(Date, nullable=False)
    granularity: Mapped[str] = mapped_column(String(20), default="daily")

    # Performance metrics
    total_interactions: Mapped[int] = mapped_column(Integer, default=0)
    successful_interactions: Mapped[int] = mapped_column(Integer, default=0)
    failed_interactions: Mapped[int] = mapped_column(Integer, default=0)

    # Response quality
    avg_response_time: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))  # ms
    avg_confidence_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(3, 2))

    # Function calling metrics
    total_function_calls: Mapped[int] = mapped_column(Integer, default=0)
    successful_function_calls: Mapped[int] = mapped_column(Integer, default=0)
    failed_function_calls: Mapped[int] = mapped_column(Integer, default=0)
    function_success_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))

    # Sentiment analysis
    avg_sentiment_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(3, 2))
    positive_sentiment_percentage: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))

    # User satisfaction
    avg_user_rating: Mapped[Optional[Decimal]] = mapped_column(Numeric(3, 2))
    total_ratings: Mapped[int] = mapped_column(Integer, default=0)

    # Cost efficiency
    cost_per_interaction: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4))
    total_cost: Mapped[Decimal] = mapped_column(Numeric(10, 4), default=0)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    agent = relationship("Agent", back_populates="metrics")

    # Indexes
    __table_args__ = (
        Index('idx_agent_metrics_org_date', 'organization_id', 'metric_date'),
        Index('idx_agent_metrics_agent_date', 'agent_id', 'metric_date'),
    )


class IntegrationMetrics(Base):
    """
    Integration usage and health metrics.
    """

    __tablename__ = "integration_metrics"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    integration_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("integrations.id", ondelete="CASCADE"), nullable=False
    )

    # Time dimension
    metric_date: Mapped[date] = mapped_column(Date, nullable=False)
    granularity: Mapped[str] = mapped_column(String(20), default="daily")

    # Workflow execution metrics
    total_workflows_executed: Mapped[int] = mapped_column(Integer, default=0)
    successful_workflows: Mapped[int] = mapped_column(Integer, default=0)
    failed_workflows: Mapped[int] = mapped_column(Integer, default=0)
    workflow_success_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))

    # API usage metrics
    total_api_calls: Mapped[int] = mapped_column(Integer, default=0)
    successful_api_calls: Mapped[int] = mapped_column(Integer, default=0)
    failed_api_calls: Mapped[int] = mapped_column(Integer, default=0)
    api_success_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))

    # Performance metrics
    avg_response_time: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))  # ms
    max_response_time: Mapped[Optional[int]] = mapped_column(Integer)
    min_response_time: Mapped[Optional[int]] = mapped_column(Integer)

    # Error tracking
    error_count: Mapped[int] = mapped_column(Integer, default=0)
    timeout_count: Mapped[int] = mapped_column(Integer, default=0)
    rate_limit_count: Mapped[int] = mapped_column(Integer, default=0)

    # Health score (0-100)
    health_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))

    # Data volume
    data_synced_count: Mapped[int] = mapped_column(Integer, default=0)
    data_sync_errors: Mapped[int] = mapped_column(Integer, default=0)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    integration = relationship("Integration", back_populates="metrics")

    # Indexes
    __table_args__ = (
        Index('idx_integration_metrics_org_date', 'organization_id', 'metric_date'),
        Index('idx_integration_metrics_integration_date', 'integration_id', 'metric_date'),
    )


class DailySummary(Base):
    """
    Daily summary aggregating all metrics for quick dashboard loading.
    """

    __tablename__ = "daily_summaries"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )

    # Date
    summary_date: Mapped[date] = mapped_column(Date, nullable=False, unique=True)

    # Overall call metrics
    total_calls: Mapped[int] = mapped_column(Integer, default=0)
    total_call_minutes: Mapped[int] = mapped_column(Integer, default=0)
    total_call_cost: Mapped[Decimal] = mapped_column(Numeric(10, 4), default=0)

    # Agent metrics
    active_agents_count: Mapped[int] = mapped_column(Integer, default=0)
    total_agent_interactions: Mapped[int] = mapped_column(Integer, default=0)
    avg_agent_performance: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))

    # Integration metrics
    active_integrations_count: Mapped[int] = mapped_column(Integer, default=0)
    total_workflow_executions: Mapped[int] = mapped_column(Integer, default=0)
    avg_integration_health: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))

    # Quality metrics
    avg_sentiment_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(3, 2))
    avg_user_rating: Mapped[Optional[Decimal]] = mapped_column(Numeric(3, 2))

    # Success rates
    call_success_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    workflow_success_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))

    # Top performers (JSON)
    top_agents: Mapped[dict] = mapped_column(JSON, default=list)
    top_integrations: Mapped[dict] = mapped_column(JSON, default=list)

    # Trend data (compared to previous day)
    call_volume_change: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))  # percentage
    cost_change: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    sentiment_change: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Indexes
    __table_args__ = (
        Index('idx_daily_summary_org_date', 'organization_id', 'summary_date'),
    )


class RealTimeMetrics(Base):
    """
    Real-time metrics cache for current day.
    Updated every minute for live dashboards.
    """

    __tablename__ = "realtime_metrics"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )

    # Current metrics (updated every minute)
    current_active_calls: Mapped[int] = mapped_column(Integer, default=0)
    calls_today: Mapped[int] = mapped_column(Integer, default=0)
    calls_last_hour: Mapped[int] = mapped_column(Integer, default=0)
    calls_last_5_minutes: Mapped[int] = mapped_column(Integer, default=0)

    # Cost tracking
    cost_today: Mapped[Decimal] = mapped_column(Numeric(10, 4), default=0)
    cost_last_hour: Mapped[Decimal] = mapped_column(Numeric(10, 4), default=0)

    # Performance
    avg_response_time_last_hour: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))
    current_system_load: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))  # 0-100

    # Active resources
    active_agents: Mapped[int] = mapped_column(Integer, default=0)
    active_integrations: Mapped[int] = mapped_column(Integer, default=0)
    active_workflows: Mapped[int] = mapped_column(Integer, default=0)

    # Health indicators
    system_health: Mapped[str] = mapped_column(String(20), default="healthy")  # healthy, degraded, down
    error_rate_last_hour: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))

    # Recent activity (JSON arrays)
    recent_calls: Mapped[dict] = mapped_column(JSON, default=list)  # last 10 calls
    recent_errors: Mapped[dict] = mapped_column(JSON, default=list)  # last 10 errors

    # Timestamps
    last_updated: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Indexes
    __table_args__ = (
        Index('idx_realtime_metrics_org', 'organization_id'),
    )


class MetricsCache(Base):
    """
    Cache for frequently accessed metric calculations.
    """

    __tablename__ = "metrics_cache"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )

    # Cache key (e.g., "calls_last_30_days", "agent_performance_week")
    cache_key: Mapped[str] = mapped_column(String(255), nullable=False)

    # Cached data
    data: Mapped[dict] = mapped_column(JSON, nullable=False)

    # Cache metadata
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    hit_count: Mapped[int] = mapped_column(Integer, default=0)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Indexes
    __table_args__ = (
        Index('idx_metrics_cache_org_key', 'organization_id', 'cache_key'),
        Index('idx_metrics_cache_expires', 'expires_at'),
    )
