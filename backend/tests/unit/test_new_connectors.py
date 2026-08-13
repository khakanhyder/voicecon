"""Behaviour of the connectors added for the previously-unbuilt tiles.

No network: every test drives the connector's own logic with fabricated
credentials and asserts on what it decides. The one thing that genuinely needs
a live provider — whether a real credential works — is out of scope here.
"""
from types import SimpleNamespace

import pytest

from app.services.integrations import connectors as C
from app.services.integrations.connector_base import ConnectorError
from app.services.integrations.connectors.smtp_connector import SMTPConnector


class _FakeCredentials:
    def decrypt(self, value):
        return value

    def decrypt_dict(self, value):
        return value or {}


def build(cls, *, secret="dummy", auth_data=None, config=None, auth_config=None,
          base_url="https://api.example.com", auth_type="api_key"):
    connector = SimpleNamespace(
        slug="test", name="Test", base_url=base_url, auth_type=auth_type,
        auth_config=auth_config or {}, rate_limit_per_minute=None,
        rate_limit_per_hour=None, rate_limit_per_day=None,
    )
    connection = SimpleNamespace(
        id=None, config=config or {}, api_key_encrypted=secret,
        access_token_encrypted=None, auth_data_encrypted=auth_data or {},
    )
    instance = cls(connection=connection, connector=connector, db=None)
    instance.credential_manager = _FakeCredentials()
    return instance


class TestTeamsWebhookAcknowledgement:
    """Teams answers 200 for URLs that route nowhere.

    Microsoft's edge accepts a POST to any path under *.webhook.office.com and
    returns 200 with an empty body; a webhook that exists returns "1". Trusting
    the status code reported a mistyped or revoked URL as Connected, and every
    later notification then vanished with nothing raised anywhere.
    """

    def test_empty_body_is_rejected(self):
        teams = build(C.MicrosoftTeamsConnector)
        reason = teams._reject_reason(200, "")
        assert reason is not None
        assert "does not point at a live Incoming Webhook" in reason

    def test_whitespace_only_body_is_rejected(self):
        teams = build(C.MicrosoftTeamsConnector)
        assert teams._reject_reason(200, "  \n ") is not None

    def test_the_documented_success_body_is_accepted(self):
        teams = build(C.MicrosoftTeamsConnector)
        assert teams._reject_reason(200, "1") is None

    def test_other_providers_do_not_inherit_the_rule(self):
        """Zapier legitimately answers 200 with an empty body."""
        assert build(C.ZapierConnector)._reject_reason(200, "") is None


class TestTeamsPayloadShape:
    """Teams rejects arbitrary JSON — a bare object is a 400."""

    def test_plain_text_is_wrapped_in_a_message_card(self):
        card = build(C.MicrosoftTeamsConnector)._build_payload({"text": "hello"})
        assert card["@type"] == "MessageCard"
        assert card["text"] == "hello"
        assert card["summary"], "Teams drops a card with no summary or title"

    def test_a_hand_built_card_is_passed_through(self):
        supplied = {"type": "message", "attachments": []}
        assert build(C.MicrosoftTeamsConnector)._build_payload(supplied) == supplied

    def test_an_unshaped_payload_still_carries_its_data(self):
        card = build(C.MicrosoftTeamsConnector)._build_payload({"caller": "Sajid"})
        assert "Sajid" in card["text"]


class TestWebhookUrlValidation:
    def test_a_non_https_url_is_refused(self):
        connector = build(C.ZapierConnector, secret="http://hooks.zapier.com/x")
        with pytest.raises(ConnectorError, match="https"):
            connector._webhook_url()

    def test_a_url_from_the_wrong_provider_is_refused(self):
        """Pasting a Slack URL into the Zapier tile should fail at setup."""
        connector = build(C.ZapierConnector, secret="https://hooks.slack.com/services/x")
        with pytest.raises(ConnectorError, match="does not look like a Zapier"):
            connector._webhook_url()

    def test_a_valid_url_is_accepted(self):
        url = "https://hooks.zapier.com/hooks/catch/1/abc/"
        assert build(C.ZapierConnector, secret=url)._webhook_url() == url

    def test_make_accepts_any_region_host(self):
        for host in ("hook.eu1.make.com", "hook.us1.make.com", "hook.eu2.make.com"):
            url = f"https://{host}/abcdef"
            assert build(C.MakeConnector, secret=url)._webhook_url() == url

    def test_a_missing_url_is_refused(self):
        with pytest.raises(ConnectorError, match="No Zapier webhook URL"):
            build(C.ZapierConnector, secret="")._webhook_url()


class TestAzureCredentialDetection:
    """Which credential style this is, decided by shape rather than field name.

    A user who pastes a SAS into the "account key" box still gets a working
    connection instead of a 403 they cannot interpret.
    """

    def test_a_sas_token_is_recognised_from_its_shape(self):
        sas = "sv=2021-08-06&se=2030-01-01T00:00:00Z&sr=c&sp=rwl&sig=abc123"
        settings = build(
            C.AzureBlobConnector, secret=sas, auth_data={"account_name": "acct"}
        )._settings()
        assert settings["sas_token"] == sas
        assert settings["account_key"] == ""

    def test_a_leading_question_mark_is_stripped(self):
        sas = "?sv=2021-08-06&se=2030-01-01T00:00:00Z&sig=abc"
        settings = build(
            C.AzureBlobConnector, secret=sas, auth_data={"account_name": "acct"}
        )._settings()
        assert settings["sas_token"].startswith("sv=")

    def test_an_account_key_is_recognised_as_such(self):
        key = "Zm9vYmFyYmF6cXV4"  # base64, no signature parameter
        settings = build(
            C.AzureBlobConnector, secret=key, auth_data={"account_name": "acct"}
        )._settings()
        assert settings["account_key"] == key
        assert settings["sas_token"] == ""

    def test_the_host_is_derived_from_the_account_name(self):
        settings = build(
            C.AzureBlobConnector, secret="a", auth_data={"account_name": "acct"}
        )._settings()
        assert settings["base_url"] == "https://acct.blob.core.windows.net"

    def test_the_account_is_recovered_from_an_explicit_host(self):
        """Signing needs the account by name even when only a URL was given."""
        settings = build(
            C.AzureBlobConnector,
            secret="a",
            config={"base_url": "https://realacct.blob.core.windows.net"},
        )._settings()
        assert settings["account"] == "realacct"

    def test_no_account_at_all_is_an_actionable_error(self):
        with pytest.raises(ConnectorError, match="storage account name"):
            build(C.AzureBlobConnector, secret="a", base_url=None)._settings()


class TestObjectStorageConfiguration:
    def test_r2_builds_its_account_scoped_endpoint(self):
        r2 = build(C.CloudflareR2Connector, auth_data={"account_id": "abc123"})
        assert r2._endpoint_url() == "https://abc123.r2.cloudflarestorage.com"

    def test_r2_without_an_account_id_says_so(self):
        with pytest.raises(ConnectorError, match="Account ID"):
            build(C.CloudflareR2Connector)._endpoint_url()

    def test_gcs_uses_the_s3_compatible_endpoint(self):
        assert build(C.GCSConnector)._endpoint_url() == "https://storage.googleapis.com"

    def test_s3_lets_botocore_pick_the_regional_endpoint(self):
        assert build(C.AWSS3Connector)._endpoint_url() is None

    def test_s3_defaults_to_a_real_region_not_auto(self):
        """The region is part of the SigV4 credential scope; S3 rejects 'auto'."""
        assert C.AWSS3Connector.default_region == "us-east-1"

    def test_a_missing_bucket_is_an_actionable_error(self):
        with pytest.raises(ConnectorError, match="No bucket configured"):
            build(C.AWSS3Connector)._bucket()

    def test_an_action_level_bucket_overrides_the_connection(self):
        s3 = build(C.AWSS3Connector, auth_data={"bucket": "default-bucket"})
        assert s3._bucket("other-bucket") == "other-bucket"
        assert s3._bucket() == "default-bucket"

    def test_bucket_name_is_accepted_as_an_alias(self):
        """The setup forms say bucket_name; the connector reads either."""
        s3 = build(C.AWSS3Connector, auth_data={"bucket_name": "from-form"})
        assert s3._bucket() == "from-form"


class TestSMTPSettings:
    def test_gmail_and_outlook_carry_their_presets(self):
        assert C.GmailSMTPConnector.default_host == "smtp.gmail.com"
        assert C.OutlookSMTPConnector.default_host == "smtp-mail.outlook.com"
        assert C.CustomSMTPConnector.default_host is None

    def test_port_465_selects_implicit_ssl(self):
        """Getting this backwards hangs rather than erroring."""
        settings = build(
            C.CustomSMTPConnector,
            auth_data={"host": "smtp.example.com", "port": "465", "username": "a@b.co"},
        )._settings()
        assert settings["use_ssl"] is True
        assert settings["use_tls"] is False

    def test_port_587_selects_starttls(self):
        settings = build(
            C.CustomSMTPConnector,
            auth_data={"host": "smtp.example.com", "port": "587", "username": "a@b.co"},
        )._settings()
        assert settings["use_ssl"] is False
        assert settings["use_tls"] is True

    def test_the_port_arrives_as_a_string_from_the_form(self):
        settings = build(
            C.GmailSMTPConnector, auth_data={"username": "a@b.co", "port": "587"}
        )._settings()
        assert settings["port"] == 587

    def test_a_non_numeric_port_is_an_actionable_error(self):
        with pytest.raises(ConnectorError, match="is not a number"):
            build(
                C.GmailSMTPConnector, auth_data={"username": "a@b.co", "port": "abc"}
            )._settings()

    def test_the_sender_defaults_to_the_username(self):
        settings = build(
            C.GmailSMTPConnector, auth_data={"username": "me@gmail.com"}
        )._settings()
        assert settings["from_email"] == "me@gmail.com"

    def test_a_custom_server_without_a_host_says_so(self):
        with pytest.raises(ConnectorError, match="No SMTP host"):
            build(C.CustomSMTPConnector, auth_data={"username": "a@b.co"})._settings()


class TestSMTPRecipientParsing:
    """An agent asked to "send it to me and my assistant" produces a list."""

    def test_a_comma_separated_list_is_split(self):
        assert SMTPConnector._parse_addresses(
            "a@b.co, c@d.co", field="to_email"
        ) == ["a@b.co", "c@d.co"]

    def test_semicolons_work_too(self):
        assert SMTPConnector._parse_addresses(
            "a@b.co; c@d.co", field="to_email"
        ) == ["a@b.co", "c@d.co"]

    def test_display_names_are_stripped_to_the_address(self):
        assert SMTPConnector._parse_addresses(
            "Sajid <sajid@example.com>", field="to_email"
        ) == ["sajid@example.com"]

    def test_a_malformed_address_names_itself(self):
        with pytest.raises(ConnectorError, match="not-an-email"):
            SMTPConnector._parse_addresses("not-an-email", field="to_email")
