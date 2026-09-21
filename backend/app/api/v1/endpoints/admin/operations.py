"""Cross-tenant operational views: calls, numbers, integrations, workflow runs."""
from __future__ import annotations

from datetime import timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.admin import require_platform_admin
from app.database import get_db
from app.models.agent import Agent
from app.models.call import Call, PhoneNumber
from app.models.integration import IntegrationConnection, IntegrationConnector, Workflow, WorkflowExecution
from app.models.user import Organization

from ._common import PageParams, iso, like, num, paginated, parse_uuid, utcnow

router = APIRouter()

FAILED_CALL_STATUSES = ("failed", "busy", "no-answer", "no_answer", "error", "canceled")


def _count_query(query):
    return select(func.count()).select_from(query.order_by(None).subquery())


@router.get("/calls")
async def list_calls(
    search: Optional[str] = Query(None, max_length=100),
    call_status: Optional[str] = Query(None, alias="status", max_length=30),
    direction: Optional[str] = Query(None, pattern="^(inbound|outbound)$"),
    organization_id: Optional[str] = None,
    days: int = Query(30, ge=1, le=365),
    params: PageParams = Depends(),
    db: AsyncSession = Depends(get_db),
    _admin=Depends(require_platform_admin),
):
    query = (
        select(Call, Organization.name, Agent.name)
        .join(Organization, Organization.id == Call.organization_id)
        .outerjoin(Agent, Agent.id == Call.agent_id)
        .where(Call.created_at >= utcnow() - timedelta(days=days))
    )
    if search:
        term = like(search.strip())
        query = query.where(
            or_(Call.from_number.ilike(term), Call.to_number.ilike(term), Organization.name.ilike(term), Agent.name.ilike(term))
        )
    if call_status == "failed":
        query = query.where(Call.status.in_(FAILED_CALL_STATUSES))
    elif call_status:
        query = query.where(Call.status == call_status)
    if direction:
        query = query.where(Call.direction == direction)
    if organization_id:
        query = query.where(Call.organization_id == parse_uuid(organization_id, "organization"))

    total = int((await db.execute(_count_query(query))).scalar() or 0)
    rows = (
        await db.execute(query.order_by(Call.created_at.desc()).offset(params.offset).limit(params.page_size))
    ).all()
    items = [
        {
            "id": str(c.id),
            "organization_id": str(c.organization_id),
            "organization_name": org_name,
            "agent_name": agent_name,
            "direction": c.direction,
            "status": c.status,
            "from_number": c.from_number,
            "to_number": c.to_number,
            "duration_seconds": c.duration_seconds,
            "cost_total": num(c.cost_total),
            "has_recording": bool(c.recording_url),
            "has_transcript": bool(c.transcript or c.transcript_json),
            "created_at": iso(c.created_at),
        }
        for c, org_name, agent_name in rows
    ]
    return paginated(items, total, params)


@router.get("/calls/{call_id}")
async def get_call(
    call_id: str,
    db: AsyncSession = Depends(get_db),
    _admin=Depends(require_platform_admin),
):
    row = (
        await db.execute(
            select(Call, Organization.name, Agent.name)
            .join(Organization, Organization.id == Call.organization_id)
            .outerjoin(Agent, Agent.id == Call.agent_id)
            .where(Call.id == parse_uuid(call_id, "call"))
        )
    ).first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Call not found")
    c, org_name, agent_name = row
    return {
        "id": str(c.id),
        "organization_id": str(c.organization_id),
        "organization_name": org_name,
        "agent_name": agent_name,
        "direction": c.direction,
        "status": c.status,
        "from_number": c.from_number,
        "to_number": c.to_number,
        "provider": c.provider,
        "provider_call_sid": c.provider_call_sid,
        "started_at": iso(c.started_at),
        "answered_at": iso(c.answered_at),
        "ended_at": iso(c.ended_at),
        "duration_seconds": c.duration_seconds,
        "billable_duration_seconds": c.billable_duration_seconds,
        "recording_url": c.recording_url,
        "transcript": c.transcript,
        "transcript_json": c.transcript_json,
        "summary": c.summary,
        "sentiment_label": c.sentiment_label,
        "costs": {
            "stt": num(c.cost_stt),
            "llm": num(c.cost_llm),
            "tts": num(c.cost_tts),
            "telephony": num(c.cost_telephony),
            "total": num(c.cost_total),
        },
        "created_at": iso(c.created_at),
    }


@router.get("/phone-numbers")
async def list_phone_numbers(
    search: Optional[str] = Query(None, max_length=100),
    number_status: Optional[str] = Query(None, alias="status", max_length=30),
    provider: Optional[str] = Query(None, max_length=30),
    params: PageParams = Depends(),
    db: AsyncSession = Depends(get_db),
    _admin=Depends(require_platform_admin),
):
    query = (
        select(PhoneNumber, Organization.name, Organization.is_active, Agent.name)
        .join(Organization, Organization.id == PhoneNumber.organization_id)
        .outerjoin(Agent, Agent.id == PhoneNumber.agent_id)
    )
    if search:
        term = like(search.strip())
        query = query.where(or_(PhoneNumber.phone_number.ilike(term), Organization.name.ilike(term)))
    if number_status:
        query = query.where(PhoneNumber.status == number_status)
    if provider:
        query = query.where(PhoneNumber.provider == provider)

    total = int((await db.execute(_count_query(query))).scalar() or 0)
    rows = (
        await db.execute(query.order_by(PhoneNumber.created_at.desc()).offset(params.offset).limit(params.page_size))
    ).all()
    items = [
        {
            "id": str(n.id),
            "phone_number": n.phone_number,
            "organization_id": str(n.organization_id),
            "organization_name": org_name,
            "organization_active": org_active,
            "agent_name": agent_name,
            "provider": n.provider,
            "provider_sid": n.provider_sid,
            "bring_your_own": n.integration_connection_id is not None,
            "status": n.status,
            "monthly_cost": num(n.monthly_cost),
            "created_at": iso(n.created_at),
        }
        for n, org_name, org_active, agent_name in rows
    ]
    return paginated(items, total, params)


@router.get("/integrations/connections")
async def list_connections(
    connection_status: Optional[str] = Query(None, alias="status", max_length=30),
    params: PageParams = Depends(),
    db: AsyncSession = Depends(get_db),
    _admin=Depends(require_platform_admin),
):
    query = (
        select(IntegrationConnection, Organization.name, IntegrationConnector.name, IntegrationConnector.slug)
        .join(Organization, Organization.id == IntegrationConnection.organization_id)
        .join(IntegrationConnector, IntegrationConnector.id == IntegrationConnection.connector_id)
        .where(IntegrationConnection.is_active.is_(True))
    )
    if connection_status == "problem":
        query = query.where(IntegrationConnection.status.in_(("expired", "error")))
    elif connection_status:
        query = query.where(IntegrationConnection.status == connection_status)

    total = int((await db.execute(_count_query(query))).scalar() or 0)
    rows = (
        await db.execute(
            query.order_by(IntegrationConnection.updated_at.desc()).offset(params.offset).limit(params.page_size)
        )
    ).all()
    items = [
        {
            "id": str(c.id),
            "organization_id": str(c.organization_id),
            "organization_name": org_name,
            "connector_name": connector_name,
            "connector_slug": connector_slug,
            "name": c.name,
            "status": c.status,
            "last_error": c.last_error,
            "error_count": c.error_count,
            "token_expires_at": iso(c.token_expires_at),
            "last_sync_at": iso(c.last_sync_at),
            "updated_at": iso(c.updated_at),
        }
        for c, org_name, connector_name, connector_slug in rows
    ]
    return paginated(items, total, params)


@router.get("/workflows/runs")
async def list_workflow_runs(
    run_status: Optional[str] = Query("failed", alias="status", max_length=30),
    hours: int = Query(72, ge=1, le=24 * 30),
    params: PageParams = Depends(),
    db: AsyncSession = Depends(get_db),
    _admin=Depends(require_platform_admin),
):
    query = (
        select(WorkflowExecution, Workflow.name, Workflow.trigger_type, Organization.id, Organization.name)
        .join(Workflow, Workflow.id == WorkflowExecution.workflow_id)
        .join(Organization, Organization.id == Workflow.organization_id)
        .where(WorkflowExecution.started_at >= utcnow() - timedelta(hours=hours))
    )
    if run_status:
        query = query.where(WorkflowExecution.status == run_status)

    total = int((await db.execute(_count_query(query))).scalar() or 0)
    rows = (
        await db.execute(
            query.order_by(WorkflowExecution.started_at.desc()).offset(params.offset).limit(params.page_size)
        )
    ).all()
    items = [
        {
            "id": str(e.id),
            "workflow_id": str(e.workflow_id),
            "workflow_name": wf_name,
            "trigger_type": trigger_type,
            "organization_id": str(org_id),
            "organization_name": org_name,
            "status": e.status,
            "error_message": e.error_message,
            "steps_executed": e.steps_executed,
            "steps_failed": e.steps_failed,
            "duration_ms": e.duration_ms,
            "started_at": iso(e.started_at),
        }
        for e, wf_name, trigger_type, org_id, org_name in rows
    ]
    return paginated(items, total, params)
