"""
The resource picker's pure logic: normalising wildly different provider
responses, pulling ids out of pasted links, and falling back to a connection's
defaults.

These are the parts that decide whether a non-technical user ever has to see an
internal id, and every one of them is a pure function — so they are tested
directly rather than through an HTTP round trip to a live Trello account.
"""

import pytest

from app.services.integrations.action_registry import (
    resource_fields,
    strip_ui_only_parameters,
)
from app.services.integrations.resource_registry import (
    ResourceSpec,
    apply_connection_defaults,
    describe_kinds,
    get_spec,
    normalize_resources,
    parse_resource_url,
    search_resources,
    supports_url,
)

pytestmark = [pytest.mark.unit]


class TestNormalisation:
    """Connectors were written independently and disagree about response shape.

    Each case below is the literal shape one of the real connectors returns.
    """

    def test_trello_style_wrapped_list(self):
        spec = ResourceSpec(method="get_lists", label="List", result_keys=("lists",))
        raw = {"lists": [{"id": "l1", "name": "To Do"}, {"id": "l2", "name": "Done"}], "count": 2}

        assert normalize_resources(raw, spec) == [
            {"id": "l1", "name": "To Do"},
            {"id": "l2", "name": "Done"},
        ]

    def test_google_style_items_key(self):
        spec = ResourceSpec(method="list_calendars", label="Calendar", result_keys=("items",))
        raw = {"items": [{"id": "primary", "summary": "Work"}]}

        # Google calls the display name "summary", not "name".
        assert normalize_resources(raw, spec) == [{"id": "primary", "name": "Work"}]

    def test_bare_list(self):
        spec = ResourceSpec(method="get_lists", label="List")
        raw = [{"id": "1", "name": "Newsletter"}]

        assert normalize_resources(raw, spec) == [{"id": "1", "name": "Newsletter"}]

    def test_graphql_nested_shape(self):
        """Monday returns {"data": {"boards": [...]}}."""
        spec = ResourceSpec(method="list_boards", label="Board", result_keys=("boards",))
        raw = {"data": {"boards": [{"id": "77", "name": "Sales"}]}}

        assert normalize_resources(raw, spec) == [{"id": "77", "name": "Sales"}]

    def test_items_without_an_id_are_dropped(self):
        """An option that cannot be selected is worse than one that is absent."""
        spec = ResourceSpec(method="x", label="Thing", result_keys=("things",))
        raw = {"things": [{"name": "no id here"}, {"id": "ok", "name": "Fine"}]}

        assert normalize_resources(raw, spec) == [{"id": "ok", "name": "Fine"}]

    def test_missing_name_falls_back_to_the_id(self):
        """Still reachable, even when the provider omits a label."""
        spec = ResourceSpec(method="x", label="Thing", result_keys=("things",))
        raw = {"things": [{"id": "abc123"}]}

        assert normalize_resources(raw, spec) == [{"id": "abc123", "name": "abc123"}]

    def test_provider_order_is_preserved(self):
        """Trello returns lists in board order and that order means something.

        Alphabetising turns "To Do, Doing, Done" into "Doing, Done, To Do",
        which is actively worse for the person reading the dropdown.
        """
        spec = ResourceSpec(method="get_lists", label="List", result_keys=("lists",))
        raw = {"lists": [
            {"id": "1", "name": "To Do"},
            {"id": "2", "name": "Doing"},
            {"id": "3", "name": "Done"},
        ]}

        assert [r["name"] for r in normalize_resources(raw, spec)] == [
            "To Do",
            "Doing",
            "Done",
        ]

    def test_unrecognised_shape_yields_nothing_rather_than_raising(self):
        spec = ResourceSpec(method="x", label="Thing")

        assert normalize_resources({"unexpected": "string"}, spec) == []
        assert normalize_resources(None, spec) == []


class TestSearch:
    def test_filters_case_insensitively(self):
        items = [{"id": "1", "name": "To Do"}, {"id": "2", "name": "Done"}]

        assert search_resources(items, "do") == items  # both contain "do"
        assert search_resources(items, "TO") == [{"id": "1", "name": "To Do"}]

    def test_blank_query_returns_everything(self):
        items = [{"id": "1", "name": "To Do"}]

        assert search_resources(items, "") == items
        assert search_resources(items, None) == items


class TestUrlParsing:
    """Pasting a link is the fastest route when the tab is already open."""

    @pytest.mark.parametrize(
        "slug,kind,url,expected",
        [
            ("trello", "boards", "https://trello.com/b/aBc123Xy/my-board", "aBc123Xy"),
            ("trello", "cards", "https://trello.com/c/Zz99Yy/4-fix-the-sink", "Zz99Yy"),
            (
                "google-sheets",
                "spreadsheets",
                "https://docs.google.com/spreadsheets/d/1A2b3C4d5E6f7G8h9I0jKlMnOpQ/edit#gid=0",
                "1A2b3C4d5E6f7G8h9I0jKlMnOpQ",
            ),
            (
                "slack",
                "channels",
                "https://acme.slack.com/archives/C01234ABCDE",
                "C01234ABCDE",
            ),
            ("monday", "boards", "https://acme.monday.com/boards/123456789", "123456789"),
            (
                "airtable",
                "bases",
                "https://airtable.com/appAbC123/tblXyZ789/viwFoo",
                "appAbC123",
            ),
            (
                "airtable",
                "tables",
                "https://airtable.com/appAbC123/tblXyZ789/viwFoo",
                "tblXyZ789",
            ),
        ],
    )
    def test_extracts_the_id(self, slug, kind, url, expected):
        assert parse_resource_url(slug, kind, url) == expected

    def test_a_link_of_the_wrong_kind_is_rejected(self):
        """Better an explicit error than a value that fails at 2am mid-run."""
        assert parse_resource_url("trello", "boards", "https://example.com/nope") is None

    def test_blank_and_unknown_kinds_are_safe(self):
        assert parse_resource_url("trello", "boards", "") is None
        assert parse_resource_url("trello", "nonexistent", "https://trello.com/b/x") is None
        assert parse_resource_url("nosuchconnector", "boards", "https://x") is None

    def test_supports_url_reports_availability(self):
        assert supports_url("trello", "boards") is True
        # Google Calendar has no useful public URL form for a calendar id.
        assert supports_url("google-calendar", "calendars") is False


class TestConnectionDefaults:
    """The bit that makes the picker disappear for most people."""

    def test_fills_a_blank_parameter(self):
        result = apply_connection_defaults(
            {"name": "New card"}, {"defaults": {"list_id": "L1"}}
        )

        assert result == {"name": "New card", "list_id": "L1"}

    def test_never_overrides_an_explicit_value(self):
        """A default silently replacing what someone typed would be far worse
        than a missing value they can see."""
        result = apply_connection_defaults(
            {"list_id": "CHOSEN"}, {"defaults": {"list_id": "DEFAULT"}}
        )

        assert result["list_id"] == "CHOSEN"

    def test_treats_empty_string_as_blank(self):
        result = apply_connection_defaults(
            {"list_id": ""}, {"defaults": {"list_id": "L1"}}
        )

        assert result["list_id"] == "L1"

    def test_no_config_is_a_no_op(self):
        assert apply_connection_defaults({"a": 1}, None) == {"a": 1}
        assert apply_connection_defaults({"a": 1}, {}) == {"a": 1}
        assert apply_connection_defaults({"a": 1}, {"defaults": {}}) == {"a": 1}

    def test_does_not_mutate_the_caller_dict(self):
        original = {"name": "x"}
        apply_connection_defaults(original, {"defaults": {"list_id": "L1"}})

        assert original == {"name": "x"}


class TestActionSchemaAnnotations:
    def test_trello_create_card_declares_a_cascade(self):
        fields = resource_fields("trello", "create_card")

        assert fields["board_id"]["x-resource"] == "boards"
        assert fields["list_id"]["x-resource"] == "lists"
        assert fields["list_id"]["x-depends-on"] == "board_id"

    def test_ui_only_parameters_never_reach_the_connector(self):
        """TrelloConnector.create_card takes no board_id — passing it raises."""
        cleaned = strip_ui_only_parameters(
            "trello", "create_card", {"board_id": "B", "list_id": "L", "name": "Card"}
        )

        assert cleaned == {"list_id": "L", "name": "Card"}

    def test_stripping_is_a_no_op_for_actions_without_ui_fields(self):
        params = {"channel": "C1", "message": "hi"}

        assert strip_ui_only_parameters("slack", "send_message", params) == params

    def test_unknown_action_passes_parameters_through(self):
        params = {"anything": "goes"}

        assert strip_ui_only_parameters("trello", "no_such_action", params) == params


class TestProviderDeclarations:
    def test_trello_declares_the_board_to_list_relationship(self):
        lists = get_spec("trello", "lists")

        assert lists is not None
        assert lists.parent_kind == "boards"
        assert lists.parent_arg == "board_id"

    def test_describe_kinds_drives_the_setup_screen(self):
        described = {k["kind"]: k for k in describe_kinds("trello")}

        assert described["boards"]["supports_url"] is True
        assert described["lists"]["parent_kind"] == "boards"

    def test_a_connector_without_providers_is_empty_not_an_error(self):
        assert describe_kinds("stripe") == []
        assert get_spec("stripe", "anything") is None
