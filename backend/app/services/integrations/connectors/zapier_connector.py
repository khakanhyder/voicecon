"""
Zapier Connector.

Posts to a Zapier "Catch Hook" trigger URL, which puts every one of Zapier's
several-thousand app integrations one step downstream of a Voicecon workflow.
"""
import logging

from app.services.integrations.connectors.webhook_base import WebhookConnector

logger = logging.getLogger(__name__)


class ZapierConnector(WebhookConnector):
    """Zapier Catch Hook."""

    provider_label = "Zapier"
    allowed_host_suffixes = ("hooks.zapier.com",)
