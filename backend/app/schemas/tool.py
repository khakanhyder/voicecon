"""Tool Pydantic schemas."""
from typing import Optional, Dict, Any, List
from datetime import datetime
from pydantic import BaseModel, Field


class ToolCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    tool_type: str = Field(..., description=(
        "phone_call: transfer_call | hang_up | leave_voicemail | dtmf | send_sms | sip_request | "
        "assistant: handoff | query_knowledge_base | "
        "integration: api_request | mcp | slack | google_sheets | google_calendar"
    ))
    category: str = Field(default="integration")
    config: Dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True


class ToolUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None


class ToolResponse(BaseModel):
    id: str
    user_id: str
    organization_id: str
    name: str
    description: Optional[str]
    tool_type: str
    category: str
    config: Dict[str, Any]
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ToolListResponse(BaseModel):
    tools: List[ToolResponse]
    total: int


class AgentToolAssignmentResponse(BaseModel):
    id: str
    agent_id: str
    tool_id: str
    tool: ToolResponse
    created_at: datetime

    class Config:
        from_attributes = True


class ToolTestRequest(BaseModel):
    parameters: Dict[str, Any] = Field(default_factory=dict)


class ToolTestResponse(BaseModel):
    success: bool
    message: str
    response: Optional[Dict[str, Any]] = None
    response_time_ms: int = 0
