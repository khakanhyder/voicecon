"""
Tests that every shipped workflow template is actually installable and runnable.

This file exists because the previous templates were not. They were written in
an invented schema — ``{trigger, conditions, actions}`` with step types like
``extract_data`` and ``salesforce_create_lead`` — that no handler implemented,
declared triggers (``intent.detected``) that are not trigger types, and named
integrations the platform has no connector for. They listed cleanly in the
marketplace and could not have produced a working workflow.

Nothing caught it because nothing checked templates against the code that runs
them. These tests are that check: every node type must have a handler, every
edge must land on a real node, and every trigger must satisfy the same
validator a hand-built workflow does.
"""
import pytest

from app.schemas.workflow import StepType, TriggerType
from app.services.templates import WORKFLOW_TEMPLATES
from app.services.workflows.graph import normalize_graph
from app.services.workflows.step_handlers import StepHandlerFactory
from app.services.workflows.trigger_handlers import TriggerValidator

#: Apps the backend can actually route an integration event for.
SUPPORTED_INTEGRATIONS = {
    "salesforce",
    "hubspot",
    "stripe",
    "slack",
    "sendgrid",
    "google-calendar",
}

#: Every template, as (slug, template) so failures name the offender.
CASES = [(t["slug"], t) for t in WORKFLOW_TEMPLATES]


def graph_of(template):
    return normalize_graph(template["workflow_definition"])


def test_there_are_templates_to_check():
    """A silent empty list would make every parametrised test below vacuous."""
    assert WORKFLOW_TEMPLATES


@pytest.mark.parametrize("slug,template", CASES)
class TestTemplateShape:
    def test_declares_every_column_the_seeder_writes(self, slug, template):
        required = {
            "name",
            "slug",
            "description",
            "category",
            "version",
            "author_name",
            "status",
            "trigger_type",
            "trigger_config",
            "workflow_definition",
        }
        assert required <= set(template), f"{slug} is missing {required - set(template)}"

    def test_is_published_or_it_will_never_be_listed(self, slug, template):
        # The list endpoint filters on status == "published".
        assert template["status"] == "published"

    def test_slug_is_unique(self, slug, template):
        assert [t["slug"] for t in WORKFLOW_TEMPLATES].count(slug) == 1


@pytest.mark.parametrize("slug,template", CASES)
class TestTemplateGraph:
    def test_is_a_v2_graph(self, slug, template):
        graph = graph_of(template)
        assert graph["schema_version"] == 2
        assert graph["nodes"], f"{slug} has no nodes"

    def test_starts_at_exactly_one_trigger_node(self, slug, template):
        triggers = [n for n in graph_of(template)["nodes"] if n["type"] == "trigger"]
        assert len(triggers) == 1, f"{slug} has {len(triggers)} trigger nodes"

    def test_every_step_type_has_a_handler(self, slug, template):
        """
        The failure this is here to prevent: a template naming a step type the
        engine has never heard of, which installs fine and dies on first run.
        """
        for node in graph_of(template)["nodes"]:
            if node["type"] == "trigger":
                continue

            # Must be a real StepType...
            step_type = StepType(node["type"])
            # ...and that StepType must be wired to a handler.
            assert StepHandlerFactory.get_handler(step_type) is not None

    def test_no_edge_dangles(self, slug, template):
        graph = graph_of(template)
        ids = {n["id"] for n in graph["nodes"]}
        for edge in graph["edges"]:
            assert edge["source"] in ids, f"{slug}: edge from unknown {edge['source']}"
            assert edge["target"] in ids, f"{slug}: edge to unknown {edge['target']}"

    def test_node_ids_are_unique(self, slug, template):
        ids = [n["id"] for n in graph_of(template)["nodes"]]
        assert len(ids) == len(set(ids)), f"{slug} reuses a node id"

    def test_every_step_is_reachable_from_the_trigger(self, slug, template):
        """An unreachable step is dead weight the user has to diagnose."""
        graph = graph_of(template)
        trigger = next(n for n in graph["nodes"] if n["type"] == "trigger")

        reachable = set()
        stack = [trigger["id"]]
        while stack:
            current = stack.pop()
            if current in reachable:
                continue
            reachable.add(current)
            stack.extend(
                e["target"] for e in graph["edges"] if e["source"] == current
            )

        unreachable = {n["id"] for n in graph["nodes"]} - reachable
        assert not unreachable, f"{slug} cannot reach {sorted(unreachable)}"

    def test_branching_steps_connect_every_output(self, slug, template):
        """
        A Branch with no `false` edge, or a Switch missing a rule's branch,
        silently drops half the runs.
        """
        graph = graph_of(template)
        handles = {
            (e["source"], e.get("sourceHandle", "out")) for e in graph["edges"]
        }

        for node in graph["nodes"]:
            if node["type"] == "condition":
                expected = {"true", "false"}
            elif node["type"] == "switch":
                rules = node["config"].get("rules") or []
                expected = {f"branch-{i}" for i in range(len(rules))} | {"fallback"}
            else:
                continue

            missing = {h for h in expected if (node["id"], h) not in handles}
            assert not missing, f"{slug}: {node['id']} leaves {sorted(missing)} unconnected"


@pytest.mark.parametrize("slug,template", CASES)
class TestTemplateTrigger:
    def test_trigger_type_is_real(self, slug, template):
        TriggerType(template["trigger_type"])

    def test_trigger_config_passes_the_same_validator_as_a_hand_built_workflow(
        self, slug, template
    ):
        trigger_type = TriggerType(template["trigger_type"])
        config = dict(template["trigger_config"] or {})

        # A webhook key is generated per install, so no template carries one —
        # shipping one would hand every install the same URL. The install path
        # fills it in before validating, so do the same here.
        if trigger_type == TriggerType.WEBHOOK and not config.get("webhook_key"):
            config["webhook_key"] = "k" * 32

        TriggerValidator.validate_trigger_config(trigger_type, config)


@pytest.mark.parametrize("slug,template", CASES)
class TestTemplateIntegrations:
    def test_only_names_integrations_that_exist(self, slug, template):
        """
        Six of the ten previous templates required Zendesk, Shopify, Twilio or
        Mailgun — none of which the platform connects to, so their setup guides
        asked for something impossible.
        """
        declared = set(template.get("required_integrations") or [])
        assert declared <= SUPPORTED_INTEGRATIONS, (
            f"{slug} requires unsupported {sorted(declared - SUPPORTED_INTEGRATIONS)}"
        )

    def test_integration_steps_leave_the_connection_blank(self, slug, template):
        """
        Connections are per-workspace, so a baked-in id would point at another
        workspace's connection or at nothing. Blank is what makes the builder
        flag the step as needing attention.
        """
        for node in graph_of(template)["nodes"]:
            if node["type"] != "action":
                continue
            assert not node["config"].get("connection_id"), (
                f"{slug}: {node['id']} ships a hardcoded connection_id"
            )

    def test_a_template_with_action_steps_says_what_to_connect(self, slug, template):
        """Otherwise the blank connection is a puzzle rather than a setup step."""
        has_action = any(
            n["type"] == "action" for n in graph_of(template)["nodes"]
        )
        if has_action:
            assert template.get("required_integrations"), (
                f"{slug} has integration steps but declares no required_integrations"
            )


class TestTemplateCoverage:
    """The set as a whole, not any single template."""

    def test_some_templates_need_no_setup_at_all(self):
        """
        At least one template must run without connecting anything. Otherwise
        every first-time user hits an OAuth flow before seeing a workflow work,
        which is the slowest possible way to learn what the feature does.
        """
        zero_setup = [
            t for t in WORKFLOW_TEMPLATES if not t.get("required_integrations")
        ]
        assert len(zero_setup) >= 2, "fewer than two templates run with no setup"

    def test_templates_cover_more_than_one_trigger_type(self):
        """Templates teach shapes; a set that all start the same way teaches one."""
        assert len({t["trigger_type"] for t in WORKFLOW_TEMPLATES}) >= 3
