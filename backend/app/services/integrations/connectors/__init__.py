"""
Integration Connectors.

Concrete implementations of integration connectors.
"""
from app.services.integrations.connectors.salesforce_connector import SalesforceConnector
from app.services.integrations.connectors.sendgrid_connector import SendGridConnector
from app.services.integrations.connectors.hubspot_connector import HubSpotConnector
from app.services.integrations.connectors.google_calendar_connector import GoogleCalendarConnector
from app.services.integrations.connectors.slack_connector import SlackConnector
from app.services.integrations.connectors.stripe_connector import StripeConnector
from app.services.integrations.connectors.notion_connector import NotionConnector
from app.services.integrations.connectors.clickup_connector import ClickUpConnector
from app.services.integrations.connectors.trello_connector import TrelloConnector
from app.services.integrations.connectors.whatsapp_connector import WhatsAppConnector
from app.services.integrations.connectors.airtable_connector import AirtableConnector
from app.services.integrations.connectors.gohighlevel_connector import GoHighLevelConnector
from app.services.integrations.connectors.twilio_connector import TwilioConnector
from app.services.integrations.connectors.langfuse_connector import LangfuseConnector
from app.services.integrations.connectors.calendly_connector import CalendlyConnector
from app.services.integrations.connectors.google_sheets_connector import GoogleSheetsConnector
from app.services.integrations.connectors.google_drive_connector import GoogleDriveConnector
from app.services.integrations.connectors.cal_com_connector import CalComConnector
from app.services.integrations.connectors.monday_connector import MondayConnector
from app.services.integrations.connectors.vonage_connector import VonageConnector
from app.services.integrations.connectors.telnyx_connector import TelnyxConnector
from app.services.integrations.connectors.supabase_connector import SupabaseConnector

# ── Object storage (S3-compatible family + Azure) ────────────────────────────
from app.services.integrations.connectors.aws_s3_connector import AWSS3Connector
from app.services.integrations.connectors.cloudflare_r2_connector import CloudflareR2Connector
from app.services.integrations.connectors.gcs_connector import GCSConnector
from app.services.integrations.connectors.azure_blob_connector import AzureBlobConnector

# ── Outbound webhooks ────────────────────────────────────────────────────────
from app.services.integrations.connectors.zapier_connector import ZapierConnector
from app.services.integrations.connectors.make_connector import MakeConnector
from app.services.integrations.connectors.microsoft_teams_connector import MicrosoftTeamsConnector

# ── SMTP email ───────────────────────────────────────────────────────────────
from app.services.integrations.connectors.smtp_connector import (
    GmailSMTPConnector,
    OutlookSMTPConnector,
    CustomSMTPConnector,
)

# ── CRM / support ────────────────────────────────────────────────────────────
from app.services.integrations.connectors.pipedrive_connector import PipedriveConnector
from app.services.integrations.connectors.zendesk_connector import ZendeskConnector
from app.services.integrations.connectors.intercom_connector import IntercomConnector

__all__ = [
    "SalesforceConnector",
    "SendGridConnector",
    "HubSpotConnector",
    "GoogleCalendarConnector",
    "SlackConnector",
    "StripeConnector",
    "NotionConnector",
    "ClickUpConnector",
    "TrelloConnector",
    "WhatsAppConnector",
    "AirtableConnector",
    "GoHighLevelConnector",
    "TwilioConnector",
    "LangfuseConnector",
    "CalendlyConnector",
    "GoogleSheetsConnector",
    "GoogleDriveConnector",
    "CalComConnector",
    "MondayConnector",
    "VonageConnector",
    "TelnyxConnector",
    "SupabaseConnector",
    "AWSS3Connector",
    "CloudflareR2Connector",
    "GCSConnector",
    "AzureBlobConnector",
    "ZapierConnector",
    "MakeConnector",
    "MicrosoftTeamsConnector",
    "GmailSMTPConnector",
    "OutlookSMTPConnector",
    "CustomSMTPConnector",
    "PipedriveConnector",
    "ZendeskConnector",
    "IntercomConnector",
]
