"""
AWS S3 Connector.

Store call recordings, transcripts and artifacts in Amazon S3.
"""
import logging
from typing import Optional

from app.services.integrations.connectors.object_storage_base import (
    ObjectStorageConnector,
)

logger = logging.getLogger(__name__)


class AWSS3Connector(ObjectStorageConnector):
    """Amazon S3.

    The only S3-compatible provider that wants a real region: the region is
    part of the SigV4 credential scope, and a bucket in eu-west-1 signed for
    us-east-1 is rejected. Defaulting to us-east-1 rather than "auto" for that
    reason — "auto" is a Cloudflare/Google convention S3 itself rejects.
    """

    default_region = "us-east-1"
    provider_label = "AWS S3"

    def _endpoint_url(self) -> Optional[str]:
        # None lets botocore build the regional endpoint itself, which also
        # gets virtual-host addressing and dualstack right.
        return None
