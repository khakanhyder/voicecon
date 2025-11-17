"""
Workflow Step Handlers.

Handlers for different types of workflow steps.
"""
import logging
import asyncio
import re
from typing import Dict, Any, Optional
from datetime import datetime
from decimal import Decimal

from app.schemas.workflow import StepType

logger = logging.getLogger(__name__)


class StepExecutionError(Exception):
    """Raised when step execution fails."""
    pass


class WorkflowContext:
    """
    Workflow execution context.

    Stores variables and data that can be referenced across steps.
    """

    def __init__(self, trigger_data: Optional[Dict[str, Any]] = None):
        """
        Initialize workflow context.

        Args:
            trigger_data: Initial trigger data
        """
        self.variables = {
            "trigger": trigger_data or {},
            "steps": {},
        }

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
            condition = config.get("condition")

            if not condition:
                raise StepExecutionError("Missing condition in condition config")

            # Interpolate condition
            condition_str = context.interpolate(condition)

            # Evaluate condition safely
            result = self._evaluate_condition(condition_str, context)

            logger.info(f"Condition evaluated to: {result}")

            return {
                "success": True,
                "result": result,
                "next_steps": config.get("on_true" if result else "on_false", []),
            }

        except Exception as e:
            logger.error(f"Condition step failed: {e}", exc_info=True)
            raise StepExecutionError(f"Condition step failed: {str(e)}")

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
            items_ref = config.get("items")

            if not items_ref:
                raise StepExecutionError("Missing items in loop config")

            # Get items from context
            items = context.get_variable(items_ref.strip("{}"))

            if not isinstance(items, list):
                raise StepExecutionError(f"Items must be a list, got {type(items)}")

            max_iterations = config.get("max_iterations", 100)
            if len(items) > max_iterations:
                logger.warning(f"Loop truncated to {max_iterations} iterations")
                items = items[:max_iterations]

            results = []

            for index, item in enumerate(items):
                # Set loop variables
                context.set_variable("loop.item", item)
                context.set_variable("loop.index", index)

                logger.info(f"Loop iteration {index + 1}/{len(items)}")

                # Note: Sub-steps execution would be handled by the main engine
                # This handler just manages the loop state
                results.append(item)

            logger.info(f"Loop completed: {len(results)} iterations")

            return {
                "success": True,
                "result": results,
                "iterations": len(results),
            }

        except Exception as e:
            logger.error(f"Loop step failed: {e}", exc_info=True)
            raise StepExecutionError(f"Loop step failed: {str(e)}")


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
            StepType.ACTION: ActionStepHandler,
            StepType.CONDITION: ConditionStepHandler,
            StepType.LOOP: LoopStepHandler,
            StepType.TRANSFORM: TransformStepHandler,
            StepType.DELAY: DelayStepHandler,
        }

        handler_class = handlers.get(step_type)

        if not handler_class:
            raise ValueError(f"Unknown step type: {step_type}")

        return handler_class(db=db)
