"""
Analytics aggregation and metrics calculation service.
"""
import uuid
from datetime import datetime, date, timedelta
from typing import List, Optional, Dict, Any
from decimal import Decimal
from sqlalchemy import select, func, and_, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.analytics import (
    CallMetrics, AgentMetrics, IntegrationMetrics,
    DailySummary, RealTimeMetrics, MetricsCache
)
from app.models.call import Call, CallLog
from app.models.agent import Agent
from app.models.integration import Workflow, WorkflowExecution


class AnalyticsService:
    """
    Service for analytics aggregation and metrics calculation.
    Handles pre-aggregation for performance optimization.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    # ==================== CALL METRICS ====================

    async def aggregate_call_metrics(
        self,
        organization_id: uuid.UUID,
        start_date: date,
        end_date: date,
        granularity: str = "daily",
        agent_id: Optional[uuid.UUID] = None
    ) -> List[CallMetrics]:
        """
        Aggregate call metrics for a date range.

        Args:
            organization_id: Organization UUID
            start_date: Start date for aggregation
            end_date: End date for aggregation
            granularity: 'hourly' or 'daily'
            agent_id: Optional agent filter

        Returns:
            List of CallMetrics records
        """
        metrics = []
        current_date = start_date

        while current_date <= end_date:
            if granularity == "hourly":
                # Aggregate hourly metrics
                for hour in range(24):
                    metric = await self._aggregate_call_metrics_for_hour(
                        organization_id=organization_id,
                        metric_date=current_date,
                        metric_hour=hour,
                        agent_id=agent_id
                    )
                    if metric:
                        metrics.append(metric)
            else:
                # Aggregate daily metrics
                metric = await self._aggregate_call_metrics_for_day(
                    organization_id=organization_id,
                    metric_date=current_date,
                    agent_id=agent_id
                )
                if metric:
                    metrics.append(metric)

            current_date += timedelta(days=1)

        return metrics

    async def _aggregate_call_metrics_for_day(
        self,
        organization_id: uuid.UUID,
        metric_date: date,
        agent_id: Optional[uuid.UUID] = None
    ) -> Optional[CallMetrics]:
        """Aggregate call metrics for a single day."""

        # Build query for calls on this day
        query = select(
            func.count(Call.id).label('total_calls'),
            func.count(Call.id).filter(Call.status == 'completed').label('completed_calls'),
            func.count(Call.id).filter(Call.status == 'failed').label('failed_calls'),
            func.count(Call.id).filter(Call.status == 'missed').label('missed_calls'),
            func.sum(Call.duration).label('total_duration'),
            func.avg(Call.duration).label('avg_duration'),
            func.max(Call.duration).label('max_duration'),
            func.min(Call.duration).label('min_duration'),
            func.sum(Call.cost).label('total_cost'),
            func.avg(Call.cost).label('avg_cost_per_call'),
            func.avg(Call.sentiment_score).label('avg_sentiment_score'),
            func.count(Call.id).filter(Call.sentiment_score > 0.6).label('positive_sentiment'),
            func.count(Call.id).filter(Call.sentiment_score < 0.4).label('negative_sentiment'),
            func.count(Call.id).filter(
                and_(Call.sentiment_score >= 0.4, Call.sentiment_score <= 0.6)
            ).label('neutral_sentiment'),
        ).where(
            and_(
                Call.organization_id == organization_id,
                func.date(Call.started_at) == metric_date
            )
        )

        if agent_id:
            query = query.where(Call.agent_id == agent_id)

        result = await self.db.execute(query)
        row = result.first()

        if not row or row.total_calls == 0:
            return None

        # Calculate success rate
        success_rate = None
        if row.total_calls > 0:
            success_rate = Decimal(row.completed_calls / row.total_calls * 100)

        # Check if metric already exists
        existing = await self.db.execute(
            select(CallMetrics).where(
                and_(
                    CallMetrics.organization_id == organization_id,
                    CallMetrics.metric_date == metric_date,
                    CallMetrics.granularity == 'daily',
                    CallMetrics.agent_id == agent_id if agent_id else CallMetrics.agent_id.is_(None)
                )
            )
        )
        metric = existing.scalar_one_or_none()

        if metric:
            # Update existing metric
            metric.total_calls = row.total_calls
            metric.completed_calls = row.completed_calls
            metric.failed_calls = row.failed_calls
            metric.missed_calls = row.missed_calls
            metric.total_duration = row.total_duration or 0
            metric.avg_duration = row.avg_duration
            metric.max_duration = row.max_duration
            metric.min_duration = row.min_duration
            metric.total_cost = row.total_cost or Decimal(0)
            metric.avg_cost_per_call = row.avg_cost_per_call
            metric.avg_sentiment_score = row.avg_sentiment_score
            metric.positive_sentiment_count = row.positive_sentiment
            metric.negative_sentiment_count = row.negative_sentiment
            metric.neutral_sentiment_count = row.neutral_sentiment
            metric.success_rate = success_rate
        else:
            # Create new metric
            metric = CallMetrics(
                organization_id=organization_id,
                agent_id=agent_id,
                metric_date=metric_date,
                granularity='daily',
                total_calls=row.total_calls,
                completed_calls=row.completed_calls,
                failed_calls=row.failed_calls,
                missed_calls=row.missed_calls,
                total_duration=row.total_duration or 0,
                avg_duration=row.avg_duration,
                max_duration=row.max_duration,
                min_duration=row.min_duration,
                total_cost=row.total_cost or Decimal(0),
                avg_cost_per_call=row.avg_cost_per_call,
                avg_sentiment_score=row.avg_sentiment_score,
                positive_sentiment_count=row.positive_sentiment,
                negative_sentiment_count=row.negative_sentiment,
                neutral_sentiment_count=row.neutral_sentiment,
                success_rate=success_rate
            )
            self.db.add(metric)

        await self.db.commit()
        await self.db.refresh(metric)
        return metric

    async def _aggregate_call_metrics_for_hour(
        self,
        organization_id: uuid.UUID,
        metric_date: date,
        metric_hour: int,
        agent_id: Optional[uuid.UUID] = None
    ) -> Optional[CallMetrics]:
        """Aggregate call metrics for a single hour."""

        start_time = datetime.combine(metric_date, datetime.min.time()).replace(hour=metric_hour)
        end_time = start_time + timedelta(hours=1)

        # Similar query as daily but filtered by hour
        query = select(
            func.count(Call.id).label('total_calls'),
            func.count(Call.id).filter(Call.status == 'completed').label('completed_calls'),
            func.count(Call.id).filter(Call.status == 'failed').label('failed_calls'),
            func.sum(Call.duration).label('total_duration'),
            func.avg(Call.duration).label('avg_duration'),
            func.sum(Call.cost).label('total_cost'),
            func.avg(Call.sentiment_score).label('avg_sentiment_score'),
        ).where(
            and_(
                Call.organization_id == organization_id,
                Call.started_at >= start_time,
                Call.started_at < end_time
            )
        )

        if agent_id:
            query = query.where(Call.agent_id == agent_id)

        result = await self.db.execute(query)
        row = result.first()

        if not row or row.total_calls == 0:
            return None

        # Check if metric already exists
        existing = await self.db.execute(
            select(CallMetrics).where(
                and_(
                    CallMetrics.organization_id == organization_id,
                    CallMetrics.metric_date == metric_date,
                    CallMetrics.metric_hour == metric_hour,
                    CallMetrics.granularity == 'hourly',
                    CallMetrics.agent_id == agent_id if agent_id else CallMetrics.agent_id.is_(None)
                )
            )
        )
        metric = existing.scalar_one_or_none()

        if metric:
            metric.total_calls = row.total_calls
            metric.completed_calls = row.completed_calls
            metric.failed_calls = row.failed_calls
            metric.total_duration = row.total_duration or 0
            metric.avg_duration = row.avg_duration
            metric.total_cost = row.total_cost or Decimal(0)
            metric.avg_sentiment_score = row.avg_sentiment_score
        else:
            metric = CallMetrics(
                organization_id=organization_id,
                agent_id=agent_id,
                metric_date=metric_date,
                metric_hour=metric_hour,
                granularity='hourly',
                total_calls=row.total_calls,
                completed_calls=row.completed_calls,
                failed_calls=row.failed_calls,
                total_duration=row.total_duration or 0,
                avg_duration=row.avg_duration,
                total_cost=row.total_cost or Decimal(0),
                avg_sentiment_score=row.avg_sentiment_score
            )
            self.db.add(metric)

        await self.db.commit()
        await self.db.refresh(metric)
        return metric

    # ==================== AGENT METRICS ====================

    async def aggregate_agent_metrics(
        self,
        organization_id: uuid.UUID,
        agent_id: uuid.UUID,
        metric_date: date
    ) -> AgentMetrics:
        """Aggregate performance metrics for a specific agent."""

        # Query agent interactions (calls)
        calls_query = select(
            func.count(Call.id).label('total_interactions'),
            func.count(Call.id).filter(Call.status == 'completed').label('successful'),
            func.count(Call.id).filter(Call.status == 'failed').label('failed'),
            func.avg(Call.sentiment_score).label('avg_sentiment'),
            func.sum(Call.cost).label('total_cost'),
        ).where(
            and_(
                Call.agent_id == agent_id,
                Call.organization_id == organization_id,
                func.date(Call.started_at) == metric_date
            )
        )

        result = await self.db.execute(calls_query)
        row = result.first()

        # Calculate function call metrics from call logs
        function_query = select(
            func.count(CallLog.id).filter(CallLog.event_type == 'function_call').label('total_functions'),
            func.count(CallLog.id).filter(
                and_(
                    CallLog.event_type == 'function_call',
                    CallLog.metadata['success'].astext.cast(Boolean) == True
                )
            ).label('successful_functions'),
        ).join(Call).where(
            and_(
                Call.agent_id == agent_id,
                Call.organization_id == organization_id,
                func.date(Call.started_at) == metric_date
            )
        )

        func_result = await self.db.execute(function_query)
        func_row = func_result.first()

        # Calculate success rates
        function_success_rate = None
        if func_row and func_row.total_functions > 0:
            function_success_rate = Decimal(
                func_row.successful_functions / func_row.total_functions * 100
            )

        positive_sentiment_pct = None
        if row and row.total_interactions > 0 and row.avg_sentiment:
            # Calculate percentage of positive sentiments
            positive_count_query = select(
                func.count(Call.id).filter(Call.sentiment_score > 0.6)
            ).where(
                and_(
                    Call.agent_id == agent_id,
                    Call.organization_id == organization_id,
                    func.date(Call.started_at) == metric_date
                )
            )
            pos_result = await self.db.execute(positive_count_query)
            positive_count = pos_result.scalar() or 0
            positive_sentiment_pct = Decimal(positive_count / row.total_interactions * 100)

        cost_per_interaction = None
        if row and row.total_interactions > 0 and row.total_cost:
            cost_per_interaction = row.total_cost / row.total_interactions

        # Check if metric exists
        existing = await self.db.execute(
            select(AgentMetrics).where(
                and_(
                    AgentMetrics.agent_id == agent_id,
                    AgentMetrics.metric_date == metric_date,
                    AgentMetrics.granularity == 'daily'
                )
            )
        )
        metric = existing.scalar_one_or_none()

        if metric:
            metric.total_interactions = row.total_interactions if row else 0
            metric.successful_interactions = row.successful if row else 0
            metric.failed_interactions = row.failed if row else 0
            metric.avg_sentiment_score = row.avg_sentiment if row else None
            metric.positive_sentiment_percentage = positive_sentiment_pct
            metric.total_function_calls = func_row.total_functions if func_row else 0
            metric.successful_function_calls = func_row.successful_functions if func_row else 0
            metric.failed_function_calls = (
                (func_row.total_functions - func_row.successful_functions) if func_row else 0
            )
            metric.function_success_rate = function_success_rate
            metric.total_cost = row.total_cost or Decimal(0) if row else Decimal(0)
            metric.cost_per_interaction = cost_per_interaction
        else:
            metric = AgentMetrics(
                organization_id=organization_id,
                agent_id=agent_id,
                metric_date=metric_date,
                granularity='daily',
                total_interactions=row.total_interactions if row else 0,
                successful_interactions=row.successful if row else 0,
                failed_interactions=row.failed if row else 0,
                avg_sentiment_score=row.avg_sentiment if row else None,
                positive_sentiment_percentage=positive_sentiment_pct,
                total_function_calls=func_row.total_functions if func_row else 0,
                successful_function_calls=func_row.successful_functions if func_row else 0,
                failed_function_calls=(
                    (func_row.total_functions - func_row.successful_functions) if func_row else 0
                ),
                function_success_rate=function_success_rate,
                total_cost=row.total_cost or Decimal(0) if row else Decimal(0),
                cost_per_interaction=cost_per_interaction
            )
            self.db.add(metric)

        await self.db.commit()
        await self.db.refresh(metric)
        return metric

    # ==================== INTEGRATION METRICS ====================

    async def aggregate_integration_metrics(
        self,
        organization_id: uuid.UUID,
        integration_id: uuid.UUID,
        metric_date: date
    ) -> IntegrationMetrics:
        """Aggregate metrics for a specific integration."""

        # Query workflow executions
        workflows_query = select(
            func.count(WorkflowExecution.id).label('total_workflows'),
            func.count(WorkflowExecution.id).filter(
                WorkflowExecution.status == 'completed'
            ).label('successful_workflows'),
            func.count(WorkflowExecution.id).filter(
                WorkflowExecution.status == 'failed'
            ).label('failed_workflows'),
            func.avg(WorkflowExecution.execution_time).label('avg_response_time'),
            func.max(WorkflowExecution.execution_time).label('max_response_time'),
            func.min(WorkflowExecution.execution_time).label('min_response_time'),
            func.count(WorkflowExecution.id).filter(
                WorkflowExecution.error_message.isnot(None)
            ).label('error_count'),
        ).join(Workflow).where(
            and_(
                Workflow.integration_id == integration_id,
                Workflow.organization_id == organization_id,
                func.date(WorkflowExecution.started_at) == metric_date
            )
        )

        result = await self.db.execute(workflows_query)
        row = result.first()

        # Calculate success rates
        workflow_success_rate = None
        api_success_rate = None
        if row and row.total_workflows > 0:
            workflow_success_rate = Decimal(
                row.successful_workflows / row.total_workflows * 100
            )
            api_success_rate = workflow_success_rate  # Same for now

        # Calculate health score (0-100)
        health_score = None
        if row and row.total_workflows > 0:
            # Health score based on success rate and response time
            success_factor = workflow_success_rate or Decimal(0)

            # Response time factor (assume <1000ms is excellent)
            response_factor = Decimal(100)
            if row.avg_response_time:
                if row.avg_response_time > 5000:
                    response_factor = Decimal(50)
                elif row.avg_response_time > 2000:
                    response_factor = Decimal(75)

            health_score = (success_factor * Decimal(0.7)) + (response_factor * Decimal(0.3))

        # Check if metric exists
        existing = await self.db.execute(
            select(IntegrationMetrics).where(
                and_(
                    IntegrationMetrics.integration_id == integration_id,
                    IntegrationMetrics.metric_date == metric_date,
                    IntegrationMetrics.granularity == 'daily'
                )
            )
        )
        metric = existing.scalar_one_or_none()

        if metric:
            metric.total_workflows_executed = row.total_workflows if row else 0
            metric.successful_workflows = row.successful_workflows if row else 0
            metric.failed_workflows = row.failed_workflows if row else 0
            metric.workflow_success_rate = workflow_success_rate
            metric.total_api_calls = row.total_workflows if row else 0
            metric.successful_api_calls = row.successful_workflows if row else 0
            metric.failed_api_calls = row.failed_workflows if row else 0
            metric.api_success_rate = api_success_rate
            metric.avg_response_time = row.avg_response_time if row else None
            metric.max_response_time = row.max_response_time if row else None
            metric.min_response_time = row.min_response_time if row else None
            metric.error_count = row.error_count if row else 0
            metric.health_score = health_score
        else:
            metric = IntegrationMetrics(
                organization_id=organization_id,
                integration_id=integration_id,
                metric_date=metric_date,
                granularity='daily',
                total_workflows_executed=row.total_workflows if row else 0,
                successful_workflows=row.successful_workflows if row else 0,
                failed_workflows=row.failed_workflows if row else 0,
                workflow_success_rate=workflow_success_rate,
                total_api_calls=row.total_workflows if row else 0,
                successful_api_calls=row.successful_workflows if row else 0,
                failed_api_calls=row.failed_workflows if row else 0,
                api_success_rate=api_success_rate,
                avg_response_time=row.avg_response_time if row else None,
                max_response_time=row.max_response_time if row else None,
                min_response_time=row.min_response_time if row else None,
                error_count=row.error_count if row else 0,
                health_score=health_score
            )
            self.db.add(metric)

        await self.db.commit()
        await self.db.refresh(metric)
        return metric

    # ==================== DAILY SUMMARY ====================

    async def generate_daily_summary(
        self,
        organization_id: uuid.UUID,
        summary_date: date
    ) -> DailySummary:
        """
        Generate comprehensive daily summary.
        Aggregates all metrics into a single summary record.
        """

        # Get or create summary
        existing = await self.db.execute(
            select(DailySummary).where(
                and_(
                    DailySummary.organization_id == organization_id,
                    DailySummary.summary_date == summary_date
                )
            )
        )
        summary = existing.scalar_one_or_none()

        if not summary:
            summary = DailySummary(
                organization_id=organization_id,
                summary_date=summary_date
            )
            self.db.add(summary)

        # Aggregate call metrics
        call_metrics_query = select(
            func.sum(CallMetrics.total_calls).label('total_calls'),
            func.sum(CallMetrics.total_duration).label('total_minutes'),
            func.sum(CallMetrics.total_cost).label('total_cost'),
            func.avg(CallMetrics.success_rate).label('success_rate'),
            func.avg(CallMetrics.avg_sentiment_score).label('avg_sentiment'),
        ).where(
            and_(
                CallMetrics.organization_id == organization_id,
                CallMetrics.metric_date == summary_date,
                CallMetrics.granularity == 'daily',
                CallMetrics.agent_id.is_(None)  # Only organization-wide metrics
            )
        )

        call_result = await self.db.execute(call_metrics_query)
        call_row = call_result.first()

        # Aggregate agent metrics
        agent_metrics_query = select(
            func.count(func.distinct(AgentMetrics.agent_id)).label('active_agents'),
            func.sum(AgentMetrics.total_interactions).label('total_interactions'),
            func.avg(AgentMetrics.function_success_rate).label('avg_performance'),
            func.avg(AgentMetrics.avg_user_rating).label('avg_rating'),
        ).where(
            and_(
                AgentMetrics.organization_id == organization_id,
                AgentMetrics.metric_date == summary_date
            )
        )

        agent_result = await self.db.execute(agent_metrics_query)
        agent_row = agent_result.first()

        # Aggregate integration metrics
        integration_metrics_query = select(
            func.count(func.distinct(IntegrationMetrics.integration_id)).label('active_integrations'),
            func.sum(IntegrationMetrics.total_workflows_executed).label('total_workflows'),
            func.avg(IntegrationMetrics.health_score).label('avg_health'),
            func.avg(IntegrationMetrics.workflow_success_rate).label('workflow_success_rate'),
        ).where(
            and_(
                IntegrationMetrics.organization_id == organization_id,
                IntegrationMetrics.metric_date == summary_date
            )
        )

        int_result = await self.db.execute(integration_metrics_query)
        int_row = int_result.first()

        # Get top performing agents
        top_agents_query = select(
            AgentMetrics.agent_id,
            Agent.name,
            AgentMetrics.total_interactions,
            AgentMetrics.avg_sentiment_score
        ).join(Agent).where(
            and_(
                AgentMetrics.organization_id == organization_id,
                AgentMetrics.metric_date == summary_date
            )
        ).order_by(desc(AgentMetrics.total_interactions)).limit(5)

        top_agents_result = await self.db.execute(top_agents_query)
        top_agents = [
            {
                'agent_id': str(row.agent_id),
                'name': row.name,
                'interactions': row.total_interactions,
                'sentiment': float(row.avg_sentiment_score) if row.avg_sentiment_score else None
            }
            for row in top_agents_result
        ]

        # Calculate trends (compare to previous day)
        prev_date = summary_date - timedelta(days=1)
        prev_summary_query = select(DailySummary).where(
            and_(
                DailySummary.organization_id == organization_id,
                DailySummary.summary_date == prev_date
            )
        )
        prev_summary_result = await self.db.execute(prev_summary_query)
        prev_summary = prev_summary_result.scalar_one_or_none()

        call_volume_change = None
        cost_change = None
        sentiment_change = None

        if prev_summary and call_row:
            if prev_summary.total_calls and call_row.total_calls:
                call_volume_change = Decimal(
                    ((call_row.total_calls - prev_summary.total_calls) / prev_summary.total_calls) * 100
                )
            if prev_summary.total_call_cost and call_row.total_cost:
                cost_change = Decimal(
                    ((call_row.total_cost - prev_summary.total_call_cost) / prev_summary.total_call_cost) * 100
                )
            if prev_summary.avg_sentiment_score and call_row.avg_sentiment:
                sentiment_change = Decimal(
                    ((call_row.avg_sentiment - prev_summary.avg_sentiment_score) / prev_summary.avg_sentiment_score) * 100
                )

        # Update summary
        summary.total_calls = call_row.total_calls or 0 if call_row else 0
        summary.total_call_minutes = (call_row.total_minutes // 60) if call_row and call_row.total_minutes else 0
        summary.total_call_cost = call_row.total_cost or Decimal(0) if call_row else Decimal(0)
        summary.call_success_rate = call_row.success_rate if call_row else None
        summary.avg_sentiment_score = call_row.avg_sentiment if call_row else None

        summary.active_agents_count = agent_row.active_agents or 0 if agent_row else 0
        summary.total_agent_interactions = agent_row.total_interactions or 0 if agent_row else 0
        summary.avg_agent_performance = agent_row.avg_performance if agent_row else None
        summary.avg_user_rating = agent_row.avg_rating if agent_row else None

        summary.active_integrations_count = int_row.active_integrations or 0 if int_row else 0
        summary.total_workflow_executions = int_row.total_workflows or 0 if int_row else 0
        summary.avg_integration_health = int_row.avg_health if int_row else None
        summary.workflow_success_rate = int_row.workflow_success_rate if int_row else None

        summary.top_agents = top_agents
        summary.call_volume_change = call_volume_change
        summary.cost_change = cost_change
        summary.sentiment_change = sentiment_change

        await self.db.commit()
        await self.db.refresh(summary)
        return summary

    # ==================== REAL-TIME METRICS ====================

    async def update_realtime_metrics(
        self,
        organization_id: uuid.UUID
    ) -> RealTimeMetrics:
        """
        Update real-time metrics for live dashboards.
        Should be called every minute via background task.
        """

        now = datetime.utcnow()
        today = now.date()
        one_hour_ago = now - timedelta(hours=1)
        five_min_ago = now - timedelta(minutes=5)

        # Get or create real-time metrics
        existing = await self.db.execute(
            select(RealTimeMetrics).where(
                RealTimeMetrics.organization_id == organization_id
            )
        )
        metrics = existing.scalar_one_or_none()

        if not metrics:
            metrics = RealTimeMetrics(organization_id=organization_id)
            self.db.add(metrics)

        # Count active calls
        active_calls_query = select(func.count(Call.id)).where(
            and_(
                Call.organization_id == organization_id,
                Call.status == 'in_progress'
            )
        )
        active_calls = await self.db.execute(active_calls_query)
        metrics.current_active_calls = active_calls.scalar() or 0

        # Calls today
        calls_today_query = select(func.count(Call.id)).where(
            and_(
                Call.organization_id == organization_id,
                func.date(Call.started_at) == today
            )
        )
        calls_today = await self.db.execute(calls_today_query)
        metrics.calls_today = calls_today.scalar() or 0

        # Calls last hour
        calls_hour_query = select(
            func.count(Call.id).label('count'),
            func.sum(Call.cost).label('cost')
        ).where(
            and_(
                Call.organization_id == organization_id,
                Call.started_at >= one_hour_ago
            )
        )
        calls_hour = await self.db.execute(calls_hour_query)
        hour_row = calls_hour.first()
        metrics.calls_last_hour = hour_row.count or 0 if hour_row else 0
        metrics.cost_last_hour = hour_row.cost or Decimal(0) if hour_row else Decimal(0)

        # Calls last 5 minutes
        calls_5min_query = select(func.count(Call.id)).where(
            and_(
                Call.organization_id == organization_id,
                Call.started_at >= five_min_ago
            )
        )
        calls_5min = await self.db.execute(calls_5min_query)
        metrics.calls_last_5_minutes = calls_5min.scalar() or 0

        # Cost today
        cost_today_query = select(func.sum(Call.cost)).where(
            and_(
                Call.organization_id == organization_id,
                func.date(Call.started_at) == today
            )
        )
        cost_today = await self.db.execute(cost_today_query)
        metrics.cost_today = cost_today.scalar() or Decimal(0)

        # Active resources
        active_agents_query = select(func.count(func.distinct(Call.agent_id))).where(
            and_(
                Call.organization_id == organization_id,
                Call.started_at >= one_hour_ago
            )
        )
        active_agents = await self.db.execute(active_agents_query)
        metrics.active_agents = active_agents.scalar() or 0

        # System health (based on error rate)
        failed_calls_hour = await self.db.execute(
            select(func.count(Call.id)).where(
                and_(
                    Call.organization_id == organization_id,
                    Call.started_at >= one_hour_ago,
                    Call.status == 'failed'
                )
            )
        )
        failed_count = failed_calls_hour.scalar() or 0

        error_rate = None
        if metrics.calls_last_hour > 0:
            error_rate = Decimal((failed_count / metrics.calls_last_hour) * 100)
            metrics.error_rate_last_hour = error_rate

            # Determine system health
            if error_rate > 10:
                metrics.system_health = 'down'
            elif error_rate > 5:
                metrics.system_health = 'degraded'
            else:
                metrics.system_health = 'healthy'
        else:
            metrics.system_health = 'healthy'

        # Get recent calls
        recent_calls_query = select(
            Call.id,
            Call.status,
            Call.duration,
            Call.started_at,
            Agent.name.label('agent_name')
        ).join(Agent, Call.agent_id == Agent.id, isouter=True).where(
            Call.organization_id == organization_id
        ).order_by(desc(Call.started_at)).limit(10)

        recent_calls_result = await self.db.execute(recent_calls_query)
        metrics.recent_calls = [
            {
                'id': str(row.id),
                'status': row.status,
                'duration': row.duration,
                'started_at': row.started_at.isoformat() if row.started_at else None,
                'agent_name': row.agent_name
            }
            for row in recent_calls_result
        ]

        await self.db.commit()
        await self.db.refresh(metrics)
        return metrics

    # ==================== CACHE MANAGEMENT ====================

    async def get_cached_metric(
        self,
        organization_id: uuid.UUID,
        cache_key: str
    ) -> Optional[Dict[str, Any]]:
        """Get cached metric if not expired."""

        result = await self.db.execute(
            select(MetricsCache).where(
                and_(
                    MetricsCache.organization_id == organization_id,
                    MetricsCache.cache_key == cache_key,
                    MetricsCache.expires_at > datetime.utcnow()
                )
            )
        )
        cache = result.scalar_one_or_none()

        if cache:
            cache.hit_count += 1
            await self.db.commit()
            return cache.data

        return None

    async def set_cached_metric(
        self,
        organization_id: uuid.UUID,
        cache_key: str,
        data: Dict[str, Any],
        ttl_minutes: int = 60
    ) -> MetricsCache:
        """Set cached metric with expiration."""

        expires_at = datetime.utcnow() + timedelta(minutes=ttl_minutes)

        # Check if cache exists
        existing = await self.db.execute(
            select(MetricsCache).where(
                and_(
                    MetricsCache.organization_id == organization_id,
                    MetricsCache.cache_key == cache_key
                )
            )
        )
        cache = existing.scalar_one_or_none()

        if cache:
            cache.data = data
            cache.expires_at = expires_at
        else:
            cache = MetricsCache(
                organization_id=organization_id,
                cache_key=cache_key,
                data=data,
                expires_at=expires_at
            )
            self.db.add(cache)

        await self.db.commit()
        await self.db.refresh(cache)
        return cache

    async def clear_expired_cache(self) -> int:
        """Clear expired cache entries. Returns number of entries cleared."""

        result = await self.db.execute(
            select(MetricsCache).where(
                MetricsCache.expires_at <= datetime.utcnow()
            )
        )
        expired = result.scalars().all()

        count = len(expired)
        for cache in expired:
            await self.db.delete(cache)

        await self.db.commit()
        return count
