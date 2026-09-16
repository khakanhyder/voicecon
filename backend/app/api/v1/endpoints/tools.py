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
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func

from app.database import get_db
from app.core.dependencies import get_current_active_user, get_current_org_id
from app.models.user import User, OrganizationMember
from app.models.agent import Agent
from app.models.tool import Tool, AgentToolAssignment
from app.services.tools.http_tools import HTTP_TOOL_TYPES, run_http_tool
from app.services.tools.validation import check_tool_references, validate_tool_config
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
    org_id: uuid.UUID = Depends(get_current_org_id),
):
    # Reject a tool that could never run, rather than let the agent call it
    # mid-conversation and discover the missing destination then.
    await _validate_tool(data.tool_type, data.config, data.description, org_id, db)

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
    org_id: uuid.UUID = Depends(get_current_org_id),
):
    q = select(Tool).where(Tool.organization_id == org_id)
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
    org_id: uuid.UUID = Depends(get_current_org_id),
):
    tool = await _get_tool_or_404(tool_id, org_id, db)
    return tool


@router.patch("/{tool_id}", response_model=ToolResponse)
async def update_tool(
    tool_id: str,
    data: ToolUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    org_id: uuid.UUID = Depends(get_current_org_id),
):
    tool = await _get_tool_or_404(tool_id, org_id, db)
    update = data.model_dump(exclude_unset=True)
    # Toggling a tool on or off leaves its configuration alone, so it is not
    # re-checked — an older tool saved before validation can still be paused.
    if "config" in update or "description" in update:
        await _validate_tool(
            tool.tool_type,
            update.get("config", tool.config),
            update.get("description", tool.description),
            org_id,
            db,
        )
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
    org_id: uuid.UUID = Depends(get_current_org_id),
):
    tool = await _get_tool_or_404(tool_id, org_id, db)
    await db.delete(tool)
    await db.commit()


# ── TEST ──────────────────────────────────────────────────────────────────────

@router.post("/{tool_id}/test", response_model=ToolTestResponse)
async def test_tool(
    tool_id: str,
    body: ToolTestRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    org_id: uuid.UUID = Depends(get_current_org_id),
):
    tool = await _get_tool_or_404(tool_id, org_id, db)
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
    org_id: uuid.UUID = Depends(get_current_org_id),
):
    await _get_agent_or_404(agent_id, org_id, db)
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
    org_id: uuid.UUID = Depends(get_current_org_id),
):
    # Both sides must live in the caller's workspace.
    await _get_agent_or_404(agent_id, org_id, db)
    await _get_tool_or_404(tool_id, org_id, db)

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
    org_id: uuid.UUID = Depends(get_current_org_id),
):
    await _get_agent_or_404(agent_id, org_id, db)
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

async def _validate_tool(
    tool_type: str,
    config: Optional[dict],
    description: Optional[str],
    org_id: uuid.UUID,
    db: AsyncSession,
) -> None:
    """Raise 422 naming every field that stops this tool from working.

    ``detail`` is a sentence (the first problem) so any client can show it as
    is; ``errors`` maps each field to its message for a form to place inline.
    """
    errors = {}
    # The description is how the model decides when to call the tool; without
    # one the agent has no reason to ever use it.
    if not (description or "").strip():
        errors["description"] = "Description is required — it tells the AI when to use this tool."
    errors.update(validate_tool_config(tool_type, config))
    if not errors:
        errors.update(await check_tool_references(tool_type, config, org_id, db))
    if errors:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": next(iter(errors.values())), "errors": errors},
        )


async def _get_tool_or_404(tool_id: str, org_id: uuid.UUID, db: AsyncSession) -> Tool:
    result = await db.execute(
        select(Tool).where(and_(Tool.id == tool_id, Tool.organization_id == org_id))
    )
    tool = result.scalar_one_or_none()
    if not tool:
        raise HTTPException(status_code=404, detail=f"Tool {tool_id} not found")
    return tool


async def _get_agent_or_404(agent_id: str, org_id: uuid.UUID, db: AsyncSession) -> Agent:
    """Agent lookup scoped to the workspace.

    The assignment endpoints previously took the agent id on trust, so any
    signed-in user could read or rewrite another tenant's agent-tool wiring.
    """
    result = await db.execute(
        select(Agent).where(and_(Agent.id == agent_id, Agent.organization_id == org_id))
    )
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")
    return agent


#: What "Test" reports for a tool it deliberately does not execute, and why.
#: These need a live call, a workspace connection, or would cause real side
#: effects that pressing a button in a form should not.
_NOT_TESTABLE = {
    "transfer_call": "Transfers happen on a live call; there is nothing to transfer here.",
    "hang_up": "Hanging up needs a live call.",
    "leave_voicemail": "Leaving a voicemail needs a live call.",
    "dtmf": "Sending tones needs a live call.",
    "send_sms": "Sending a text needs a live call to take the number from.",
    "sip_request": "A SIP request needs a live call.",
    "handoff": "A handoff needs a live call to hand off.",
    "query_knowledge_base": (
        "Use the knowledge base's own Test retrieval panel, which shows the "
        "matched passages and their scores."
    ),
    "workflow": (
        "Running this would run the whole workflow, side effects included. "
        "Use the workflow builder's Run button, which shows every step."
    ),
    "google_sheets": (
        "Google Sheets tools run through a connected integration. Connect "
        "Google Sheets under Integrations and recreate this as a Connected "
        "Integration tool."
    ),
    "google_calendar": (
        "Google Calendar tools run through a connected integration. Connect "
        "Google Calendar under Integrations and recreate this as a Connected "
        "Integration tool."
    ),
    "gohighlevel": (
        "GoHighLevel tools run through a connected integration. Connect "
        "GoHighLevel under Integrations and recreate this as a Connected "
        "Integration tool."
    ),
    "integration": (
        "Test a connected integration from the Integrations page, where the "
        "connection itself can be checked."
    ),
    "connected_integration": (
        "Test a connected integration from the Integrations page, where the "
        "connection itself can be checked."
    ),
}


async def _execute_tool(tool: Tool, params: dict) -> dict:
    """Execute a tool for the builder's "Test" button.

    The HTTP-shaped types go through exactly the same code as a live call, so a
    tool that passes here behaves the same way on the phone. This used to be a
    second implementation, and the two drifted: the copy here still took its URL
    from the caller-supplied ``params`` — an authenticated user could point it
    at the cloud metadata endpoint and read the response out of the test result
    — and it still unpacked config fields the form stores as text, which raised
    ``TypeError`` for every tool whose headers had been edited.

    Args:
        tool: The tool to exercise
        params: Sample parameters supplied by whoever pressed Test

    Returns:
        A result dict for the test panel
    """
    cfg = tool.config or {}
    t = tool.tool_type

    if t in HTTP_TOOL_TYPES:
        return await run_http_tool(t, cfg, params or {})

    if t in _NOT_TESTABLE:
        return {"simulated": True, "tool_type": t, "note": _NOT_TESTABLE[t]}

    return {"simulated": True, "tool_type": t, "note": "This tool type has no test action."}
