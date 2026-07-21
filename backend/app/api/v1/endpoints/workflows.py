"""
Workflow API endpoints.

Handles workflow CRUD, execution, and monitoring.
"""
import logging
import secrets
import uuid
from typing import Optional, List
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, desc

from app.database import get_db
from app.core.dependencies import get_current_active_user, get_current_org_id
from app.models.user import User, OrganizationMember
from app.models.integration import Workflow, WorkflowExecution
from app.schemas.workflow import (
    WorkflowCreate,
    WorkflowUpdate,
    WorkflowResponse,
    WorkflowListResponse,
    WorkflowExecuteRequest,
    WorkflowExecutionResponse,
    WorkflowExecutionListResponse,
    WorkflowStatsResponse,
    WorkflowUsageResponse,
)
from app.services.workflows import get_workflow_engine, WorkflowEngine
from app.services.workflows.graph import load_graph, normalize_graph, validate_graph

logger = logging.getLogger(__name__)

router = APIRouter()


def _prepare_trigger_config(trigger_type, trigger_config: Optional[dict]) -> dict:
    """
    Validate a trigger configuration and fill in generated defaults.

    Webhook triggers get an auto-generated key when none is supplied: matching
    now fails closed on a missing key, so a keyless webhook workflow could never
    be triggered at all.

    Args:
        trigger_type: Type of trigger
        trigger_config: Raw trigger configuration from the request

    Returns:
        The validated configuration

    Raises:
        HTTPException: 400 if the configuration is invalid
    """
    from app.services.workflows.trigger_handlers import TriggerError, TriggerValidator
    from app.schemas.workflow import TriggerType

    config = dict(trigger_config or {})

    if trigger_type == TriggerType.WEBHOOK and not config.get("webhook_key"):
        config["webhook_key"] = secrets.token_urlsafe(32)

    try:
        TriggerValidator.validate_trigger_config(trigger_type, config)
    except TriggerError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid trigger configuration: {e}",
        )

    return config


# ============================================================================
# Workflow CRUD Endpoints
# ============================================================================


@router.post("", response_model=WorkflowResponse, status_code=status.HTTP_201_CREATED)
async def create_workflow(
    workflow_data: WorkflowCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new workflow.

    Args:
        workflow_data: Workflow creation data
        current_user: Current authenticated user
        db: Database session

    Returns:
        WorkflowResponse: Created workflow

    Raises:
        HTTPException: If creation fails
    """
    try:
        # Get user's organization
        org_result = await db.execute(
            select(OrganizationMember)
            .where(OrganizationMember.user_id == current_user.id)
            .limit(1)
        )
        org_member = org_result.scalar_one_or_none()

        if not org_member:
            raise HTTPException(
                status_code=400,
                detail="User is not associated with any organization"
            )

        # Validate the trigger configuration. TriggerValidator existed but was
        # never called, so invalid cron expressions and short webhook keys were
        # stored and only failed silently later, inside the scheduler loop.
        trigger_config = _prepare_trigger_config(
            workflow_data.trigger_type,
            workflow_data.trigger_config,
        )

        # Store the v2 graph when supplied, otherwise wrap legacy steps.
        if workflow_data.graph is not None:
            workflow_steps_dict = normalize_graph(workflow_data.graph)
        else:
            workflow_steps_dict = {
                "steps": [step.dict() for step in workflow_data.workflow_steps]
            }

        # Create workflow
        workflow = Workflow(
            user_id=current_user.id,
            organization_id=org_member.organization_id,
            name=workflow_data.name,
            description=workflow_data.description,
            trigger_type=workflow_data.trigger_type,
            trigger_config=trigger_config,
            workflow_steps=workflow_steps_dict,
            is_active=workflow_data.is_active,
            execution_mode=workflow_data.execution_mode,
            error_handling=workflow_data.error_handling,
            max_retries=workflow_data.max_retries,
            retry_delay=workflow_data.retry_delay,
        )

        db.add(workflow)
        await db.commit()
        await db.refresh(workflow)

        logger.info(f"Workflow created: {workflow.id}")

        return workflow

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create workflow: {e}", exc_info=True)
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create workflow: {str(e)}",
        )


@router.get("", response_model=WorkflowListResponse)
async def list_workflows(
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    trigger_type: Optional[str] = Query(None, description="Filter by trigger type"),
    search: Optional[str] = Query(None, description="Search by name or description"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Page size"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    List user's workflows.

    Args:
        is_active: Filter by active status
        trigger_type: Filter by trigger type
        search: Search term
        page: Page number
        page_size: Page size
        current_user: Current authenticated user
        db: Database session

    Returns:
        WorkflowListResponse: List of workflows
    """
    try:
        # Build query
        query = select(Workflow).where(
            and_(
                Workflow.user_id == current_user.id,
                Workflow.deleted_at.is_(None),
            )
        )

        # Apply filters
        filters = []
        if is_active is not None:
            filters.append(Workflow.is_active == is_active)
        if trigger_type:
            filters.append(Workflow.trigger_type == trigger_type)
        if search:
            search_term = f"%{search}%"
            filters.append(
                or_(
                    Workflow.name.ilike(search_term),
                    Workflow.description.ilike(search_term),
                )
            )

        if filters:
            query = query.where(and_(*filters))

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await db.execute(count_query)
        total = total_result.scalar_one()

        # Apply pagination
        query = query.order_by(desc(Workflow.created_at))
        query = query.offset((page - 1) * page_size).limit(page_size)

        # Execute query
        result = await db.execute(query)
        workflows = result.scalars().all()

        return WorkflowListResponse(
            workflows=workflows,
            total=total,
            page=page,
            page_size=page_size,
        )

    except Exception as e:
        logger.error(f"Failed to list workflows: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list workflows: {str(e)}",
        )


@router.get("/{workflow_id}", response_model=WorkflowResponse)
async def get_workflow(
    workflow_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Get a specific workflow by ID.

    Args:
        workflow_id: Workflow ID
        current_user: Current authenticated user
        db: Database session

    Returns:
        WorkflowResponse: Workflow details

    Raises:
        HTTPException: If workflow not found
    """
    try:
        try:
            workflow_uuid = uuid.UUID(workflow_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid workflow ID format",
            )

        query = select(Workflow).where(
            and_(
                Workflow.id == workflow_uuid,
                Workflow.user_id == current_user.id,
                Workflow.deleted_at.is_(None),
            )
        )
        result = await db.execute(query)
        workflow = result.scalar_one_or_none()

        if not workflow:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Workflow {workflow_id} not found",
            )

        return workflow

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get workflow: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get workflow: {str(e)}",
        )


@router.patch("/{workflow_id}", response_model=WorkflowResponse)
async def update_workflow(
    workflow_id: str,
    update_data: WorkflowUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Update a workflow.

    Args:
        workflow_id: Workflow ID
        update_data: Update data
        current_user: Current authenticated user
        db: Database session

    Returns:
        WorkflowResponse: Updated workflow

    Raises:
        HTTPException: If workflow not found or update fails
    """
    try:
        try:
            workflow_uuid = uuid.UUID(workflow_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid workflow ID format",
            )

        query = select(Workflow).where(
            and_(
                Workflow.id == workflow_uuid,
                Workflow.user_id == current_user.id,
                Workflow.deleted_at.is_(None),
            )
        )
        result = await db.execute(query)
        workflow = result.scalar_one_or_none()

        if not workflow:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Workflow {workflow_id} not found",
            )

        # Update fields
        update_dict = update_data.dict(exclude_unset=True)

        # Validate the trigger config against the resulting trigger type, which
        # may itself be changing in this same request.
        if "trigger_config" in update_dict:
            update_dict["trigger_config"] = _prepare_trigger_config(
                update_dict.get("trigger_type", workflow.trigger_type),
                update_dict["trigger_config"],
            )

        # The graph and the legacy step list share one column, so a graph
        # update replaces workflow_steps outright.
        if update_dict.get("graph") is not None:
            update_dict["workflow_steps"] = normalize_graph(update_dict["graph"])
            workflow.version += 1
        elif "workflow_steps" in update_dict:
            update_dict["workflow_steps"] = {"steps": update_dict["workflow_steps"]}
            # Increment version
            workflow.version += 1

        update_dict.pop("graph", None)

        for field, value in update_dict.items():
            setattr(workflow, field, value)

        workflow.updated_at = datetime.utcnow()

        await db.commit()
        await db.refresh(workflow)

        logger.info(f"Workflow updated: {workflow.id}")

        return workflow

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update workflow: {e}", exc_info=True)
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update workflow: {str(e)}",
        )


@router.delete("/{workflow_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workflow(
    workflow_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Delete (soft delete) a workflow.

    Args:
        workflow_id: Workflow ID
        current_user: Current authenticated user
        db: Database session

    Raises:
        HTTPException: If workflow not found
    """
    try:
        try:
            workflow_uuid = uuid.UUID(workflow_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid workflow ID format",
            )

        query = select(Workflow).where(
            and_(
                Workflow.id == workflow_uuid,
                Workflow.user_id == current_user.id,
                Workflow.deleted_at.is_(None),
            )
        )
        result = await db.execute(query)
        workflow = result.scalar_one_or_none()

        if not workflow:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Workflow {workflow_id} not found",
            )

        # Soft delete
        workflow.deleted_at = datetime.utcnow()
        workflow.is_active = False

        await db.commit()

        logger.info(f"Workflow deleted: {workflow.id}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete workflow: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete workflow: {str(e)}",
        )


# ============================================================================
# Workflow Execution Endpoints
# ============================================================================


@router.post("/{workflow_id}/execute", response_model=WorkflowExecutionResponse)
async def execute_workflow(
    workflow_id: str,
    execute_request: WorkflowExecuteRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Execute a workflow.

    Args:
        workflow_id: Workflow ID
        execute_request: Execution request data
        current_user: Current authenticated user
        db: Database session

    Returns:
        WorkflowExecutionResponse: Execution details

    Raises:
        HTTPException: If execution fails
    """
    try:
        try:
            workflow_uuid = uuid.UUID(workflow_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid workflow ID format",
            )

        # Verify workflow belongs to user
        query = select(Workflow).where(
            and_(
                Workflow.id == workflow_uuid,
                Workflow.user_id == current_user.id,
                Workflow.deleted_at.is_(None),
            )
        )
        result = await db.execute(query)
        workflow = result.scalar_one_or_none()

        if not workflow:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Workflow {workflow_id} not found",
            )

        # Get workflow engine
        engine = get_workflow_engine(db)

        # Execute workflow
        execution = await engine.execute_workflow(
            workflow_id=str(workflow.id),
            trigger_data=execute_request.trigger_data,
            wait_for_completion=execute_request.wait_for_completion,
        )

        logger.info(f"Workflow execution started: {execution.id}")

        return execution

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to execute workflow: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to execute workflow: {str(e)}",
        )


@router.get("/{workflow_id}/executions", response_model=WorkflowExecutionListResponse)
async def list_workflow_executions(
    workflow_id: str,
    status_filter: Optional[str] = Query(None, description="Filter by status", alias="status"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Page size"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    List workflow executions.

    Args:
        workflow_id: Workflow ID
        status_filter: Filter by status
        page: Page number
        page_size: Page size
        current_user: Current authenticated user
        db: Database session

    Returns:
        WorkflowExecutionListResponse: List of executions
    """
    try:
        try:
            workflow_uuid = uuid.UUID(workflow_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid workflow ID format",
            )

        # Verify workflow belongs to user
        workflow_query = select(Workflow).where(
            and_(
                Workflow.id == workflow_uuid,
                Workflow.user_id == current_user.id,
            )
        )
        workflow_result = await db.execute(workflow_query)
        workflow = workflow_result.scalar_one_or_none()

        if not workflow:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Workflow {workflow_id} not found",
            )

        # Build query
        query = select(WorkflowExecution).where(
            WorkflowExecution.workflow_id == workflow_uuid
        )

        if status_filter:
            query = query.where(WorkflowExecution.status == status_filter)

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await db.execute(count_query)
        total = total_result.scalar_one()

        # Apply pagination
        query = query.order_by(desc(WorkflowExecution.started_at))
        query = query.offset((page - 1) * page_size).limit(page_size)

        # Execute query
        result = await db.execute(query)
        executions = result.scalars().all()

        return WorkflowExecutionListResponse(
            executions=executions,
            total=total,
            page=page,
            page_size=page_size,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list executions: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list executions: {str(e)}",
        )


@router.get("/{workflow_id}/executions/{execution_id}", response_model=WorkflowExecutionResponse)
async def get_workflow_execution(
    workflow_id: str,
    execution_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Get a specific workflow execution.

    Args:
        workflow_id: Workflow ID
        execution_id: Execution ID
        current_user: Current authenticated user
        db: Database session

    Returns:
        WorkflowExecutionResponse: Execution details

    Raises:
        HTTPException: If execution not found
    """
    try:
        try:
            workflow_uuid = uuid.UUID(workflow_id)
            execution_uuid = uuid.UUID(execution_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid ID format",
            )

        # Verify workflow belongs to user
        workflow_query = select(Workflow).where(
            and_(
                Workflow.id == workflow_uuid,
                Workflow.user_id == current_user.id,
            )
        )
        workflow_result = await db.execute(workflow_query)
        workflow = workflow_result.scalar_one_or_none()

        if not workflow:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Workflow {workflow_id} not found",
            )

        # Get execution
        query = select(WorkflowExecution).where(
            and_(
                WorkflowExecution.id == execution_uuid,
                WorkflowExecution.workflow_id == workflow_uuid,
            )
        )
        result = await db.execute(query)
        execution = result.scalar_one_or_none()

        if not execution:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Execution {execution_id} not found",
            )

        return execution

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get execution: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get execution: {str(e)}",
        )


# ============================================================================
# Statistics Endpoints
# ============================================================================


@router.get("/{workflow_id}/stats", response_model=WorkflowStatsResponse)
async def get_workflow_stats(
    workflow_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Get workflow statistics.

    Args:
        workflow_id: Workflow ID
        current_user: Current authenticated user
        db: Database session

    Returns:
        WorkflowStatsResponse: Workflow statistics

    Raises:
        HTTPException: If workflow not found
    """
    try:
        try:
            workflow_uuid = uuid.UUID(workflow_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid workflow ID format",
            )

        query = select(Workflow).where(
            and_(
                Workflow.id == workflow_uuid,
                Workflow.user_id == current_user.id,
            )
        )
        result = await db.execute(query)
        workflow = result.scalar_one_or_none()

        if not workflow:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Workflow {workflow_id} not found",
            )

        # Calculate statistics
        success_rate = (
            (workflow.successful_executions / workflow.total_executions * 100)
            if workflow.total_executions > 0
            else 0.0
        )

        # Get average duration
        avg_duration_query = select(func.avg(WorkflowExecution.duration_ms)).where(
            and_(
                WorkflowExecution.workflow_id == workflow_uuid,
                WorkflowExecution.status == "completed",
            )
        )
        avg_duration_result = await db.execute(avg_duration_query)
        average_duration_ms = avg_duration_result.scalar_one() or 0.0

        # Get total cost
        total_cost_query = select(func.sum(WorkflowExecution.cost)).where(
            WorkflowExecution.workflow_id == workflow_uuid
        )
        total_cost_result = await db.execute(total_cost_query)
        total_cost = float(total_cost_result.scalar_one() or 0.0)

        # Get executions in time periods
        now = datetime.utcnow()

        # Last 24 hours
        last_24h = now - timedelta(hours=24)
        last_24h_query = select(func.count()).where(
            and_(
                WorkflowExecution.workflow_id == workflow_uuid,
                WorkflowExecution.started_at >= last_24h,
            )
        )
        last_24h_result = await db.execute(last_24h_query)
        executions_last_24h = last_24h_result.scalar_one()

        # Last 7 days
        last_7d = now - timedelta(days=7)
        last_7d_query = select(func.count()).where(
            and_(
                WorkflowExecution.workflow_id == workflow_uuid,
                WorkflowExecution.started_at >= last_7d,
            )
        )
        last_7d_result = await db.execute(last_7d_query)
        executions_last_7d = last_7d_result.scalar_one()

        # Last 30 days
        last_30d = now - timedelta(days=30)
        last_30d_query = select(func.count()).where(
            and_(
                WorkflowExecution.workflow_id == workflow_uuid,
                WorkflowExecution.started_at >= last_30d,
            )
        )
        last_30d_result = await db.execute(last_30d_query)
        executions_last_30d = last_30d_result.scalar_one()

        return WorkflowStatsResponse(
            workflow_id=workflow_id,
            total_executions=workflow.total_executions,
            successful_executions=workflow.successful_executions,
            failed_executions=workflow.failed_executions,
            success_rate=success_rate,
            average_duration_ms=float(average_duration_ms),
            total_cost=total_cost,
            executions_last_24h=executions_last_24h,
            executions_last_7d=executions_last_7d,
            executions_last_30d=executions_last_30d,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get workflow stats: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get workflow stats: {str(e)}",
        )


# ============================================================================
# Trigger Management Endpoints
# ============================================================================


@router.post("/{workflow_id}/test-trigger")
async def test_workflow_trigger(
    workflow_id: str,
    test_data: dict,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Test a workflow trigger with sample data.

    Args:
        workflow_id: Workflow ID
        test_data: Test event data
        current_user: Current authenticated user
        db: Database session

    Returns:
        Test results

    Raises:
        HTTPException: If test fails
    """
    from app.services.workflows import get_trigger_manager, TriggerError

    try:
        # Verify workflow exists and belongs to user
        workflow_uuid = uuid.UUID(workflow_id)
        query = select(Workflow).where(
            and_(
                Workflow.id == workflow_uuid,
                Workflow.user_id == current_user.id,
            )
        )
        result = await db.execute(query)
        workflow = result.scalar_one_or_none()

        if not workflow:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Workflow not found",
            )

        # Test trigger
        trigger_manager = get_trigger_manager(db)
        test_result = await trigger_manager.test_trigger(
            workflow_id=workflow_id,
            test_data=test_data,
        )

        return test_result

    except TriggerError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to test trigger: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to test trigger: {str(e)}",
        )


@router.post("/{workflow_id}/validate")
async def validate_workflow_graph(
    workflow_id: str,
    payload: Optional[dict] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Validate a workflow graph without saving it.

    The builder calls this with its in-progress graph so structural problems
    surface while editing rather than at execution time.

    Args:
        workflow_id: Workflow ID
        payload: Optionally ``{"graph": {...}}`` to validate instead of the
            stored definition
        current_user: Current authenticated user
        db: Database session

    Returns:
        ``{"valid": bool, "errors": [...], "warnings": [...]}``
    """
    try:
        workflow_uuid = uuid.UUID(workflow_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid workflow ID format",
        )

    result = await db.execute(
        select(Workflow).where(
            and_(
                Workflow.id == workflow_uuid,
                Workflow.user_id == current_user.id,
                Workflow.deleted_at.is_(None),
            )
        )
    )
    workflow = result.scalar_one_or_none()

    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow {workflow_id} not found",
        )

    graph = (payload or {}).get("graph")
    graph = normalize_graph(graph) if graph else load_graph(workflow.workflow_steps)

    report = validate_graph(graph)

    return {
        "valid": not report["errors"],
        "errors": report["errors"],
        "warnings": report["warnings"],
    }


@router.post("/webhook/{webhook_key}")
async def trigger_webhook(
    webhook_key: str,
    payload: dict,
    db: AsyncSession = Depends(get_db),
):
    """
    Trigger workflow via webhook.

    Public endpoint - does not require authentication.

    Args:
        webhook_key: Webhook key
        payload: Webhook payload
        db: Database session

    Returns:
        Execution IDs

    Raises:
        HTTPException: If webhook is invalid
    """
    from app.services.workflows import get_trigger_manager
    from app.schemas.workflow import TriggerType

    try:
        # Build event data
        event_data = {
            "webhook_key": webhook_key,
            "payload": payload,
            "headers": {},
            "source_ip": "unknown",  # TODO: Get from request
        }

        # Process webhook trigger. Matching is by webhook key only; workflows
        # without a configured key never match (fail closed).
        trigger_manager = get_trigger_manager(db)
        execution_ids = await trigger_manager.process_webhook(
            webhook_key=webhook_key,
            event_data=event_data,
        )

        if not execution_ids:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No workflows matched this webhook",
            )

        return {
            "success": True,
            "execution_ids": execution_ids,
            "count": len(execution_ids),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Webhook trigger failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Webhook trigger failed: {str(e)}",
        )


@router.post("/trigger/voice-event")
async def trigger_voice_event(
    event_data: dict,
    current_user: User = Depends(get_current_active_user),
    organization_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db),
):
    """
    Trigger workflows based on voice events.

    Args:
        event_data: Voice event data
        current_user: Current authenticated user
        db: Database session

    Returns:
        Execution IDs

    Raises:
        HTTPException: If trigger fails
    """
    from app.services.workflows import get_trigger_manager
    from app.schemas.workflow import TriggerType

    try:
        # Determine event type
        event_type = event_data.get("event_type")

        if event_type == "call_started":
            trigger_type = TriggerType.CALL_STARTED
        elif event_type in ["call_completed", "call_ended"]:
            trigger_type = TriggerType.CALL_COMPLETED
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid event_type: {event_type}",
            )

        # Process voice event trigger, scoped to the caller's organization
        trigger_manager = get_trigger_manager(db)
        execution_ids = await trigger_manager.process_event(
            event_type=trigger_type,
            event_data=event_data,
            organization_id=organization_id,
        )

        return {
            "success": True,
            "event_type": event_type,
            "execution_ids": execution_ids,
            "count": len(execution_ids),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Voice event trigger failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Voice event trigger failed: {str(e)}",
        )


@router.post("/trigger/integration-event")
async def trigger_integration_event(
    event_data: dict,
    current_user: User = Depends(get_current_active_user),
    organization_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db),
):
    """
    Trigger workflows based on integration events.

    Args:
        event_data: Integration event data
        current_user: Current authenticated user
        db: Database session

    Returns:
        Execution IDs

    Raises:
        HTTPException: If trigger fails
    """
    from app.services.workflows import get_trigger_manager
    from app.schemas.workflow import TriggerType

    try:
        # Process integration event trigger, scoped to the caller's organization
        trigger_manager = get_trigger_manager(db)
        execution_ids = await trigger_manager.process_event(
            event_type=TriggerType.INTEGRATION_EVENT,
            event_data=event_data,
            organization_id=organization_id,
        )

        return {
            "success": True,
            "integration_type": event_data.get("integration_type"),
            "event_type": event_data.get("event_type"),
            "execution_ids": execution_ids,
            "count": len(execution_ids),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Integration event trigger failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Integration event trigger failed: {str(e)}",
        )
