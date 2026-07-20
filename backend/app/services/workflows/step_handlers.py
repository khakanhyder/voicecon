"""
Workflow Step Handlers.

Handlers for different types of workflow steps.
"""
import logging
import asyncio
import json
import re
import uuid
from typing import Dict, Any, Optional
from datetime import datetime
from decimal import Decimal

from app.schemas.workflow import StepType

logger = logging.getLogger(__name__)


class StepExecutionError(Exception):
    """Raised when step execution fails."""
    pass


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
    ):
        """
        Initialize workflow context.

        Args:
            trigger_data: Initial trigger data
            channel: Execution channel for voice steps (speak/ask/transfer/end).
                Defaults to a SimulatedChannel so a flow is always runnable —
                e.g. a "Run" from the dashboard, where there is no live call.
        """
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
        # Support dot notation (e.g., "trigger.call_id")
        keys = key.split(".")
        value = self.variables

        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
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
        Interpolate variables in strings.

        Supports {{variable.path}} syntax.

        Args:
            value: Value to interpolate

        Returns:
            Interpolated value
        """
        if isinstance(value, str):
            # Find all {{variable}} patterns
            pattern = r'\{\{([^}]+)\}\}'
            matches = re.findall(pattern, value)

            if not matches:
                return value

            result = value
            for match in matches:
                var_value = self.get_variable(match.strip())
                if var_value is not None:
                    result = result.replace(f"{{{{{match}}}}}", str(var_value))

            return result

        elif isinstance(value, dict):
            return {k: self.interpolate(v) for k, v in value.items()}

        elif isinstance(value, list):
            return [self.interpolate(item) for item in value]

        else:
            return value


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

            # Get connection and connector
            query = select(IntegrationConnection).where(
                IntegrationConnection.id == connection_id
            )
            result = await self.db.execute(query)
            connection = result.scalar_one_or_none()

            if not connection:
                raise StepExecutionError(f"Connection {connection_id} not found")

            # Get connector
            query = select(IntegrationConnector).where(
                IntegrationConnector.id == connection.connector_id
            )
            result = await self.db.execute(query)
            connector = result.scalar_one_or_none()

            if not connector:
                raise StepExecutionError("Connector not found")

            # Get connector class dynamically
            connector_map = {
                "salesforce": "SalesforceConnector",
                "hubspot": "HubSpotConnector",
                "sendgrid": "SendGridConnector",
                "google-calendar": "GoogleCalendarConnector",
                "slack": "SlackConnector",
                "stripe": "StripeConnector",
                "notion": "NotionConnector",
                "clickup": "ClickUpConnector",
                "trello": "TrelloConnector",
                "whatsapp": "WhatsAppConnector",
                "airtable": "AirtableConnector",
                "gohighlevel": "GoHighLevelConnector",
                "twilio": "TwilioConnector",
                "langfuse": "LangfuseConnector",
                "calendly": "CalendlyConnector",
                "google-sheets": "GoogleSheetsConnector",
                "google-drive": "GoogleDriveConnector",
                "cal-com": "CalComConnector",
                "monday": "MondayConnector",
                "vonage": "VonageConnector",
                "telnyx": "TelnyxConnector",
                "supabase": "SupabaseConnector",
            }

            connector_class_name = connector_map.get(connector.slug)
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
                if not hasattr(connector_instance, action):
                    raise StepExecutionError(f"Action {action} not found on connector")

                action_method = getattr(connector_instance, action)
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
                condition_str = context.interpolate(config["condition"])
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
        condition = condition.strip()

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
                result = mapper.map_fields(source_data, mapping_config, validate=validate)

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
                        source = transform_spec.get("source")
                        if source:
                            value = context.get_variable(source)
                        else:
                            value = transform_spec.get("value")

                        # Apply transformation if specified
                        if "transform" in transform_spec:
                            value = mapper.apply_transformation(value, transform_spec["transform"])

                        # Apply default if value is None
                        if value is None and "default" in transform_spec:
                            value = transform_spec["default"]

                    elif isinstance(transform_spec, str):
                        # Simple string: interpolate it
                        value = context.interpolate(transform_spec)

                    else:
                        # Literal value
                        value = transform_spec

                    results[key] = value

                logger.info(f"Transform completed: {len(results)} variables")

                return {
                    "success": True,
                    "result": results,
                }

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

            result = await self.db.execute(select(Tool).where(Tool.id == uuid.UUID(tool_id)))
            tool = result.scalar_one_or_none()
            if not tool:
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

            method = str(config.get("method", "POST")).upper()
            headers = self._as_dict(config.get("headers"), "headers", context)
            body = self._as_dict(config.get("body"), "body", context)
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
                    params=body if method == "GET" and body else None,
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
            StepType.LOOP: LoopStepHandler,
            StepType.TRANSFORM: TransformStepHandler,
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
