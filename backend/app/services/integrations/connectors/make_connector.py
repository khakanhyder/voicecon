"""
Make (Integromat) Connector.

Posts to a Make scenario's Custom Webhook URL.
"""
import logging

from app.services.integrations.connectors.webhook_base import WebhookConnector

logger = logging.getLogger(__name__)


class MakeConnector(WebhookConnector):
    """Make custom webhook.

    Make's webhook host is region-specific — hook.eu1, hook.eu2, hook.us1 and
    so on — which is why the whole URL is stored per connection rather than a
    path against one seeded host.
    """

    provider_label = "Make"
    allowed_host_suffixes = ("make.com", "integromat.com")
