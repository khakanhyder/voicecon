"""
Workflow Scheduler.

Handles scheduled workflow triggers (cron, interval, one-time).
"""
import logging
import asyncio
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from croniter import croniter
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.workflow import TriggerType
from app.core.database import async_session_maker

logger = logging.getLogger(__name__)


class WorkflowScheduler:
    """
    Scheduler for workflow triggers.

    Supports:
    - Cron expressions
    - Fixed intervals
    - One-time scheduled execution
    """

    def __init__(self):
        """Initialize workflow scheduler."""
        self._running = False
        self._tasks = {}

    async def start(self) -> None:
        """Start the scheduler."""
        if self._running:
            logger.warning("Scheduler already running")
            return

        self._running = True
        logger.info("Starting workflow scheduler")

        # Start scheduler loop
        asyncio.create_task(self._scheduler_loop())

    async def stop(self) -> None:
        """Stop the scheduler."""
        logger.info("Stopping workflow scheduler")
        self._running = False

        # Cancel all running tasks
        for task_id, task in self._tasks.items():
            if not task.done():
                task.cancel()

        self._tasks.clear()

    async def _scheduler_loop(self) -> None:
        """Main scheduler loop."""
        while self._running:
            try:
                async with async_session_maker() as db:
                    await self._check_scheduled_workflows(db)
            except Exception as e:
                logger.error(f"Scheduler loop error: {e}", exc_info=True)

            # Check every 30 seconds
            await asyncio.sleep(30)

    async def _check_scheduled_workflows(self, db: AsyncSession) -> None:
        """
        Check for workflows that need to be triggered.

        Args:
            db: Database session
        """
        from app.models.integration import Workflow

        # Get all active scheduled workflows
        query = select(Workflow).where(
            and_(
                Workflow.trigger_type == TriggerType.SCHEDULE,
                Workflow.is_active == True,
            )
        )
        result = await db.execute(query)
        workflows = result.scalars().all()

        now = datetime.utcnow()

        for workflow in workflows:
            try:
                config = workflow.trigger_config
                schedule_type = config.get("schedule_type")

                should_trigger = False

                if schedule_type == "cron":
                    should_trigger = await self._check_cron_schedule(workflow, now)

                elif schedule_type == "interval":
                    should_trigger = await self._check_interval_schedule(workflow, now)

                elif schedule_type == "one_time":
                    should_trigger = await self._check_one_time_schedule(workflow, now)

                if should_trigger:
                    # Trigger workflow
                    asyncio.create_task(self._trigger_workflow(workflow, db))

            except Exception as e:
                logger.error(f"Error checking workflow {workflow.id}: {e}", exc_info=True)

    async def _check_cron_schedule(self, workflow, now: datetime) -> bool:
        """
        Check if cron schedule should trigger.

        Args:
            workflow: Workflow instance
            now: Current datetime

        Returns:
            True if should trigger
        """
        config = workflow.trigger_config
        cron_expression = config.get("cron_expression")

        if not cron_expression:
            return False

        try:
            # Get last execution time
            last_execution = workflow.last_executed_at

            if last_execution is None:
                # Never executed, check if should trigger now
                cron = croniter(cron_expression, now)
                next_run = cron.get_prev(datetime)

                # If next run is within last minute, trigger
                if (now - next_run).total_seconds() < 60:
                    return True
            else:
                # Check if cron has triggered since last execution
                cron = croniter(cron_expression, last_execution)
                next_run = cron.get_next(datetime)

                if next_run <= now:
                    return True

        except Exception as e:
            logger.error(f"Error parsing cron expression: {e}")

        return False

    async def _check_interval_schedule(self, workflow, now: datetime) -> bool:
        """
        Check if interval schedule should trigger.

        Args:
            workflow: Workflow instance
            now: Current datetime

        Returns:
            True if should trigger
        """
        config = workflow.trigger_config
        interval_seconds = config.get("interval_seconds")

        if not interval_seconds:
            return False

        last_execution = workflow.last_executed_at

        if last_execution is None:
            # Never executed, trigger now
            return True

        # Check if interval has elapsed
        elapsed = (now - last_execution).total_seconds()

        return elapsed >= interval_seconds

    async def _check_one_time_schedule(self, workflow, now: datetime) -> bool:
        """
        Check if one-time schedule should trigger.

        Args:
            workflow: Workflow instance
            now: Current datetime

        Returns:
            True if should trigger
        """
        config = workflow.trigger_config
        scheduled_at = config.get("scheduled_at")

        if not scheduled_at:
            return False

        # Parse scheduled time
        if isinstance(scheduled_at, str):
            scheduled_time = datetime.fromisoformat(scheduled_at.replace('Z', '+00:00'))
        else:
            scheduled_time = scheduled_at

        # Check if already executed
        if workflow.last_executed_at and workflow.last_executed_at >= scheduled_time:
            # Already executed, disable workflow
            workflow.is_active = False
            return False

        # Check if time has come
        return now >= scheduled_time

    async def _trigger_workflow(self, workflow, db: AsyncSession) -> None:
        """
        Trigger a scheduled workflow.

        Args:
            workflow: Workflow instance
            db: Database session
        """
        from app.services.workflows.workflow_engine import get_workflow_engine

        try:
            trigger_data = {
                "event_type": "scheduled",
                "schedule_type": workflow.trigger_config.get("schedule_type"),
                "triggered_at": datetime.utcnow().isoformat(),
            }

            engine = get_workflow_engine(db)
            execution = await engine.execute_workflow(
                workflow_id=str(workflow.id),
                trigger_data=trigger_data,
                wait_for_completion=False,
            )

            logger.info(f"Triggered scheduled workflow {workflow.id}, execution {execution.id}")

            # Update last executed time
            workflow.last_executed_at = datetime.utcnow()
            await db.commit()

        except Exception as e:
            logger.error(f"Failed to trigger scheduled workflow {workflow.id}: {e}", exc_info=True)

    async def schedule_workflow(
        self,
        workflow_id: str,
        schedule_config: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Schedule a workflow for future execution.

        Args:
            workflow_id: Workflow ID
            schedule_config: Schedule configuration

        Returns:
            Schedule information
        """
        schedule_type = schedule_config.get("schedule_type")

        if schedule_type == "cron":
            return await self._schedule_cron(workflow_id, schedule_config)
        elif schedule_type == "interval":
            return await self._schedule_interval(workflow_id, schedule_config)
        elif schedule_type == "one_time":
            return await self._schedule_one_time(workflow_id, schedule_config)
        else:
            raise ValueError(f"Invalid schedule type: {schedule_type}")

    async def _schedule_cron(
        self,
        workflow_id: str,
        config: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Schedule workflow with cron expression.

        Args:
            workflow_id: Workflow ID
            config: Cron configuration

        Returns:
            Schedule info
        """
        cron_expression = config.get("cron_expression")

        # Validate cron expression
        try:
            cron = croniter(cron_expression)
            next_run = cron.get_next(datetime)
        except Exception as e:
            raise ValueError(f"Invalid cron expression: {str(e)}")

        return {
            "workflow_id": workflow_id,
            "schedule_type": "cron",
            "cron_expression": cron_expression,
            "next_run": next_run.isoformat(),
            "description": self._describe_cron(cron_expression),
        }

    async def _schedule_interval(
        self,
        workflow_id: str,
        config: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Schedule workflow with fixed interval.

        Args:
            workflow_id: Workflow ID
            config: Interval configuration

        Returns:
            Schedule info
        """
        interval_seconds = config.get("interval_seconds")

        if not isinstance(interval_seconds, int) or interval_seconds <= 0:
            raise ValueError("interval_seconds must be a positive integer")

        next_run = datetime.utcnow() + timedelta(seconds=interval_seconds)

        return {
            "workflow_id": workflow_id,
            "schedule_type": "interval",
            "interval_seconds": interval_seconds,
            "next_run": next_run.isoformat(),
            "description": f"Every {interval_seconds} seconds",
        }

    async def _schedule_one_time(
        self,
        workflow_id: str,
        config: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Schedule workflow for one-time execution.

        Args:
            workflow_id: Workflow ID
            config: One-time schedule configuration

        Returns:
            Schedule info
        """
        scheduled_at = config.get("scheduled_at")

        if isinstance(scheduled_at, str):
            scheduled_time = datetime.fromisoformat(scheduled_at.replace('Z', '+00:00'))
        else:
            scheduled_time = scheduled_at

        if scheduled_time <= datetime.utcnow():
            raise ValueError("scheduled_at must be in the future")

        return {
            "workflow_id": workflow_id,
            "schedule_type": "one_time",
            "scheduled_at": scheduled_time.isoformat(),
            "description": f"Once at {scheduled_time.isoformat()}",
        }

    def _describe_cron(self, cron_expression: str) -> str:
        """
        Generate human-readable description of cron expression.

        Args:
            cron_expression: Cron expression

        Returns:
            Human-readable description
        """
        # Simple descriptions for common patterns
        patterns = {
            "* * * * *": "Every minute",
            "0 * * * *": "Every hour",
            "0 0 * * *": "Every day at midnight",
            "0 9 * * *": "Every day at 9:00 AM",
            "0 0 * * 0": "Every Sunday at midnight",
            "0 0 1 * *": "First day of every month",
            "0 0 1 1 *": "Every January 1st",
        }

        return patterns.get(cron_expression, cron_expression)


# Singleton instance
_scheduler: Optional[WorkflowScheduler] = None


def get_scheduler() -> WorkflowScheduler:
    """
    Get scheduler instance (singleton).

    Returns:
        WorkflowScheduler instance
    """
    global _scheduler
    if _scheduler is None:
        _scheduler = WorkflowScheduler()
    return _scheduler
