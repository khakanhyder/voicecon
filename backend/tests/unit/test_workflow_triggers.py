"""
Tests for workflow trigger configuration and schedule evaluation.

These cover the trigger half of the workflow feature, which the builder now
configures directly:

* Cron schedules are evaluated in the workflow's own timezone. Before that,
  "every day at 09:00" meant 09:00 UTC wherever the user was, so the run landed
  at the wrong hour for everyone outside UTC.
* The call-event agent filter is read from ``filters``. The builder used to
  write ``agent_id`` at the top level, where nothing read it, so the workflow
  fired for *every* agent's calls regardless of the one selected.
"""
from datetime import datetime, timedelta

import pytest

from app.schemas.workflow import TriggerType
from app.services.workflows.scheduler import WorkflowScheduler, _resolve_timezone
from app.services.workflows.trigger_handlers import (
    TriggerError,
    TriggerValidator,
    VoiceEventTriggerHandler,
)


def workflow(config: dict, last_executed_at=None):
    """Minimal stand-in for the Workflow row the scheduler reads."""

    class W:
        trigger_config = config

    W.last_executed_at = last_executed_at
    return W()


# ---------------------------------------------------------------------------
# Timezone resolution
# ---------------------------------------------------------------------------


class TestTimezoneResolution:
    def test_resolves_a_real_zone(self):
        assert str(_resolve_timezone("Asia/Karachi")) == "Asia/Karachi"

    def test_falls_back_to_utc_when_absent(self):
        assert str(_resolve_timezone(None)) == "UTC"
        assert str(_resolve_timezone("")) == "UTC"

    def test_falls_back_to_utc_rather_than_raising(self):
        """
        The zone is free text in a JSON column. A typo must not stop the
        scheduler loop — every other workflow in the poll would stop too.
        """
        assert str(_resolve_timezone("Not/AZone")) == "UTC"


# ---------------------------------------------------------------------------
# Cron schedules
# ---------------------------------------------------------------------------


class TestCronRespectsTimezone:
    """A daily cron fires on the user's wall clock, not on UTC's."""

    @pytest.mark.asyncio
    async def test_fires_at_the_local_hour_not_the_utc_hour(self):
        scheduler = WorkflowScheduler()
        config = {
            "schedule_type": "cron",
            "cron_expression": "0 9 * * *",  # 09:00 in Karachi
            "timezone": "Asia/Karachi",
        }

        # Karachi is UTC+5, so 09:00 local is 04:00 UTC.
        due = datetime(2026, 6, 1, 4, 0)
        assert (
            await scheduler._check_cron_schedule(
                workflow(config, last_executed_at=due - timedelta(hours=24)), due
            )
            is True
        )

    @pytest.mark.asyncio
    async def test_does_not_fire_at_the_utc_hour(self):
        scheduler = WorkflowScheduler()
        config = {
            "schedule_type": "cron",
            "cron_expression": "0 9 * * *",
            "timezone": "Asia/Karachi",
        }

        # 09:00 UTC is 14:00 in Karachi — five hours after the last run, and
        # nowhere near the next 09:00 local occurrence.
        not_due = datetime(2026, 6, 1, 9, 0)
        assert (
            await scheduler._check_cron_schedule(
                workflow(config, last_executed_at=datetime(2026, 6, 1, 4, 0)),
                not_due,
            )
            is False
        )

    @pytest.mark.asyncio
    async def test_utc_remains_the_default(self):
        """Configs saved before timezones existed keep their old behaviour."""
        scheduler = WorkflowScheduler()
        config = {"schedule_type": "cron", "cron_expression": "0 9 * * *"}

        due = datetime(2026, 6, 1, 9, 0)
        assert (
            await scheduler._check_cron_schedule(
                workflow(config, last_executed_at=due - timedelta(hours=24)), due
            )
            is True
        )

    @pytest.mark.asyncio
    async def test_never_run_fires_on_a_recent_occurrence(self):
        scheduler = WorkflowScheduler()
        config = {
            "schedule_type": "cron",
            "cron_expression": "0 9 * * *",
            "timezone": "Asia/Karachi",
        }

        # Ten seconds past the local 09:00, and never executed.
        assert (
            await scheduler._check_cron_schedule(
                workflow(config, last_executed_at=None), datetime(2026, 6, 1, 4, 0, 10)
            )
            is True
        )

    @pytest.mark.asyncio
    async def test_never_run_does_not_fire_mid_cycle(self):
        scheduler = WorkflowScheduler()
        config = {
            "schedule_type": "cron",
            "cron_expression": "0 9 * * *",
            "timezone": "Asia/Karachi",
        }

        # Hours past the occurrence: activating a workflow at noon must not
        # immediately fire this morning's run.
        assert (
            await scheduler._check_cron_schedule(
                workflow(config, last_executed_at=None), datetime(2026, 6, 1, 7, 0)
            )
            is False
        )

    @pytest.mark.asyncio
    async def test_a_broken_expression_does_not_raise(self):
        """One bad workflow must not take the scheduler loop down."""
        scheduler = WorkflowScheduler()
        config = {"schedule_type": "cron", "cron_expression": "not a cron"}

        assert (
            await scheduler._check_cron_schedule(workflow(config), datetime.utcnow())
            is False
        )

    @pytest.mark.asyncio
    async def test_an_unknown_zone_falls_back_rather_than_never_firing(self):
        scheduler = WorkflowScheduler()
        config = {
            "schedule_type": "cron",
            "cron_expression": "0 9 * * *",
            "timezone": "Mars/Olympus",
        }

        due = datetime(2026, 6, 1, 9, 0)
        assert (
            await scheduler._check_cron_schedule(
                workflow(config, last_executed_at=due - timedelta(hours=24)), due
            )
            is True
        )


# ---------------------------------------------------------------------------
# Trigger validation
# ---------------------------------------------------------------------------


class TestScheduleValidation:
    """The builder mirrors these rules client-side; they must agree."""

    def test_accepts_the_shapes_the_builder_produces(self):
        for config in (
            {"schedule_type": "interval", "interval_seconds": 900},
            {"schedule_type": "cron", "cron_expression": "0 9 * * *", "timezone": "UTC"},
            {
                "schedule_type": "cron",
                "cron_expression": "30 17 * * 5",
                "timezone": "Asia/Karachi",
            },
            {"schedule_type": "one_time", "scheduled_at": "2026-09-01T14:30"},
        ):
            TriggerValidator.validate_trigger_config(TriggerType.SCHEDULE, config)

    def test_rejects_an_empty_config(self):
        """The create form used to send `{}` here, which 400'd every time."""
        with pytest.raises(TriggerError, match="schedule_type"):
            TriggerValidator.validate_trigger_config(TriggerType.SCHEDULE, {})

    def test_rejects_an_unknown_timezone(self):
        with pytest.raises(TriggerError, match="[Uu]nknown timezone"):
            TriggerValidator.validate_trigger_config(
                TriggerType.SCHEDULE,
                {
                    "schedule_type": "cron",
                    "cron_expression": "0 9 * * *",
                    "timezone": "Mars/Olympus",
                },
            )

    def test_allows_a_cron_config_with_no_timezone(self):
        TriggerValidator.validate_trigger_config(
            TriggerType.SCHEDULE,
            {"schedule_type": "cron", "cron_expression": "0 9 * * *"},
        )


class TestIntegrationEventValidation:
    def test_accepts_a_configured_event(self):
        TriggerValidator.validate_trigger_config(
            TriggerType.INTEGRATION_EVENT,
            {"integration_type": "hubspot", "event_type": "contact.creation"},
        )

    def test_rejects_an_empty_config(self):
        with pytest.raises(TriggerError, match="integration_type"):
            TriggerValidator.validate_trigger_config(
                TriggerType.INTEGRATION_EVENT, {}
            )

    def test_rejects_an_app_it_cannot_route(self):
        with pytest.raises(TriggerError, match="Invalid integration_type"):
            TriggerValidator.validate_trigger_config(
                TriggerType.INTEGRATION_EVENT,
                {"integration_type": "notion", "event_type": "page.created"},
            )


# ---------------------------------------------------------------------------
# Call-event filters
# ---------------------------------------------------------------------------


class TestCallEventAgentFilter:
    """
    The agent filter has to actually filter.

    The builder wrote `agent_id` at the top level of trigger_config, but the
    handler only ever read `filters`, so choosing an agent narrowed nothing.
    """

    @pytest.mark.asyncio
    async def test_matches_the_chosen_agent(self):
        handler = VoiceEventTriggerHandler(db=None)
        config = {"filters": {"agent_id": "agent-1"}}

        assert await handler.should_trigger(config, {"agent_id": "agent-1"}) is True

    @pytest.mark.asyncio
    async def test_excludes_other_agents(self):
        handler = VoiceEventTriggerHandler(db=None)
        config = {"filters": {"agent_id": "agent-1"}}

        assert await handler.should_trigger(config, {"agent_id": "agent-2"}) is False

    @pytest.mark.asyncio
    async def test_honours_the_legacy_top_level_shape(self):
        """Workflows saved before the fix must start filtering, not stay broken."""
        handler = VoiceEventTriggerHandler(db=None)
        config = {"agent_id": "agent-1"}

        assert await handler.should_trigger(config, {"agent_id": "agent-1"}) is True
        assert await handler.should_trigger(config, {"agent_id": "agent-2"}) is False

    @pytest.mark.asyncio
    async def test_filters_take_precedence_over_the_legacy_key(self):
        handler = VoiceEventTriggerHandler(db=None)
        config = {"agent_id": "stale", "filters": {"agent_id": "agent-1"}}

        assert await handler.should_trigger(config, {"agent_id": "agent-1"}) is True

    @pytest.mark.asyncio
    async def test_no_filters_still_matches_everything(self):
        handler = VoiceEventTriggerHandler(db=None)

        assert await handler.should_trigger({}, {"agent_id": "anyone"}) is True
        assert await handler.should_trigger({"filters": {}}, {"agent_id": "x"}) is True

    @pytest.mark.asyncio
    async def test_combines_with_other_filters(self):
        handler = VoiceEventTriggerHandler(db=None)
        config = {"filters": {"agent_id": "agent-1", "duration_min": 60}}

        assert (
            await handler.should_trigger(
                config, {"agent_id": "agent-1", "duration": 120}
            )
            is True
        )
        assert (
            await handler.should_trigger(
                config, {"agent_id": "agent-1", "duration": 30}
            )
            is False
        )
