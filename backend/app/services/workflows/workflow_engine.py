"""
Workflow Execution Engine.

Core engine for executing workflows.
"""
import logging
import asyncio
import time
import uuid
from typing import Dict, Any, Optional, List, Set
from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_

from app.models.integration import Workflow, WorkflowExecution
from app.services.workflows import graph as graph_utils
from app.services.workflows.executor import (
    DEFAULT_MAX_CONCURRENCY,
    GraphExecutor,
    NodeOutcome,
    default_handles,
)
from app.services.workflows.step_handlers import (
    StepHandlerFactory,
    WorkflowContext,
    StepExecutionError,
)

logger = logging.getLogger(__name__)


class WorkflowEngineError(Exception):
    """Raised when workflow engine encounters an error."""
    pass


def _as_uuid(value: Any) -> Any:
    """
    Coerce an id to UUID, leaving anything unparseable alone.

    Ids arrive as strings from the API layer while the columns are UUID typed.

    Args:
        value: Id as a string or UUID

    Returns:
        A UUID when parseable, otherwise the original value
    """
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except (ValueError, AttributeError, TypeError):
        return value


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
        on_event: Optional[Any] = None,
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
            # Callers pass the id as a string; the column is a real UUID type,
            # which some drivers will not coerce for us.
            query = select(Workflow).where(Workflow.id == _as_uuid(workflow_id))
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
                    workflow, execution, trigger_data or {}, channel,
                    sync=True, on_event=on_event,
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

    async def _run_loop(
        self,
        node: Dict[str, Any],
        graph: Dict[str, Any],
        workflow: Workflow,
        context: WorkflowContext,
        sync: bool,
    ) -> NodeOutcome:
        """
        Run a loop node's body once per item.

        The body is the sub-graph hanging off the ``loop`` output. Running it as
        a nested execution rather than as a cycle in the main graph keeps the
        main graph acyclic, which is what lets the scheduler reason about
        readiness at all.

        Args:
            node: The loop node
            graph: Full workflow graph, used to extract the body
            workflow: Owning workflow
            context: Shared execution context
            sync: True when an HTTP caller is blocked on this run

        Returns:
            Outcome firing the ``done`` output
        """
        config = node.get("config") or {}
        max_iterations = int(config.get("max_iterations", 100) or 100)

        items = self._resolve_loop_items(config, context)

        if len(items) > max_iterations:
            logger.warning(
                f"Loop {node.get('name')} capped at {max_iterations} of "
                f"{len(items)} items"
            )
            items = items[:max_iterations]

        body = graph_utils.subgraph_from(graph, node["id"], graph_utils.HANDLE_LOOP)

        if not body["nodes"]:
            logger.info(f"Loop {node.get('name')} has an empty body")
            return NodeOutcome(
                status="success",
                handles=[graph_utils.HANDLE_DONE],
                result={"iterations": 0, "items": len(items)},
            )

        iterations: List[Dict[str, Any]] = []
        failed = 0

        for index, item in enumerate(items):
            # Body steps reference the current item through these.
            context.set_variable(
                "loop", {"item": item, "index": index, "length": len(items)}
            )

            executor = GraphExecutor(
                body,
                run_node=lambda n: self._run_node(n, graph, workflow, context, sync),
                max_concurrency=DEFAULT_MAX_CONCURRENCY,
            )
            results, counts = await executor.run()

            failed += counts["failed"]
            iterations.append({"index": index, "steps": results, "counts": counts})

            if counts["failed"] and (
                (node.get("settings") or {}).get("on_error", workflow.error_handling)
                == "stop"
            ):
                logger.info(f"Loop {node.get('name')} stopping after a failed item")
                break

        return NodeOutcome(
            status="failed" if failed else "success",
            handles=[graph_utils.HANDLE_DONE],
            result={"iterations": len(iterations), "items": len(items),
                    "runs": iterations},
            error=f"{failed} step(s) failed inside the loop" if failed else None,
        )

    def _resolve_loop_items(
        self,
        config: Dict[str, Any],
        context: WorkflowContext,
    ) -> List[Any]:
        """
        Work out what a loop iterates over.

        Accepts a literal list, a ``{{reference}}`` to one, or a plain count.

        Args:
            config: Loop node configuration
            context: Execution context, for resolving references

        Returns:
            The list of items
        """
        raw = config.get("items")

        if isinstance(raw, list):
            return raw

        if isinstance(raw, str) and raw.strip():
            resolved = context.get_variable(
                raw.strip().strip("{}").strip()
            )
            if isinstance(resolved, list):
                return resolved
            if resolved is None:
                logger.warning(f"Loop items reference '{raw}' resolved to nothing")
                return []
            return [resolved]

        count = config.get("count")
        if count:
            return list(range(int(count)))

        return []

    async def _run_node(
        self,
        node: Dict[str, Any],
        graph: Dict[str, Any],
        workflow: Workflow,
        context: WorkflowContext,
        sync: bool,
    ) -> NodeOutcome:
        """
        Execute a single node, applying its retry, timeout and error policy.

        Scheduling lives in GraphExecutor; this is the per-node half. It never
        raises: a failure is reported as an outcome so the scheduler can keep
        other branches running.

        Args:
            node: Node definition
            workflow: Owning workflow, for default retry/error settings
            context: Shared execution context
            sync: True when an HTTP caller is blocked on this run

        Returns:
            The node's outcome, including which outputs fired
        """
        node_id = node.get("id")
        node_name = node.get("name", node_id)
        node_type = node.get("type")
        started = time.time()

        settings = node.get("settings") or {}
        retry_settings = settings.get("retry") or {}

        # Only steps that reach out to something fallible are retried by
        # default — replaying a spoken line would repeat it at the caller.
        retryable = node_type in ("action", "tool", "webhook")
        if "enabled" in retry_settings:
            retryable = bool(retry_settings["enabled"])

        max_retries = (
            int(retry_settings.get("max_tries", workflow.max_retries)) if retryable else 0
        )
        retry_delay = int(retry_settings.get("delay_seconds", workflow.retry_delay))
        backoff = retry_settings.get("backoff", "fixed")
        timeout_seconds = settings.get("timeout_seconds")

        # A synchronous caller is holding an HTTP connection open, so the
        # workflow's real backoff would hang the request for minutes.
        if sync and retryable:
            max_retries = min(max_retries, SYNC_MAX_RETRIES)
            retry_delay = min(retry_delay, SYNC_MAX_RETRY_DELAY)

        logger.info(f"Executing node: {node_name} ({node_type})")

        # A loop runs its body sub-graph once per item rather than delegating
        # to a handler, so it is dispatched before the retry loop.
        if node_type == "loop":
            try:
                return await self._run_loop(node, graph, workflow, context, sync)
            except Exception as exc:
                logger.error(f"Loop {node_name} failed: {exc}", exc_info=True)
                return self._failure_outcome(node, workflow, str(exc))

        attempt = 0
        while True:
            try:
                handler = StepHandlerFactory.get_handler(node_type, db=self.db)

                if timeout_seconds:
                    result = await asyncio.wait_for(
                        handler.execute(node, context), timeout=float(timeout_seconds)
                    )
                else:
                    result = await handler.execute(node, context)

                context.set_step_result(node_id, result.get("result"))

                logger.info(
                    f"Node {node_name} completed in "
                    f"{int((time.time() - started) * 1000)}ms"
                )

                return NodeOutcome(
                    status="success",
                    handles=default_handles(node, result),
                    result=result.get("result"),
                    ended=context.ended,
                )

            except asyncio.TimeoutError:
                error = f"Step timed out after {timeout_seconds}s"
                logger.error(f"Node {node_name}: {error}")
                return self._failure_outcome(node, workflow, error)

            except Exception as exc:
                if attempt < max_retries:
                    # Exponential backoff doubles each attempt; a fixed delay
                    # hammers a struggling API at a constant rate.
                    wait = (
                        retry_delay * (2 ** attempt)
                        if backoff == "exponential"
                        else retry_delay
                    )
                    if sync:
                        wait = min(wait, SYNC_MAX_RETRY_DELAY)

                    logger.warning(
                        f"Node {node_name} failed (attempt {attempt + 1}/"
                        f"{max_retries + 1}), retrying in {wait}s: {exc}"
                    )
                    attempt += 1
                    await asyncio.sleep(wait)
                    continue

                logger.error(f"Node {node_name} failed: {exc}", exc_info=True)
                return self._failure_outcome(node, workflow, str(exc))

    def _failure_outcome(
        self,
        node: Dict[str, Any],
        workflow: Workflow,
        error: str,
    ) -> NodeOutcome:
        """
        Build the outcome for a failed node according to its error policy.

        A node's own on_error setting wins over the workflow default, so one
        tolerant step does not force the whole workflow to continue-on-error.
        """
        settings = node.get("settings") or {}
        on_error = settings.get("on_error") or workflow.error_handling

        if on_error == "stop":
            # Ending the run is the scheduler's job; signal it here.
            return NodeOutcome(status="failed", handles=[], error=error, ended=True)

        # Continue: let downstream nodes run so the rest of the flow completes.
        return NodeOutcome(
            status="failed",
            handles=default_handles(node, None),
            error=error,
        )

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
        graph: Dict[str, Any],
        step: Dict[str, Any],
        step_result: Optional[Dict[str, Any]],
        current_id: str,
    ) -> Optional[str]:
        """
        Decide which node runs next by following the graph's edges.

        Precedence:
          1. The edge leaving the branch handle the node chose (true/false).
          2. The edge leaving the node's default output.
          3. A legacy `next_step_id` from the step or its result, for graphs
             migrated from v1 whose edges could not be reconstructed.

        Args:
            graph: Workflow graph
            step: Node that just executed
            step_result: Result returned by its handler
            current_id: Node id that just executed

        Returns:
            Next node id, or None when this branch ends here
        """
        branch: Optional[bool] = None
        if step_result and step_result.get("branch") is not None:
            branch = step_result["branch"] == "true"

        target = graph_utils.next_node_id(graph, current_id, branch=branch)
        if target:
            return target

        # A branching node whose taken handle has no edge ends that path;
        # falling through to the legacy pointer would silently run the wrong
        # node, so only consult it for non-branching nodes.
        if branch is not None:
            return None

        if step_result and step_result.get("next_step_id"):
            return step_result["next_step_id"]

        return step.get("next_step_id")

    async def _execute_workflow_steps(
        self,
        workflow: Workflow,
        execution: WorkflowExecution,
        trigger_data: Dict[str, Any],
        channel: Optional[Any] = None,
        sync: bool = False,
        on_event: Optional[Any] = None,
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

            # Load the flow as a graph. v1 workflows (a flat ordered list) are
            # migrated on read, so both formats execute through one code path.
            graph = graph_utils.load_graph(workflow.workflow_steps)

            # The trigger is a canvas anchor, not an executable node.
            runnable = [n for n in graph.get("nodes", []) if n.get("type") != "trigger"]

            if not runnable:
                raise WorkflowEngineError("Workflow has no steps")

            # Schedule the graph. Independent branches run concurrently; the
            # executor decides readiness from edge state rather than following
            # a single cursor, which is what makes parallel paths and joins
            # possible at all.
            executor = GraphExecutor(
                graph,
                run_node=lambda node: self._run_node(node, graph, workflow, context, sync),
                max_concurrency=DEFAULT_MAX_CONCURRENCY,
                on_event=on_event,
            )

            step_results, counts = await executor.run()

            executed_steps = counts["executed"]
            successful_steps = counts["successful"]
            failed_steps = counts["failed"]


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
            query = select(WorkflowExecution).where(
                WorkflowExecution.id == _as_uuid(execution_id)
            )
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


async def reap_stranded_executions(
    db: AsyncSession,
    older_than_seconds: Optional[int] = None,
) -> int:
    """
    Mark executions stuck in ``running`` as failed.

    Executions run in-process, so a restart kills them while leaving the row at
    ``running`` forever — nothing previously cleaned these up, and the stats
    endpoints counted them as in-flight indefinitely.

    Called at startup with ``older_than_seconds=None``, which reaps every
    running row: if the process just started, none of them can still be alive.
    The periodic sweep passes an age threshold so it does not kill live runs.

    Args:
        db: Database session
        older_than_seconds: Only reap runs started at least this long ago.
            None reaps all running rows.

    Returns:
        Number of executions reaped
    """
    conditions = [WorkflowExecution.status == "running"]

    if older_than_seconds is not None:
        cutoff = datetime.utcnow() - timedelta(seconds=older_than_seconds)
        conditions.append(WorkflowExecution.started_at <= cutoff)

    now = datetime.utcnow()

    result = await db.execute(
        update(WorkflowExecution)
        .where(and_(*conditions))
        .values(
            status="failed",
            completed_at=now,
            error_message=(
                "Execution was interrupted before it could complete "
                "(the worker process stopped while it was running)."
            ),
        )
    )
    await db.commit()

    count = result.rowcount or 0
    if count:
        logger.warning(f"Reaped {count} stranded workflow execution(s)")

    return count


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
