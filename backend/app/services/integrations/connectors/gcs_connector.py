"""
Google Cloud Storage Connector.

Uses GCS's S3-compatible XML API with interoperability (HMAC) keys, so it
shares the S3 implementation rather than pulling in a second auth stack.

Why HMAC keys and not a service-account JSON: the JSON API would need the
google-auth signing flow, a second credential format, and a private key stored
per connection. GCS ships interoperability keys precisely so S3 tooling works
unchanged, and it keeps all four storage tiles on one code path — one place for
a bug to be found and fixed.
"""
import logging
from typing import Optional

from app.services.integrations.connectors.object_storage_base import (
    ObjectStorageConnector,
)

logger = logging.getLogger(__name__)


class GCSConnector(ObjectStorageConnector):
    """Google Cloud Storage over the S3-compatible endpoint."""

    default_region = "auto"
    provider_label = "Google Cloud Storage"

    def _endpoint_url(self) -> Optional[str]:
        return "https://storage.googleapis.com"
