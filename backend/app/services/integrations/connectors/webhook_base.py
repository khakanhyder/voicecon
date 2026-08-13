"""
Outbound webhook connectors.

Zapier, Make and Microsoft Teams all reduce to the same thing: the user pastes
a URL their side generated, and we POST JSON to it. There is no API to browse,
no token to refresh, no resources to list.

That is also why they are *not* OAuth, despite Zapier being seeded as ``oauth2``
originally. An OAuth connector cannot be used at all until the platform owner
registers an app and sets client credentials; a webhook works the moment the
user pastes the URL. For a "connect this to your automation" tile, waiting on
an admin is the wrong trade.

The URL is the credential — it is unguessable and possession of it is authority
to post — so it is stored encrypted in ``api_key`` like any other secret, and
never logged.
"""
import logging
from typing import Any, Dict, Optional

import httpx

from app.services.integrations.connector_base import BaseConnector, ConnectorError

logger = logging.getLogger(__name__)


class WebhookConnector(BaseConnector):
    """POST a JSON payload to a user-supplied URL."""

    provider_label = "Webhook"

    #: Hosts a valid URL for this provider must end with. Empty means any host
    #: is acceptable. This is a typo guard, not a security boundary: pasting a
    #: Slack URL into the Zapier tile should fail at setup, not silently post
    #: call data somewhere unintended.
    allowed_host_suffixes: tuple = ()

    def _webhook_url(self) -> str:
        url = self.credential_manager.decrypt(self.connection.api_key_encrypted or "")
        if not url:
            raise ConnectorError(
                f"No {self.provider_label} webhook URL is stored on this connection."
            )
        if not url.startswith("https://"):
            raise ConnectorError(
                f"{self.provider_label} webhook URLs must be https — refusing to "
                f"send call data over plaintext."
            )
        if self.allowed_host_suffixes:
            host = url.split("//", 1)[-1].split("/", 1)[0].lower()
            if not host.endswith(self.allowed_host_suffixes):
                raise ConnectorError(
                    f"That does not look like a {self.provider_label} webhook URL "
                    f"(host '{host}'). Expected one of: "
                    f"{', '.join(self.allowed_host_suffixes)}."
                )
        return url

    def _build_payload(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Hook for providers whose body has a required shape (e.g. Teams)."""
        return data

    async def _post(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        url = self._webhook_url()
        try:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=False) as client:
                response = await client.post(url, json=payload)
        except httpx.HTTPError as exc:
            raise ConnectorError(
                f"{self.provider_label} webhook request failed: {exc}"
            ) from exc

        if response.status_code >= 400:
            # Deliberately does not include the URL: it is the credential, and
            # this string ends up in workflow logs the user can read and share.
            raise ConnectorError(
                f"{self.provider_label} webhook returned "
                f"{response.status_code}: {response.text[:300]}"
            )

        raw = response.text
        body: Any
        try:
            body = response.json()
        except ValueError:
            # Teams answers a bare "1", Zapier answers JSON. Neither is wrong.
            body = raw[:300]

        problem = self._reject_reason(response.status_code, raw)
        if problem:
            raise ConnectorError(problem)

        return {"success": True, "status_code": response.status_code, "response": body}

    def _reject_reason(self, status_code: int, body: str) -> Optional[str]:
        """Why this 2xx response should still be treated as a failure, if it should.

        Overridden by providers whose front door answers 200 for URLs that do
        not actually route anywhere. Returning None means the response is good.
        """
        return None

    async def test_connection(self) -> Dict[str, Any]:
        """Send a labelled test payload.

        A GET or HEAD would be gentler, but Zapier and Make both answer those
        with an error even for a perfectly good hook, and both platforms expect
        a sample POST during setup in order to learn the payload shape. So the
        honest test is the real thing, marked as a test.
        """
        try:
            result = await self._post(
                self._build_payload(
                    {
                        "test": True,
                        "source": "voicecon",
                        "message": f"Voicecon {self.provider_label} connection test",
                    }
                )
            )
            return {
                "success": True,
                "message": f"{self.provider_label} webhook accepted the test payload",
                "details": {"status_code": result["status_code"]},
            }
        except Exception as exc:  # noqa: BLE001
            return {
                "success": False,
                "message": f"Connection test failed: {exc}",
                "details": {},
            }

    async def send_webhook(
        self,
        data: Optional[Dict[str, Any]] = None,
        event: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Send an arbitrary JSON payload."""
        payload: Dict[str, Any] = dict(data or {})
        if event:
            payload.setdefault("event", event)
        if not payload:
            raise ConnectorError("send_webhook was called with an empty payload")
        return await self._post(self._build_payload(payload))
