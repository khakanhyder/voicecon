"""
Agent API endpoints.

Handles agent CRUD, configuration, testing, and templates.
"""
import logging
import uuid
import asyncio
from typing import Optional, List
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func

from app.database import get_db
from app.core.security import get_current_active_user
from app.models.user import User
from app.models.agent import Agent, AgentFunction
from app.schemas.agent import (
    AgentCreate,
    AgentUpdate,
    AgentResponse,
    AgentListResponse,
    AgentFunctionCreate,
    AgentFunctionUpdate,
    AgentFunctionResponse,
    AgentTestRequest,
    AgentTestResponse,
    AgentCloneRequest,
)
from app.services.agent_service import get_agent_service
from app.services.voice.llm_service import get_llm_service, ChatMessage
from app.services.voice.tts_service import get_tts_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
async def create_agent(
    agent_data: AgentCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new agent.

    Args:
        agent_data: Agent creation data
        current_user: Current authenticated user
        db: Database session

    Returns:
        Created agent
    """
    try:
        agent_service = get_agent_service()

        agent = await agent_service.create_agent(
            agent_data=agent_data,
            user_id=current_user.id,
            organization_id=current_user.organizations[0].id,
            db=db,
        )

        return agent

    except Exception as e:
        logger.error(f"Error creating agent: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create agent: {str(e)}"
        )


@router.get("/", response_model=AgentListResponse)
async def list_agents(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    search: Optional[str] = Query(default=None, description="Search by name/description"),
    tags: Optional[List[str]] = Query(default=None, description="Filter by tags"),
    is_active: Optional[bool] = Query(default=None, description="Filter by active status"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    List user's agents.

    Args:
        skip: Number of records to skip
        limit: Maximum records to return
        search: Search query
        tags: Filter by tags
        is_active: Filter by active status
        current_user: Current authenticated user
        db: Database session

    Returns:
        List of agents
    """
    try:
        # Build query
        query = select(Agent).where(
            and_(
                Agent.user_id == current_user.id,
                Agent.deleted_at.is_(None),
            )
        )

        if search:
            search_filter = or_(
                Agent.name.ilike(f"%{search}%"),
                Agent.description.ilike(f"%{search}%"),
            )
            query = query.where(search_filter)

        if tags:
            # Filter by any matching tag
            query = query.where(Agent.tags.overlap(tags))

        if is_active is not None:
            query = query.where(Agent.is_active == is_active)

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await db.execute(count_query)
        total = total_result.scalar()

        # Get agents
        query = query.order_by(Agent.created_at.desc()).offset(skip).limit(limit)
        result = await db.execute(query)
        agents = result.scalars().all()

        return AgentListResponse(
            agents=agents,
            total=total,
            skip=skip,
            limit=limit,
        )

    except Exception as e:
        logger.error(f"Error listing agents: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list agents: {str(e)}"
        )


@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(
    agent_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get agent by ID.

    Args:
        agent_id: Agent ID
        current_user: Current authenticated user
        db: Database session

    Returns:
        Agent details
    """
    try:
        result = await db.execute(
            select(Agent).where(
                and_(
                    Agent.id == agent_id,
                    Agent.user_id == current_user.id,
                    Agent.deleted_at.is_(None),
                )
            )
        )
        agent = result.scalar_one_or_none()

        if not agent:
            raise HTTPException(
                status_code=404,
                detail="Agent not found"
            )

        return agent

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting agent: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get agent: {str(e)}"
        )


@router.patch("/{agent_id}", response_model=AgentResponse)
async def update_agent(
    agent_id: uuid.UUID,
    agent_data: AgentUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Update an agent.

    Args:
        agent_id: Agent ID
        agent_data: Update data
        current_user: Current authenticated user
        db: Database session

    Returns:
        Updated agent
    """
    try:
        agent_service = get_agent_service()

        agent = await agent_service.update_agent(
            agent_id=agent_id,
            agent_data=agent_data,
            user_id=current_user.id,
            db=db,
        )

        if not agent:
            raise HTTPException(
                status_code=404,
                detail="Agent not found"
            )

        return agent

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating agent: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update agent: {str(e)}"
        )


@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent(
    agent_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Delete an agent (soft delete).

    Args:
        agent_id: Agent ID
        current_user: Current authenticated user
        db: Database session
    """
    try:
        agent_service = get_agent_service()

        deleted = await agent_service.delete_agent(
            agent_id=agent_id,
            user_id=current_user.id,
            db=db,
            soft_delete=True,
        )

        if not deleted:
            raise HTTPException(
                status_code=404,
                detail="Agent not found"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting agent: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete agent: {str(e)}"
        )


@router.post("/{agent_id}/clone", response_model=AgentResponse)
async def clone_agent(
    agent_id: uuid.UUID,
    clone_request: AgentCloneRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Clone an existing agent.

    Args:
        agent_id: Agent ID to clone
        clone_request: Clone configuration
        current_user: Current authenticated user
        db: Database session

    Returns:
        Cloned agent
    """
    try:
        agent_service = get_agent_service()

        agent = await agent_service.clone_agent(
            agent_id=agent_id,
            new_name=clone_request.name,
            user_id=current_user.id,
            organization_id=current_user.organizations[0].id,
            db=db,
            include_functions=clone_request.include_functions,
        )

        if not agent:
            raise HTTPException(
                status_code=404,
                detail="Agent not found"
            )

        return agent

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cloning agent: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to clone agent: {str(e)}"
        )


@router.post("/{agent_id}/test", response_model=AgentTestResponse)
async def test_agent(
    agent_id: uuid.UUID,
    test_request: AgentTestRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Test an agent with a sample message.

    Args:
        agent_id: Agent ID
        test_request: Test configuration
        current_user: Current authenticated user
        db: Database session

    Returns:
        Test results
    """
    try:
        # Get agent
        result = await db.execute(
            select(Agent).where(
                and_(
                    Agent.id == agent_id,
                    Agent.user_id == current_user.id,
                )
            )
        )
        agent = result.scalar_one_or_none()

        if not agent:
            raise HTTPException(
                status_code=404,
                detail="Agent not found"
            )

        # Run test
        start_time = datetime.utcnow()

        # Test LLM
        llm_service = get_llm_service()
        messages = []

        if agent.system_prompt:
            messages.append(ChatMessage(role="system", content=agent.system_prompt))

        messages.append(ChatMessage(role="user", content=test_request.test_message))

        # Generate response
        response_text = ""
        async for chunk in llm_service.chat_stream(
            messages=messages,
            provider=agent.llm_provider,
            model=agent.llm_model,
            temperature=float(agent.llm_temperature),
            max_tokens=agent.llm_max_tokens,
        ):
            response_text += chunk

        # Calculate latency
        end_time = datetime.utcnow()
        latency_ms = int((end_time - start_time).total_seconds() * 1000)

        # Get usage stats
        llm_stats = await llm_service.get_usage_stats(provider=agent.llm_provider)
        last_usage = llm_stats[-1] if llm_stats else None

        costs = {
            "llm": float(last_usage.cost) if last_usage else 0,
            "total": float(last_usage.cost) if last_usage else 0,
        }

        # Test TTS if requested
        if test_request.test_mode == "audio":
            tts_service = get_tts_service()

            # Synthesize (don't stream for test)
            tts_result = await tts_service.synthesize(
                text=response_text[:200],  # Limit for testing
                provider=agent.tts_provider,
                voice_id=agent.tts_voice_id or "rachel",
            )

            tts_stats = await tts_service.get_usage_stats(provider=agent.tts_provider)
            last_tts = tts_stats[-1] if tts_stats else None

            costs["tts"] = float(last_tts.cost) if last_tts else 0
            costs["total"] += costs["tts"]

        return AgentTestResponse(
            success=True,
            test_id=uuid.uuid4(),
            agent_response=response_text,
            latency_ms=latency_ms,
            costs=costs,
            metadata={
                "agent_id": str(agent_id),
                "test_message": test_request.test_message,
                "test_mode": test_request.test_mode,
                "model": agent.llm_model,
                "provider": agent.llm_provider,
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error testing agent: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to test agent: {str(e)}"
        )


@router.get("/templates/list")
async def list_templates(
    current_user: User = Depends(get_current_active_user),
):
    """
    List available agent templates.

    Args:
        current_user: Current authenticated user

    Returns:
        List of templates
    """
    try:
        agent_service = get_agent_service()
        templates = agent_service.get_templates()

        return {
            "templates": templates,
            "total": len(templates),
        }

    except Exception as e:
        logger.error(f"Error listing templates: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list templates: {str(e)}"
        )


@router.post("/templates/{template_id}/create", response_model=AgentResponse)
async def create_from_template(
    template_id: str,
    custom_name: Optional[str] = Query(default=None),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Create agent from template.

    Args:
        template_id: Template ID
        custom_name: Optional custom name
        current_user: Current authenticated user
        db: Database session

    Returns:
        Created agent
    """
    try:
        agent_service = get_agent_service()

        agent = await agent_service.create_from_template(
            template_id=template_id,
            user_id=current_user.id,
            organization_id=current_user.organizations[0].id,
            db=db,
            custom_name=custom_name,
        )

        if not agent:
            raise HTTPException(
                status_code=404,
                detail="Template not found"
            )

        return agent

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating from template: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create from template: {str(e)}"
        )


# Agent Functions endpoints


@router.post("/{agent_id}/functions", response_model=AgentFunctionResponse)
async def create_agent_function(
    agent_id: uuid.UUID,
    function_data: AgentFunctionCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a function for an agent.

    Args:
        agent_id: Agent ID
        function_data: Function data
        current_user: Current authenticated user
        db: Database session

    Returns:
        Created function
    """
    try:
        # Verify agent ownership
        result = await db.execute(
            select(Agent).where(
                and_(
                    Agent.id == agent_id,
                    Agent.user_id == current_user.id,
                )
            )
        )
        agent = result.scalar_one_or_none()

        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")

        # Create function
        function = AgentFunction(
            agent_id=agent_id,
            name=function_data.name,
            description=function_data.description,
            parameters=function_data.parameters,
            webhook_url=function_data.webhook_url,
            http_method=function_data.http_method,
            headers=function_data.headers,
            timeout=function_data.timeout,
            retry_count=function_data.retry_count,
            is_active=function_data.is_active,
            execution_order=function_data.execution_order,
        )

        db.add(function)
        await db.commit()
        await db.refresh(function)

        return function

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating function: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{agent_id}/functions", response_model=List[AgentFunctionResponse])
async def list_agent_functions(
    agent_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    List agent's functions.

    Args:
        agent_id: Agent ID
        current_user: Current authenticated user
        db: Database session

    Returns:
        List of functions
    """
    try:
        # Verify agent ownership
        result = await db.execute(
            select(Agent).where(
                and_(
                    Agent.id == agent_id,
                    Agent.user_id == current_user.id,
                )
            )
        )
        agent = result.scalar_one_or_none()

        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")

        # Get functions
        result = await db.execute(
            select(AgentFunction)
            .where(AgentFunction.agent_id == agent_id)
            .order_by(AgentFunction.execution_order)
        )
        functions = result.scalars().all()

        return functions

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing functions: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{agent_id}/functions/{function_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent_function(
    agent_id: uuid.UUID,
    function_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Delete an agent function.

    Args:
        agent_id: Agent ID
        function_id: Function ID
        current_user: Current authenticated user
        db: Database session
    """
    try:
        # Verify agent ownership
        result = await db.execute(
            select(Agent).where(
                and_(
                    Agent.id == agent_id,
                    Agent.user_id == current_user.id,
                )
            )
        )
        agent = result.scalar_one_or_none()

        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")

        # Delete function
        result = await db.execute(
            select(AgentFunction).where(
                and_(
                    AgentFunction.id == function_id,
                    AgentFunction.agent_id == agent_id,
                )
            )
        )
        function = result.scalar_one_or_none()

        if not function:
            raise HTTPException(status_code=404, detail="Function not found")

        await db.delete(function)
        await db.commit()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting function: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# Function Testing Endpoint
class FunctionTestRequest(BaseModel):
    """Function test request."""
    parameters: Dict[str, Any] = Field(..., description="Function parameters to test")


class FunctionTestResponse(BaseModel):
    """Function test response."""
    success: bool
    function_name: str
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    execution_time_ms: int
    formatted_result: str


@router.post("/{agent_id}/functions/{function_id}/test", response_model=FunctionTestResponse)
async def test_function(
    agent_id: str,
    function_id: str,
    test_request: FunctionTestRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Test a function with sample parameters.

    Args:
        agent_id: Agent ID
        function_id: Function ID
        test_request: Test request with parameters
        current_user: Current authenticated user
        db: Database session

    Returns:
        Function test result
    """
    try:
        # Verify agent ownership
        result = await db.execute(
            select(Agent).where(
                and_(
                    Agent.id == agent_id,
                    Agent.user_id == current_user.id,
                )
            )
        )
        agent = result.scalar_one_or_none()

        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")

        # Get function
        result = await db.execute(
            select(AgentFunction).where(
                and_(
                    AgentFunction.id == function_id,
                    AgentFunction.agent_id == agent_id,
                )
            )
        )
        function = result.scalar_one_or_none()

        if not function:
            raise HTTPException(status_code=404, detail="Function not found")

        # Execute function
        from app.services.function_executor import get_function_executor

        executor = get_function_executor()

        execution_result = await executor.execute_function(
            function=function,
            parameters=test_request.parameters,
            call_id=None,  # No call ID for testing
            db=None,  # Don't log test executions
        )

        # Format result for display
        formatted_result = executor.format_for_llm(function, execution_result)

        return FunctionTestResponse(
            success=execution_result["success"],
            function_name=execution_result["function_name"],
            result=execution_result.get("result"),
            error=execution_result.get("error"),
            execution_time_ms=execution_result["execution_time_ms"],
            formatted_result=formatted_result,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error testing function: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
