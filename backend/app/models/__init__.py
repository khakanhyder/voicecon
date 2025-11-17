"""
SQLAlchemy models for Voicecon.
"""
from app.database import Base

# Import all models here for Alembic auto-generation
from app.models.user import User, Organization, OrganizationMember, ApiKey
from app.models.agent import Agent, AgentFunction, Squad, SquadMember, KnowledgeBaseDocument, AgentFlow
from app.models.call import PhoneNumber, Call, CallLog
from app.models.integration import IntegrationConnector, IntegrationConnection, Workflow, WorkflowExecution
from app.models.analytics import (
    CallMetrics, AgentMetrics, IntegrationMetrics,
    DailySummary, RealTimeMetrics, MetricsCache
)

__all__ = [
    "Base",
    # User models
    "User",
    "Organization",
    "OrganizationMember",
    "ApiKey",
    # Agent models
    "Agent",
    "AgentFunction",
    "Squad",
    "SquadMember",
    "KnowledgeBaseDocument",
    "AgentFlow",
    # Call models
    "PhoneNumber",
    "Call",
    "CallLog",
    # Integration models
    "IntegrationConnector",
    "IntegrationConnection",
    "Workflow",
    "WorkflowExecution",
    # Analytics models
    "CallMetrics",
    "AgentMetrics",
    "IntegrationMetrics",
    "DailySummary",
    "RealTimeMetrics",
    "MetricsCache",
]
