"""
Tools API endpoints — global tools that agents can invoke during calls.

Tool categories mirror Vapi.ai:
  phone_call  — transfer_call, hang_up, leave_voicemail, dtmf, send_sms, sip_request
  assistant   — handoff, query_knowledge_base
  integration — api_request, mcp, slack, google_sheets, google_calendar
"""
import logging
import uuid
import time
from datetime import datetime
from typing import Optional, List
import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func

from app.database import get_db
from app.core.dependencies import get_current_active_user
from app.models.user import User, OrganizationMember
from app.models.tool import Tool, AgentToolAssignment
from app.schemas.tool import (
    ToolCreate, ToolUpdate, ToolResponse, ToolListResponse,
    AgentToolAssignmentResponse, ToolTestRequest, ToolTestResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter()

TOOL_CATEGORIES = {
    "transfer_call": "phone_call",
    "hang_up": "phone_call",
    "leave_voicemail": "phone_call",
    "dtmf": "phone_call",
    "send_sms": "phone_call",
    "sip_request": "phone_call",
    "handoff": "assistant",
    "query_knowledge_base": "assistant",
    # Runs a workflow. config: {"workflow_id": "...", "filler_message": "..."}
    "workflow": "assistant",
    "api_request": "integration",
    "mcp": "integration",
    "slack": "integration",
    "google_sheets": "integration",
    "google_calendar": "integration",
    "gohighlevel": "integration",
    "custom_tool": "integration",
    "connected_integration": "integration",
    "integration": "integration",
}


# ── CRUD ─────────────────────────────────────────────────────────────────────

@router.post("", response_model=ToolResponse, status_code=status.HTTP_201_CREATED)
async def create_tool(
    data: ToolCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    # Get user's org; fall back to user_id so solo users can still create tools
    org_result = await db.execute(
        select(OrganizationMember).where(OrganizationMember.user_id == current_user.id).limit(1)
    )
    org_member = org_result.scalar_one_or_none()
    org_id = org_member.organization_id.hex if org_member else current_user.id.hex

    # A workflow tool is only useful once it names a workflow — reject early
    # rather than let the agent call a tool that can never do anything.
    if data.tool_type == "workflow" and not (data.config or {}).get("workflow_id"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A workflow tool needs a workflow_id in its config.",
        )

    category = TOOL_CATEGORIES.get(data.tool_type, data.category)
    tool = Tool(
        id=uuid.uuid4().hex,
        user_id=current_user.id.hex,
        organization_id=org_id,
        name=data.name,
        description=data.description,
        tool_type=data.tool_type,
        category=category,
        config=data.config,
        is_active=data.is_active,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(tool)
    await db.commit()
    await db.refresh(tool)
    return tool


@router.get("", response_model=ToolListResponse)
async def list_tools(
    category: Optional[str] = Query(None),
    tool_type: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    q = select(Tool).where(Tool.user_id == current_user.id.hex)
    if category:
        q = q.where(Tool.category == category)
    if tool_type:
        q = q.where(Tool.tool_type == tool_type)
    if search:
        q = q.where(Tool.name.ilike(f"%{search}%"))
    if is_active is not None:
        q = q.where(Tool.is_active == is_active)

    count_q = select(func.count()).select_from(q.subquery())
    total = (await db.execute(count_q)).scalar_one()

    q = q.order_by(Tool.created_at.desc())
    result = await db.execute(q)
    tools = result.scalars().all()
    return ToolListResponse(tools=list(tools), total=total)


@router.get("/{tool_id}", response_model=ToolResponse)
async def get_tool(
    tool_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    tool = await _get_tool_or_404(tool_id, current_user, db)
    return tool


@router.patch("/{tool_id}", response_model=ToolResponse)
async def update_tool(
    tool_id: str,
    data: ToolUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    tool = await _get_tool_or_404(tool_id, current_user, db)
    update = data.model_dump(exclude_unset=True)
    for k, v in update.items():
        setattr(tool, k, v)
    tool.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(tool)
    return tool


@router.delete("/{tool_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tool(
    tool_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    tool = await _get_tool_or_404(tool_id, current_user, db)
    await db.delete(tool)
    await db.commit()


# ── TEST ──────────────────────────────────────────────────────────────────────

@router.post("/{tool_id}/test", response_model=ToolTestResponse)
async def test_tool(
    tool_id: str,
    body: ToolTestRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    tool = await _get_tool_or_404(tool_id, current_user, db)
    start = time.time()

    try:
        result = await _execute_tool(tool, body.parameters)
        ms = int((time.time() - start) * 1000)
        return ToolTestResponse(success=True, message="Tool executed successfully", response=result, response_time_ms=ms)
    except Exception as exc:
        ms = int((time.time() - start) * 1000)
        return ToolTestResponse(success=False, message=str(exc), response_time_ms=ms)


# ── AGENT ASSIGNMENT ──────────────────────────────────────────────────────────

@router.get("/agents/{agent_id}/tools", response_model=List[AgentToolAssignmentResponse])
async def list_agent_tools(
    agent_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    q = select(AgentToolAssignment).where(AgentToolAssignment.agent_id == agent_id)
    result = await db.execute(q)
    assignments = result.scalars().all()
    for a in assignments:
        await db.refresh(a, ["tool"])
    return list(assignments)


@router.post("/agents/{agent_id}/tools/{tool_id}", response_model=AgentToolAssignmentResponse, status_code=status.HTTP_201_CREATED)
async def assign_tool_to_agent(
    agent_id: str,
    tool_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    # verify tool belongs to user
    await _get_tool_or_404(tool_id, current_user, db)

    # check existing
    existing = await db.execute(
        select(AgentToolAssignment).where(
            and_(AgentToolAssignment.agent_id == agent_id, AgentToolAssignment.tool_id == tool_id)
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Tool already assigned to this agent")

    assignment = AgentToolAssignment(
        id=uuid.uuid4().hex,
        agent_id=agent_id,
        tool_id=tool_id,
        created_at=datetime.utcnow(),
    )
    db.add(assignment)
    await db.commit()
    await db.refresh(assignment, ["tool"])
    return assignment


@router.delete("/agents/{agent_id}/tools/{tool_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_tool_from_agent(
    agent_id: str,
    tool_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    q = select(AgentToolAssignment).where(
        and_(AgentToolAssignment.agent_id == agent_id, AgentToolAssignment.tool_id == tool_id)
    )
    result = await db.execute(q)
    assignment = result.scalar_one_or_none()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    await db.delete(assignment)
    await db.commit()


# ── HELPERS ───────────────────────────────────────────────────────────────────

async def _get_tool_or_404(tool_id: str, current_user: User, db: AsyncSession) -> Tool:
    result = await db.execute(
        select(Tool).where(and_(Tool.id == tool_id, Tool.user_id == current_user.id.hex))
    )
    tool = result.scalar_one_or_none()
    if not tool:
        raise HTTPException(status_code=404, detail=f"Tool {tool_id} not found")
    return tool


async def _execute_tool(tool: Tool, params: dict) -> dict:
    """Execute a tool based on its type. Returns result dict."""
    cfg = tool.config or {}
    t = tool.tool_type

    if t == "api_request":
        url = cfg.get("url") or params.get("url")
        if not url:
            raise ValueError("No URL configured for api_request tool")
        method = cfg.get("method", "POST").upper()
        headers = {**cfg.get("headers", {})}
        body = {**cfg.get("body", {}), **params}
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.request(method, url, headers=headers, json=body)
            return {"status_code": resp.status_code, "body": resp.text[:2000]}

    elif t == "slack":
        webhook_url = cfg.get("webhook_url")
        if not webhook_url:
            raise ValueError("No webhook_url configured for Slack tool")
        message = params.get("message") or cfg.get("default_message", "Voicecon notification")
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(webhook_url, json={"text": message})
            return {"status_code": resp.status_code, "ok": resp.text == "ok"}

    elif t in ("transfer_call", "hang_up", "leave_voicemail", "dtmf", "send_sms", "sip_request"):
        # These are telephony actions — validated during call, not testable in isolation
        return {"simulated": True, "tool_type": t, "config": cfg}

    elif t == "handoff":
        return {"simulated": True, "destination": cfg.get("destination"), "message": cfg.get("message")}

    elif t == "query_knowledge_base":
        return {"simulated": True, "knowledge_base_id": cfg.get("knowledge_base_id")}

    elif t in ("google_sheets", "google_calendar"):
        return {"simulated": True, "note": f"{t} requires OAuth credentials — configure in Integrations"}

    elif t == "mcp":
        server_url = cfg.get("server_url")
        if not server_url:
            raise ValueError("No server_url configured for MCP tool")
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(server_url, json={"tool": cfg.get("tool_name"), "params": params})
            return {"status_code": resp.status_code, "body": resp.text[:2000]}

    return {"executed": True, "tool_type": t}
