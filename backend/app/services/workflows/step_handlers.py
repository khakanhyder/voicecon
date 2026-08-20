"""
Workflow Step Handlers.

Handlers for different types of workflow steps.
"""
import logging
import asyncio
import json
import re
import uuid
from typing import Dict, Any, List, Optional, Tuple
from datetime import date, datetime, time
from decimal import Decimal

from app.schemas.workflow import StepType
from app.services.workflows.data_mapper import DataMappingError

logger = logging.getLogger(__name__)

#: Transforms that are meaningful on an absent or empty value. An aggregation
#: over nothing has a real answer (no orders total 0, and there is no average of
#: nothing), so these are allowed through instead of being reported as a broken
#: reference.
_EMPTY_SAFE_TRANSFORMS = frozenset({
    "sum", "average", "min_value", "max_value", "count", "pluck",
    "array_length", "array_first", "array_last", "array_join", "array_filter",
    "default", "coalesce", "to_string",
})

# Matches an array access segment in a variable path, e.g. "results[0]".
_ARRAY_ACCESS = re.compile(r"^(\w+)\[(-?\d+)\]$")

# Any {{reference}} inside a larger string.
_TEMPLATE = re.compile(r"\{\{([^}]+)\}\}")

# A string that is *only* one reference, e.g. "{{trigger.amount}}" or
# "  {{ trigger.amount }}  ". Surrounding whitespace is tolerated because a
# builder field trivially collects it; anything else around the reference makes
# it a mixed template whose result can only be text.
_WHOLE_TEMPLATE = re.compile(r"^\s*\{\{([^}]+)\}\}\s*$")


class StepExecutionError(Exception):
    """Raised when step execution fails."""
    pass


def _as_text(value: Any) -> str:
    """Render a resolved value for embedding in text.

    ``str()`` is wrong for containers and booleans: it produces Python
    spellings (``True``, single-quoted dict reprs) that are not valid JSON and
    read as nonsense in a spoken prompt. Structures are rendered as JSON;
    scalars keep their natural text form.
    """
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (dict, list, tuple)):
        try:
            return json.dumps(value, default=str)
        except (TypeError, ValueError):
            return str(value)
    if isinstance(value, Decimal):
        return format(value, "f")
    return str(value)


def json_safe(value: Any) -> Any:
    """Render a value in a form the finished run can actually be saved as.

    A workflow's result — every step's output and the whole final context — is
    persisted to a JSON column. The date transforms hand back real ``datetime``
    objects, which is exactly what makes them chainable, but one of those left
    anywhere in the run kills it at save time with "Object of type datetime is
    not JSON serializable". The step itself reported success, so the failure
    surfaced far from its cause and took the run's whole record with it.

    Dates become ISO 8601 text, which round-trips: ``add_hours``, ``add_days``
    and ``format_date`` all parse an ISO string, so a later step can still build
    on an earlier one. ``Decimal`` and ``UUID`` get the same treatment because a
    connector response can carry either.

    Args:
        value: Any value produced by a step

    Returns:
        The same value with unserializable leaves rendered as text
    """
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, dict):
        return {key: json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [json_safe(item) for item in value]
    return value


def _transform_chain(spec: Dict[str, Any], field: str) -> List[Tuple[str, Any]]:
    """Read a field's transform as an ordered chain of (name, argument).

    One transform per field cannot express "work the value out, then format it"
    — and the date transforms *need* that pairing, because on their own they
    return a datetime rather than something a caller can read. So ``transform``
    accepts a list as well as a single name.

    Both spellings of a chain step are honoured: ``"format_date:%H:%M"`` for
    hand-written config, and ``{"name": ..., "args": ...}`` for the builder,
    which keeps the argument in its own box rather than asking a non-technical
    user to punctuate it.

    Args:
        spec: The field's mapping spec
        field: Field name, for error messages

    Returns:
        Ordered (transform name, argument) pairs; empty when none is set
    """
    raw = spec.get("transform")
    if not raw:
        return []

    if isinstance(raw, str):
        return [(raw, spec.get("args"))]

    if isinstance(raw, list):
        chain: List[Tuple[str, Any]] = []
        for step in raw:
            if isinstance(step, str):
                # Split once only: a format like "%H:%M" contains colons too.
                name, separator, inline = step.partition(":")
                chain.append((name.strip(), inline if separator else None))
            elif isinstance(step, dict):
                chain.append((str(step.get("name") or "").strip(), step.get("args")))
            else:
                raise StepExecutionError(
                    f"Set Fields: '{field}' has a transform step that is neither "
                    f"a name nor a name and argument."
                )
            if not chain[-1][0]:
                raise StepExecutionError(
                    f"Set Fields: '{field}' has a transform step with no name."
                )
        return chain

    raise StepExecutionError(
        f"Set Fields: '{field}' has a transform that is neither a name nor a list."
    )


def _normalize_var_name(raw: Any) -> str:
    """
    Turn a user-entered variable reference into a plain context key.

    Accepts "name", "{{name}}", or "{{ name }}" — the builder's help text shows
    the braced form, so both spellings turn up in real configs.
    """
    name = str(raw or "").strip()
    if name.startswith("{{") and name.endswith("}}"):
        name = name[2:-2].strip()
    return name


class WorkflowContext:
    """
    Workflow execution context.

    Stores variables and data that can be referenced across steps.
    """

    def __init__(
        self,
        trigger_data: Optional[Dict[str, Any]] = None,
        channel: Optional[Any] = None,
        organization_id: Optional[uuid.UUID] = None,
    ):
        """
        Initialize workflow context.

        Args:
            trigger_data: Initial trigger data
            channel: Execution channel for voice steps (speak/ask/transfer/end).
                Defaults to a SimulatedChannel so a flow is always runnable —
                e.g. a "Run" from the dashboard, where there is no live call.
            organization_id: The workspace this run belongs to. Steps that look
                up a stored record by an id taken from step config MUST scope
                that lookup to it.

                This context previously carried no tenant identity at all, which
                meant the integration and tool steps loaded rows by bare id: a
                user could name *another organization's* connection or tool in
                their own workflow and the step would execute it, using that
                organization's decrypted credentials and returning the response.
                Scoping is only possible if the org travels with the run, which
                is what this field is for.
        """
        self.organization_id = organization_id

        self.variables = {
            "trigger": trigger_data or {},
            "steps": {},
        }

        if channel is None:
            # No live call: dry-run the flow. A test run can script the caller's
            # side by passing trigger_data={"answers": {"<variable>": "<reply>"}},
            # which is what the dashboard's "Run" uses to exercise branches.
            from app.services.workflows.channels import SimulatedChannel

            answers = (trigger_data or {}).get("answers")
            channel = SimulatedChannel(answers=answers if isinstance(answers, dict) else None)
        self.channel = channel

        # Set by an `end` step to tell the engine to stop walking the flow.
        self.ended: bool = False

    def set_variable(self, key: str, value: Any) -> None:
        """
        Set a context variable.

        Args:
            key: Variable key
            value: Variable value
        """
        self.variables[key] = value

    def get_variable(self, key: str, default: Any = None) -> Any:
        """
        Get a context variable.

        Args:
            key: Variable key
            default: Default value if not found

        Returns:
            Variable value
        """
        # Dot notation with array indexing, e.g.
        # "steps.geocode.body.results[0].latitude". Real APIs return arrays
        # constantly, so without indexing most responses were unreachable.
        keys = key.split(".")
        value = self.variables

        for k in keys:
            match = _ARRAY_ACCESS.match(k)

            if match:
                name, index = match.group(1), int(match.group(2))
                if not isinstance(value, dict):
                    return default
                value = value.get(name)
                if not isinstance(value, (list, tuple)) or not (
                    -len(value) <= index < len(value)
                ):
                    return default
                value = value[index]
            elif isinstance(value, dict):
                value = value.get(k)
            elif isinstance(value, (list, tuple)) and k.lstrip("-").isdigit():
                # Also allow plain "results.0.latitude"
                index = int(k)
                if not (-len(value) <= index < len(value)):
                    return default
                value = value[index]
            else:
                return default

            if value is None:
                return default

        return value

    def set_step_result(self, step_id: str, result: Any) -> None:
        """
        Set step result.

        Args:
            step_id: Step ID
            result: Step result
        """
        if "steps" not in self.variables:
            self.variables["steps"] = {}

        self.variables["steps"][step_id] = result

    def interpolate(self, value: Any) -> Any:
        """
        Resolve ``{{variable.path}}`` references, preserving JSON types.

        Two distinct cases, because they mean different things:

        * **Whole-value** — the string is nothing but one reference, e.g.
          ``"{{trigger.amount}}"``. The reference *is* the value, so the
          resolved value is returned with its own type: ``42`` stays the number
          42, ``True`` stays a boolean, an object stays an object. This is what
          a builder field bound to a single variable produces, and it is by far
          the common case.
        * **Mixed** — the reference is embedded in surrounding text, e.g.
          ``"Hello {{name}}, you owe {{amount}}"``. The result can only be a
          string, so each reference is stringified and substituted.

        Stringifying the whole-value case (which is what this used to do)
        silently corrupted every integration that sends anything but text: a
        webhook step posted ``"amount": "42"`` where the receiving API wanted
        ``42``, ``"paid": "True"`` instead of JSON ``true``, and an object as
        its Python ``repr`` — all while the run reported success.

        An unresolved reference becomes ``None`` (whole-value) or an empty
        string (mixed) rather than being left in place. Leaking a literal
        ``"{{trigger.missing}}"`` into an outbound payload is never what the
        caller meant, and it is impossible to distinguish downstream from a
        real value.

        Args:
            value: A string, or any structure containing strings

        Returns:
            The value with references resolved; strings only where the input
            was genuinely text
        """
        if isinstance(value, str):
            whole = _WHOLE_TEMPLATE.match(value)
            if whole:
                return self.get_variable(whole.group(1).strip())

            matches = _TEMPLATE.findall(value)
            if not matches:
                return value

            result = value
            for match in matches:
                var_value = self.get_variable(match.strip())
                replacement = "" if var_value is None else _as_text(var_value)
                result = result.replace(f"{{{{{match}}}}}", replacement)

            return result

        elif isinstance(value, dict):
            return {k: self.interpolate(v) for k, v in value.items()}

        elif isinstance(value, list):
            return [self.interpolate(item) for item in value]

        else:
            return value

    def interpolate_text(self, value: Any) -> str:
        """Interpolate and force the result to a string.

        For sinks that can only accept text — HTTP header values, spoken
        prompts — where a resolved object or number has to be rendered rather
        than passed through.
        """
        return _as_text(self.interpolate(value))


class BaseStepHandler:
    """Base class for step handlers."""

    def __init__(self, db=None):
        """
        Initialize step handler.

        Args:
            db: Database session
        """
        self.db = db

    async def execute(
        self,
        step: Dict[str, Any],
        context: WorkflowContext,
    ) -> Dict[str, Any]:
        """
        Execute step.

        Args:
            step: Step configuration
            context: Workflow context

        Returns:
            Step result

        Raises:
            StepExecutionError: If step execution fails
        """
        raise NotImplementedError("Subclasses must implement execute()")


class ActionStepHandler(BaseStepHandler):
    """Handler for action steps."""

    async def execute(
        self,
        step: Dict[str, Any],
        context: WorkflowContext,
    ) -> Dict[str, Any]:
        """
        Execute action step.

        Calls an integration connector action.

        Args:
            step: Step configuration
            context: Workflow context

        Returns:
            Action result
        """
        try:
            config = step.get("config", {})

            # Get connection
            connection_id = config.get("connection_id")
            if not connection_id:
                raise StepExecutionError("Missing connection_id in action config")

            action = config.get("action")
            if not action:
                raise StepExecutionError("Missing action in action config")

            # Interpolate parameters
            parameters = context.interpolate(config.get("parameters", {}))

            logger.info(f"Executing action: {action} with connection {connection_id}")

            # Import here to avoid circular imports
            from sqlalchemy import select
            from app.models.integration import IntegrationConnection, IntegrationConnector

            # Get connection and connector.
            #
            # Scoped to the running workflow's organization. Without this, the
            # bare id from step config selected any connection on the platform,
            # and the step then executed against that tenant's decrypted OAuth
            # tokens and returned the response — cross-tenant read and write
            # through someone else's credentials.
            if context.organization_id is None:
                raise StepExecutionError(
                    "Action step cannot resolve a connection without a workspace "
                    "context"
                )

            query = select(IntegrationConnection).where(
                IntegrationConnection.id == connection_id,
                IntegrationConnection.organization_id == context.organization_id,
            )
            result = await self.db.execute(query)
            connection = result.scalar_one_or_none()

            if not connection:
                # Deliberately identical to the genuinely-missing case: telling
                # the caller a connection exists but belongs to someone else
                # confirms the id, which is exactly what a probe is looking for.
                raise StepExecutionError(f"Connection {connection_id} not found")

            # Get connector
            query = select(IntegrationConnector).where(
                IntegrationConnector.id == connection.connector_id
            )
            result = await self.db.execute(query)
            connector = result.scalar_one_or_none()

            if not connector:
                raise StepExecutionError("Connector not found")

            # Get connector class dynamically. CONNECTOR_CLASS_MAP is the one
            # source of truth — this used to be a second hand-maintained copy of
            # it, and the copies drifted: Stripe was present here but absent
            # from the registry, so a 696-line working connector could not be
            # reached from a workflow at all.
            from app.services.integrations.action_registry import CONNECTOR_CLASS_MAP

            connector_class_name = CONNECTOR_CLASS_MAP.get(connector.slug)
            if not connector_class_name:
                raise StepExecutionError(f"Unsupported connector: {connector.slug}")

            # Import connector dynamically
            from app.services.integrations import connectors
            connector_class = getattr(connectors, connector_class_name)

            # Initialize connector
            connector_instance = connector_class(
                connection=connection,
                connector=connector,
                db=self.db,
            )

            try:
                # Execute action
                # The registry is the allowlist, not merely a source of parameter
                # defaults. `hasattr` alone let step config name *any* attribute
                # on the connector — including internal helpers never meant to be
                # reachable from a workflow — because a connector with no schema
                # for the action simply fell through with `accepted = None`.
                from app.services.integrations.action_registry import (
                    get_action_schema as _lookup_action,
                )

                if not _lookup_action(connector.slug, action):
                    raise StepExecutionError(
                        f"Action '{action}' is not available on {connector.slug}"
                    )

                if not hasattr(connector_instance, action):
                    raise StepExecutionError(f"Action {action} not found on connector")

                # Anything the author left blank falls back to the choice made
                # once when the integration was connected — "cards go to this
                # list" — so most workflows never have to name a list at all.
                # An explicit value always wins; this only fills gaps.
                from app.services.integrations.action_registry import (
                    adapt_parameters,
                    drop_unsupported_arguments,
                    get_action_schema,
                    strip_ui_only_parameters,
                )
                from app.services.integrations.resource_registry import (
                    apply_connection_defaults,
                )

                # Only defaults this action actually accepts. A Trello
                # connection defaults board_id and list_id; add_comment takes
                # neither, and passing them raises TypeError.
                schema = get_action_schema(connector.slug, action)
                accepted = set(
                    ((schema.get("parameters") or {}).get("properties") or {}).keys()
                ) or None
                parameters = apply_connection_defaults(
                    parameters, connection.config, accepted_keys=accepted
                )
                # Fields that only exist to drive a picker are not real
                # arguments; passing them raises TypeError.
                parameters = strip_ui_only_parameters(
                    connector.slug, action, parameters
                )
                # Saved steps store the schema's parameter names. Translate to
                # the connector's before drop_unsupported_arguments gets a look
                # at them, or a renamed key is discarded as "unknown" and the
                # step fails on a missing required argument instead.
                parameters = adapt_parameters(connector.slug, action, parameters)

                action_method = getattr(connector_instance, action)
                # Last line of defence before ``**parameters``: a step whose
                # action was changed after it was configured still carries the
                # old action's fields, and one unknown key is a TypeError that
                # kills the run. The signature is the only thing that knows for
                # certain what is safe to pass.
                parameters = drop_unsupported_arguments(
                    action_method, parameters, context=f"{connector.slug}.{action}"
                )
                result = await action_method(**parameters)

                logger.info(f"Action {action} executed successfully")

                return {
                    "success": True,
                    "result": result,
                }

            finally:
                await connector_instance.close()

        except Exception as e:
            logger.error(f"Action step failed: {e}", exc_info=True)
            raise StepExecutionError(f"Action step failed: {str(e)}")


class ConditionStepHandler(BaseStepHandler):
    """Handler for condition steps."""

    async def execute(
        self,
        step: Dict[str, Any],
        context: WorkflowContext,
    ) -> Dict[str, Any]:
        """
        Execute condition step.

        Evaluates a condition and determines which branch to take.

        Args:
            step: Step configuration
            context: Workflow context

        Returns:
            Condition result
        """
        try:
            config = step.get("config", {})

            # Two accepted shapes:
            #  1. Builder UI:  {variable, operator, value}  — the structured form
            #     the visual editor writes.
            #  2. Expression:  {condition: "{{x}} == 5"}    — free-form string.
            if config.get("variable") is not None and config.get("operator"):
                result = self._evaluate_structured(config, context)
            elif config.get("condition"):
                # An expression is parsed as text, so render rather than
                # resolve: "{{flag}}" must arrive as "true", not a bool.
                condition_str = context.interpolate_text(config["condition"])
                result = self._evaluate_condition(condition_str, context)
            else:
                raise StepExecutionError(
                    "Condition step needs either 'variable' + 'operator' or a 'condition' expression"
                )

            logger.info(f"Condition evaluated to: {result}")

            # Branch target: a step id to jump to. The engine falls through to the
            # next step in order when the taken branch has no target set.
            return {
                "success": True,
                "result": result,
                "branch": "true" if result else "false",
                "next_step_id": config.get("on_true" if result else "on_false") or None,
            }

        except Exception as e:
            logger.error(f"Condition step failed: {e}", exc_info=True)
            raise StepExecutionError(f"Condition step failed: {str(e)}")

    def _evaluate_structured(self, config: Dict[str, Any], context: WorkflowContext) -> bool:
        """
        Evaluate the builder's {variable, operator, value} condition.

        `variable` may be a bare name ("intent"), a dotted path
        ("trigger.intent"), or wrapped ("{{intent}}"). Comparison is
        case-insensitive on strings, which is what callers' transcribed speech
        realistically needs.
        """
        ref = _normalize_var_name(config.get("variable", ""))
        actual = context.get_variable(ref)
        operator = str(config.get("operator", "equals")).strip()
        expected = context.interpolate(config.get("value", ""))

        # Presence checks first — they don't need a comparison value.
        if operator == "is_empty":
            return actual is None or str(actual).strip() == ""
        if operator == "is_not_empty":
            return actual is not None and str(actual).strip() != ""

        a = "" if actual is None else str(actual).strip().lower()
        b = "" if expected is None else str(expected).strip().lower()

        # Compare numerically when both sides are numbers, so "10" > "9" is right.
        def _as_num(x):
            try:
                return float(x)
            except (TypeError, ValueError):
                return None

        na, nb = _as_num(a), _as_num(b)

        if operator == "equals":
            return (na == nb) if (na is not None and nb is not None) else (a == b)
        if operator == "not_equals":
            return (na != nb) if (na is not None and nb is not None) else (a != b)
        if operator == "contains":
            return b in a
        if operator == "not_contains":
            return b not in a
        if operator == "starts_with":
            return a.startswith(b)
        if operator == "ends_with":
            return a.endswith(b)
        if operator in ("greater_than", "gt", ">"):
            return na is not None and nb is not None and na > nb
        if operator in ("less_than", "lt", "<"):
            return na is not None and nb is not None and na < nb

        raise StepExecutionError(f"Unsupported condition operator: {operator}")

    def _evaluate_condition(self, condition: str, context: WorkflowContext) -> bool:
        """
        Safely evaluate condition.

        Args:
            condition: Condition expression
            context: Workflow context

        Returns:
            Condition result
        """
        # Simple safe evaluation
        # Supports: ==, !=, <, >, <=, >=, contains, in

        # Replace common operators
        condition = str(condition).strip()

        # Handle "contains" operator
        if " contains " in condition:
            parts = condition.split(" contains ", 1)
            left = parts[0].strip().strip('"\'')
            right = parts[1].strip().strip('"\'')
            return right in left

        # Handle "in" operator
        if " in " in condition:
            parts = condition.split(" in ", 1)
            left = parts[0].strip().strip('"\'')
            right = parts[1].strip().strip('"\'')
            return left in right

        # Handle comparison operators
        for op in ["==", "!=", "<=", ">=", "<", ">"]:
            if op in condition:
                parts = condition.split(op, 1)
                left = parts[0].strip().strip('"\'')
                right = parts[1].strip().strip('"\'')

                # Try to convert to numbers if possible
                try:
                    left_num = float(left)
                    right_num = float(right)
                    left = left_num
                    right = right_num
                except ValueError:
                    pass

                if op == "==":
                    return left == right
                elif op == "!=":
                    return left != right
                elif op == "<":
                    return left < right
                elif op == ">":
                    return left > right
                elif op == "<=":
                    return left <= right
                elif op == ">=":
                    return left >= right

        # If no operator found, treat as boolean
        return bool(condition.lower() in ["true", "yes", "1"])


class LoopStepHandler(BaseStepHandler):
    """Handler for loop steps."""

    async def execute(
        self,
        step: Dict[str, Any],
        context: WorkflowContext,
    ) -> Dict[str, Any]:
        """
        Execute loop step.

        Iterates over items and executes sub-steps.

        Args:
            step: Step configuration
            context: Workflow context

        Returns:
            Loop result
        """
        try:
            config = step.get("config", {})

            # ── Resolve the items to iterate over ──────────────────────────
            # Accepts: a literal list; a "{{path}}"/"path" reference into the
            # context; or a numeric `count` for an N-times loop.
            items = self._resolve_items(config, context)

            max_iterations = config.get("max_iterations", 100)
            if len(items) > max_iterations:
                logger.warning(
                    f"Loop truncated to {max_iterations} of {len(items)} items"
                )
                items = items[:max_iterations]

            # ── The loop body: a list of sub-steps (same shape as top-level) ─
            sub_steps = config.get("steps") or config.get("body") or []
            if not isinstance(sub_steps, list):
                raise StepExecutionError("Loop 'steps' must be a list of steps")

            continue_on_error = bool(config.get("continue_on_error", False))
            # Preserve any outer loop scope so nested loops restore it after.
            outer_loop = context.variables.get("loop")

            iterations = []
            for index, item in enumerate(items):
                # Expose loop.item / loop.index / loop.length to sub-steps.
                # Stored as a nested dict so {{loop.item}} resolves via dot-path.
                context.variables["loop"] = {
                    "item": item,
                    "index": index,
                    "length": len(items),
                }

                logger.info(f"Loop iteration {index + 1}/{len(items)}")

                iter_results = []
                for sub_step in sub_steps:
                    sub_type = sub_step.get("type")
                    sub_id = sub_step.get("id", f"{step.get('id', 'loop')}[{index}]")
                    try:
                        handler = StepHandlerFactory.get_handler(sub_type, db=self.db)
                        sub_result = await handler.execute(sub_step, context)
                        # Make the sub-step's result referenceable by later steps.
                        if sub_step.get("id"):
                            context.set_step_result(sub_step["id"], sub_result.get("result"))
                        iter_results.append({
                            "step_id": sub_id,
                            "status": "success",
                            "result": sub_result.get("result"),
                        })
                    except Exception as sub_err:
                        logger.error(
                            f"Loop sub-step '{sub_id}' failed on iteration {index}: {sub_err}"
                        )
                        iter_results.append({
                            "step_id": sub_id,
                            "status": "failed",
                            "error": str(sub_err),
                        })
                        if not continue_on_error:
                            raise StepExecutionError(
                                f"Loop failed at iteration {index}, step '{sub_id}': {sub_err}"
                            )

                iterations.append({"index": index, "item": item, "steps": iter_results})

            # Restore the outer loop scope (or clear it) so nesting is clean.
            if outer_loop is not None:
                context.variables["loop"] = outer_loop
            else:
                context.variables.pop("loop", None)

            logger.info(f"Loop completed: {len(iterations)} iterations, {len(sub_steps)} step(s) each")

            return {
                "success": True,
                "result": {"iterations": iterations, "count": len(iterations)},
                "iterations": len(iterations),
            }

        except StepExecutionError:
            raise
        except Exception as e:
            logger.error(f"Loop step failed: {e}", exc_info=True)
            raise StepExecutionError(f"Loop step failed: {str(e)}")

    def _resolve_items(self, config: Dict[str, Any], context: "WorkflowContext") -> list:
        """Resolve the loop's iterable from config (list / reference / count)."""
        raw = config.get("items")

        if isinstance(raw, list):
            return raw

        if isinstance(raw, str) and raw.strip():
            ref = raw.strip()
            if ref.startswith("{{") and ref.endswith("}}"):
                ref = ref[2:-2]
            ref = ref.strip()
            resolved = context.get_variable(ref)
            if isinstance(resolved, list):
                return resolved
            if resolved is None:
                raise StepExecutionError(f"Loop items reference '{raw}' resolved to nothing")
            raise StepExecutionError(f"Loop items '{raw}' is not a list (got {type(resolved).__name__})")

        count = config.get("count")
        if isinstance(count, int) and count >= 0:
            return list(range(count))

        raise StepExecutionError("Loop requires 'items' (list or reference) or 'count'")


class TransformStepHandler(BaseStepHandler):
    """Handler for transform steps."""

    async def execute(
        self,
        step: Dict[str, Any],
        context: WorkflowContext,
    ) -> Dict[str, Any]:
        """
        Execute transform step.

        Transforms data using the DataMapper engine.

        Supports two modes:
        1. Simple transformations: key-value pairs with transformation specs
        2. Advanced mapping: Use DataMapper with full mapping configuration

        Args:
            step: Step configuration
            context: Workflow context

        Returns:
            Transform result
        """
        try:
            config = step.get("config", {})

            # Check if using advanced mapping mode
            if "mapping_config" in config:
                # Advanced mode: Use DataMapper
                from app.services.workflows.data_mapper import get_data_mapper

                mapper = get_data_mapper()
                mapping_config = config.get("mapping_config")

                # Get source data from context
                source_path = config.get("source", "trigger")
                source_data = context.get_variable(source_path)

                if not isinstance(source_data, dict):
                    # If source is not a dict, wrap it
                    source_data = {"value": source_data}

                # Interpolate mapping config if needed
                mapping_config = context.interpolate(mapping_config)

                # Apply mapping
                validate = config.get("validate", True)
                result = json_safe(
                    mapper.map_fields(source_data, mapping_config, validate=validate)
                )

                logger.info(f"Advanced transform completed with DataMapper")

                return {
                    "success": True,
                    "result": result,
                }

            else:
                # Simple mode: Basic transformations
                transformations = config.get("transformations", {})

                # Get DataMapper for transformation support
                from app.services.workflows.data_mapper import get_data_mapper
                mapper = get_data_mapper()

                results = {}

                for key, transform_spec in transformations.items():
                    # Get source value
                    if isinstance(transform_spec, dict):
                        # `source` names where the value comes from. The builder
                        # writes it braced ({{trigger.orders}}) because that is
                        # what every other field shows, so accept either form
                        # rather than silently resolving nothing.
                        source = transform_spec.get("source")
                        if source:
                            value = context.interpolate(source) \
                                if _TEMPLATE.search(str(source)) \
                                else context.get_variable(str(source))
                        else:
                            # A literal typed into the builder may still contain
                            # references; interpolating it keeps the two field
                            # kinds behaving the same way.
                            value = context.interpolate(transform_spec.get("value"))

                        # A default stands in for a missing source *before* the
                        # transform runs, so "Format as money" with a default of
                        # 0 formats the 0 rather than failing on the absence.
                        if value is None and "default" in transform_spec:
                            value = context.interpolate(transform_spec["default"])

                        # Apply the transforms in order. `args` is kept separate
                        # from the name so the builder can offer a dropdown plus
                        # an argument box instead of asking a non-technical user
                        # to type "truncate:40", and a chain lets one field both
                        # work a value out and format it.
                        for transform, args in _transform_chain(transform_spec, key):
                            if args not in (None, ""):
                                spec = {
                                    "name": transform,
                                    "args": context.interpolate(args),
                                }
                            else:
                                spec = transform

                            # Aggregations answer honestly for an empty list —
                            # "no orders" really does total 0 — but every other
                            # transform on a missing value is a broken
                            # reference, and reporting it here beats letting a
                            # TypeError surface as "float() argument must be a
                            # string or a real number, not 'NoneType'".
                            if value is None and transform not in _EMPTY_SAFE_TRANSFORMS:
                                raise StepExecutionError(
                                    f"Set Fields: '{key}' has no value to work on, so "
                                    f"'{transform}' cannot run. Check that the step "
                                    f"providing {transform_spec.get('source') or 'it'} "
                                    f"ran first, or set a default."
                                )

                            try:
                                value = mapper.apply_transformation(value, spec)
                            except DataMappingError as exc:
                                # Name the field, the transform and its argument.
                                # The mapper only ever sees the value, so its
                                # message alone leaves a builder user with
                                # nothing to act on.
                                detail = str(exc).replace("Transformation failed: ", "")
                                where = (
                                    f"'{transform}' (argument '{args}')"
                                    if args not in (None, "")
                                    else f"'{transform}'"
                                )
                                raise StepExecutionError(
                                    f"Set Fields: '{key}' — {where} failed: {detail}"
                                ) from exc

                        # A transform may still return nothing (average of an
                        # empty list); fall back to the default in that case too.
                        if value is None and "default" in transform_spec:
                            value = context.interpolate(transform_spec["default"])

                    elif isinstance(transform_spec, str):
                        # Simple string: interpolate it
                        value = context.interpolate(transform_spec)

                    else:
                        # Literal value
                        value = transform_spec

                    # A date transform returns a datetime, which the run cannot
                    # be saved with; render it before it reaches the context.
                    results[key] = json_safe(value)

                # Publish each field at the top level so later steps can use
                # {{field_name}} directly. Without this the builder's "Set
                # Fields" node and the data picker both promised names that
                # never resolved.
                for key, value in results.items():
                    context.set_variable(key, value)

                logger.info(f"Transform completed: {len(results)} variables")

                return {
                    "success": True,
                    "result": results,
                }

        except StepExecutionError:
            # Already phrased for the person who built the step; re-wrapping it
            # would prepend a second, less useful prefix.
            raise
        except Exception as e:
            logger.error(f"Transform step failed: {e}", exc_info=True)
            raise StepExecutionError(f"Transform step failed: {str(e)}")


class DelayStepHandler(BaseStepHandler):
    """Handler for delay steps."""

    async def execute(
        self,
        step: Dict[str, Any],
        context: WorkflowContext,
    ) -> Dict[str, Any]:
        """
        Execute delay step.

        Waits for specified duration.

        Args:
            step: Step configuration
            context: Workflow context

        Returns:
            Delay result
        """
        try:
            config = step.get("config", {})
            delay_seconds = config.get("delay_seconds", 0)

            if delay_seconds > 0:
                logger.info(f"Delaying for {delay_seconds} seconds")
                await asyncio.sleep(delay_seconds)

            return {
                "success": True,
                "result": {"delayed_seconds": delay_seconds},
            }

        except Exception as e:
            logger.error(f"Delay step failed: {e}", exc_info=True)
            raise StepExecutionError(f"Delay step failed: {str(e)}")


class SpeakStepHandler(BaseStepHandler):
    """Handler for speak steps — the agent says something to the caller."""

    async def execute(
        self,
        step: Dict[str, Any],
        context: WorkflowContext,
    ) -> Dict[str, Any]:
        try:
            config = step.get("config", {})
            message = context.interpolate(config.get("message", ""))

            if not str(message).strip():
                raise StepExecutionError("Speak step has an empty message")

            await context.channel.speak(str(message), voice=config.get("voice"))

            return {"success": True, "result": {"spoken": message}}

        except StepExecutionError:
            raise
        except Exception as e:
            logger.error(f"Speak step failed: {e}", exc_info=True)
            raise StepExecutionError(f"Speak step failed: {str(e)}")


class AskStepHandler(BaseStepHandler):
    """Handler for ask steps — ask the caller something and capture the answer."""

    async def execute(
        self,
        step: Dict[str, Any],
        context: WorkflowContext,
    ) -> Dict[str, Any]:
        try:
            config = step.get("config", {})
            question = context.interpolate(config.get("question", ""))

            # The field wants a bare name ("customer_name"), but the hint next to
            # it shows {{customer_name}}, so people naturally paste the braces in.
            # Accept either rather than silently storing under a braced key.
            variable = _normalize_var_name(config.get("variable", ""))

            if not str(question).strip():
                raise StepExecutionError("Ask step has an empty question")
            if not variable:
                raise StepExecutionError("Ask step needs a 'variable' to store the answer in")

            answer = await context.channel.ask(
                str(question),
                timeout=int(config.get("timeout", 10) or 10),
                input_type=config.get("input_type", "speech"),
                variable=variable,
            )

            # Publish at the top level so later steps can use {{variable}} directly.
            context.set_variable(variable, answer)

            return {
                "success": True,
                "result": {"question": question, "variable": variable, "answer": answer},
            }

        except StepExecutionError:
            raise
        except Exception as e:
            logger.error(f"Ask step failed: {e}", exc_info=True)
            raise StepExecutionError(f"Ask step failed: {str(e)}")


class SwitchStepHandler(BaseStepHandler):
    """
    Routes to the first matching branch, n-way.

    Each rule is a {variable, operator, value} triple identical to a condition,
    evaluated in order. The first match wins and its handle fires; when nothing
    matches the `fallback` output fires instead.
    """

    async def execute(
        self,
        step: Dict[str, Any],
        context: WorkflowContext,
    ) -> Dict[str, Any]:
        try:
            config = step.get("config", {})
            rules = config.get("rules") or []

            if not rules:
                raise StepExecutionError("Switch step has no rules")

            evaluator = ConditionStepHandler(db=self.db)

            for index, rule in enumerate(rules):
                if evaluator._evaluate_structured(rule, context):
                    handle = f"branch-{index}"
                    logger.info(f"Switch matched rule {index} -> {handle}")
                    return {
                        "success": True,
                        "result": {
                            "matched": True,
                            "rule_index": index,
                            "label": rule.get("label") or f"Branch {index + 1}",
                        },
                        "handle": handle,
                    }

            logger.info("Switch matched no rule, taking fallback")
            return {
                "success": True,
                "result": {"matched": False},
                "handle": "fallback",
            }

        except StepExecutionError:
            raise
        except Exception as e:
            logger.error(f"Switch step failed: {e}", exc_info=True)
            raise StepExecutionError(f"Switch step failed: {str(e)}")


class FilterStepHandler(BaseStepHandler):
    """
    Continues only when its condition holds.

    Unlike a branch, a filter has a single output: if the condition fails the
    path simply stops, which the scheduler treats as a skip.
    """

    async def execute(
        self,
        step: Dict[str, Any],
        context: WorkflowContext,
    ) -> Dict[str, Any]:
        try:
            config = step.get("config", {})
            passed = ConditionStepHandler(db=self.db)._evaluate_structured(
                config, context
            )

            logger.info(f"Filter {'passed' if passed else 'blocked'} the path")

            return {
                "success": True,
                "result": {"passed": passed},
                "passed": passed,
            }

        except Exception as e:
            logger.error(f"Filter step failed: {e}", exc_info=True)
            raise StepExecutionError(f"Filter step failed: {str(e)}")


class MergeStepHandler(BaseStepHandler):
    """
    Join point for parallel branches.

    Scheduling does the real work — the executor decides when a merge is
    runnable based on its ``merge_mode`` setting. This handler just records
    which upstream branches actually arrived.
    """

    async def execute(
        self,
        step: Dict[str, Any],
        context: WorkflowContext,
    ) -> Dict[str, Any]:
        arrived = step.get("_arrived_from") or []

        return {
            "success": True,
            "result": {"arrived_from": arrived, "count": len(arrived)},
        }


class CalculateStepHandler(BaseStepHandler):
    """
    Arithmetic across workflow values, expressed as rows rather than an expression.

    Each row is ``{name, left, operator, right}``. Rows are evaluated in order
    and each result is published immediately, so a later row can build on an
    earlier one (``subtotal`` → ``tax`` → ``total``) without needing three
    separate nodes on the canvas.

    Operands may be literals or ``{{references}}``. A non-numeric operand is a
    hard error naming the offending row: the alternative is a silently missing
    variable that a Speak step later reads to the caller as a blank.
    """

    #: name -> (symbol shown in errors, function)
    OPERATORS = {
        "add": ("+", lambda a, b: a + b),
        "subtract": ("-", lambda a, b: a - b),
        "multiply": ("x", lambda a, b: a * b),
        "divide": ("/", lambda a, b: a / b),
        "modulo": ("%", lambda a, b: a % b),
        # "15 percent_of 200" reads as "15% of 200" — the order a builder user
        # types it after picking the operator from the middle column.
        "percent_of": ("% of", lambda a, b: b * a / 100),
    }

    def _number(self, raw: Any, row_name: str, side: str) -> float:
        """Coerce an operand to a number, or fail with a message a user can act on."""
        if isinstance(raw, bool) or raw is None or (
            isinstance(raw, str) and not raw.strip()
        ):
            raise StepExecutionError(
                f"Calculate: '{row_name}' has no {side} value. "
                f"Check the step that should provide it ran first."
            )
        if isinstance(raw, (int, float, Decimal)):
            return float(raw)
        try:
            return float(str(raw).strip().replace(",", ""))
        except (TypeError, ValueError):
            raise StepExecutionError(
                f"Calculate: '{row_name}' {side} value {raw!r} is not a number."
            )

    async def execute(
        self,
        step: Dict[str, Any],
        context: WorkflowContext,
    ) -> Dict[str, Any]:
        try:
            config = step.get("config", {})
            rows = config.get("calculations") or []

            if not rows:
                raise StepExecutionError("Calculate step has no calculations")

            decimals = config.get("decimals")
            results: Dict[str, Any] = {}

            for index, row in enumerate(rows):
                name = str(row.get("name") or "").strip()
                if not name:
                    raise StepExecutionError(
                        f"Calculate: row {index + 1} needs a name to store its result in"
                    )

                operator = str(row.get("operator") or "add")
                if operator not in self.OPERATORS:
                    raise StepExecutionError(
                        f"Calculate: '{name}' uses unknown operator '{operator}'"
                    )

                symbol, func = self.OPERATORS[operator]
                left = self._number(context.interpolate(row.get("left")), name, "first")
                right = self._number(context.interpolate(row.get("right")), name, "second")

                if operator in ("divide", "modulo") and right == 0:
                    raise StepExecutionError(
                        f"Calculate: '{name}' cannot divide by zero"
                    )

                value = func(left, right)

                if decimals not in (None, ""):
                    value = round(value, int(decimals))

                # Drop the binary-floating-point tail (0.30000000000000004),
                # which a Speak step would otherwise read out digit by digit.
                value = round(value, 10)
                if value == int(value):
                    value = int(value)

                logger.info(f"Calculate: {name} = {left} {symbol} {right} = {value}")

                results[name] = value
                # Publish immediately so the next row can reference this one.
                context.set_variable(name, value)

            return {"success": True, "result": results}

        except StepExecutionError:
            raise
        except Exception as e:
            logger.error(f"Calculate step failed: {e}", exc_info=True)
            raise StepExecutionError(f"Calculate step failed: {str(e)}")


class TransferStepHandler(BaseStepHandler):
    """Handler for transfer steps — hand the call to a human/another number."""

    async def execute(
        self,
        step: Dict[str, Any],
        context: WorkflowContext,
    ) -> Dict[str, Any]:
        try:
            config = step.get("config", {})
            destination = str(context.interpolate(config.get("destination", ""))).strip()

            if not destination:
                raise StepExecutionError("Transfer step needs a destination")

            # Optional hand-off line ("Connecting you now...") before the transfer.
            message = context.interpolate(config.get("message", ""))
            if str(message).strip():
                await context.channel.speak(str(message))

            transfer_type = config.get("transfer_type", "blind")
            await context.channel.transfer(destination, transfer_type=transfer_type)

            # The call has left us — nothing after this can run.
            context.ended = True

            return {
                "success": True,
                "result": {"transferred_to": destination, "transfer_type": transfer_type},
            }

        except StepExecutionError:
            raise
        except Exception as e:
            logger.error(f"Transfer step failed: {e}", exc_info=True)
            raise StepExecutionError(f"Transfer step failed: {str(e)}")


class EndStepHandler(BaseStepHandler):
    """Handler for end steps — say goodbye and hang up."""

    async def execute(
        self,
        step: Dict[str, Any],
        context: WorkflowContext,
    ) -> Dict[str, Any]:
        try:
            config = step.get("config", {})
            farewell = context.interpolate(config.get("farewell", ""))
            farewell = str(farewell).strip() or None

            await context.channel.end(farewell=farewell)
            context.ended = True

            return {"success": True, "result": {"ended": True, "farewell": farewell}}

        except Exception as e:
            logger.error(f"End step failed: {e}", exc_info=True)
            raise StepExecutionError(f"End step failed: {str(e)}")


class ToolStepHandler(BaseStepHandler):
    """Handler for tool steps — run one of the user's configured Tools."""

    async def execute(
        self,
        step: Dict[str, Any],
        context: WorkflowContext,
    ) -> Dict[str, Any]:
        try:
            config = step.get("config", {})
            tool_id = str(config.get("tool_id", "")).strip()

            if not tool_id:
                raise StepExecutionError("Tool step needs a tool_id")
            if self.db is None:
                raise StepExecutionError("Tool step requires a database session")

            # The builder stores parameters as a JSON *string*; API callers may
            # send a real object. Accept both.
            parameters = config.get("parameters", {})
            if isinstance(parameters, str):
                raw = parameters.strip() or "{}"
                try:
                    parameters = json.loads(raw)
                except json.JSONDecodeError as e:
                    raise StepExecutionError(f"Tool parameters is not valid JSON: {e}")
            if not isinstance(parameters, dict):
                raise StepExecutionError("Tool parameters must be a JSON object")

            parameters = context.interpolate(parameters)

            from sqlalchemy import select
            from app.models.tool import Tool

            # Scoped to the running workflow's organization — a tool carries its
            # own URL and authorization headers, so executing another tenant's
            # tool ran their request with their secrets and returned the body.
            if context.organization_id is None:
                raise StepExecutionError(
                    "Tool step cannot resolve a tool without a workspace context"
                )

            result = await self.db.execute(
                select(Tool).where(
                    Tool.id == uuid.UUID(tool_id),
                    Tool.organization_id == context.organization_id,
                )
            )
            tool = result.scalar_one_or_none()
            if not tool:
                # Same message whether it is missing or someone else's, so the
                # error cannot be used to confirm that an id exists.
                raise StepExecutionError(f"Tool {tool_id} not found")

            from app.services.function_executor import get_function_executor

            executor = get_function_executor()
            res = await executor.execute_global_tool(
                tool=tool, parameters=parameters, call_id=None, db=self.db
            )

            if not res.get("success"):
                raise StepExecutionError(
                    f"Tool '{tool.name}' failed: {res.get('error', 'unknown error')}"
                )

            return {"success": True, "result": res.get("result")}

        except StepExecutionError:
            raise
        except ValueError as e:
            raise StepExecutionError(f"Invalid tool_id: {e}")
        except Exception as e:
            logger.error(f"Tool step failed: {e}", exc_info=True)
            raise StepExecutionError(f"Tool step failed: {str(e)}")


class WebhookStepHandler(BaseStepHandler):
    """Handler for webhook steps — call an external HTTP endpoint."""

    async def execute(
        self,
        step: Dict[str, Any],
        context: WorkflowContext,
    ) -> Dict[str, Any]:
        try:
            config = step.get("config", {})
            url = str(context.interpolate(config.get("url", ""))).strip()

            if not url:
                raise StepExecutionError("Webhook step needs a url")
            if not url.startswith(("http://", "https://")):
                raise StepExecutionError(f"Webhook url must be http(s): {url}")

            # The URL is author-supplied and interpolated from run data, so it
            # can name anything this container can route to. The response body
            # is returned in the step result, which made an unrestricted fetch a
            # read primitive against the cloud metadata endpoint and every
            # internal service. Redirects are disabled below for the same reason
            # — a public URL can 302 to a private one after this check.
            from app.core.egress import UnsafeURLError, assert_safe_url

            try:
                assert_safe_url(url)
            except UnsafeURLError as exc:
                raise StepExecutionError(f"Webhook url rejected: {exc}")

            method = str(config.get("method", "POST")).upper()
            # A JSON body keeps its types — that is the whole point, so the
            # receiving API gets 42 and not "42". Headers and query strings are
            # text by definition and are rendered, since aiohttp rejects
            # non-string values there.
            headers = {
                str(k): _as_text(v)
                for k, v in self._as_dict(config.get("headers"), "headers", context).items()
            }
            body = self._as_dict(config.get("body"), "body", context)
            params = {str(k): _as_text(v) for k, v in body.items()} if body else None
            timeout = float(config.get("timeout", 30) or 30)

            import aiohttp

            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=timeout)
            ) as session:
                async with session.request(
                    method,
                    url,
                    headers=headers or None,
                    json=body if method in ("POST", "PUT", "PATCH") and body else None,
                    params=params if method == "GET" else None,
                    # A checked public URL can still redirect to an internal
                    # one, and the redirect target is never validated. Following
                    # redirects would reopen exactly what assert_safe_url closed.
                    allow_redirects=False,
                ) as resp:
                    text = await resp.text()
                    try:
                        payload = json.loads(text) if text else None
                    except json.JSONDecodeError:
                        payload = text

                    if resp.status >= 400:
                        raise StepExecutionError(
                            f"Webhook returned {resp.status}: {str(payload)[:200]}"
                        )

                    return {
                        "success": True,
                        "result": {"status": resp.status, "body": payload},
                    }

        except StepExecutionError:
            raise
        except Exception as e:
            logger.error(f"Webhook step failed: {e}", exc_info=True)
            raise StepExecutionError(f"Webhook step failed: {str(e)}")

    @staticmethod
    def _as_dict(value: Any, field: str, context: WorkflowContext) -> Dict[str, Any]:
        """Coerce a builder JSON-string field into an interpolated dict."""
        if value is None or value == "":
            return {}
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except json.JSONDecodeError as e:
                raise StepExecutionError(f"Webhook {field} is not valid JSON: {e}")
        if not isinstance(value, dict):
            raise StepExecutionError(f"Webhook {field} must be a JSON object")
        return context.interpolate(value)


class AIStepHandler(BaseStepHandler):
    """
    Handler for AI steps — let the LLM produce a contextual line, then say it.

    The builder gives this step a `context` (what the AI should do) and optional
    `constraints`. Captured variables are supplied to the model so it can use
    what the caller already told us.
    """

    async def execute(
        self,
        step: Dict[str, Any],
        context: WorkflowContext,
    ) -> Dict[str, Any]:
        try:
            config = step.get("config", {})
            instruction = str(context.interpolate(config.get("context", ""))).strip()

            if not instruction:
                raise StepExecutionError("AI step needs a 'context' instruction")

            constraints = str(context.interpolate(config.get("constraints", ""))).strip()

            system = (
                "You are a voice assistant on a live phone call. "
                "Reply with one short, natural spoken response — no markdown, no lists."
            )
            if constraints:
                system += f"\nConstraints: {constraints}"

            # Give the model whatever the flow has captured so far.
            known = {
                k: v for k, v in context.variables.items()
                if k not in ("steps", "loop") and not isinstance(v, (dict, list))
            }
            user = instruction
            if known:
                user += f"\n\nKnown information: {json.dumps(known, default=str)}"

            from app.services.voice.llm_service import get_llm_service, ChatMessage

            llm = get_llm_service()
            completion = await llm.chat(
                messages=[
                    ChatMessage(role="system", content=system),
                    ChatMessage(role="user", content=user),
                ],
                model=config.get("model") or "gpt-4o-mini",
                temperature=float(config.get("temperature", 0.7)),
                max_tokens=int(config.get("max_tokens", 150)),
            )

            text = (getattr(completion, "content", None) or "").strip()
            if not text:
                raise StepExecutionError("AI step produced an empty response")

            await context.channel.speak(text)

            # Optionally capture the reply for later steps.
            variable = str(config.get("variable", "")).strip()
            if variable:
                context.set_variable(variable, text)

            return {"success": True, "result": {"response": text}}

        except StepExecutionError:
            raise
        except Exception as e:
            logger.error(f"AI step failed: {e}", exc_info=True)
            raise StepExecutionError(f"AI step failed: {str(e)}")


class StepHandlerFactory:
    """Factory for creating step handlers."""

    @staticmethod
    def get_handler(step_type: str, db=None) -> BaseStepHandler:
        """
        Get handler for step type.

        Args:
            step_type: Step type
            db: Database session

        Returns:
            Step handler instance

        Raises:
            ValueError: If step type is unknown
        """
        handlers = {
            # Data / automation steps
            StepType.ACTION: ActionStepHandler,
            StepType.CONDITION: ConditionStepHandler,
            StepType.SWITCH: SwitchStepHandler,
            StepType.FILTER: FilterStepHandler,
            StepType.MERGE: MergeStepHandler,
            StepType.LOOP: LoopStepHandler,
            StepType.TRANSFORM: TransformStepHandler,
            StepType.CALCULATE: CalculateStepHandler,
            StepType.DELAY: DelayStepHandler,
            StepType.TOOL: ToolStepHandler,
            StepType.WEBHOOK: WebhookStepHandler,
            # Conversation steps (the builder's palette)
            StepType.SPEAK: SpeakStepHandler,
            StepType.ASK: AskStepHandler,
            StepType.TRANSFER: TransferStepHandler,
            StepType.AI: AIStepHandler,
            StepType.END: EndStepHandler,
        }

        handler_class = handlers.get(step_type)

        if not handler_class:
            raise ValueError(
                f"Unknown step type: {step_type}. "
                f"Supported: {', '.join(sorted(h.value for h in handlers))}"
            )

        return handler_class(db=db)
