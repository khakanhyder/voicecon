"""
Microsoft Teams Connector.

Posts to a channel's Incoming Webhook.

Why a webhook rather than Graph: posting to a channel through Graph needs an
Azure AD app registration, admin consent for ChannelMessage.Send, and a tenant
admin willing to grant it — none of which a user setting up a voice agent can
do for themselves. An Incoming Webhook is created by the channel owner in a few
clicks and needs nothing from us. For "tell my team when something happens on a
call", that is the whole requirement.
"""
import logging
from typing import Any, Dict, Optional

from app.services.integrations.connector_base import ConnectorError
from app.services.integrations.connectors.webhook_base import WebhookConnector

logger = logging.getLogger(__name__)


class MicrosoftTeamsConnector(WebhookConnector):
    """Microsoft Teams Incoming Webhook."""

    provider_label = "Microsoft Teams"
    allowed_host_suffixes = (
        "webhook.office.com",
        "office.com",
        "logic.azure.com",           # Power Automate "Workflows" replacement
        "azure.com",
    )

    def _reject_reason(self, status_code: int, body: str) -> Optional[str]:
        """Teams answers 200 for URLs that route nowhere.

        Microsoft's edge (``Microsoft-HTTPAPI``) accepts a POST to any path
        under ``*.webhook.office.com`` and returns **200 with an empty body**. A
        webhook that actually exists returns the body ``1``. Trusting the status
        code alone therefore reports a mistyped or revoked URL as Connected, and
        every later notification vanishes silently — the worst version of this
        bug, because nothing ever surfaces an error.

        So an empty body is treated as a failure. Anything Teams says explicitly
        is passed through; only silence is rejected.
        """
        if status_code == 200 and not body.strip():
            return (
                "Teams accepted the request but did not acknowledge it, which "
                "means this URL does not point at a live Incoming Webhook. "
                "Check the URL was copied whole, and that the webhook still "
                "exists in the channel's connector settings."
            )
        return None

    def _build_payload(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Wrap a plain payload in the MessageCard shape Teams requires.

        Teams rejects arbitrary JSON — a bare {"foo": "bar"} is a 400. Anything
        that already declares a card type is passed through untouched so a
        caller can send a hand-built Adaptive Card.
        """
        if "@type" in data or "type" in data or "attachments" in data:
            return data

        text = data.get("text") or data.get("message")
        if not text:
            # Nothing message-shaped: render the payload so the post still
            # carries its information rather than failing or arriving blank.
            text = "\n".join(f"**{k}:** {v}" for k, v in data.items())

        card: Dict[str, Any] = {
            "@type": "MessageCard",
            "@context": "https://schema.org/extensions",
            "text": text,
        }
        title = data.get("title")
        if title:
            card["title"] = title
            card["summary"] = title
        else:
            # Teams drops a card with neither summary nor title.
            card["summary"] = "Voicecon notification"
        return card

    async def send_message(
        self, message: str, title: Optional[str] = None
    ) -> Dict[str, Any]:
        """Post a message to the connected Teams channel."""
        if not message:
            raise ConnectorError("send_message needs a message")
        payload: Dict[str, Any] = {"text": message}
        if title:
            payload["title"] = title
        return await self._post(self._build_payload(payload))
