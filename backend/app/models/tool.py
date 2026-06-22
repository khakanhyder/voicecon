"""Tool models for the Voicecon platform."""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, Boolean, DateTime, JSON, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from app.database import Base


class Tool(Base):
    __tablename__ = "tools"

    id = Column(String(32), primary_key=True, default=lambda: uuid.uuid4().hex)
    user_id = Column(String(32), nullable=False, index=True)
    organization_id = Column(String(32), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    # Category: phone_call | assistant | integration
    category = Column(String(50), nullable=False, default="integration")
    # Type: transfer_call | hang_up | leave_voicemail | dtmf | send_sms | sip_request |
    #       handoff | query_knowledge_base | api_request | mcp | slack | google_sheets | google_calendar
    tool_type = Column(String(50), nullable=False)
    config = Column(JSON, nullable=False, default=dict)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    agent_assignments = relationship("AgentToolAssignment", back_populates="tool", cascade="all, delete-orphan")


class AgentToolAssignment(Base):
    __tablename__ = "agent_tool_assignments"
    __table_args__ = (UniqueConstraint("agent_id", "tool_id", name="uq_agent_tool"),)

    id = Column(String(32), primary_key=True, default=lambda: uuid.uuid4().hex)
    agent_id = Column(String(32), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True)
    tool_id = Column(String(32), ForeignKey("tools.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    tool = relationship("Tool", back_populates="agent_assignments")
