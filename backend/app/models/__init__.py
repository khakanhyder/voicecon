"""
SQLAlchemy models for Voicecon.
"""
from app.database import Base

# Import all models here for Alembic auto-generation
from app.models.user import User, Organization, OrganizationMember, ApiKey
from app.models.company import CompanyProfile
from app.models.agent import Agent, AgentFunction, Squad, SquadMember, KnowledgeBaseDocument, AgentFlow
from app.models.call import PhoneNumber, Call, CallLog
from app.models.integration import IntegrationConnector, IntegrationConnection, Workflow, WorkflowExecution, IntegrationChange
from app.models.analytics import (
    CallMetrics, AgentMetrics, IntegrationMetrics,
    DailySummary, RealTimeMetrics, MetricsCache
)
from app.models.knowledge_base import (
    KnowledgeBase, Document, DocumentChunk, DocumentFile,
    AgentKnowledgeBase, SearchQuery
)
from app.models.subscription import (
    SubscriptionPlan, Subscription, UsageRecord,
    Invoice, PaymentFailure, SubscriptionEvent, ProcessedStripeEvent,
    TrialGrant, OrganizationEntitlementOverride
)
from app.models.template import (
    AgentTemplate, WorkflowTemplate, TemplateInstallation,
    TemplateReview, TemplateVersion
)
from app.models.chat import ChatWidget, ChatSession, ChatMessage
from app.models.invitation import Invitation
from app.models.notification import Notification
from app.models.verification import VerificationCode
from app.models.platform import PlatformSetting, AdminAuditLog
from app.models.voice import CustomVoice
from app.models.wallet import Wallet, WalletTransaction
from app.models.affiliate import (
    AffiliateProgram, Affiliate, AffiliateApplication, AffiliateClick, AffiliateReferral,
    AffiliateCommission, AffiliatePayout,
)

__all__ = [
    "Base",
    # Prepaid wallet (Pay As You Go)
    "Wallet",
    "WalletTransaction",
    # Chat widget models
    "ChatWidget",
    "ChatSession",
    "ChatMessage",
    # Team invitations & notifications
    "Invitation",
    # Platform administration
    "PlatformSetting",
    "AdminAuditLog",
    # Affiliate program
    "AffiliateProgram",
    "Affiliate",
    "AffiliateApplication",
    "AffiliateClick",
    "AffiliateReferral",
    "AffiliateCommission",
    "AffiliatePayout",
    "Notification",
    # User models
    "User",
    "Organization",
    "OrganizationMember",
    "ApiKey",
    "CompanyProfile",
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
    "IntegrationChange",
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
    "DocumentFile",
    "AgentKnowledgeBase",
    "SearchQuery",
    # Subscription models
    "SubscriptionPlan",
    "Subscription",
    "UsageRecord",
    "Invoice",
    "PaymentFailure",
    "SubscriptionEvent",
    "ProcessedStripeEvent",
    "TrialGrant",
    "OrganizationEntitlementOverride",
    # Template models
    "AgentTemplate",
    "WorkflowTemplate",
    "TemplateInstallation",
    "TemplateReview",
    "TemplateVersion",
    # Auth
    "VerificationCode",
    # Voice library
    "CustomVoice",
]
