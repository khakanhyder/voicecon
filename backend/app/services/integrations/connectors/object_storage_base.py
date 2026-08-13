"""
Object storage connectors (S3-compatible).

One implementation behind four tiles. AWS S3, Cloudflare R2 and Google Cloud
Storage all speak the S3 API and authenticate with SigV4 over an access-key
pair; only the endpoint and region differ, so they are subclasses that supply
those two things rather than three separate connectors.

Azure Blob is not S3-compatible and lives in its own module.

Why boto3 rather than the shared IntegrationHTTPClient: S3 authentication is a
per-request signature over the canonicalised method, path, query, headers and
payload hash. That is not something to hand-roll — a subtly wrong signature
fails as 403 SignatureDoesNotMatch, which reads exactly like a bad credential.
botocore already does it correctly and is already a dependency. The client is
synchronous, so every call is pushed to a worker thread; the alternative is
blocking the event loop that is also carrying live calls.
"""
import asyncio
import logging
from typing import Any, Dict, List, Optional

import httpx

from app.services.integrations.connector_base import BaseConnector, ConnectorError

logger = logging.getLogger(__name__)

#: Refuse to stream an unbounded remote file into memory. Call recordings are
#: single-digit MB; anything past this is a misconfiguration, not a recording.
MAX_FETCH_BYTES = 256 * 1024 * 1024


class ObjectStorageConnector(BaseConnector):
    """Shared behaviour for every S3-compatible provider.

    Subclasses supply :meth:`_endpoint_url` and :attr:`default_region`.

    Credentials arrive as: the secret access key in ``api_key`` (it is the
    actual secret), everything else — key id, bucket, region, account id — in
    the connection's additional fields.
    """

    #: S3 requires a region in the signature. The non-AWS providers ignore the
    #: value but still demand one be present; "auto" is what they document.
    default_region: str = "auto"

    #: Shown in error messages so a misconfigured connection names itself.
    provider_label: str = "object storage"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._client = None

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    def _endpoint_url(self) -> Optional[str]:
        """Provider endpoint, or None to use botocore's AWS default."""
        return None

    def _credentials(self) -> Dict[str, Any]:
        auth = self.get_auth_data()
        secret = self.credential_manager.decrypt(self.connection.api_key_encrypted or "")
        return {
            "access_key_id": auth.get("access_key_id") or auth.get("aws_access_key_id"),
            "secret_access_key": secret,
            "region": auth.get("region") or self.default_region,
            "bucket": auth.get("bucket") or auth.get("bucket_name"),
            "account_id": auth.get("account_id"),
        }

    def _bucket(self, override: Optional[str] = None) -> str:
        bucket = override or self._credentials().get("bucket")
        if not bucket:
            raise ConnectorError(
                f"No bucket configured for this {self.provider_label} connection. "
                f"Set one when connecting, or pass bucket on the action."
            )
        return bucket

    def _get_client(self):
        """Build the botocore client once per connector instance."""
        if self._client is not None:
            return self._client

        try:
            import boto3
            from botocore.config import Config
        except ImportError as exc:  # pragma: no cover - boto3 is a dependency
            raise ConnectorError(f"boto3 is required for {self.provider_label}: {exc}")

        creds = self._credentials()
        if not creds["access_key_id"] or not creds["secret_access_key"]:
            raise ConnectorError(
                f"{self.provider_label} needs both an access key ID and a secret "
                f"access key on the connection."
            )

        self._client = boto3.client(
            "s3",
            endpoint_url=self._endpoint_url(),
            aws_access_key_id=creds["access_key_id"],
            aws_secret_access_key=creds["secret_access_key"],
            region_name=creds["region"],
            config=Config(
                signature_version="s3v4",
                retries={"max_attempts": 3, "mode": "standard"},
                connect_timeout=15,
                read_timeout=60,
            ),
        )
        return self._client

    async def _call(self, operation: str, **kwargs) -> Dict[str, Any]:
        """Run one blocking botocore call off the event loop."""
        client = self._get_client()
        method = getattr(client, operation)
        try:
            return await asyncio.to_thread(lambda: method(**kwargs))
        except Exception as exc:  # noqa: BLE001 - botocore raises many types
            raise ConnectorError(
                f"{self.provider_label} {operation} failed: {exc}"
            ) from exc

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    async def test_connection(self) -> Dict[str, Any]:
        """Verify the credentials, and the bucket if one was configured.

        Listing the bucket rather than listing *all* buckets is deliberate:
        scoped keys — which is what a careful user creates — are typically
        denied ListAllMyBuckets while having full access to the one bucket they
        are for. Testing with the broad call would reject exactly the
        credentials we most want people to use.
        """
        creds = self._credentials()
        try:
            if creds.get("bucket"):
                await self._call(
                    "list_objects_v2", Bucket=creds["bucket"], MaxKeys=1
                )
                return {
                    "success": True,
                    "message": f"{self.provider_label} connection successful",
                    "details": {"bucket": creds["bucket"], "region": creds["region"]},
                }

            result = await self._call("list_buckets")
            return {
                "success": True,
                "message": f"{self.provider_label} connection successful",
                "details": {
                    "buckets": [b["Name"] for b in result.get("Buckets", [])][:25]
                },
            }
        except Exception as exc:  # noqa: BLE001
            return {
                "success": False,
                "message": f"Connection test failed: {exc}",
                "details": {},
            }

    async def upload_text(
        self,
        key: str,
        content: str,
        bucket: Optional[str] = None,
        content_type: str = "text/plain",
    ) -> Dict[str, Any]:
        """Store a transcript, summary or note as an object."""
        target = self._bucket(bucket)
        await self._call(
            "put_object",
            Bucket=target,
            Key=key,
            Body=content.encode("utf-8"),
            ContentType=content_type,
        )
        logger.info(f"{self.provider_label}: stored {target}/{key}")
        return {"success": True, "bucket": target, "key": key, "size": len(content)}

    async def upload_from_url(
        self,
        key: str,
        source_url: str,
        bucket: Optional[str] = None,
        content_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Copy a remote file — normally a call recording — into the bucket."""
        target = self._bucket(bucket)

        async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
            try:
                response = await client.get(source_url)
                response.raise_for_status()
            except httpx.HTTPError as exc:
                raise ConnectorError(f"Could not fetch {source_url}: {exc}") from exc

            body = response.content
            if len(body) > MAX_FETCH_BYTES:
                raise ConnectorError(
                    f"{source_url} is {len(body)} bytes, over the "
                    f"{MAX_FETCH_BYTES} byte limit for a single upload"
                )
            resolved_type = (
                content_type
                or response.headers.get("content-type")
                or "application/octet-stream"
            )

        await self._call(
            "put_object",
            Bucket=target,
            Key=key,
            Body=body,
            ContentType=resolved_type,
        )
        logger.info(f"{self.provider_label}: copied {source_url} to {target}/{key}")
        return {
            "success": True,
            "bucket": target,
            "key": key,
            "size": len(body),
            "content_type": resolved_type,
        }

    async def list_objects(
        self,
        prefix: str = "",
        bucket: Optional[str] = None,
        limit: int = 100,
    ) -> Dict[str, Any]:
        target = self._bucket(bucket)
        result = await self._call(
            "list_objects_v2",
            Bucket=target,
            Prefix=prefix,
            MaxKeys=max(1, min(int(limit), 1000)),
        )
        objects: List[Dict[str, Any]] = [
            {
                "key": item["Key"],
                "size": item.get("Size"),
                # botocore returns datetimes; the result is serialised to JSON
                # for the workflow log, which cannot take them raw.
                "last_modified": item["LastModified"].isoformat()
                if item.get("LastModified")
                else None,
            }
            for item in result.get("Contents", [])
        ]
        return {"success": True, "bucket": target, "objects": objects,
                "count": len(objects)}

    async def delete_object(
        self, key: str, bucket: Optional[str] = None
    ) -> Dict[str, Any]:
        target = self._bucket(bucket)
        await self._call("delete_object", Bucket=target, Key=key)
        logger.info(f"{self.provider_label}: deleted {target}/{key}")
        return {"success": True, "bucket": target, "key": key}

    async def generate_presigned_url(
        self,
        key: str,
        bucket: Optional[str] = None,
        expires_in: int = 3600,
    ) -> Dict[str, Any]:
        """A time-limited link, so a recording can be shared without opening
        the bucket to the world."""
        target = self._bucket(bucket)
        client = self._get_client()
        # Clamp to a week: S3 rejects longer, and an effectively permanent link
        # defeats the point of presigning.
        ttl = max(60, min(int(expires_in), 7 * 24 * 3600))
        try:
            url = await asyncio.to_thread(
                lambda: client.generate_presigned_url(
                    "get_object",
                    Params={"Bucket": target, "Key": key},
                    ExpiresIn=ttl,
                )
            )
        except Exception as exc:  # noqa: BLE001
            raise ConnectorError(f"Could not presign {target}/{key}: {exc}") from exc

        return {"success": True, "url": url, "bucket": target, "key": key,
                "expires_in": ttl}
