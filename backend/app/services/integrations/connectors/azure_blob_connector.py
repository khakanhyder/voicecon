"""
Azure Blob Storage Connector.

The one storage provider that is not S3-compatible, so it carries its own
authentication.

Two credential styles, because Azure users genuinely have both:

* **SAS token** (preferred, and what the setup form asks for first) — a signed
  query string scoped to one container with an expiry. Requests just carry it;
  nothing to sign here.
* **Account key** — full access to the whole storage account, signed per
  request with Shared Key. Supported because plenty of accounts only hand these
  out, but it is the bigger blast radius of the two and the setup copy says so.
"""
import base64
import hashlib
import hmac
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import quote, urlencode
from xml.etree import ElementTree

import httpx

from app.services.integrations.connector_base import BaseConnector, ConnectorError

logger = logging.getLogger(__name__)

MAX_FETCH_BYTES = 256 * 1024 * 1024
API_VERSION = "2021-08-06"


class AzureBlobConnector(BaseConnector):
    """Azure Blob Storage over the REST API."""

    provider_label = "Azure Blob Storage"

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    def _settings(self) -> Dict[str, Any]:
        auth = self.get_auth_data()
        secret = self.credential_manager.decrypt(
            self.connection.api_key_encrypted or ""
        )
        account = auth.get("account_name")
        # The connection's host was normalised at connect time; fall back to
        # deriving it from the account name.
        base = (self.connection.config or {}).get("base_url") or (
            f"https://{account}.blob.core.windows.net" if account else None
        )
        if not base:
            raise ConnectorError(
                "Azure Blob needs the storage account name (or its full "
                "https://<account>.blob.core.windows.net URL)."
            )
        if not account:
            # Recover the account from the host so Shared Key signing, which
            # needs it by name, still works.
            account = base.split("//", 1)[-1].split(".", 1)[0]

        # Which credential style this is, decided by the shape of the secret
        # rather than by which form field it arrived in. A SAS token is a query
        # string and always carries a signature parameter; an account key is
        # base64 and never does. Sniffing the value means a user who pastes a
        # SAS into the "account key" box still gets a working connection
        # instead of a 403 they cannot interpret.
        candidate = (auth.get("sas_token") or secret or "").strip()
        is_sas = "sig=" in candidate and ("sv=" in candidate or "se=" in candidate)

        return {
            "account": account,
            "base_url": base.rstrip("/"),
            "container": auth.get("container") or auth.get("container_name"),
            "sas_token": candidate.lstrip("?") if is_sas else "",
            "account_key": "" if is_sas else candidate,
        }

    def _container(self, override: Optional[str] = None) -> str:
        container = override or self._settings().get("container")
        if not container:
            raise ConnectorError(
                "No container configured for this Azure Blob connection. Set "
                "one when connecting, or pass container on the action."
            )
        return container

    # ------------------------------------------------------------------
    # Shared Key signing
    # ------------------------------------------------------------------

    def _sign(
        self,
        method: str,
        path: str,
        query: Dict[str, str],
        headers: Dict[str, str],
        content_length: int,
    ) -> str:
        """Build the ``SharedKey`` Authorization header.

        The string-to-sign is positional: every field is present, in this exact
        order, empty when unused. A single missing newline produces a 403 that
        is indistinguishable from a wrong key, which is why this is written out
        line by line rather than assembled cleverly.
        """
        settings = self._settings()

        canonical_headers = "".join(
            f"{name.lower()}:{value.strip()}\n"
            for name, value in sorted(headers.items())
            if name.lower().startswith("x-ms-")
        )
        canonical_resource = f"/{settings['account']}/{path.lstrip('/')}"
        for key in sorted(query):
            canonical_resource += f"\n{key.lower()}:{query[key]}"

        string_to_sign = "\n".join(
            [
                method.upper(),
                "",                                     # Content-Encoding
                "",                                     # Content-Language
                str(content_length) if content_length else "",
                "",                                     # Content-MD5
                headers.get("Content-Type", ""),
                "",                                     # Date (using x-ms-date)
                "",                                     # If-Modified-Since
                "",                                     # If-Match
                "",                                     # If-None-Match
                "",                                     # If-Unmodified-Since
                "",                                     # Range
                canonical_headers + canonical_resource,
            ]
        )

        try:
            key = base64.b64decode(settings["account_key"])
        except Exception as exc:  # noqa: BLE001
            raise ConnectorError(
                f"The Azure account key is not valid base64: {exc}"
            ) from exc

        signature = base64.b64encode(
            hmac.new(key, string_to_sign.encode("utf-8"), hashlib.sha256).digest()
        ).decode()
        return f"SharedKey {settings['account']}:{signature}"

    async def _request(
        self,
        method: str,
        path: str,
        query: Optional[Dict[str, str]] = None,
        body: Optional[bytes] = None,
        content_type: Optional[str] = None,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> httpx.Response:
        settings = self._settings()
        query = dict(query or {})

        headers = {
            "x-ms-version": API_VERSION,
            "x-ms-date": datetime.now(timezone.utc).strftime(
                "%a, %d %b %Y %H:%M:%S GMT"
            ),
        }
        if content_type:
            headers["Content-Type"] = content_type
        if extra_headers:
            headers.update(extra_headers)

        if settings["sas_token"]:
            # A SAS token already carries its own signature; adding a Shared
            # Key header on top makes Azure reject the request outright.
            url = f"{settings['base_url']}/{path.lstrip('/')}"
            merged = urlencode(query) if query else ""
            suffix = "&".join(part for part in (merged, settings["sas_token"]) if part)
            if suffix:
                url = f"{url}?{suffix}"
        elif settings["account_key"]:
            headers["Authorization"] = self._sign(
                method, path, query, headers, len(body or b"")
            )
            url = f"{settings['base_url']}/{path.lstrip('/')}"
            if query:
                url = f"{url}?{urlencode(query)}"
        else:
            raise ConnectorError(
                "Azure Blob needs either a SAS token or an account key."
            )

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.request(
                method, url, headers=headers, content=body
            )

        if response.status_code >= 400:
            raise ConnectorError(
                f"Azure Blob {method} {path} failed with "
                f"{response.status_code}: {response.text[:400]}"
            )
        return response

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    async def test_connection(self) -> Dict[str, Any]:
        try:
            settings = self._settings()
            container = settings.get("container")
            if container:
                await self._request(
                    "GET",
                    container,
                    query={"restype": "container", "comp": "list", "maxresults": "1"},
                )
                details = {"account": settings["account"], "container": container}
            else:
                await self._request("GET", "", query={"comp": "list"})
                details = {"account": settings["account"]}

            return {
                "success": True,
                "message": "Azure Blob Storage connection successful",
                "details": details,
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
        container: Optional[str] = None,
        content_type: str = "text/plain",
    ) -> Dict[str, Any]:
        target = self._container(container)
        body = content.encode("utf-8")
        await self._request(
            "PUT",
            f"{target}/{quote(key)}",
            body=body,
            content_type=content_type,
            extra_headers={"x-ms-blob-type": "BlockBlob"},
        )
        logger.info(f"Azure Blob: stored {target}/{key}")
        return {"success": True, "container": target, "key": key, "size": len(body)}

    async def upload_from_url(
        self,
        key: str,
        source_url: str,
        container: Optional[str] = None,
        content_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        target = self._container(container)

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
                    f"{MAX_FETCH_BYTES} byte upload limit"
                )
            resolved = (
                content_type
                or response.headers.get("content-type")
                or "application/octet-stream"
            )

        await self._request(
            "PUT",
            f"{target}/{quote(key)}",
            body=body,
            content_type=resolved,
            extra_headers={"x-ms-blob-type": "BlockBlob"},
        )
        logger.info(f"Azure Blob: copied {source_url} to {target}/{key}")
        return {
            "success": True,
            "container": target,
            "key": key,
            "size": len(body),
            "content_type": resolved,
        }

    async def list_objects(
        self,
        prefix: str = "",
        container: Optional[str] = None,
        limit: int = 100,
    ) -> Dict[str, Any]:
        target = self._container(container)
        query = {
            "restype": "container",
            "comp": "list",
            "maxresults": str(max(1, min(int(limit), 5000))),
        }
        if prefix:
            query["prefix"] = prefix

        response = await self._request("GET", target, query=query)

        # The list API answers XML, not JSON — the one place Azure's REST
        # surface diverges from everything else this codebase talks to.
        try:
            root = ElementTree.fromstring(response.text)
        except ElementTree.ParseError as exc:
            raise ConnectorError(f"Azure returned unparseable XML: {exc}") from exc

        objects: List[Dict[str, Any]] = []
        for blob in root.findall(".//Blob"):
            properties = blob.find("Properties")
            objects.append(
                {
                    "key": blob.findtext("Name"),
                    "size": int(properties.findtext("Content-Length") or 0)
                    if properties is not None
                    else None,
                    "last_modified": properties.findtext("Last-Modified")
                    if properties is not None
                    else None,
                }
            )

        return {"success": True, "container": target, "objects": objects,
                "count": len(objects)}

    async def delete_object(
        self, key: str, container: Optional[str] = None
    ) -> Dict[str, Any]:
        target = self._container(container)
        await self._request("DELETE", f"{target}/{quote(key)}")
        logger.info(f"Azure Blob: deleted {target}/{key}")
        return {"success": True, "container": target, "key": key}

    async def generate_presigned_url(
        self,
        key: str,
        container: Optional[str] = None,
        expires_in: int = 3600,
    ) -> Dict[str, Any]:
        """A read-only, time-limited link to one blob.

        With a SAS connection the stored token is already exactly that, so it is
        reused. With an account key a fresh service SAS is minted, scoped to the
        single blob rather than the container.
        """
        settings = self._settings()
        target = self._container(container)
        ttl = max(60, min(int(expires_in), 7 * 24 * 3600))
        blob_path = f"{target}/{quote(key)}"

        if settings["sas_token"]:
            return {
                "success": True,
                "url": f"{settings['base_url']}/{blob_path}?{settings['sas_token']}",
                "container": target,
                "key": key,
                # The link inherits the stored token's expiry, which the user
                # set on Azure's side; claiming our own ttl here would be a lie.
                "expires_in": None,
            }

        if not settings["account_key"]:
            raise ConnectorError(
                "Generating a link needs either a SAS token or an account key."
            )

        expiry = (datetime.now(timezone.utc) + timedelta(seconds=ttl)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        start = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        signed = {
            "sp": "r",
            "st": start,
            "se": expiry,
            "sv": API_VERSION,
            "sr": "b",
        }
        # Service SAS string-to-sign, in Azure's fixed field order.
        string_to_sign = "\n".join(
            [
                signed["sp"],
                signed["st"],
                signed["se"],
                f"/blob/{settings['account']}/{target}/{key}",
                "",                       # identifier
                "",                       # IP range
                "",                       # protocol
                signed["sv"],
                signed["sr"],
                "", "", "", "", "", "", "",
            ]
        )
        signature = base64.b64encode(
            hmac.new(
                base64.b64decode(settings["account_key"]),
                string_to_sign.encode("utf-8"),
                hashlib.sha256,
            ).digest()
        ).decode()

        token = urlencode({**signed, "sig": signature})
        return {
            "success": True,
            "url": f"{settings['base_url']}/{blob_path}?{token}",
            "container": target,
            "key": key,
            "expires_in": ttl,
        }
