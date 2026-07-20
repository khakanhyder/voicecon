"""
Workflow Execution Engine.

Core engine for executing workflows.
"""
import logging
import asyncio
import time
import uuid
from typing import Dict, Any, Optional, List, Set
from datetime import datetime
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.integration import Workflow, WorkflowExecution
from app.services.workflows.step_handlers import (
    StepHandlerFactory,
    WorkflowContext,
    StepExecutionError,
)

logger = logging.getLogger(__name__)


class WorkflowEngineError(Exception):
    """Raised when workflow engine encounters an error."""
    pass


# Strong references to in-flight background runs. asyncio only holds a weak
# reference to a task, so without this a fire-and-forget run can be garbage
# collected before it finishes.
_background_tasks: Set[asyncio.Task] = set()

# Retry ceilings applied only when a caller is blocked waiting on the run.
SYNC_MAX_RETRIES = 1
SYNC_MAX_RETRY_DELAY = 2  # seconds


class WorkflowEngine:
    """
    Workflow execution engine.

    Manages workflow execution, step orchestration, and error handling.
    """

    def __init__(self, db: AsyncSession):
        """
        Initialize workflow engine.

        Args:
            db: Database session
        """
        self.db = db

    async def execute_workflow(
        self,
        workflow_id: str,
        trigger_data: Optional[Dict[str, Any]] = None,
        wait_for_completion: bool = False,
        channel: Optional[Any] = None,
    ) -> WorkflowExecution:
        """
        Execute a workflow.

        Args:
            workflow_id: Workflow ID
            trigger_data: Trigger data
            wait_for_completion: Wait for workflow to complete
            channel: Execution channel for conversation steps. Defaults to a
                simulated (dry-run) channel — see services/workflows/channels.py.

        Returns:
            Workflow execution record

        Raises:
            WorkflowEngineError: If workflow execution fails
        """
        try:
            # Get workflow
            query = select(Workflow).where(Workflow.id == workflow_id)
            result = await self.db.execute(query)
            workflow = result.scalar_one_or_none()

            if not workflow:
                raise WorkflowEngineError(f"Workflow {workflow_id} not found")

            if not workflow.is_active:
                raise WorkflowEngineError(f"Workflow {workflow_id} is not active")

            # Create execution record
            execution = WorkflowExecution(
                workflow_id=workflow.id,
                trigger_data=trigger_data or {},
                status="running",
                started_at=datetime.utcnow(),
            )

            self.db.add(execution)
            await self.db.commit()
            await self.db.refresh(execution)

            logger.info(f"Starting workflow execution: {execution.id}")

            # Execute in background if not waiting
            if wait_for_completion:
                await self._execute_workflow_steps(
                    workflow, execution, trigger_data or {}, channel, sync=True
                )
            else:
                # Fire-and-forget. This MUST NOT reuse self.db: that session is
                # request-scoped and gets closed the moment the HTTP response is
                # returned, which would leave the run writing to a dead session.
                # _run_detached opens its own session instead.
                task = asyncio.create_task(
                    self._run_detached(
                        str(workflow.id), str(execution.id), trigger_data or {}, channel
                    )
                )
                # Keep a reference so the task isn't garbage-collected mid-flight.
                _background_tasks.add(task)
                task.add_done_callback(_background_tasks.discard)

            return execution

        except Exception as e:
            logger.error(f"Failed to start workflow execution: {e}", exc_info=True)
            raise WorkflowEngineError(f"Failed to start workflow execution: {str(e)}")

    async def _run_detached(
        self,
        workflow_id: str,
        execution_id: str,
        trigger_data: Dict[str, Any],
        channel: Optional[Any] = None,
    ) -> None:
        """
        Run a workflow in the background on its own DB session.

        The caller's session belongs to an HTTP request and is closed as soon as
        that request returns, so a background run has to open its own.
        """
        from app.database import AsyncSessionLocal

        try:
            async with AsyncSessionLocal() as db:
                workflow = await db.get(Workflow, uuid.UUID(workflow_id))
                execution = await db.get(WorkflowExecution, uuid.UUID(execution_id))

                if not workflow or not execution:
                    logger.error(
                        f"Detached run aborted: workflow={workflow_id} "
                        f"execution={execution_id} could not be reloaded"
                    )
                    return

                engine = WorkflowEngine(db)
                await engine._execute_workflow_steps(
                    workflow, execution, trigger_data, channel
                )
        except Exception as e:
            logger.error(f"Detached workflow run failed: {e}", exc_info=True)

    def _order_steps(self, steps: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Index steps by id and remember their declared order."""
        by_id: Dict[str, Dict[str, Any]] = {}
        order: List[str] = []
        for i, step in enumerate(steps):
            sid = step.get("id") or f"step_{i}"
            step.setdefault("id", sid)
            by_id[sid] = step
            order.append(sid)
        return {"by_id": by_id, "order": order}

    def _next_step_id(
        self,
        step: Dict[str, Any],
        step_result: Optional[Dict[str, Any]],
        order: List[str],
        current_id: str,
    ) -> Optional[str]:
        """
        Decide which step runs next.

        Precedence:
          1. A branch target chosen by the step itself (condition on_true/on_false).
          2. An explicit `next_step_id` on the step.
          3. The next step in declared order (the builder's linear flow).
        """
        if step_result and step_result.get("next_step_id"):
            return step_result["next_step_id"]

        if step.get("next_step_id"):
            return step["next_step_id"]

        try:
            idx = order.index(current_id)
        except ValueError:
            return None
        return order[idx + 1] if idx + 1 < len(order) else None

    async def _execute_workflow_steps(
        self,
        workflow: Workflow,
        execution: WorkflowExecution,
        trigger_data: Dict[str, Any],
        channel: Optional[Any] = None,
        sync: bool = False,
    ) -> None:
        """
        Execute workflow steps.

        Walks the flow step-by-step rather than blindly iterating the list, so
        condition branches and `next_step_id` links are honoured, and an `end`
        step stops the run.

        Args:
            workflow: Workflow model
            execution: Execution record
            trigger_data: Trigger data
            channel: Execution channel for conversation steps
            sync: True when an HTTP caller is blocked waiting on this run, which
                caps retry backoff so the request can't hang for minutes.
        """
        start_time = time.time()

        try:
            # Initialize context
            context = WorkflowContext(trigger_data, channel=channel)

            # Get workflow steps
            steps = workflow.workflow_steps.get("steps", [])

            if not steps:
                raise WorkflowEngineError("Workflow has no steps")

            indexed = self._order_steps(steps)
            by_id, order = indexed["by_id"], indexed["order"]

            # Execute by walking the flow
            step_results = []
            executed_steps = 0
            successful_steps = 0
            failed_steps = 0

            current_id: Optional[str] = order[0]
            visited: Dict[str, int] = {}
            # Backstop against a flow that loops back on itself forever.
            max_steps = max(len(order) * 10, 100)

            while current_id and executed_steps < max_steps:
                step = by_id.get(current_id)
                if step is None:
                    logger.error(f"Flow points at unknown step '{current_id}', stopping")
                    break

                visited[current_id] = visited.get(current_id, 0) + 1

                step_id = step.get("id")
                step_name = step.get("name", step_id)
                step_type = step.get("type")

                logger.info(f"Executing step: {step_name} ({step_type})")

                step_start_time = time.time()
                step_result: Optional[Dict[str, Any]] = None

                try:
                    # Get step handler
                    handler = StepHandlerFactory.get_handler(step_type, db=self.db)

                    # Execute step with retry logic. Only steps that reach out to
                    # something fallible are worth retrying — replaying a spoken
                    # line or a branch decision would just repeat it at the caller.
                    retryable = step_type in ("action", "tool", "webhook")
                    max_retries = workflow.max_retries if retryable else 0
                    retry_delay = workflow.retry_delay

                    # A synchronous caller is holding an HTTP connection open, so
                    # the workflow's real backoff (60s x 3 by default) would hang
                    # the request for minutes. Background runs keep full backoff.
                    if sync and retryable:
                        max_retries = min(max_retries, SYNC_MAX_RETRIES)
                        retry_delay = min(retry_delay, SYNC_MAX_RETRY_DELAY)

                    attempt = 0

                    while attempt <= max_retries:
                        try:
                            step_result = await handler.execute(step, context)

                            # Store step result in context
                            context.set_step_result(step_id, step_result.get("result"))

                            # Record step success
                            step_duration = int((time.time() - step_start_time) * 1000)

                            step_results.append({
                                "step_id": step_id,
                                "step_name": step_name,
                                "status": "success",
                                "started_at": datetime.fromtimestamp(step_start_time).isoformat(),
                                "completed_at": datetime.utcnow().isoformat(),
                                "duration_ms": step_duration,
                                "result": step_result.get("result"),
                                "error": None,
                            })

                            executed_steps += 1
                            successful_steps += 1

                            logger.info(f"Step {step_name} completed successfully")
                            break  # Success, exit retry loop

                        except Exception as retry_error:
                            if attempt < max_retries:
                                logger.warning(
                                    f"Step {step_name} failed (attempt {attempt + 1}/{max_retries + 1}), "
                                    f"retrying in {retry_delay}s: {retry_error}"
                                )
                                attempt += 1
                                await asyncio.sleep(retry_delay)
                            else:
                                raise  # Max retries reached

                except Exception as step_error:
                    logger.error(f"Step {step_name} failed: {step_error}", exc_info=True)

                    step_duration = int((time.time() - step_start_time) * 1000)

                    step_results.append({
                        "step_id": step_id,
                        "step_name": step_name,
                        "status": "failed",
                        "started_at": datetime.fromtimestamp(step_start_time).isoformat(),
                        "completed_at": datetime.utcnow().isoformat(),
                        "duration_ms": step_duration,
                        "result": None,
                        "error": str(step_error),
                    })

                    executed_steps += 1
                    failed_steps += 1

                    # Handle error based on workflow configuration
                    if workflow.error_handling == "stop":
                        logger.info("Error handling set to 'stop', halting workflow")
                        break
                    else:
                        logger.info("Error handling set to 'continue', proceeding to next step")

                # An `end`/`transfer` step means the conversation is over.
                if context.ended:
                    logger.info("Flow reached a terminal step, stopping")
                    break

                current_id = self._next_step_id(step, step_result, order, current_id)

            if executed_steps >= max_steps:
                logger.warning(
                    f"Workflow {workflow.id} hit the {max_steps}-step ceiling; "
                    "stopping to avoid an infinite loop"
                )

            # Calculate final execution time
            duration_ms = int((time.time() - start_time) * 1000)

            # Update execution record
            execution.status = "completed" if failed_steps == 0 else "failed"
            execution.completed_at = datetime.utcnow()
            execution.duration_ms = duration_ms
            execution.steps_executed = executed_steps
            execution.steps_successful = successful_steps
            execution.steps_failed = failed_steps
            execution.result_data = {
                "steps": step_results,
                "final_context": context.variables,
            }

            # For a dry run, include what the agent would have said — that's the
            # whole point of testing a flow from the dashboard.
            transcript = getattr(context.channel, "transcript", None)
            if transcript:
                execution.result_data["transcript"] = transcript
                execution.result_data["simulated"] = not getattr(
                    context.channel, "is_live", False
                )

            if failed_steps > 0:
                execution.error_message = f"{failed_steps} step(s) failed"

            # Update workflow stats
            workflow.total_executions += 1
            if execution.status == "completed":
                workflow.successful_executions += 1
            else:
                workflow.failed_executions += 1
            workflow.last_executed_at = datetime.utcnow()

            await self.db.commit()

            logger.info(
                f"Workflow execution {execution.id} completed: "
                f"{successful_steps}/{executed_steps} steps successful"
            )

        except Exception as e:
            logger.error(f"Workflow execution failed: {e}", exc_info=True)

            # Update execution as failed
            execution.status = "failed"
            execution.completed_at = datetime.utcnow()
            execution.duration_ms = int((time.time() - start_time) * 1000)
            execution.error_message = str(e)
            execution.error_details = {"error_type": type(e).__name__}

            # Update workflow stats
            workflow.total_executions += 1
            workflow.failed_executions += 1
            workflow.last_executed_at = datetime.utcnow()

            await self.db.commit()

    async def cancel_execution(self, execution_id: str) -> bool:
        """
        Cancel a running execution.

        Args:
            execution_id: Execution ID

        Returns:
            True if cancelled successfully

        Raises:
            WorkflowEngineError: If cancellation fails
        """
        try:
            query = select(WorkflowExecution).where(WorkflowExecution.id == execution_id)
            result = await self.db.execute(query)
            execution = result.scalar_one_or_none()

            if not execution:
                raise WorkflowEngineError(f"Execution {execution_id} not found")

            if execution.status != "running":
                raise WorkflowEngineError(f"Execution {execution_id} is not running")

            execution.status = "cancelled"
            execution.completed_at = datetime.utcnow()

            await self.db.commit()

            logger.info(f"Execution {execution_id} cancelled")

            return True

        except Exception as e:
            logger.error(f"Failed to cancel execution: {e}", exc_info=True)
            raise WorkflowEngineError(f"Failed to cancel execution: {str(e)}")


# Global workflow engine instance
_workflow_engine: Optional[WorkflowEngine] = None


def get_workflow_engine(db: AsyncSession) -> WorkflowEngine:
    """
    Get workflow engine instance.

    Args:
        db: Database session

    Returns:
        WorkflowEngine instance
    """
    # Note: We create a new instance per request to use the correct DB session
    return WorkflowEngine(db)
