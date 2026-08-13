"""
Cloudflare R2 Connector.

Zero-egress object storage. Speaks the S3 API, so it reuses the S3 connector
wholesale and only supplies its account-scoped endpoint.
"""
import logging
from typing import Optional

from app.services.integrations.connector_base import ConnectorError
from app.services.integrations.connectors.object_storage_base import (
    ObjectStorageConnector,
)

logger = logging.getLogger(__name__)


class CloudflareR2Connector(ObjectStorageConnector):
    """Cloudflare R2.

    R2's endpoint is per-account — ``https://<account_id>.r2.cloudflarestorage.com``
    — so the account id is a required setup field rather than something that
    can be seeded once for everybody.
    """

    default_region = "auto"
    provider_label = "Cloudflare R2"

    def _endpoint_url(self) -> Optional[str]:
        account_id = self._credentials().get("account_id")
        if not account_id:
            raise ConnectorError(
                "Cloudflare R2 needs the Account ID from your Cloudflare "
                "dashboard — the endpoint is account-specific."
            )
        return f"https://{account_id}.r2.cloudflarestorage.com"
