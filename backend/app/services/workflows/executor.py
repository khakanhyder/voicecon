"""
DAG scheduler for workflow graphs.

Replaces the original single-cursor walk, which could only ever be at one node
at a time and therefore had no way to express parallel branches or joins.

The algorithm resolves *edges* rather than following a pointer:

  * Every edge ends up either ``activated`` (data flowed down it) or
    ``skipped`` (the branch that would have fed it was not taken).
  * A node becomes runnable once all of its inbound edges are resolved and at
    least one is activated.
  * A node whose inbound edges are all skipped is itself skipped, and its
    outbound edges are skipped in turn. That propagation is what lets a join
    downstream of an if/else fire exactly once instead of waiting forever on
    the branch that never ran.
  * Every runnable node in a wave is dispatched concurrently, bounded by a
    semaphore, so independent branches genuinely run in parallel.

Cycles are rejected by ``validate_graph`` before execution, so the main graph
is a DAG. Iteration is expressed by the ``loop`` node, which runs its body as a
nested sub-graph once per item rather than by looping an edge back.
"""
import asyncio
import logging
from typing import Any, Awaitable, Callable, Dict, List, Optional, Set, Tuple

from app.services.workflows import graph as graph_utils

logger = logging.getLogger(__name__)

# Edge resolution states
ACTIVATED = "activated"
SKIPPED = "skipped"

DEFAULT_MAX_CONCURRENCY = 10

# Node types whose inbound edges must not all be waited on.
FIRST_ARRIVAL_TYPES = {"merge"}


class NodeOutcome:
    """
    What a node produced, and which of its outputs fired.

    Attributes:
        status: "success", "failed", or "skipped"
        handles: Output handle ids that should carry data onward. An empty
            list means every downstream edge from this node is skipped.
        result: The handler's result payload
        error: Error message when the node failed
        ended: True when the node terminated the whole run (end/transfer)
    """

    __slots__ = ("status", "handles", "result", "error", "ended")

    def __init__(
        self,
        status: str,
        handles: List[str],
        result: Any = None,
        error: Optional[str] = None,
        ended: bool = False,
    ):
        self.status = status
        self.handles = handles
        self.result = result
        self.error = error
        self.ended = ended


# Signature of the callback that actually runs one node.
RunNode = Callable[[Dict[str, Any]], Awaitable[NodeOutcome]]


class GraphExecutor:
    """
    Executes a workflow graph, running independent branches concurrently.

    The executor owns scheduling only. Running an individual node — handler
    lookup, retries, timeouts, error policy — stays in the engine and is
    injected as ``run_node``.
    """

    def __init__(
        self,
        graph: Dict[str, Any],
        run_node: RunNode,
        max_concurrency: int = DEFAULT_MAX_CONCURRENCY,
        max_nodes: int = 1000,
        on_event: Optional[Callable[[Dict[str, Any]], Awaitable[None]]] = None,
    ):
        """
        Args:
            graph: Normalized v2 graph
            run_node: Coroutine that executes one node and returns a NodeOutcome
            max_concurrency: Ceiling on nodes running at once
            max_nodes: Backstop on total node executions
            on_event: Optional async callback fired as nodes start, finish, and
                are skipped. Used to stream live status to the builder canvas.
                Failures in the callback never affect execution.
        """
        self.graph = graph
        self.run_node = run_node
        self.max_nodes = max_nodes
        self._on_event = on_event
        self._semaphore = asyncio.Semaphore(max_concurrency)

        self.nodes = graph_utils.index_nodes(graph)
        self.edges = graph.get("edges", [])

        # edge id -> ACTIVATED | SKIPPED
        self.edge_state: Dict[str, str] = {}
        # node id -> "done" | "skipped"
        self.node_state: Dict[str, str] = {}

        self._inbound: Dict[str, List[Dict[str, Any]]] = {}
        for edge in self.edges:
            self._inbound.setdefault(edge["target"], []).append(edge)

    # ------------------------------------------------------------------
    # Scheduling
    # ------------------------------------------------------------------

    def _inbound_edges(self, node_id: str) -> List[Dict[str, Any]]:
        return self._inbound.get(node_id, [])

    def _is_runnable(self, node_id: str) -> bool:
        """A node runs when its inbound edges are resolved and one activated."""
        if node_id in self.node_state:
            return False

        inbound = self._inbound_edges(node_id)
        if not inbound:
            return False

        states = [self.edge_state.get(e["id"]) for e in inbound]

        node_type = (self.nodes.get(node_id) or {}).get("type")
        settings = (self.nodes.get(node_id) or {}).get("settings") or {}
        mode = settings.get("merge_mode", "wait_all")

        # A merge in first-arrival mode fires as soon as any branch reaches it,
        # which is the point of that mode: take whichever path won.
        if node_type in FIRST_ARRIVAL_TYPES and mode == "first_arrival":
            return any(state == ACTIVATED for state in states)

        if any(state is None for state in states):
            return False

        return any(state == ACTIVATED for state in states)

    def _is_skippable(self, node_id: str) -> bool:
        """All inbound edges resolved and none activated."""
        if node_id in self.node_state:
            return False

        inbound = self._inbound_edges(node_id)
        if not inbound:
            return False

        states = [self.edge_state.get(e["id"]) for e in inbound]
        if any(state is None for state in states):
            return False

        return all(state == SKIPPED for state in states)

    def _resolve_outbound(self, node_id: str, fired: List[str]) -> None:
        """
        Mark this node's outbound edges activated or skipped.

        Args:
            node_id: Node that just finished
            fired: Handle ids that carry data onward
        """
        for edge in graph_utils.outgoing(self.graph, node_id):
            handle = edge.get("sourceHandle", graph_utils.HANDLE_OUT)
            self.edge_state[edge["id"]] = ACTIVATED if handle in fired else SKIPPED

    def _skip_node(self, node_id: str) -> None:
        """Mark a node skipped and propagate the skip to everything below it."""
        self.node_state[node_id] = SKIPPED
        self._resolve_outbound(node_id, [])

    # ------------------------------------------------------------------
    # Run
    # ------------------------------------------------------------------

    async def run(self) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
        """
        Execute the graph.

        Returns:
            (ordered node results, {"executed", "successful", "failed", "skipped"})
        """
        results: List[Dict[str, Any]] = []
        counts = {"executed": 0, "successful": 0, "failed": 0, "skipped": 0}

        # Seed: activate everything leaving the trigger. A graph with no
        # trigger falls back to nodes that have no inbound edges.
        seeded = False
        for node in self.graph.get("nodes", []):
            if node.get("type") == "trigger":
                self.node_state[node["id"]] = "done"
                self._resolve_outbound(node["id"], [graph_utils.HANDLE_OUT])
                seeded = True

        if not seeded:
            targets = {e["target"] for e in self.edges}
            roots = [n for n in self.graph.get("nodes", []) if n["id"] not in targets]
            # A root has no inbound edge to activate, so run it directly.
            pending_roots = [n["id"] for n in roots]
        else:
            pending_roots = []

        stop_requested = False

        while not stop_requested:
            if counts["executed"] >= self.max_nodes:
                logger.warning(
                    f"Workflow hit the {self.max_nodes}-node ceiling; stopping"
                )
                break

            # Resolve skips first so joins downstream of an untaken branch can
            # become runnable in this same wave.
            progressed = True
            while progressed:
                progressed = False
                for node_id in list(self.nodes):
                    if self._is_skippable(node_id):
                        self._skip_node(node_id)
                        counts["skipped"] += 1
                        progressed = True
                        await self._emit("node_skipped", node_id)

            wave = [nid for nid in self.nodes if self._is_runnable(nid)]
            wave.extend(nid for nid in pending_roots if nid not in self.node_state)
            pending_roots = []

            if not wave:
                break

            # Claim the whole wave before awaiting so a node cannot be
            # scheduled twice by a concurrent branch.
            for node_id in wave:
                self.node_state[node_id] = "running"
                await self._emit("node_started", node_id)

            outcomes = await asyncio.gather(
                *(self._run_guarded(node_id) for node_id in wave)
            )

            for node_id, outcome in zip(wave, outcomes):
                self.node_state[node_id] = "done"
                node = self.nodes[node_id]

                results.append(
                    {
                        "step_id": node_id,
                        "step_name": node.get("name", node_id),
                        "status": "success" if outcome.status == "success" else "failed",
                        "result": outcome.result,
                        "error": outcome.error,
                    }
                )

                counts["executed"] += 1
                if outcome.status == "success":
                    counts["successful"] += 1
                else:
                    counts["failed"] += 1

                await self._emit(
                    "node_finished",
                    node_id,
                    status="success" if outcome.status == "success" else "failed",
                    error=outcome.error,
                )

                self._resolve_outbound(node_id, outcome.handles)

                if outcome.ended:
                    logger.info("Flow reached a terminal node, stopping")
                    stop_requested = True

        return results, counts

    async def _emit(self, event: str, node_id: str, **extra: Any) -> None:
        """
        Fire the progress callback for one node, swallowing any error.

        A broken subscriber must never take down an execution, so failures here
        are logged and ignored.
        """
        if not self._on_event:
            return
        try:
            node = self.nodes.get(node_id, {})
            await self._on_event(
                {
                    "event": event,
                    "node_id": node_id,
                    "node_name": node.get("name", node_id),
                    **extra,
                }
            )
        except Exception as e:
            logger.debug(f"Execution event callback failed: {e}")

    async def _run_guarded(self, node_id: str) -> NodeOutcome:
        """Run one node under the concurrency limit."""
        async with self._semaphore:
            node = self.nodes[node_id]
            return await self.run_node(node)


def default_handles(node: Dict[str, Any], result: Optional[Dict[str, Any]]) -> List[str]:
    """
    Work out which outputs a completed node fires.

    Args:
        node: The node definition
        result: Its handler's result payload

    Returns:
        Handle ids that carry data onward
    """
    node_type = node.get("type", "")
    result = result or {}

    # if/else: exactly one of true/false
    if node_type == "condition":
        branch = result.get("branch")
        if branch in (graph_utils.HANDLE_TRUE, graph_utils.HANDLE_FALSE):
            return [branch]
        return [graph_utils.HANDLE_TRUE if result.get("result") else graph_utils.HANDLE_FALSE]

    # filter: pass through, or stop this path entirely
    if node_type == "filter":
        return [graph_utils.HANDLE_OUT] if result.get("passed") else []

    # switch: the matched branch, else the fallback
    if node_type == "switch":
        handle = result.get("handle")
        return [handle] if handle else []

    # loop: the body already ran inline, so only `done` continues
    if node_type == "loop":
        return [graph_utils.HANDLE_DONE]

    if node_type in graph_utils.TERMINAL_TYPES:
        return []

    return [graph_utils.HANDLE_OUT]
