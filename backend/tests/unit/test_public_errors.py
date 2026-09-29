"""What failure text may reach a customer (app/core/public_errors.py)."""

import pytest

from app.core.public_errors import looks_technical, public_message, public_test_result


@pytest.mark.parametrize(
    "text",
    [
        "That number is no longer available",
        "Could not connect with those credentials. Check them and try again.",
        "Agent not found",
        "Starter includes 1 agent. Upgrade to add more.",
    ],
)
def test_written_sentences_pass(text):
    assert not looks_technical(text)
    assert public_message(text, "fallback") == text


@pytest.mark.parametrize(
    "text",
    [
        "",
        None,
        {"error": "x"},
        "'NoneType' object has no attribute 'id'",
        "Client error '401 Unauthorized' for url 'https://api.hubapi.com/x'",
        "HTTPSConnectionPool(host='api.x.com', port=443): Max retries exceeded",
        '(sqlalchemy.exc.IntegrityError) duplicate key value violates unique constraint "uq"',
        "ValueError: bad",
        '{"error": {"code": 500}}',
        "<html><body>Bad gateway</body></html>",
        "x" * 300,
    ],
)
def test_technical_text_is_replaced(text):
    assert looks_technical(text)
    assert public_message(text, "fallback") == "fallback"


def test_failed_test_hides_provider_body_and_names_credentials():
    result = public_test_result(
        {
            "success": False,
            "message": "HubSpot connection test failed: Client error '401 Unauthorized' for url 'https://api.hubapi.com'",
            "details": {"response": '{"status":"error","message":"token expired"}'},
        },
        "HubSpot",
    )
    assert result["message"] == "HubSpot rejected these credentials. Check them and try again."
    assert result["details"] == {}


def test_failed_test_generic_when_no_hint():
    result = public_test_result(
        {"success": False, "message": "Connection test failed: timed out", "details": {}},
        "Notion",
    )
    assert result["message"] == "We couldn't connect to Notion. Check your details and try again."


def test_failed_test_keeps_a_written_message():
    result = public_test_result(
        {"success": False, "message": "Add a sender email before testing.", "details": {"x": 1}},
        "SMTP",
    )
    assert result["message"] == "Add a sender email before testing."
    assert result["details"] == {}


def test_success_is_untouched():
    ok = {"success": True, "message": "Connected as Acme", "details": {"team": "Acme"}}
    assert public_test_result(ok, "Slack") == ok
