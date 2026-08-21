"""
Reading a tool's stored configuration.

Every case here is a bug that reached a live call. The builder form stores its
JSON fields as the text the user typed, and the consumers assumed parsed
values, so a tool saved cleanly and then failed on the phone.
"""
import pytest

from app.services.tools.config import (
    ToolConfigError,
    as_header_map,
    as_mapping,
    as_sequence,
    as_timeout,
    build_body,
    render,
    resolve,
)


class TestAsMapping:
    """The reported bug: `{**cfg["headers"]}` on a string."""

    def test_parses_the_text_the_form_stores(self):
        # This is verbatim what the api_request form writes by default.
        raw = '{\n  "Content-Type": "application/json"\n}'
        assert as_mapping(raw, "Headers") == {"Content-Type": "application/json"}

    def test_accepts_an_already_parsed_object(self):
        # A tool created through the API holds the object itself, and both
        # spellings are valid on the wire.
        assert as_mapping({"A": "b"}, "Headers") == {"A": "b"}

    def test_unset_and_blank_are_empty(self):
        assert as_mapping(None, "Headers") == {}
        assert as_mapping("", "Headers") == {}
        assert as_mapping("   ", "Headers") == {}

    def test_invalid_json_names_the_field_and_the_position(self):
        with pytest.raises(ToolConfigError) as exc:
            as_mapping('{"a": 1,}', "Headers")
        assert "Headers" in str(exc.value)
        assert "line" in str(exc.value)

    def test_a_json_array_is_not_a_header_map(self):
        with pytest.raises(ToolConfigError, match="Headers must be a JSON object"):
            as_mapping('["a", "b"]', "Headers")


class TestAsHeaderMap:
    def test_renders_non_string_values_rather_than_failing(self):
        # A header must be text on the wire, and {"X-Retries": 3} is an obvious
        # intent — failing the call over it helps nobody.
        assert as_header_map('{"X-Retries": 3, "X-On": true}') == {
            "X-Retries": "3",
            "X-On": "true",
        }

    def test_refuses_a_structured_value(self):
        with pytest.raises(ToolConfigError, match="single value"):
            as_header_map('{"X-Thing": {"nested": 1}}')


class TestAsTimeout:
    """The form offers a timeout; the executor used to hardcode one."""

    def test_reads_the_text_the_form_stores(self):
        assert as_timeout("20", 30.0) == 20.0

    def test_blank_means_the_default_not_zero(self):
        assert as_timeout("", 30.0) == 30.0
        assert as_timeout(None, 30.0) == 30.0

    def test_nonsense_falls_back_rather_than_breaking_the_tool(self):
        assert as_timeout("soon", 30.0) == 30.0

    def test_clamped_so_one_tool_cannot_pin_a_worker_open(self):
        assert as_timeout("99999", 30.0) == 120.0
        assert as_timeout("0", 30.0) == 1.0
        assert as_timeout("-5", 30.0) == 1.0


class TestRender:
    """Type preservation, matching the workflow templating rules."""

    def test_a_whole_value_reference_keeps_its_type(self):
        assert render("{{count}}", {"count": 42}) == 42
        assert render("{{ok}}", {"ok": True}) is True
        assert render("{{items}}", {"items": [1, 2]}) == [1, 2]

    def test_a_mixed_template_is_text(self):
        assert render("Order {{id}} shipped", {"id": 7}) == "Order 7 shipped"

    def test_a_missing_whole_value_is_none(self):
        assert render("{{nope}}", {}) is None

    def test_a_missing_reference_in_text_leaves_nothing_behind(self):
        # Leaking a literal "{{nope}}" into an outbound payload is never what
        # the author meant.
        assert render("a{{nope}}b", {}) == "ab"

    def test_walks_nested_structures(self):
        assert render({"a": {"b": "{{x}}"}}, {"x": 5}) == {"a": {"b": 5}}

    def test_dotted_paths_reach_into_an_object_parameter(self):
        assert resolve("address.city", {"address": {"city": "Leeds"}}) == "Leeds"

    def test_indexes_into_an_array_parameter(self):
        assert resolve("days[0]", {"days": ["Mon", "Tue"]}) == "Mon"

    def test_a_path_through_a_missing_branch_is_none(self):
        assert resolve("address.city", {}) is None
        assert resolve("days[9]", {"days": []}) is None


class TestBuildBody:
    """A body template is a template, not a set of extra keys."""

    def test_fills_placeholders_from_the_extracted_parameters(self):
        body = build_body(
            '{"email": "{{customer_email}}"}', {"customer_email": "ada@example.com"}
        )
        assert body == {"email": "ada@example.com"}

    def test_a_referenced_parameter_is_not_also_appended(self):
        # The old code merged parameters over the template, so the placeholder
        # went out verbatim alongside the value.
        body = build_body('{"email": "{{email}}"}', {"email": "a@b.c"})
        assert body == {"email": "a@b.c"}
        assert "{{email}}" not in str(body)

    def test_numbers_survive_as_numbers(self):
        body = build_body('{"amount": "{{total}}"}', {"total": 42})
        assert body["amount"] == 42
        assert not isinstance(body["amount"], str)

    def test_parameters_the_template_ignores_are_still_passed_through(self):
        # A tool with no template at all must keep working as it always has.
        assert build_body("{}", {"a": 1}) == {"a": 1}
        assert build_body(None, {"a": 1}) == {"a": 1}

    def test_renames_nothing_it_was_not_asked_to(self):
        body = build_body('{"to": "{{email}}"}', {"email": "a@b.c", "note": "hi"})
        assert body == {"to": "a@b.c", "note": "hi"}


class TestAsSequence:
    def test_parses_a_row_template(self):
        assert as_sequence('["{{name}}", "{{phone}}"]', "Row") == [
            "{{name}}",
            "{{phone}}",
        ]

    def test_refuses_an_object(self):
        with pytest.raises(ToolConfigError, match="must be a JSON array"):
            as_sequence('{"a": 1}', "Row")
