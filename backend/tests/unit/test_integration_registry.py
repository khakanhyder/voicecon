"""Contract tests between the action registry and the connector classes.

Every one of these guards a bug that shipped. The registry is what the workflow
builder renders, what a saved step stores and what an agent's tool definition
advertises; the connector methods are what actually runs. Nothing checked that
the two agreed, and they had drifted in seven places — Slack's send_message
declared ``message`` while the method took ``text``, so the text was dropped by
``drop_unsupported_arguments`` and the call failed on a missing argument, with
nothing in the logs pointing at the rename.

These are pure inspection tests: no database, no network, no credentials.
"""
import inspect

import pytest

from app.services.integrations import connectors
from app.services.integrations.action_registry import (
    CONNECTOR_CLASS_MAP,
    INTEGRATION_ACTIONS,
    adapt_parameters,
    strip_ui_only_parameters,
)

# A value of the right shape for each JSON Schema type, so adapters that index
# into a parameter get something they can work with.
SAMPLE_BY_TYPE = {
    "string": "x",
    "integer": 1,
    "number": 1.0,
    "object": {},
    "array": [],
    "boolean": True,
}


def _all_actions():
    for slug, actions in INTEGRATION_ACTIONS.items():
        for action in actions:
            yield slug, action


def _sample(properties, keys):
    return {
        key: SAMPLE_BY_TYPE.get((properties.get(key) or {}).get("type"), "x")
        for key in keys
    }


def _prepare(slug, action_name, params):
    """Run params through the same pipeline the executors use."""
    params = strip_ui_only_parameters(slug, action_name, params)
    return adapt_parameters(slug, action_name, params)


def _method_for(slug, action_name):
    cls = getattr(connectors, CONNECTOR_CLASS_MAP[slug], None)
    assert cls is not None, f"No connector class exported for '{slug}'"
    return getattr(cls, action_name, None)


def test_every_exported_connector_is_reachable():
    """A connector class nothing maps to is dead code.

    This is how Stripe sat unusable: 696 lines of working connector, exported
    and importable, but absent from the registry, so no workflow step and no
    agent tool could name it.
    """
    exported = set(connectors.__all__)
    mapped = set(CONNECTOR_CLASS_MAP.values())
    assert not exported - mapped, (
        f"Connector classes exported but not in CONNECTOR_CLASS_MAP: "
        f"{sorted(exported - mapped)}"
    )


def test_every_mapped_class_exists():
    missing = sorted(
        name for name in set(CONNECTOR_CLASS_MAP.values())
        if not hasattr(connectors, name)
    )
    assert not missing, f"CONNECTOR_CLASS_MAP names non-existent classes: {missing}"


def test_every_connector_with_actions_has_a_class():
    orphans = sorted(set(INTEGRATION_ACTIONS) - set(CONNECTOR_CLASS_MAP))
    assert not orphans, f"Actions declared for slugs with no connector: {orphans}"


@pytest.mark.parametrize(
    "slug,action",
    [(slug, action) for slug, action in _all_actions()],
    ids=lambda v: v if isinstance(v, str) else v["action"],
)
def test_action_resolves_to_a_real_method(slug, action):
    assert _method_for(slug, action["action"]) is not None, (
        f"{slug}.{action['action']} is offered in the builder but the connector "
        f"has no such method"
    )


@pytest.mark.parametrize(
    "slug,action",
    [(slug, action) for slug, action in _all_actions()],
    ids=lambda v: v if isinstance(v, str) else v["action"],
)
def test_declared_parameters_are_accepted_by_the_method(slug, action):
    """Nothing the schema offers may be silently discarded.

    ``drop_unsupported_arguments`` is a safety net for stale saved steps, not a
    licence for the schema to advertise fields the method cannot take. A field
    that reaches it from a *fresh* form fill is a naming bug.
    """
    method = _method_for(slug, action["action"])
    accepted = set(inspect.signature(method).parameters) - {"self"}
    properties = (action.get("parameters") or {}).get("properties") or {}

    prepared = _prepare(slug, action["action"], _sample(properties, properties))
    unknown = set(prepared) - accepted

    assert not unknown, (
        f"{slug}.{action['action']} declares {sorted(unknown)}, which "
        f"{method.__qualname__} does not accept "
        f"(it takes {sorted(accepted)}). Either rename in the schema or add an "
        f"entry to ACTION_ADAPTERS."
    )


@pytest.mark.parametrize(
    "slug,action",
    [(slug, action) for slug, action in _all_actions()],
    ids=lambda v: v if isinstance(v, str) else v["action"],
)
def test_schema_supplies_every_mandatory_method_argument(slug, action):
    """Filling in only the required fields must produce a callable invocation.

    SendGrid's send_email failed this: ``from_email`` had no default and was
    not in the schema at all, so every send raised TypeError before a request
    was ever made.
    """
    method = _method_for(slug, action["action"])
    signature = inspect.signature(method)
    properties = (action.get("parameters") or {}).get("properties") or {}
    required = list((action.get("parameters") or {}).get("required") or [])

    mandatory = {
        name
        for name, param in signature.parameters.items()
        if name != "self"
        and param.default is inspect.Parameter.empty
        and param.kind
        in (inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY)
    }

    prepared = _prepare(slug, action["action"], _sample(properties, required))
    unmet = mandatory - set(prepared)

    assert not unmet, (
        f"{slug}.{action['action']}: {method.__qualname__} requires "
        f"{sorted(unmet)}, but the schema does not require (or adapt to) them. "
        f"Give the argument a default or add it to the schema."
    )


@pytest.mark.parametrize(
    "slug,action",
    [(slug, action) for slug, action in _all_actions()],
    ids=lambda v: v if isinstance(v, str) else v["action"],
)
def test_action_metadata_is_complete(slug, action):
    """The builder renders these; a missing label ships as a blank dropdown."""
    for field in ("action", "label", "description"):
        assert action.get(field), f"{slug}.{action.get('action')} has no '{field}'"
    assert (action.get("parameters") or {}).get("type") == "object", (
        f"{slug}.{action['action']} parameters must be a JSON Schema object"
    )


class TestActionAdapters:
    """The specific renames that were silently breaking actions.

    Each of these had the same signature failure: the schema's key was dropped
    as "unsupported", and the call then died on a missing required argument —
    an error naming the connector's parameter, which appears nowhere in the UI
    the user filled in.
    """

    def test_slack_message_becomes_text(self):
        """Slack's send_message is the most-used action in the product and it
        could not send anything."""
        assert adapt_parameters(
            "slack", "send_message", {"channel": "#ops", "message": "hello"}
        ) == {"channel": "#ops", "text": "hello"}

    def test_sendgrid_body_becomes_text_content(self):
        result = adapt_parameters(
            "sendgrid", "send_email", {"to_email": "a@b.c", "body": "hi"}
        )
        assert result == {"to_email": "a@b.c", "text_content": "hi"}

    def test_calendar_title_becomes_summary(self):
        result = adapt_parameters("google-calendar", "create_event", {"title": "Demo"})
        assert result == {"summary": "Demo"}

    def test_calendar_single_attendee_becomes_a_list(self):
        result = adapt_parameters(
            "google-calendar", "create_event", {"attendee_email": "a@b.c"}
        )
        assert result == {"attendees": ["a@b.c"]}

    def test_calendar_dates_widen_to_a_full_day_window(self):
        result = adapt_parameters(
            "google-calendar", "find_available_slots", {"date": "2026-08-13"}
        )
        assert result["search_start"] == "2026-08-13T00:00:00Z"
        assert result["search_end"] == "2026-08-13T23:59:59Z"

    def test_an_explicit_timestamp_is_left_alone(self):
        result = adapt_parameters(
            "google-calendar", "list_events", {"start_date": "2026-08-13T09:30:00Z"}
        )
        assert result["time_min"] == "2026-08-13T09:30:00Z"

    def test_calendar_id_becomes_a_list_for_freebusy(self):
        result = adapt_parameters(
            "google-calendar", "check_availability", {"calendar_id": "primary"}
        )
        assert result == {"calendar_ids": ["primary"]}

    def test_hubspot_flat_fields_fold_into_the_property_bag(self):
        result = adapt_parameters(
            "hubspot",
            "update_contact",
            {"contact_id": "1", "phone": "555", "company": "Acme"},
        )
        assert result == {
            "contact_id": "1",
            "properties": {"phone": "555", "company": "Acme"},
        }

    def test_hubspot_additional_properties_merge_with_flat_fields(self):
        result = adapt_parameters(
            "hubspot",
            "update_contact",
            {"contact_id": "1", "phone": "555", "additional_properties": {"city": "NY"}},
        )
        assert result["properties"] == {"city": "NY", "phone": "555"}

    def test_hubspot_survives_a_malformed_additional_properties(self):
        """The value comes from an LLM; a string here must not kill the call."""
        result = adapt_parameters(
            "hubspot",
            "update_contact",
            {"contact_id": "1", "phone": "555", "additional_properties": "oops"},
        )
        assert result["properties"] == {"phone": "555"}

    def test_salesforce_lead_source_is_preserved_as_a_real_field(self):
        result = adapt_parameters(
            "salesforce", "create_lead", {"last_name": "Ali", "lead_source": "Phone"}
        )
        assert result["additional_fields"] == {"LeadSource": "Phone"}

    def test_an_action_with_no_adapter_passes_through_untouched(self):
        params = {"to": "123", "message": "hi"}
        assert adapt_parameters("whatsapp", "send_message", params) == params

    def test_adapters_do_not_mutate_the_callers_dict(self):
        """Executors reuse the parameter dict for logging and retries."""
        original = {"channel": "#ops", "message": "hello"}
        adapt_parameters("slack", "send_message", original)
        assert original == {"channel": "#ops", "message": "hello"}

    def test_an_explicit_connector_name_is_not_overwritten(self):
        result = adapt_parameters(
            "slack", "send_message", {"message": "schema", "text": "explicit"}
        )
        assert result["text"] == "explicit"
