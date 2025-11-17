"""
Analytics Service.

Handles call analytics, metrics, and reporting.
"""
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from dataclasses import dataclass
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_

from app.models.call import Call, CallLog
from app.models.agent import Agent

logger = logging.getLogger(__name__)


@dataclass
class CallMetrics:
    """Call metrics for a specific period."""
    total_calls: int
    completed_calls: int
    failed_calls: int
    total_duration_seconds: int
    average_duration_seconds: float
    total_cost: Decimal
    average_cost: Decimal
    cost_breakdown: Dict[str, Decimal]
    calls_by_direction: Dict[str, int]
    calls_by_status: Dict[str, int]
    peak_hour: Optional[int]
    busiest_day: Optional[str]


@dataclass
class AgentMetrics:
    """Metrics for a specific agent."""
    agent_id: str
    agent_name: str
    total_calls: int
    average_duration: float
    total_cost: Decimal
    success_rate: float
    average_response_time_ms: float
    most_common_topics: List[str]


@dataclass
class CostMetrics:
    """Detailed cost metrics."""
    total_cost: Decimal
    stt_cost: Decimal
    llm_cost: Decimal
    tts_cost: Decimal
    telephony_cost: Decimal
    cost_per_minute: Decimal
    cost_per_call: Decimal
    cost_trend: List[Dict[str, Any]]  # Daily cost trend


class AnalyticsService:
    """
    Service for call analytics and reporting.

    Features:
    - Calculate call metrics
    - Track costs over time
    - Generate reports
    - Identify trends
    - Monitor agent performance
    """

    def __init__(self):
        """Initialize analytics service."""
        pass

    async def get_call_metrics(
        self,
        db: AsyncSession,
        user_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        agent_id: Optional[str] = None,
    ) -> CallMetrics:
        """
        Get call metrics for a period.

        Args:
            db: Database session
            user_id: User ID for filtering
            start_date: Start date (default: 30 days ago)
            end_date: End date (default: now)
            agent_id: Optional agent filter

        Returns:
            Call metrics
        """
        try:
            # Default date range: last 30 days
            if not end_date:
                end_date = datetime.utcnow()
            if not start_date:
                start_date = end_date - timedelta(days=30)

            # Build query
            query = select(Call).where(
                and_(
                    Call.user_id == user_id,
                    Call.created_at >= start_date,
                    Call.created_at <= end_date,
                )
            )

            if agent_id:
                query = query.where(Call.agent_id == agent_id)

            result = await db.execute(query)
            calls = result.scalars().all()

            # Calculate metrics
            total_calls = len(calls)
            completed_calls = sum(1 for c in calls if c.status == "completed")
            failed_calls = sum(1 for c in calls if c.status in ["failed", "no-answer", "busy"])

            total_duration = sum(c.duration_seconds or 0 for c in calls)
            avg_duration = total_duration / total_calls if total_calls > 0 else 0

            total_cost = sum(c.cost_total or 0 for c in calls)
            avg_cost = total_cost / total_calls if total_calls > 0 else 0

            # Cost breakdown
            cost_breakdown = {
                "stt": sum(c.cost_stt or 0 for c in calls),
                "llm": sum(c.cost_llm or 0 for c in calls),
                "tts": sum(c.cost_tts or 0 for c in calls),
                "telephony": sum(c.cost_telephony or 0 for c in calls),
            }

            # Calls by direction
            calls_by_direction = {
                "inbound": sum(1 for c in calls if c.direction == "inbound"),
                "outbound": sum(1 for c in calls if c.direction == "outbound"),
            }

            # Calls by status
            status_counts = {}
            for call in calls:
                status_counts[call.status] = status_counts.get(call.status, 0) + 1

            # Peak hour analysis
            hour_counts = {}
            for call in calls:
                hour = call.created_at.hour
                hour_counts[hour] = hour_counts.get(hour, 0) + 1

            peak_hour = max(hour_counts.items(), key=lambda x: x[1])[0] if hour_counts else None

            # Busiest day analysis
            day_counts = {}
            for call in calls:
                day = call.created_at.strftime("%A")
                day_counts[day] = day_counts.get(day, 0) + 1

            busiest_day = max(day_counts.items(), key=lambda x: x[1])[0] if day_counts else None

            return CallMetrics(
                total_calls=total_calls,
                completed_calls=completed_calls,
                failed_calls=failed_calls,
                total_duration_seconds=total_duration,
                average_duration_seconds=avg_duration,
                total_cost=Decimal(str(total_cost)),
                average_cost=Decimal(str(avg_cost)),
                cost_breakdown=cost_breakdown,
                calls_by_direction=calls_by_direction,
                calls_by_status=status_counts,
                peak_hour=peak_hour,
                busiest_day=busiest_day,
            )

        except Exception as e:
            logger.error(f"Error getting call metrics: {e}", exc_info=True)
            return CallMetrics(
                total_calls=0,
                completed_calls=0,
                failed_calls=0,
                total_duration_seconds=0,
                average_duration_seconds=0.0,
                total_cost=Decimal("0"),
                average_cost=Decimal("0"),
                cost_breakdown={},
                calls_by_direction={},
                calls_by_status={},
                peak_hour=None,
                busiest_day=None,
            )

    async def get_agent_metrics(
        self,
        db: AsyncSession,
        agent_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Optional[AgentMetrics]:
        """
        Get metrics for a specific agent.

        Args:
            db: Database session
            agent_id: Agent ID
            start_date: Start date
            end_date: End date

        Returns:
            Agent metrics or None
        """
        try:
            # Get agent
            agent_result = await db.execute(
                select(Agent).where(Agent.id == agent_id)
            )
            agent = agent_result.scalar_one_or_none()

            if not agent:
                return None

            # Default date range
            if not end_date:
                end_date = datetime.utcnow()
            if not start_date:
                start_date = end_date - timedelta(days=30)

            # Get calls for agent
            result = await db.execute(
                select(Call).where(
                    and_(
                        Call.agent_id == agent_id,
                        Call.created_at >= start_date,
                        Call.created_at <= end_date,
                    )
                )
            )
            calls = result.scalars().all()

            total_calls = len(calls)
            if total_calls == 0:
                return AgentMetrics(
                    agent_id=str(agent_id),
                    agent_name=agent.name,
                    total_calls=0,
                    average_duration=0.0,
                    total_cost=Decimal("0"),
                    success_rate=0.0,
                    average_response_time_ms=0.0,
                    most_common_topics=[],
                )

            # Calculate metrics
            avg_duration = sum(c.duration_seconds or 0 for c in calls) / total_calls
            total_cost = sum(c.cost_total or 0 for c in calls)
            completed = sum(1 for c in calls if c.status == "completed")
            success_rate = (completed / total_calls * 100) if total_calls > 0 else 0

            # Get average response time from call logs
            log_result = await db.execute(
                select(func.avg(CallLog.duration_ms)).where(
                    and_(
                        CallLog.call_id.in_([c.id for c in calls]),
                        CallLog.log_type == "llm",
                    )
                )
            )
            avg_response_time = log_result.scalar() or 0

            # Extract common topics
            topics = []
            for call in calls:
                if call.topics:
                    topics.extend(call.topics)

            topic_counts = {}
            for topic in topics:
                topic_counts[topic] = topic_counts.get(topic, 0) + 1

            most_common = sorted(topic_counts.items(), key=lambda x: x[1], reverse=True)[:5]
            most_common_topics = [topic for topic, _ in most_common]

            return AgentMetrics(
                agent_id=str(agent_id),
                agent_name=agent.name,
                total_calls=total_calls,
                average_duration=avg_duration,
                total_cost=Decimal(str(total_cost)),
                success_rate=success_rate,
                average_response_time_ms=avg_response_time,
                most_common_topics=most_common_topics,
            )

        except Exception as e:
            logger.error(f"Error getting agent metrics: {e}", exc_info=True)
            return None

    async def get_cost_metrics(
        self,
        db: AsyncSession,
        user_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> CostMetrics:
        """
        Get detailed cost metrics.

        Args:
            db: Database session
            user_id: User ID
            start_date: Start date
            end_date: End date

        Returns:
            Cost metrics
        """
        try:
            # Default date range
            if not end_date:
                end_date = datetime.utcnow()
            if not start_date:
                start_date = end_date - timedelta(days=30)

            # Get calls
            result = await db.execute(
                select(Call).where(
                    and_(
                        Call.user_id == user_id,
                        Call.created_at >= start_date,
                        Call.created_at <= end_date,
                    )
                )
            )
            calls = result.scalars().all()

            # Calculate costs
            total_cost = sum(c.cost_total or 0 for c in calls)
            stt_cost = sum(c.cost_stt or 0 for c in calls)
            llm_cost = sum(c.cost_llm or 0 for c in calls)
            tts_cost = sum(c.cost_tts or 0 for c in calls)
            telephony_cost = sum(c.cost_telephony or 0 for c in calls)

            # Calculate averages
            total_minutes = sum(c.duration_seconds or 0 for c in calls) / 60
            cost_per_minute = total_cost / total_minutes if total_minutes > 0 else 0

            total_calls = len(calls)
            cost_per_call = total_cost / total_calls if total_calls > 0 else 0

            # Calculate daily cost trend
            cost_trend = await self._get_daily_cost_trend(calls, start_date, end_date)

            return CostMetrics(
                total_cost=Decimal(str(total_cost)),
                stt_cost=Decimal(str(stt_cost)),
                llm_cost=Decimal(str(llm_cost)),
                tts_cost=Decimal(str(tts_cost)),
                telephony_cost=Decimal(str(telephony_cost)),
                cost_per_minute=Decimal(str(cost_per_minute)),
                cost_per_call=Decimal(str(cost_per_call)),
                cost_trend=cost_trend,
            )

        except Exception as e:
            logger.error(f"Error getting cost metrics: {e}", exc_info=True)
            return CostMetrics(
                total_cost=Decimal("0"),
                stt_cost=Decimal("0"),
                llm_cost=Decimal("0"),
                tts_cost=Decimal("0"),
                telephony_cost=Decimal("0"),
                cost_per_minute=Decimal("0"),
                cost_per_call=Decimal("0"),
                cost_trend=[],
            )

    async def _get_daily_cost_trend(
        self,
        calls: List[Call],
        start_date: datetime,
        end_date: datetime,
    ) -> List[Dict[str, Any]]:
        """
        Calculate daily cost trend.

        Args:
            calls: List of calls
            start_date: Start date
            end_date: End date

        Returns:
            List of daily costs
        """
        # Group calls by date
        daily_costs = {}

        for call in calls:
            date = call.created_at.date()
            if date not in daily_costs:
                daily_costs[date] = {
                    "date": date.isoformat(),
                    "total_cost": 0,
                    "call_count": 0,
                    "stt_cost": 0,
                    "llm_cost": 0,
                    "tts_cost": 0,
                    "telephony_cost": 0,
                }

            daily_costs[date]["total_cost"] += float(call.cost_total or 0)
            daily_costs[date]["call_count"] += 1
            daily_costs[date]["stt_cost"] += float(call.cost_stt or 0)
            daily_costs[date]["llm_cost"] += float(call.cost_llm or 0)
            daily_costs[date]["tts_cost"] += float(call.cost_tts or 0)
            daily_costs[date]["telephony_cost"] += float(call.cost_telephony or 0)

        # Sort by date
        trend = sorted(daily_costs.values(), key=lambda x: x["date"])

        return trend

    async def calculate_call_cost(
        self,
        call: Call,
        stt_cost: Decimal = Decimal("0"),
        llm_cost: Decimal = Decimal("0"),
        tts_cost: Decimal = Decimal("0"),
    ) -> Decimal:
        """
        Calculate total cost for a call.

        Args:
            call: Call record
            stt_cost: STT cost
            llm_cost: LLM cost
            tts_cost: TTS cost

        Returns:
            Total cost
        """
        # Calculate telephony cost if not set
        telephony_cost = call.cost_telephony or Decimal("0")

        if not telephony_cost and call.duration_seconds:
            # Twilio pricing
            minutes = Decimal(str(call.duration_seconds)) / 60

            if call.direction == "inbound":
                telephony_cost = minutes * Decimal("0.0085")
            else:  # outbound
                telephony_cost = minutes * Decimal("0.0140")

        # Total cost
        total_cost = stt_cost + llm_cost + tts_cost + telephony_cost

        return total_cost

    async def export_analytics(
        self,
        db: AsyncSession,
        user_id: str,
        start_date: datetime,
        end_date: datetime,
        format: str = "json",
    ) -> Dict[str, Any]:
        """
        Export analytics data.

        Args:
            db: Database session
            user_id: User ID
            start_date: Start date
            end_date: End date
            format: Export format (json, csv)

        Returns:
            Export data
        """
        try:
            # Get all metrics
            call_metrics = await self.get_call_metrics(db, user_id, start_date, end_date)
            cost_metrics = await self.get_cost_metrics(db, user_id, start_date, end_date)

            export_data = {
                "period": {
                    "start": start_date.isoformat(),
                    "end": end_date.isoformat(),
                },
                "call_metrics": {
                    "total_calls": call_metrics.total_calls,
                    "completed_calls": call_metrics.completed_calls,
                    "failed_calls": call_metrics.failed_calls,
                    "total_duration_seconds": call_metrics.total_duration_seconds,
                    "average_duration_seconds": call_metrics.average_duration_seconds,
                    "calls_by_direction": call_metrics.calls_by_direction,
                    "calls_by_status": call_metrics.calls_by_status,
                    "peak_hour": call_metrics.peak_hour,
                    "busiest_day": call_metrics.busiest_day,
                },
                "cost_metrics": {
                    "total_cost": float(cost_metrics.total_cost),
                    "stt_cost": float(cost_metrics.stt_cost),
                    "llm_cost": float(cost_metrics.llm_cost),
                    "tts_cost": float(cost_metrics.tts_cost),
                    "telephony_cost": float(cost_metrics.telephony_cost),
                    "cost_per_minute": float(cost_metrics.cost_per_minute),
                    "cost_per_call": float(cost_metrics.cost_per_call),
                    "cost_trend": cost_metrics.cost_trend,
                },
            }

            logger.info(f"Exported analytics for user {user_id}")

            return export_data

        except Exception as e:
            logger.error(f"Error exporting analytics: {e}", exc_info=True)
            return {}


# Global analytics service instance
_analytics_service: Optional[AnalyticsService] = None


def get_analytics_service() -> AnalyticsService:
    """
    Get global analytics service instance (singleton).

    Returns:
        AnalyticsService instance
    """
    global _analytics_service
    if _analytics_service is None:
        _analytics_service = AnalyticsService()
    return _analytics_service
