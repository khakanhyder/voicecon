"""
Workflow Execution Engine.

Core engine for executing workflows.
"""
import logging
import asyncio
import time
from typing import Dict, Any, Optional, List
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
    ) -> WorkflowExecution:
        """
        Execute a workflow.

        Args:
            workflow_id: Workflow ID
            trigger_data: Trigger data
            wait_for_completion: Wait for workflow to complete

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
                await self._execute_workflow_steps(workflow, execution, trigger_data or {})
            else:
                # Execute in background task
                asyncio.create_task(
                    self._execute_workflow_steps(workflow, execution, trigger_data or {})
                )

            return execution

        except Exception as e:
            logger.error(f"Failed to start workflow execution: {e}", exc_info=True)
            raise WorkflowEngineError(f"Failed to start workflow execution: {str(e)}")

    async def _execute_workflow_steps(
        self,
        workflow: Workflow,
        execution: WorkflowExecution,
        trigger_data: Dict[str, Any],
    ) -> None:
        """
        Execute workflow steps.

        Args:
            workflow: Workflow model
            execution: Execution record
            trigger_data: Trigger data
        """
        start_time = time.time()

        try:
            # Initialize context
            context = WorkflowContext(trigger_data)

            # Get workflow steps
            steps = workflow.workflow_steps.get("steps", [])

            if not steps:
                raise WorkflowEngineError("Workflow has no steps")

            # Execute steps sequentially
            step_results = []
            executed_steps = 0
            successful_steps = 0
            failed_steps = 0

            for step in steps:
                step_id = step.get("id")
                step_name = step.get("name", step_id)
                step_type = step.get("type")

                logger.info(f"Executing step: {step_name} ({step_type})")

                step_start_time = time.time()

                try:
                    # Get step handler
                    handler = StepHandlerFactory.get_handler(step_type, db=self.db)

                    # Execute step with retry logic
                    max_retries = workflow.max_retries
                    retry_delay = workflow.retry_delay
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
