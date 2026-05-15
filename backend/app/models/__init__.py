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
from app.models.knowledge_base import (
    KnowledgeBase, Document, DocumentChunk,
    AgentKnowledgeBase, SearchQuery
)
from app.models.subscription import (
    SubscriptionPlan, Subscription, UsageRecord,
    Invoice, PaymentFailure
)
from app.models.template import (
    AgentTemplate, WorkflowTemplate, TemplateInstallation,
    TemplateReview, TemplateVersion
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
    # Knowledge base models
    "KnowledgeBase",
    "Document",
    "DocumentChunk",
    "AgentKnowledgeBase",
    "SearchQuery",
    # Subscription models
    "SubscriptionPlan",
    "Subscription",
    "UsageRecord",
    "Invoice",
    "PaymentFailure",
    # Template models
    "AgentTemplate",
    "WorkflowTemplate",
    "TemplateInstallation",
    "TemplateReview",
    "TemplateVersion",
]
