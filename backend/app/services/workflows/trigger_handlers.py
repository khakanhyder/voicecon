"""
Workflow Trigger Handlers.

Handlers for different types of workflow triggers.
"""
import logging
import asyncio
import re
from typing import Dict, Any, Optional, List
from datetime import datetime
from croniter import croniter
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.workflow import TriggerType

logger = logging.getLogger(__name__)


class TriggerError(Exception):
    """Raised when trigger handling fails."""
    pass


class TriggerValidator:
    """Validates trigger configurations."""

    @staticmethod
    def validate_trigger_config(trigger_type: TriggerType, config: Dict[str, Any]) -> None:
        """
        Validate trigger configuration.

        Args:
            trigger_type: Type of trigger
            config: Trigger configuration

        Raises:
            TriggerError: If configuration is invalid
        """
        validators = {
            TriggerType.MANUAL: TriggerValidator._validate_manual,
            TriggerType.SCHEDULE: TriggerValidator._validate_schedule,
            TriggerType.WEBHOOK: TriggerValidator._validate_webhook,
            TriggerType.CALL_COMPLETED: TriggerValidator._validate_call_event,
            TriggerType.CALL_STARTED: TriggerValidator._validate_call_event,
            TriggerType.INTEGRATION_EVENT: TriggerValidator._validate_integration_event,
        }

        validator = validators.get(trigger_type)
        if not validator:
            raise TriggerError(f"Unknown trigger type: {trigger_type}")

        validator(config)

    @staticmethod
    def _validate_manual(config: Dict[str, Any]) -> None:
        """Validate manual trigger config."""
        # Manual triggers don't require special validation
        pass

    @staticmethod
    def _validate_schedule(config: Dict[str, Any]) -> None:
        """Validate schedule trigger config."""
        if "schedule_type" not in config:
            raise TriggerError("schedule_type is required for schedule triggers")

        schedule_type = config["schedule_type"]

        if schedule_type == "cron":
            if "cron_expression" not in config:
                raise TriggerError("cron_expression is required for cron schedule")

            # Validate cron expression
            try:
                croniter(config["cron_expression"])
            except Exception as e:
                raise TriggerError(f"Invalid cron expression: {str(e)}")

        elif schedule_type == "interval":
            if "interval_seconds" not in config:
                raise TriggerError("interval_seconds is required for interval schedule")

            interval = config["interval_seconds"]
            if not isinstance(interval, int) or interval <= 0:
                raise TriggerError("interval_seconds must be a positive integer")

        elif schedule_type == "one_time":
            if "scheduled_at" not in config:
                raise TriggerError("scheduled_at is required for one-time schedule")

            # Validate datetime format
            try:
                if isinstance(config["scheduled_at"], str):
                    datetime.fromisoformat(config["scheduled_at"].replace('Z', '+00:00'))
            except Exception as e:
                raise TriggerError(f"Invalid scheduled_at datetime: {str(e)}")

        else:
            raise TriggerError(f"Invalid schedule_type: {schedule_type}")

    @staticmethod
    def _validate_webhook(config: Dict[str, Any]) -> None:
        """Validate webhook trigger config."""
        # Webhook key is optional, will be auto-generated if not provided
        if "webhook_key" in config:
            key = config["webhook_key"]
            if not isinstance(key, str) or len(key) < 16:
                raise TriggerError("webhook_key must be at least 16 characters")

    @staticmethod
    def _validate_call_event(config: Dict[str, Any]) -> None:
        """Validate call event trigger config."""
        # Optional filters
        if "filters" in config:
            filters = config["filters"]
            if not isinstance(filters, dict):
                raise TriggerError("filters must be a dictionary")

            # Validate filter fields
            valid_filters = [
                "status",
                "duration_min",
                "duration_max",
                "agent_id",
                "phone_number",
                "sentiment",
                "intent",
                "keywords",
            ]

            for key in filters.keys():
                if key not in valid_filters:
                    logger.warning(f"Unknown filter field: {key}")

    @staticmethod
    def _validate_integration_event(config: Dict[str, Any]) -> None:
        """Validate integration event trigger config."""
        if "integration_type" not in config:
            raise TriggerError("integration_type is required for integration events")

        if "event_type" not in config:
            raise TriggerError("event_type is required for integration events")

        valid_integrations = ["salesforce", "hubspot", "stripe", "slack", "sendgrid", "google-calendar"]
        if config["integration_type"] not in valid_integrations:
            raise TriggerError(f"Invalid integration_type: {config['integration_type']}")


class BaseTriggerHandler:
    """Base class for trigger handlers."""

    def __init__(self, db: AsyncSession):
        """
        Initialize trigger handler.

        Args:
            db: Database session
        """
        self.db = db

    async def should_trigger(
        self,
        config: Dict[str, Any],
        event_data: Dict[str, Any],
    ) -> bool:
        """
        Check if workflow should be triggered.

        Args:
            config: Trigger configuration
            event_data: Event data

        Returns:
            True if workflow should be triggered
        """
        raise NotImplementedError("Subclasses must implement should_trigger()")

    async def prepare_trigger_data(
        self,
        config: Dict[str, Any],
        event_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Prepare trigger data for workflow execution.

        Args:
            config: Trigger configuration
            event_data: Raw event data

        Returns:
            Prepared trigger data
        """
        return event_data


class ManualTriggerHandler(BaseTriggerHandler):
    """Handler for manual triggers."""

    async def should_trigger(
        self,
        config: Dict[str, Any],
        event_data: Dict[str, Any],
    ) -> bool:
        """Manual triggers always fire when invoked."""
        return True


class VoiceEventTriggerHandler(BaseTriggerHandler):
    """Handler for voice event triggers (call_started, call_completed, etc.)."""

    async def should_trigger(
        self,
        config: Dict[str, Any],
        event_data: Dict[str, Any],
    ) -> bool:
        """
        Check if voice event matches trigger filters.

        Args:
            config: Trigger configuration with optional filters
            event_data: Call event data

        Returns:
            True if event matches all filters
        """
        filters = config.get("filters", {})

        # No filters means trigger on all events
        if not filters:
            return True

        # Check status filter
        if "status" in filters:
            if event_data.get("status") != filters["status"]:
                return False

        # Check duration filters
        if "duration_min" in filters:
            duration = event_data.get("duration", 0)
            if duration < filters["duration_min"]:
                return False

        if "duration_max" in filters:
            duration = event_data.get("duration", 0)
            if duration > filters["duration_max"]:
                return False

        # Check agent filter
        if "agent_id" in filters:
            if event_data.get("agent_id") != filters["agent_id"]:
                return False

        # Check phone number filter
        if "phone_number" in filters:
            phone_pattern = filters["phone_number"]
            phone = event_data.get("phone_number", "")
            if not re.search(phone_pattern, phone):
                return False

        # Check sentiment filter
        if "sentiment" in filters:
            sentiment = event_data.get("sentiment", {}).get("label")
            if sentiment != filters["sentiment"]:
                return False

        # Check intent filter
        if "intent" in filters:
            intent = event_data.get("intent")
            if intent != filters["intent"]:
                return False

        # Check keywords
        if "keywords" in filters:
            transcript = event_data.get("transcript", "").lower()
            keywords = filters["keywords"]
            if isinstance(keywords, list):
                # All keywords must be present
                if not all(kw.lower() in transcript for kw in keywords):
                    return False
            else:
                # Single keyword
                if keywords.lower() not in transcript:
                    return False

        return True

    async def prepare_trigger_data(
        self,
        config: Dict[str, Any],
        event_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Prepare call event data for workflow.

        Args:
            config: Trigger configuration
            event_data: Call event data

        Returns:
            Enriched trigger data
        """
        # Enrich with additional context if needed
        trigger_data = {
            "event_type": "voice_event",
            "call_id": event_data.get("call_id"),
            "call_sid": event_data.get("call_sid"),
            "status": event_data.get("status"),
            "duration": event_data.get("duration"),
            "agent_id": event_data.get("agent_id"),
            "phone_number": event_data.get("phone_number"),
            "transcript": event_data.get("transcript"),
            "intent": event_data.get("intent"),
            "sentiment": event_data.get("sentiment"),
            "metadata": event_data.get("metadata", {}),
            "triggered_at": datetime.utcnow().isoformat(),
        }

        return trigger_data


class WebhookTriggerHandler(BaseTriggerHandler):
    """Handler for webhook triggers."""

    async def should_trigger(
        self,
        config: Dict[str, Any],
        event_data: Dict[str, Any],
    ) -> bool:
        """
        Validate webhook request.

        Args:
            config: Trigger configuration
            event_data: Webhook payload

        Returns:
            True if webhook is valid
        """
        # Check webhook key if configured
        if "webhook_key" in config:
            provided_key = event_data.get("webhook_key")
            if provided_key != config["webhook_key"]:
                logger.warning("Invalid webhook key provided")
                return False

        # Check IP whitelist if configured
        if "allowed_ips" in config:
            source_ip = event_data.get("source_ip")
            if source_ip not in config["allowed_ips"]:
                logger.warning(f"Webhook from unauthorized IP: {source_ip}")
                return False

        return True

    async def prepare_trigger_data(
        self,
        config: Dict[str, Any],
        event_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Prepare webhook data for workflow.

        Args:
            config: Trigger configuration
            event_data: Webhook payload

        Returns:
            Prepared trigger data
        """
        return {
            "event_type": "webhook",
            "payload": event_data.get("payload", {}),
            "headers": event_data.get("headers", {}),
            "source_ip": event_data.get("source_ip"),
            "triggered_at": datetime.utcnow().isoformat(),
        }


class IntegrationEventTriggerHandler(BaseTriggerHandler):
    """Handler for integration event triggers."""

    async def should_trigger(
        self,
        config: Dict[str, Any],
        event_data: Dict[str, Any],
    ) -> bool:
        """
        Check if integration event matches trigger config.

        Args:
            config: Trigger configuration
            event_data: Integration event data

        Returns:
            True if event matches configuration
        """
        # Check integration type
        if event_data.get("integration_type") != config.get("integration_type"):
            return False

        # Check event type
        if event_data.get("event_type") != config.get("event_type"):
            return False

        # Check optional filters
        if "filters" in config:
            filters = config["filters"]
            event_payload = event_data.get("payload", {})

            for key, value in filters.items():
                if event_payload.get(key) != value:
                    return False

        return True

    async def prepare_trigger_data(
        self,
        config: Dict[str, Any],
        event_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Prepare integration event data for workflow.

        Args:
            config: Trigger configuration
            event_data: Integration event data

        Returns:
            Prepared trigger data
        """
        return {
            "event_type": "integration_event",
            "integration_type": event_data.get("integration_type"),
            "integration_event_type": event_data.get("event_type"),
            "payload": event_data.get("payload", {}),
            "metadata": event_data.get("metadata", {}),
            "triggered_at": datetime.utcnow().isoformat(),
        }


class TriggerHandlerFactory:
    """Factory for creating trigger handlers."""

    @staticmethod
    def get_handler(trigger_type: TriggerType, db: AsyncSession) -> BaseTriggerHandler:
        """
        Get handler for trigger type.

        Args:
            trigger_type: Trigger type
            db: Database session

        Returns:
            Trigger handler instance

        Raises:
            ValueError: If trigger type is unknown
        """
        handlers = {
            TriggerType.MANUAL: ManualTriggerHandler,
            TriggerType.CALL_STARTED: VoiceEventTriggerHandler,
            TriggerType.CALL_COMPLETED: VoiceEventTriggerHandler,
            TriggerType.WEBHOOK: WebhookTriggerHandler,
            TriggerType.INTEGRATION_EVENT: IntegrationEventTriggerHandler,
        }

        handler_class = handlers.get(trigger_type)

        if not handler_class:
            raise ValueError(f"Unknown trigger type: {trigger_type}")

        return handler_class(db=db)


class TriggerManager:
    """Manages workflow trigger execution."""

    def __init__(self, db: AsyncSession):
        """
        Initialize trigger manager.

        Args:
            db: Database session
        """
        self.db = db

    async def process_event(
        self,
        event_type: TriggerType,
        event_data: Dict[str, Any],
    ) -> List[str]:
        """
        Process an event and trigger matching workflows.

        Args:
            event_type: Type of event
            event_data: Event data

        Returns:
            List of triggered workflow execution IDs
        """
        from app.models.integration import Workflow
        from app.services.workflows.workflow_engine import get_workflow_engine

        # Find workflows with matching trigger type
        query = select(Workflow).where(
            Workflow.trigger_type == event_type,
            Workflow.is_active == True,
        )
        result = await self.db.execute(query)
        workflows = result.scalars().all()

        logger.info(f"Found {len(workflows)} workflows for {event_type}")

        # Get trigger handler
        handler = TriggerHandlerFactory.get_handler(event_type, self.db)

        executions = []

        for workflow in workflows:
            try:
                # Check if workflow should be triggered
                should_trigger = await handler.should_trigger(
                    workflow.trigger_config,
                    event_data,
                )

                if not should_trigger:
                    logger.debug(f"Workflow {workflow.id} filters did not match")
                    continue

                # Prepare trigger data
                trigger_data = await handler.prepare_trigger_data(
                    workflow.trigger_config,
                    event_data,
                )

                # Execute workflow
                engine = get_workflow_engine(self.db)
                execution = await engine.execute_workflow(
                    workflow_id=str(workflow.id),
                    trigger_data=trigger_data,
                    wait_for_completion=False,  # Run async
                )

                executions.append(str(execution.id))
                logger.info(f"Triggered workflow {workflow.id}, execution {execution.id}")

            except Exception as e:
                logger.error(f"Failed to trigger workflow {workflow.id}: {e}", exc_info=True)
                # Continue with other workflows
                continue

        return executions

    async def test_trigger(
        self,
        workflow_id: str,
        test_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Test a workflow trigger with sample data.

        Args:
            workflow_id: Workflow ID
            test_data: Test event data

        Returns:
            Test results

        Raises:
            TriggerError: If test fails
        """
        from app.models.integration import Workflow

        # Get workflow
        query = select(Workflow).where(Workflow.id == workflow_id)
        result = await self.db.execute(query)
        workflow = result.scalar_one_or_none()

        if not workflow:
            raise TriggerError(f"Workflow {workflow_id} not found")

        # Get trigger handler
        handler = TriggerHandlerFactory.get_handler(workflow.trigger_type, self.db)

        # Check if would trigger
        would_trigger = await handler.should_trigger(
            workflow.trigger_config,
            test_data,
        )

        # Prepare data
        prepared_data = await handler.prepare_trigger_data(
            workflow.trigger_config,
            test_data,
        )

        return {
            "workflow_id": workflow_id,
            "trigger_type": workflow.trigger_type,
            "would_trigger": would_trigger,
            "prepared_data": prepared_data,
            "test_data": test_data,
        }


# Singleton instance
_trigger_manager: Optional[TriggerManager] = None


def get_trigger_manager(db: AsyncSession) -> TriggerManager:
    """
    Get trigger manager instance.

    Args:
        db: Database session

    Returns:
        TriggerManager instance
    """
    return TriggerManager(db)
