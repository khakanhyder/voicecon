"""
Analytics API endpoints.

Provides comprehensive analytics, metrics, and reporting with pre-aggregated data.
"""
import logging
import uuid
from typing import Optional, List
from datetime import datetime, date, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from app.database import get_db
from app.core.security import get_current_active_user
from app.models.user import User
from app.services.analytics import AnalyticsService

logger = logging.getLogger(__name__)

router = APIRouter()


# ==================== SCHEMAS ====================

class CallMetricsResponse(BaseModel):
    """Call metrics response."""
    total_calls: int
    completed_calls: int
    failed_calls: int
    missed_calls: int
    total_duration_seconds: int
    avg_duration_seconds: Optional[float]
    total_cost: float
    avg_cost_per_call: Optional[float]
    success_rate: Optional[float]
    avg_sentiment_score: Optional[float]
    positive_sentiment_count: int
    negative_sentiment_count: int
    neutral_sentiment_count: int


class AgentMetricsResponse(BaseModel):
    """Agent performance metrics."""
    agent_id: str
    total_interactions: int
    successful_interactions: int
    failed_interactions: int
    avg_sentiment_score: Optional[float]
    positive_sentiment_percentage: Optional[float]
    total_function_calls: int
    successful_function_calls: int
    failed_function_calls: int
    function_success_rate: Optional[float]
    total_cost: float
    cost_per_interaction: Optional[float]
    avg_user_rating: Optional[float]


class IntegrationMetricsResponse(BaseModel):
    """Integration health metrics."""
    integration_id: str
    total_workflows_executed: int
    successful_workflows: int
    failed_workflows: int
    workflow_success_rate: Optional[float]
    total_api_calls: int
    api_success_rate: Optional[float]
    avg_response_time_ms: Optional[float]
    error_count: int
    health_score: Optional[float]


class DailySummaryResponse(BaseModel):
    """Daily summary response."""
    summary_date: str
    total_calls: int
    total_call_minutes: int
    total_call_cost: float
    active_agents_count: int
    total_agent_interactions: int
    avg_agent_performance: Optional[float]
    active_integrations_count: int
    total_workflow_executions: int
    avg_integration_health: Optional[float]
    avg_sentiment_score: Optional[float]
    call_success_rate: Optional[float]
    workflow_success_rate: Optional[float]
    top_agents: List[dict] = Field(default_factory=list)
    call_volume_change: Optional[float]
    cost_change: Optional[float]
    sentiment_change: Optional[float]


class RealTimeMetricsResponse(BaseModel):
    """Real-time metrics response."""
    current_active_calls: int
    calls_today: int
    calls_last_hour: int
    calls_last_5_minutes: int
    cost_today: float
    cost_last_hour: float
    active_agents: int
    active_integrations: int
    system_health: str
    error_rate_last_hour: Optional[float]
    recent_calls: List[dict] = Field(default_factory=list)
    last_updated: str


class MetricsTimeSeriesResponse(BaseModel):
    """Time series metrics response."""
    dates: List[str]
    call_volumes: List[int]
    costs: List[float]
    success_rates: List[float]
    sentiment_scores: List[float]


# ==================== ENDPOINTS ====================

@router.get("/call-metrics", response_model=CallMetricsResponse)
async def get_call_metrics(
    start_date: date = Query(..., description="Start date"),
    end_date: date = Query(..., description="End date"),
    agent_id: Optional[str] = Query(None, description="Filter by agent"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get aggregated call metrics for a date range.

    Uses pre-aggregated data for optimal performance.
    """
    try:
        analytics_service = AnalyticsService(db)

        # Convert agent_id to UUID if provided
        agent_uuid = uuid.UUID(agent_id) if agent_id else None

        # Get aggregated metrics
        metrics = await analytics_service.aggregate_call_metrics(
            organization_id=current_user.organization_id,
            start_date=start_date,
            end_date=end_date,
            granularity="daily",
            agent_id=agent_uuid
        )

        if not metrics:
            return CallMetricsResponse(
                total_calls=0,
                completed_calls=0,
                failed_calls=0,
                missed_calls=0,
                total_duration_seconds=0,
                avg_duration_seconds=None,
                total_cost=0,
                avg_cost_per_call=None,
                success_rate=None,
                avg_sentiment_score=None,
                positive_sentiment_count=0,
                negative_sentiment_count=0,
                neutral_sentiment_count=0
            )

        # Aggregate across all days
        total_calls = sum(m.total_calls for m in metrics)
        completed_calls = sum(m.completed_calls for m in metrics)
        failed_calls = sum(m.failed_calls for m in metrics)
        missed_calls = sum(m.missed_calls for m in metrics)
        total_duration = sum(m.total_duration for m in metrics)
        total_cost = sum(m.total_cost for m in metrics)
        positive_sentiment = sum(m.positive_sentiment_count for m in metrics)
        negative_sentiment = sum(m.negative_sentiment_count for m in metrics)
        neutral_sentiment = sum(m.neutral_sentiment_count for m in metrics)

        avg_duration = float(total_duration / total_calls) if total_calls > 0 else None
        avg_cost = float(total_cost / total_calls) if total_calls > 0 else None
        success_rate = float((completed_calls / total_calls) * 100) if total_calls > 0 else None

        # Average sentiment across all metrics
        sentiment_scores = [m.avg_sentiment_score for m in metrics if m.avg_sentiment_score]
        avg_sentiment = float(sum(sentiment_scores) / len(sentiment_scores)) if sentiment_scores else None

        return CallMetricsResponse(
            total_calls=total_calls,
            completed_calls=completed_calls,
            failed_calls=failed_calls,
            missed_calls=missed_calls,
            total_duration_seconds=total_duration,
            avg_duration_seconds=avg_duration,
            total_cost=float(total_cost),
            avg_cost_per_call=avg_cost,
            success_rate=success_rate,
            avg_sentiment_score=avg_sentiment,
            positive_sentiment_count=positive_sentiment,
            negative_sentiment_count=negative_sentiment,
            neutral_sentiment_count=neutral_sentiment
        )

    except Exception as e:
        logger.error(f"Error getting call metrics: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get call metrics: {str(e)}"
        )


@router.get("/agent-metrics/{agent_id}", response_model=AgentMetricsResponse)
async def get_agent_metrics(
    agent_id: str,
    start_date: date = Query(..., description="Start date"),
    end_date: date = Query(..., description="End date"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get performance metrics for a specific agent.
    """
    try:
        analytics_service = AnalyticsService(db)
        agent_uuid = uuid.UUID(agent_id)

        # Get metrics for the date range and aggregate
        current_date = start_date
        all_metrics = []

        while current_date <= end_date:
            metrics = await analytics_service.aggregate_agent_metrics(
                organization_id=current_user.organization_id,
                agent_id=agent_uuid,
                metric_date=current_date
            )
            all_metrics.append(metrics)
            current_date += timedelta(days=1)

        # Aggregate metrics
        total_interactions = sum(m.total_interactions for m in all_metrics)
        successful = sum(m.successful_interactions for m in all_metrics)
        failed = sum(m.failed_interactions for m in all_metrics)
        total_functions = sum(m.total_function_calls for m in all_metrics)
        successful_functions = sum(m.successful_function_calls for m in all_metrics)
        failed_functions = sum(m.failed_function_calls for m in all_metrics)
        total_cost = sum(m.total_cost for m in all_metrics)

        # Calculate averages
        sentiment_scores = [m.avg_sentiment_score for m in all_metrics if m.avg_sentiment_score]
        avg_sentiment = float(sum(sentiment_scores) / len(sentiment_scores)) if sentiment_scores else None

        positive_pcts = [m.positive_sentiment_percentage for m in all_metrics if m.positive_sentiment_percentage]
        positive_pct = float(sum(positive_pcts) / len(positive_pcts)) if positive_pcts else None

        function_success_rate = float((successful_functions / total_functions) * 100) if total_functions > 0 else None
        cost_per_interaction = float(total_cost / total_interactions) if total_interactions > 0 else None

        return AgentMetricsResponse(
            agent_id=agent_id,
            total_interactions=total_interactions,
            successful_interactions=successful,
            failed_interactions=failed,
            avg_sentiment_score=avg_sentiment,
            positive_sentiment_percentage=positive_pct,
            total_function_calls=total_functions,
            successful_function_calls=successful_functions,
            failed_function_calls=failed_functions,
            function_success_rate=function_success_rate,
            total_cost=float(total_cost),
            cost_per_interaction=cost_per_interaction,
            avg_user_rating=None  # TODO: Add user ratings
        )

    except Exception as e:
        logger.error(f"Error getting agent metrics: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get agent metrics: {str(e)}"
        )


@router.get("/integration-metrics/{integration_id}", response_model=IntegrationMetricsResponse)
async def get_integration_metrics(
    integration_id: str,
    start_date: date = Query(..., description="Start date"),
    end_date: date = Query(..., description="End date"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get health metrics for a specific integration.
    """
    try:
        analytics_service = AnalyticsService(db)
        integration_uuid = uuid.UUID(integration_id)

        # Get metrics for date range
        current_date = start_date
        all_metrics = []

        while current_date <= end_date:
            metrics = await analytics_service.aggregate_integration_metrics(
                organization_id=current_user.organization_id,
                integration_id=integration_uuid,
                metric_date=current_date
            )
            all_metrics.append(metrics)
            current_date += timedelta(days=1)

        # Aggregate
        total_workflows = sum(m.total_workflows_executed for m in all_metrics)
        successful_workflows = sum(m.successful_workflows for m in all_metrics)
        failed_workflows = sum(m.failed_workflows for m in all_metrics)
        total_api_calls = sum(m.total_api_calls for m in all_metrics)
        error_count = sum(m.error_count for m in all_metrics)

        # Averages
        response_times = [m.avg_response_time for m in all_metrics if m.avg_response_time]
        avg_response_time = float(sum(response_times) / len(response_times)) if response_times else None

        health_scores = [m.health_score for m in all_metrics if m.health_score]
        avg_health = float(sum(health_scores) / len(health_scores)) if health_scores else None

        workflow_success_rate = float((successful_workflows / total_workflows) * 100) if total_workflows > 0 else None
        api_success_rate = workflow_success_rate  # Same for now

        return IntegrationMetricsResponse(
            integration_id=integration_id,
            total_workflows_executed=total_workflows,
            successful_workflows=successful_workflows,
            failed_workflows=failed_workflows,
            workflow_success_rate=workflow_success_rate,
            total_api_calls=total_api_calls,
            api_success_rate=api_success_rate,
            avg_response_time_ms=avg_response_time,
            error_count=error_count,
            health_score=avg_health
        )

    except Exception as e:
        logger.error(f"Error getting integration metrics: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get integration metrics: {str(e)}"
        )


@router.get("/daily-summary", response_model=DailySummaryResponse)
async def get_daily_summary(
    summary_date: date = Query(..., description="Summary date"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get comprehensive daily summary.

    Pre-aggregated data for fast dashboard loading.
    """
    try:
        analytics_service = AnalyticsService(db)

        summary = await analytics_service.generate_daily_summary(
            organization_id=current_user.organization_id,
            summary_date=summary_date
        )

        return DailySummaryResponse(
            summary_date=summary.summary_date.isoformat(),
            total_calls=summary.total_calls,
            total_call_minutes=summary.total_call_minutes,
            total_call_cost=float(summary.total_call_cost),
            active_agents_count=summary.active_agents_count,
            total_agent_interactions=summary.total_agent_interactions,
            avg_agent_performance=float(summary.avg_agent_performance) if summary.avg_agent_performance else None,
            active_integrations_count=summary.active_integrations_count,
            total_workflow_executions=summary.total_workflow_executions,
            avg_integration_health=float(summary.avg_integration_health) if summary.avg_integration_health else None,
            avg_sentiment_score=float(summary.avg_sentiment_score) if summary.avg_sentiment_score else None,
            call_success_rate=float(summary.call_success_rate) if summary.call_success_rate else None,
            workflow_success_rate=float(summary.workflow_success_rate) if summary.workflow_success_rate else None,
            top_agents=summary.top_agents,
            call_volume_change=float(summary.call_volume_change) if summary.call_volume_change else None,
            cost_change=float(summary.cost_change) if summary.cost_change else None,
            sentiment_change=float(summary.sentiment_change) if summary.sentiment_change else None
        )

    except Exception as e:
        logger.error(f"Error getting daily summary: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get daily summary: {str(e)}"
        )


@router.get("/realtime", response_model=RealTimeMetricsResponse)
async def get_realtime_metrics(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get real-time metrics for live dashboards.

    Updated every minute for current activity monitoring.
    """
    try:
        analytics_service = AnalyticsService(db)

        metrics = await analytics_service.update_realtime_metrics(
            organization_id=current_user.organization_id
        )

        return RealTimeMetricsResponse(
            current_active_calls=metrics.current_active_calls,
            calls_today=metrics.calls_today,
            calls_last_hour=metrics.calls_last_hour,
            calls_last_5_minutes=metrics.calls_last_5_minutes,
            cost_today=float(metrics.cost_today),
            cost_last_hour=float(metrics.cost_last_hour),
            active_agents=metrics.active_agents,
            active_integrations=metrics.active_integrations,
            system_health=metrics.system_health,
            error_rate_last_hour=float(metrics.error_rate_last_hour) if metrics.error_rate_last_hour else None,
            recent_calls=metrics.recent_calls,
            last_updated=metrics.last_updated.isoformat()
        )

    except Exception as e:
        logger.error(f"Error getting real-time metrics: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get real-time metrics: {str(e)}"
        )


@router.post("/aggregate")
async def trigger_aggregation(
    start_date: date = Query(..., description="Start date"),
    end_date: date = Query(..., description="End date"),
    current_user: User = Depends(get_current_active_user),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: AsyncSession = Depends(get_db),
):
    """
    Trigger metrics aggregation for a date range.

    This endpoint should be called by a scheduled job to pre-aggregate metrics.
    """
    try:
        analytics_service = AnalyticsService(db)

        # Trigger aggregation in background
        background_tasks.add_task(
            analytics_service.aggregate_call_metrics,
            organization_id=current_user.organization_id,
            start_date=start_date,
            end_date=end_date,
            granularity="daily"
        )

        return {
            "message": "Aggregation started",
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat()
        }

    except Exception as e:
        logger.error(f"Error triggering aggregation: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to trigger aggregation: {str(e)}"
        )


@router.get("/dashboard")
async def get_dashboard_summary(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get comprehensive dashboard summary.

    Combines real-time metrics and daily summary for complete overview.
    """
    try:
        analytics_service = AnalyticsService(db)
        today = date.today()

        # Get real-time metrics
        realtime = await analytics_service.update_realtime_metrics(
            organization_id=current_user.organization_id
        )

        # Get today's summary (or generate if doesn't exist)
        summary = await analytics_service.generate_daily_summary(
            organization_id=current_user.organization_id,
            summary_date=today
        )

        return {
            "realtime": {
                "active_calls": realtime.current_active_calls,
                "calls_today": realtime.calls_today,
                "calls_last_hour": realtime.calls_last_hour,
                "cost_today": float(realtime.cost_today),
                "system_health": realtime.system_health,
                "error_rate": float(realtime.error_rate_last_hour) if realtime.error_rate_last_hour else 0,
            },
            "today": {
                "total_calls": summary.total_calls,
                "total_minutes": summary.total_call_minutes,
                "total_cost": float(summary.total_call_cost),
                "success_rate": float(summary.call_success_rate) if summary.call_success_rate else 0,
                "sentiment_score": float(summary.avg_sentiment_score) if summary.avg_sentiment_score else None,
            },
            "agents": {
                "active_count": summary.active_agents_count,
                "total_interactions": summary.total_agent_interactions,
                "top_performers": summary.top_agents[:3],
            },
            "integrations": {
                "active_count": summary.active_integrations_count,
                "total_executions": summary.total_workflow_executions,
                "avg_health": float(summary.avg_integration_health) if summary.avg_integration_health else None,
            },
            "trends": {
                "call_volume_change": float(summary.call_volume_change) if summary.call_volume_change else 0,
                "cost_change": float(summary.cost_change) if summary.cost_change else 0,
                "sentiment_change": float(summary.sentiment_change) if summary.sentiment_change else 0,
            }
        }

    except Exception as e:
        logger.error(f"Error getting dashboard summary: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get dashboard summary: {str(e)}"
        )
