"""
Workflow graph model (schema v2).

Replaces the v1 representation — a flat ordered list of steps whose only
connectivity was an optional ``next_step_id`` — with an explicit directed graph
of nodes and edges, including canvas positions so a visual builder can round
trip its own layout.

The graph is stored in the existing ``workflows.workflow_steps`` JSON column so
no database migration is required:

    v1:  {"steps": [ {...}, {...} ]}
    v2:  {"schema_version": 2, "nodes": [...], "edges": [...], "viewport": {...}}

``load_graph`` accepts either and always returns a v2 graph, so old workflows
keep executing untouched.
"""
import logging
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 2

# Canvas geometry used when generating positions for migrated workflows.
_LAYOUT_X = 320
_LAYOUT_Y_SPACING = 170
_LAYOUT_BRANCH_X_OFFSET = 280

# Node types that terminate a branch.
TERMINAL_TYPES = {"end", "transfer"}

# Handle names.
HANDLE_IN = "in"
HANDLE_OUT = "out"
HANDLE_TRUE = "true"
HANDLE_FALSE = "false"
HANDLE_LOOP = "loop"
HANDLE_DONE = "done"
HANDLE_FALLBACK = "fallback"

# Types that expose true/false outputs instead of a single "out".
BRANCHING_TYPES = {"condition"}

# Types whose outputs depend on their configuration.
DYNAMIC_OUTPUT_TYPES = {"switch"}


class GraphError(Exception):
    """Raised when a workflow graph is structurally invalid."""


def output_handles(node_type: str, config: Optional[Dict[str, Any]] = None) -> List[str]:
    """
    Return the output handle names for a node.

    Args:
        node_type: Node type key
        config: Node configuration, needed for types whose outputs are
            configuration-driven (switch)

    Returns:
        Ordered list of output handle names (empty for terminal nodes)
    """
    if node_type in TERMINAL_TYPES:
        return []
    if node_type in BRANCHING_TYPES:
        return [HANDLE_TRUE, HANDLE_FALSE]
    if node_type == "loop":
        return [HANDLE_LOOP, HANDLE_DONE]
    if node_type == "switch":
        rules = (config or {}).get("rules") or []
        handles = [f"branch-{i}" for i in range(len(rules))]
        handles.append(HANDLE_FALLBACK)
        return handles
    return [HANDLE_OUT]


def has_input(node_type: str) -> bool:
    """Whether a node type accepts an inbound edge."""
    return node_type != "trigger"


# ============================================================================
# Loading / migration
# ============================================================================


def load_graph(workflow_steps: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Load a workflow definition as a v2 graph, migrating v1 on the fly.

    Args:
        workflow_steps: Raw contents of ``workflows.workflow_steps``

    Returns:
        A v2 graph dict with ``nodes`` and ``edges``
    """
    if not workflow_steps:
        return empty_graph()

    if workflow_steps.get("schema_version") == SCHEMA_VERSION or (
        "nodes" in workflow_steps and "edges" in workflow_steps
    ):
        return normalize_graph(workflow_steps)

    steps = workflow_steps.get("steps") or []
    return migrate_v1_to_v2(steps)


def input_schema(graph: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build a JSON Schema describing what a workflow expects as input.

    This is what lets a workflow be exposed to a voice agent as a callable
    tool: the LLM needs to know which parameters to extract from the
    conversation. Inputs are declared on the trigger node.

    Args:
        graph: Workflow graph

    Returns:
        A JSON Schema object with ``properties`` and ``required``
    """
    trigger = next(
        (n for n in graph.get("nodes", []) if n.get("type") == "trigger"), None
    )
    inputs = ((trigger or {}).get("config") or {}).get("inputs") or []

    properties: Dict[str, Any] = {}
    required: List[str] = []

    for field in inputs:
        name = (field.get("name") or "").strip()
        if not name:
            continue

        properties[name] = {
            "type": field.get("type") or "string",
            "description": field.get("description") or name,
        }
        if field.get("required"):
            required.append(name)

    return {"type": "object", "properties": properties, "required": required}


def empty_graph() -> Dict[str, Any]:
    """Return a new graph containing only a trigger node."""
    return {
        "schema_version": SCHEMA_VERSION,
        "nodes": [
            {
                "id": "trigger",
                "type": "trigger",
                "name": "When workflow runs",
                "position": {"x": _LAYOUT_X, "y": 40},
                "config": {},
            }
        ],
        "edges": [],
        "viewport": {"x": 0, "y": 0, "zoom": 1},
    }


def normalize_graph(graph: Dict[str, Any]) -> Dict[str, Any]:
    """
    Fill in defaults so downstream code can assume a complete graph.

    Args:
        graph: Partially specified graph

    Returns:
        Normalized graph (a new dict; the input is not mutated)
    """
    nodes = []
    for index, raw in enumerate(graph.get("nodes") or []):
        node = dict(raw)
        node.setdefault("id", f"node_{index}")
        node.setdefault("type", "speak")
        node.setdefault("name", node["type"].title())
        node.setdefault("config", {})
        # Per-node execution settings: retry, timeout, on_error.
        node.setdefault("settings", {})
        position = node.get("position") or {}
        node["position"] = {
            "x": float(position.get("x", _LAYOUT_X)),
            "y": float(position.get("y", index * _LAYOUT_Y_SPACING)),
        }
        nodes.append(node)

    edges = []
    for index, raw in enumerate(graph.get("edges") or []):
        edge = dict(raw)
        if not edge.get("source") or not edge.get("target"):
            continue
        edge.setdefault("id", f"edge_{index}")
        edge.setdefault("sourceHandle", HANDLE_OUT)
        edge.setdefault("targetHandle", HANDLE_IN)
        edges.append(edge)

    return {
        "schema_version": SCHEMA_VERSION,
        "nodes": nodes,
        "edges": edges,
        "viewport": graph.get("viewport") or {"x": 0, "y": 0, "zoom": 1},
    }


def migrate_v1_to_v2(steps: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Convert a v1 ordered step list into a v2 graph.

    Connectivity is reconstructed from, in precedence order:
      1. ``config.on_true`` / ``config.on_false`` for condition steps
      2. ``next_step_id``
      3. adjacency in the original array

    Positions are generated as a simple vertical stack; the builder's "Tidy up"
    produces a better layout on demand.

    Args:
        steps: v1 step dicts

    Returns:
        A v2 graph
    """
    if not steps:
        return empty_graph()

    nodes: List[Dict[str, Any]] = [
        {
            "id": "trigger",
            "type": "trigger",
            "name": "When workflow runs",
            "position": {"x": _LAYOUT_X, "y": 40},
            "config": {},
        }
    ]
    edges: List[Dict[str, Any]] = []

    # Assign stable ids first so edges can reference them.
    ids: List[str] = []
    for index, step in enumerate(steps):
        ids.append(str(step.get("id") or f"step_{index}"))

    known = set(ids)

    for index, step in enumerate(steps):
        node_id = ids[index]
        node_type = step.get("type") or "speak"
        nodes.append(
            {
                "id": node_id,
                "type": node_type,
                "name": step.get("name") or node_type.title(),
                "description": step.get("description"),
                "position": {
                    "x": _LAYOUT_X,
                    "y": 40 + (index + 1) * _LAYOUT_Y_SPACING,
                },
                "config": step.get("config") or {},
            }
        )

    # Entry edge from the trigger to the first step.
    edges.append(
        {
            "id": "edge_trigger",
            "source": "trigger",
            "sourceHandle": HANDLE_OUT,
            "target": ids[0],
            "targetHandle": HANDLE_IN,
        }
    )

    for index, step in enumerate(steps):
        node_id = ids[index]
        node_type = step.get("type") or "speak"
        config = step.get("config") or {}
        fallthrough = ids[index + 1] if index + 1 < len(steps) else None

        if node_type in BRANCHING_TYPES:
            # v1 stored branch targets as step ids in config, and tolerated
            # both a bare string and a single-element list.
            for handle, key in ((HANDLE_TRUE, "on_true"), (HANDLE_FALSE, "on_false")):
                target = _coerce_target(config.get(key)) or fallthrough
                if target and target in known:
                    edges.append(
                        {
                            "id": f"edge_{node_id}_{handle}",
                            "source": node_id,
                            "sourceHandle": handle,
                            "target": target,
                            "targetHandle": HANDLE_IN,
                        }
                    )
            continue

        if node_type in TERMINAL_TYPES:
            continue

        target = _coerce_target(step.get("next_step_id")) or fallthrough
        if target and target in known:
            edges.append(
                {
                    "id": f"edge_{node_id}_out",
                    "source": node_id,
                    "sourceHandle": HANDLE_OUT,
                    "target": target,
                    "targetHandle": HANDLE_IN,
                }
            )

    logger.info(f"Migrated v1 workflow: {len(steps)} steps -> {len(edges)} edges")

    return {
        "schema_version": SCHEMA_VERSION,
        "nodes": nodes,
        "edges": edges,
        "viewport": {"x": 0, "y": 0, "zoom": 1},
    }


def _coerce_target(value: Any) -> Optional[str]:
    """
    Normalize a v1 branch target.

    ``on_true``/``on_false`` were typed as ``List[str]`` in the schema but read
    as a scalar by the engine, so both shapes exist in stored data.
    """
    if not value:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return str(value[0]) if value else None
    return str(value)


# ============================================================================
# Traversal
# ============================================================================


def index_nodes(graph: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """Return a node-id -> node mapping."""
    return {node["id"]: node for node in graph.get("nodes", [])}


def outgoing(graph: Dict[str, Any], node_id: str, handle: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Return edges leaving a node, optionally filtered by source handle.

    Args:
        graph: Workflow graph
        node_id: Source node id
        handle: Source handle to filter on, or None for all

    Returns:
        Matching edges
    """
    result = []
    for edge in graph.get("edges", []):
        if edge.get("source") != node_id:
            continue
        if handle is not None and edge.get("sourceHandle", HANDLE_OUT) != handle:
            continue
        result.append(edge)
    return result


def subgraph_from(graph: Dict[str, Any], node_id: str, handle: str) -> Dict[str, Any]:
    """
    Extract the sub-graph hanging off one output handle.

    Used for a loop's body: everything downstream of the ``loop`` output is run
    once per item, independently of the ``done`` path.

    Args:
        graph: Full workflow graph
        node_id: The branching node (e.g. the loop)
        handle: Which output to follow

    Returns:
        A graph containing only the reachable nodes and the edges between them
    """
    roots = [e["target"] for e in outgoing(graph, node_id, handle)]

    reachable: Set[str] = set()
    stack = list(roots)
    while stack:
        current = stack.pop()
        # Never pull the branching node itself back into its own body.
        if current in reachable or current == node_id:
            continue
        reachable.add(current)
        for edge in outgoing(graph, current):
            stack.append(edge["target"])

    by_id = index_nodes(graph)
    nodes = [by_id[n] for n in reachable if n in by_id]
    edges = [
        e
        for e in graph.get("edges", [])
        if e.get("source") in reachable and e.get("target") in reachable
    ]

    return {
        "schema_version": SCHEMA_VERSION,
        "nodes": nodes,
        "edges": edges,
        "viewport": graph.get("viewport"),
    }


def entry_node_id(graph: Dict[str, Any]) -> Optional[str]:
    """
    Find where execution starts.

    Prefers the trigger node's first outgoing edge; otherwise falls back to any
    node with no inbound edges.

    Args:
        graph: Workflow graph

    Returns:
        Node id to execute first, or None for an empty graph
    """
    nodes = graph.get("nodes", [])
    if not nodes:
        return None

    trigger = next((n for n in nodes if n.get("type") == "trigger"), None)
    if trigger:
        edges = outgoing(graph, trigger["id"])
        if edges:
            return edges[0]["target"]
        # A trigger with nothing wired to it means an empty workflow.
        return None

    targets: Set[str] = {e.get("target") for e in graph.get("edges", [])}
    for node in nodes:
        if node["id"] not in targets:
            return node["id"]

    return nodes[0]["id"]


def next_node_id(
    graph: Dict[str, Any],
    node_id: str,
    branch: Optional[bool] = None,
) -> Optional[str]:
    """
    Resolve the next node to execute after ``node_id``.

    Args:
        graph: Workflow graph
        node_id: Node that just finished
        branch: For branching nodes, which output was taken

    Returns:
        Next node id, or None if this branch ends here
    """
    if branch is not None:
        handle = HANDLE_TRUE if branch else HANDLE_FALSE
        edges = outgoing(graph, node_id, handle)
        if edges:
            return edges[0]["target"]
        return None

    edges = outgoing(graph, node_id, HANDLE_OUT)
    if edges:
        return edges[0]["target"]

    # Tolerate graphs whose edges omit an explicit handle.
    edges = outgoing(graph, node_id)
    return edges[0]["target"] if edges else None


# ============================================================================
# Validation
# ============================================================================


def validate_graph(graph: Dict[str, Any]) -> Dict[str, List[Dict[str, str]]]:
    """
    Check a graph for structural problems.

    Returns errors (block execution) and warnings (allowed but suspect) rather
    than raising, so the builder can surface them inline while editing.

    Args:
        graph: Workflow graph

    Returns:
        ``{"errors": [...], "warnings": [...]}`` where each item is
        ``{"nodeId": str|None, "message": str}``
    """
    errors: List[Dict[str, str]] = []
    warnings: List[Dict[str, str]] = []

    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])
    by_id = index_nodes(graph)

    if not nodes:
        errors.append({"nodeId": None, "message": "Workflow is empty"})
        return {"errors": errors, "warnings": warnings}

    # Duplicate ids corrupt edge targeting.
    seen: Set[str] = set()
    for node in nodes:
        if node["id"] in seen:
            errors.append(
                {"nodeId": node["id"], "message": f"Duplicate node id '{node['id']}'"}
            )
        seen.add(node["id"])

    triggers = [n for n in nodes if n.get("type") == "trigger"]
    if len(triggers) > 1:
        errors.append({"nodeId": None, "message": "Workflow has more than one trigger"})
    if not triggers:
        warnings.append({"nodeId": None, "message": "Workflow has no trigger node"})

    # Dangling edge endpoints.
    for edge in edges:
        if edge.get("source") not in by_id:
            errors.append(
                {"nodeId": None, "message": f"Edge references missing node '{edge.get('source')}'"}
            )
        if edge.get("target") not in by_id:
            errors.append(
                {"nodeId": None, "message": f"Edge references missing node '{edge.get('target')}'"}
            )

    # Unreachable nodes.
    entry = entry_node_id(graph)
    reachable: Set[str] = set()
    if entry:
        stack = [entry]
        while stack:
            current = stack.pop()
            if current in reachable or current not in by_id:
                continue
            reachable.add(current)
            for edge in outgoing(graph, current):
                stack.append(edge["target"])

    for node in nodes:
        if node.get("type") == "trigger":
            continue
        if node["id"] not in reachable:
            warnings.append(
                {
                    "nodeId": node["id"],
                    "message": f"'{node.get('name')}' is not connected to the flow",
                }
            )

    # Branch nodes missing an output.
    for node in nodes:
        node_type = node.get("type", "")
        handles = output_handles(node_type, node.get("config"))
        if len(handles) < 2:
            continue
        for handle in handles:
            if not outgoing(graph, node["id"], handle):
                warnings.append(
                    {
                        "nodeId": node["id"],
                        "message": (
                            f"'{node.get('name')}' has no '{handle}' output connected"
                        ),
                    }
                )

    if _has_cycle(graph):
        errors.append(
            {"nodeId": None, "message": "Workflow contains a loop; remove the cycle"}
        )

    return {"errors": errors, "warnings": warnings}


def _has_cycle(graph: Dict[str, Any]) -> bool:
    """Detect a directed cycle via iterative DFS with a colour map."""
    by_id = index_nodes(graph)
    WHITE, GREY, BLACK = 0, 1, 2
    colour: Dict[str, int] = {node_id: WHITE for node_id in by_id}

    for start in list(colour):
        if colour[start] != WHITE:
            continue
        stack: List[Tuple[str, bool]] = [(start, False)]
        while stack:
            node_id, leaving = stack.pop()
            if leaving:
                colour[node_id] = BLACK
                continue
            if colour.get(node_id) == GREY:
                return True
            if colour.get(node_id) == BLACK:
                continue
            colour[node_id] = GREY
            stack.append((node_id, True))
            for edge in outgoing(graph, node_id):
                target = edge["target"]
                if colour.get(target) == GREY:
                    return True
                if colour.get(target) == WHITE:
                    stack.append((target, False))
    return False
