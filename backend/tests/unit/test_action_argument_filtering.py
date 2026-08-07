"""
Stray arguments must not kill an action step.

Every dynamic integration call ends in ``method(**parameters)``, where one key
the method does not declare is a ``TypeError`` that fails the whole step. The
reported case: a Trello node configured as "Create Card" and later switched to
"Comment on Card" kept ``board_id`` in its saved parameters, and every run died
on ``TrelloConnector.add_comment() got an unexpected keyword argument
'board_id'``.
"""

import pytest

from app.services.integrations.action_registry import drop_unsupported_arguments

pytestmark = [pytest.mark.unit]


class FakeConnector:
    """Stands in for a real connector — only the signatures matter here."""

    async def add_comment(self, card_id: str, text: str):
        return {"card_id": card_id, "text": text}

    async def create_card(
        self, list_id: str, name: str, description: str = ""
    ):
        return {"list_id": list_id, "name": name}

    async def anything_goes(self, required: str, **kwargs):
        return {"required": required, "extra": kwargs}


class TestTheReportedFailure:
    def test_a_leftover_field_from_the_previous_action_is_dropped(self):
        connector = FakeConnector()
        # Exactly what the builder saves after "Create Card" → "Comment on Card".
        saved = {
            "board_id": "68e3f...",
            "list_id": "6f219...",
            "name": "Maintenance",
            "description": "",
            "card_id": "{{steps.create_card.id}}",
            "text": "Logged by Voicecon",
        }

        cleaned = drop_unsupported_arguments(connector.add_comment, saved)

        assert cleaned == {
            "card_id": "{{steps.create_card.id}}",
            "text": "Logged by Voicecon",
        }

    async def test_the_call_that_used_to_raise_now_succeeds(self):
        connector = FakeConnector()
        saved = {"board_id": "b1", "card_id": "c1", "text": "hi"}

        with pytest.raises(TypeError, match="board_id"):
            await connector.add_comment(**saved)

        result = await connector.add_comment(
            **drop_unsupported_arguments(connector.add_comment, saved)
        )
        assert result == {"card_id": "c1", "text": "hi"}


class TestItDoesNotOverreach:
    def test_valid_arguments_are_untouched(self):
        connector = FakeConnector()
        supplied = {"list_id": "l1", "name": "Card", "description": "d"}
        assert drop_unsupported_arguments(connector.create_card, supplied) == supplied

    def test_optional_arguments_survive(self):
        connector = FakeConnector()
        supplied = {"list_id": "l1", "name": "Card"}
        assert drop_unsupported_arguments(connector.create_card, supplied) == supplied

    def test_a_method_taking_kwargs_is_left_alone(self):
        """It has already said it will take anything."""
        connector = FakeConnector()
        supplied = {"required": "x", "whatever": 1}
        assert drop_unsupported_arguments(connector.anything_goes, supplied) == supplied

    def test_a_misspelled_required_argument_still_fails_loudly(self):
        """Dropping the unknown key must not turn a typo into a silent no-op."""
        connector = FakeConnector()
        cleaned = drop_unsupported_arguments(
            connector.add_comment, {"card_id": "c1", "comment_text": "hi"}
        )
        assert cleaned == {"card_id": "c1"}
        with pytest.raises(TypeError, match="text"):
            connector.add_comment(**cleaned)

    def test_empty_parameters_are_fine(self):
        connector = FakeConnector()
        assert drop_unsupported_arguments(connector.add_comment, {}) == {}
        assert drop_unsupported_arguments(connector.add_comment, None) == {}


class TestRealConnectors:
    def test_trello_add_comment_rejects_board_id(self):
        """Against the actual connector, not a stand-in."""
        from app.services.integrations.connectors.trello_connector import (
            TrelloConnector,
        )

        cleaned = drop_unsupported_arguments(
            TrelloConnector.add_comment,
            {"board_id": "b1", "list_id": "l1", "card_id": "c1", "text": "hi"},
        )
        assert cleaned == {"card_id": "c1", "text": "hi"}
