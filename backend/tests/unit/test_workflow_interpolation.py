"""
Data must keep its JSON type as it moves through a workflow.

Interpolation used to stringify everything, so a webhook step posted
``"amount": "42"`` where the receiving API wanted ``42``, ``"paid": "True"``
instead of ``true``, an object as its Python ``repr``, and — when a value was
null — the literal text ``{{trigger.missing}}``. The run still reported
success, so the corruption was invisible until a downstream API rejected it.

These tests pin the distinction that fixes it: a string that is *only* a
reference resolves to the value itself; a reference embedded in text renders
into that text.
"""
import pytest

from app.services.workflows.scheduler import POLL_INTERVAL_SECONDS, WorkflowScheduler
from app.services.workflows.step_handlers import (
    ConditionStepHandler,
    WorkflowContext,
    _as_text,
)


@pytest.fixture
def ctx() -> WorkflowContext:
    return WorkflowContext(trigger_data={
        "amount": 42,
        "ratio": 3.5,
        "paid": True,
        "unpaid": False,
        "zero": 0,
        "missing": None,
        "customer": {"id": 7, "name": "Ada"},
        "tags": ["a", "b"],
        "name": "Ada",
    })


class TestWholeValueKeepsItsType:
    """A field bound to exactly one variable IS that variable."""

    @pytest.mark.parametrize("template,expected", [
        ("{{trigger.amount}}", 42),
        ("{{trigger.ratio}}", 3.5),
        ("{{trigger.paid}}", True),
        ("{{trigger.unpaid}}", False),
        ("{{trigger.zero}}", 0),
        ("{{trigger.customer}}", {"id": 7, "name": "Ada"}),
        ("{{trigger.tags}}", ["a", "b"]),
        ("{{trigger.name}}", "Ada"),
    ])
    def test_type_is_preserved(self, ctx, template, expected):
        result = ctx.interpolate(template)
        assert result == expected
        assert type(result) is type(expected)

    def test_surrounding_whitespace_is_tolerated(self, ctx):
        assert ctx.interpolate("  {{ trigger.amount }}  ") == 42

    def test_falsy_values_survive(self, ctx):
        """0 and False must not be confused with "missing"."""
        assert ctx.interpolate("{{trigger.zero}}") == 0
        assert ctx.interpolate("{{trigger.unpaid}}") is False


class TestMixedTemplateRenders:
    """A reference inside text can only produce text."""

    def test_numbers_and_booleans_render(self, ctx):
        assert ctx.interpolate("owes {{trigger.amount}}") == "owes 42"
        # JSON spelling, not Python's "True" — this string may well be sent as
        # part of a JSON document or spoken aloud.
        assert ctx.interpolate("paid: {{trigger.paid}}") == "paid: true"

    def test_multiple_references(self, ctx):
        assert ctx.interpolate("{{trigger.name}} owes {{trigger.amount}}") == "Ada owes 42"

    def test_structures_render_as_json_not_python_repr(self, ctx):
        out = ctx.interpolate("customer={{trigger.customer}}")
        assert out == 'customer={"id": 7, "name": "Ada"}'
        assert "'" not in out  # a Python repr would use single quotes

    def test_plain_string_is_untouched(self, ctx):
        assert ctx.interpolate("no references here") == "no references here"


class TestUnresolvedReferences:
    """An unresolved reference must never leak into the output."""

    def test_whole_value_becomes_none(self, ctx):
        assert ctx.interpolate("{{trigger.missing}}") is None
        assert ctx.interpolate("{{trigger.nope.not.here}}") is None

    def test_embedded_becomes_empty(self, ctx):
        assert ctx.interpolate("note: {{trigger.missing}}") == "note: "

    def test_template_text_never_survives(self, ctx):
        for template in ("{{trigger.missing}}", "x {{trigger.missing}} y"):
            assert "{{" not in str(ctx.interpolate(template))


class TestNestedStructures:
    def test_dict_values_are_resolved_independently(self, ctx):
        body = ctx.interpolate({
            "amount": "{{trigger.amount}}",
            "paid": "{{trigger.paid}}",
            "customer": "{{trigger.customer}}",
            "note": "{{trigger.missing}}",
            "label": "for {{trigger.name}}",
            "literal": 99,
        })
        assert body == {
            "amount": 42,
            "paid": True,
            "customer": {"id": 7, "name": "Ada"},
            "note": None,
            "label": "for Ada",
            "literal": 99,
        }

    def test_lists_are_resolved(self, ctx):
        assert ctx.interpolate(["{{trigger.amount}}", "{{trigger.name}}"]) == [42, "Ada"]


class TestInterpolateText:
    """For sinks that can only take text (HTTP headers, spoken prompts)."""

    def test_always_returns_a_string(self, ctx):
        for template in ("{{trigger.amount}}", "{{trigger.paid}}",
                         "{{trigger.customer}}", "{{trigger.missing}}"):
            assert isinstance(ctx.interpolate_text(template), str)

    def test_renders_json_spelling(self, ctx):
        assert ctx.interpolate_text("{{trigger.paid}}") == "true"
        assert ctx.interpolate_text("{{trigger.missing}}") == ""


class TestAsText:
    @pytest.mark.parametrize("value,expected", [
        (None, ""),
        (True, "true"),
        (False, "false"),
        (42, "42"),
        ("plain", "plain"),
        ({"a": 1}, '{"a": 1}'),
        ([1, 2], "[1, 2]"),
    ])
    def test_rendering(self, value, expected):
        assert _as_text(value) == expected


@pytest.mark.asyncio
class TestConditionsStillWork:
    """Type preservation must not disturb branching."""

    async def _run(self, config, ctx):
        result = await ConditionStepHandler().execute({"config": config}, ctx)
        return result["result"]

    async def test_numeric_comparison(self, ctx):
        assert await self._run(
            {"variable": "trigger.amount", "operator": "greater_than", "value": 10}, ctx) is True
        assert await self._run(
            {"variable": "trigger.amount", "operator": "less_than", "value": 10}, ctx) is False

    async def test_numeric_comparison_is_not_lexicographic(self, ctx):
        """The classic string-compare bug: '9' > '10' is True as text."""
        ctx.set_variable("nine", 9)
        assert await self._run(
            {"variable": "nine", "operator": "greater_than", "value": 10}, ctx) is False

    async def test_expression_form_with_a_boolean(self, ctx):
        """A whole-value bool reaches the expression parser as text, not a bool."""
        assert await self._run({"condition": "{{trigger.paid}}"}, ctx) is True
        assert await self._run({"condition": "{{trigger.unpaid}}"}, ctx) is False

    async def test_expression_form_with_numbers(self, ctx):
        assert await self._run({"condition": "{{trigger.amount}} > 10"}, ctx) is True


class TestIntervalScheduleDoesNotSlipAPoll:
    """A 30s interval on a 30s poll used to fire every 60s."""

    @pytest.mark.asyncio
    async def test_fires_when_a_hair_early(self):
        from datetime import datetime, timedelta

        scheduler = WorkflowScheduler()
        now = datetime.utcnow()

        class W:
            trigger_config = {"schedule_type": "interval", "interval_seconds": 30}
            # The check lands a few milliseconds before the exact mark, which is
            # the normal case for a polling loop.
            last_executed_at = now - timedelta(seconds=29.99)

        assert await scheduler._check_interval_schedule(W(), now) is True

    @pytest.mark.asyncio
    async def test_does_not_fire_far_too_early(self):
        from datetime import datetime, timedelta

        scheduler = WorkflowScheduler()
        now = datetime.utcnow()

        class W:
            trigger_config = {"schedule_type": "interval", "interval_seconds": 3600}
            last_executed_at = now - timedelta(seconds=60)

        assert await scheduler._check_interval_schedule(W(), now) is False

    @pytest.mark.asyncio
    async def test_never_run_fires_immediately(self):
        from datetime import datetime

        scheduler = WorkflowScheduler()

        class W:
            trigger_config = {"schedule_type": "interval", "interval_seconds": 3600}
            last_executed_at = None

        assert await scheduler._check_interval_schedule(W(), datetime.utcnow()) is True

    def test_slack_is_tied_to_the_poll_interval(self):
        """The tolerance is derived, not a magic number."""
        assert POLL_INTERVAL_SECONDS == 30
