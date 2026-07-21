"""
Workflow Scheduler.

Handles scheduled workflow triggers (cron, interval, one-time).
"""
import logging
import asyncio
from typing import Dict, Any, Optional
from datetime import datetime, timedelta, timezone
from croniter import croniter
from sqlalchemy import select, and_, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.workflow import TriggerType
from app.database import AsyncSessionLocal

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
        self._loop_task: Optional[asyncio.Task] = None
        # Strong references to in-flight trigger tasks. asyncio only holds weak
        # references to tasks, so without this a dispatch can be garbage
        # collected mid-execution.
        self._trigger_tasks: set = set()

    async def start(self) -> None:
        """Start the scheduler."""
        if self._running:
            logger.warning("Scheduler already running")
            return

        self._running = True
        logger.info("Starting workflow scheduler")

        # Start scheduler loop, keeping a reference so it is not GC'd
        self._loop_task = asyncio.create_task(self._scheduler_loop())

    async def stop(self) -> None:
        """Stop the scheduler."""
        logger.info("Stopping workflow scheduler")
        self._running = False

        if self._loop_task is not None and not self._loop_task.done():
            self._loop_task.cancel()
            try:
                await self._loop_task
            except asyncio.CancelledError:
                pass
        self._loop_task = None

        # Cancel all in-flight trigger tasks
        for task in list(self._trigger_tasks):
            if not task.done():
                task.cancel()
        if self._trigger_tasks:
            await asyncio.gather(*self._trigger_tasks, return_exceptions=True)
        self._trigger_tasks.clear()

        # Cancel all running tasks
        for task_id, task in self._tasks.items():
            if not task.done():
                task.cancel()

        self._tasks.clear()

    def _spawn_trigger(self, workflow_id: str, schedule_type: Optional[str]) -> None:
        """
        Dispatch a workflow trigger on its own task and session.

        Args:
            workflow_id: Workflow to trigger
            schedule_type: Schedule type, recorded in the trigger data
        """
        task = asyncio.create_task(self._trigger_workflow(workflow_id, schedule_type))
        self._trigger_tasks.add(task)
        task.add_done_callback(self._trigger_tasks.discard)

    async def _scheduler_loop(self) -> None:
        """Main scheduler loop."""
        while self._running:
            try:
                async with AsyncSessionLocal() as db:
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
                    # Claim the slot before dispatching. Writing
                    # last_executed_at after the run started meant a slow start
                    # let the next poll (30s) see the workflow as still due and
                    # fire it a second time.
                    # A one-time schedule fires exactly once, so it is
                    # deactivated in the same UPDATE that claims it.
                    claimed = await self._claim(
                        db,
                        workflow,
                        now,
                        deactivate=(schedule_type == "one_time"),
                    )
                    if claimed:
                        self._spawn_trigger(str(workflow.id), schedule_type)
                    else:
                        logger.debug(
                            f"Workflow {workflow.id} already claimed by another poll"
                        )

            except Exception as e:
                logger.error(f"Error checking workflow {workflow.id}: {e}", exc_info=True)

    async def _claim(
        self,
        db: AsyncSession,
        workflow,
        now: datetime,
        deactivate: bool = False,
    ) -> bool:
        """
        Atomically claim a scheduled workflow for this tick.

        Uses a conditional UPDATE guarded on the last_executed_at value we read,
        so concurrent polls (or multiple scheduler instances) cannot both win.

        Args:
            db: Database session
            workflow: Workflow instance
            now: Timestamp to record as the execution time
            deactivate: Also clear is_active, for one-time schedules

        Returns:
            True if this caller won the claim
        """
        from app.models.integration import Workflow

        previous = workflow.last_executed_at

        if previous is None:
            guard = Workflow.last_executed_at.is_(None)
        else:
            guard = Workflow.last_executed_at == previous

        values: Dict[str, Any] = {"last_executed_at": now}
        if deactivate:
            values["is_active"] = False

        result = await db.execute(
            update(Workflow)
            .where(
                and_(
                    Workflow.id == workflow.id,
                    Workflow.is_active == True,
                    guard,
                )
            )
            .values(**values)
            # Do not write the new value back onto the in-memory instance.
            # ORM synchronization would make a second poll holding the same
            # object read the post-claim value and wrongly win the guard.
            .execution_options(synchronize_session=False)
        )
        await db.commit()

        return result.rowcount == 1

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

        # Parse scheduled time. Normalize to naive UTC: last_executed_at and
        # `now` are naive (datetime.utcnow), and an ISO string ending in Z
        # parses to an aware datetime — comparing the two raises TypeError.
        if isinstance(scheduled_at, str):
            scheduled_time = datetime.fromisoformat(scheduled_at.replace('Z', '+00:00'))
        else:
            scheduled_time = scheduled_at

        if scheduled_time.tzinfo is not None:
            scheduled_time = scheduled_time.astimezone(timezone.utc).replace(tzinfo=None)

        # Check if already executed
        if workflow.last_executed_at and workflow.last_executed_at >= scheduled_time:
            return False

        # Check if time has come
        return now >= scheduled_time

    async def _trigger_workflow(
        self,
        workflow_id: str,
        schedule_type: Optional[str] = None,
    ) -> None:
        """
        Trigger a scheduled workflow on its own database session.

        Takes a workflow ID rather than an ORM instance: this runs as a detached
        task, and the polling loop's session is closed as soon as that loop
        iteration exits. Reusing it raised "session is closed" errors under load.

        Args:
            workflow_id: Workflow to trigger
            schedule_type: Schedule type, recorded in the trigger data
        """
        from app.services.workflows.workflow_engine import get_workflow_engine

        try:
            trigger_data = {
                "event_type": "scheduled",
                "schedule_type": schedule_type,
                "triggered_at": datetime.utcnow().isoformat(),
            }

            async with AsyncSessionLocal() as db:
                engine = get_workflow_engine(db)
                execution = await engine.execute_workflow(
                    workflow_id=workflow_id,
                    trigger_data=trigger_data,
                    wait_for_completion=True,
                )

                logger.info(
                    f"Triggered scheduled workflow {workflow_id}, "
                    f"execution {execution.id}"
                )

        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(
                f"Failed to trigger scheduled workflow {workflow_id}: {e}",
                exc_info=True,
            )

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
