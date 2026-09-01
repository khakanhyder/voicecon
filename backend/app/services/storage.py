"""
Where uploaded user files live.

One abstraction over two backends, chosen by configuration rather than by code:

* **S3** (or any S3-compatible store — Cloudflare R2, DigitalOcean Spaces,
  MinIO) when ``AWS_S3_BUCKET`` and credentials are set. This is what production
  should use. Container filesystems on a PaaS are ephemeral: a redeploy wipes
  them, and with more than one replica an avatar uploaded to container A is a
  404 from container B.
* **Local disk** otherwise, under ``backend/uploads/``, served by the same
  ``StaticFiles`` mount pattern the call recordings already use. This keeps
  development working with no cloud account, and is survivable for a
  single-container deployment *provided the directory is a mounted volume*.

Avatars are never stored as the user sent them. Every upload is decoded,
re-encoded and resized, which normalizes the format, drops EXIF (a phone photo
carries GPS coordinates), and neutralises files that are a valid image and a
valid script at the same time.
"""
import io
import logging
import os
import uuid
from typing import Optional, Tuple

from PIL import Image, UnidentifiedImageError

from app.core.config import settings

logger = logging.getLogger(__name__)

#: Formats we accept from the browser. Note SVG is deliberately absent — it is
#: a document format that can carry script, and an avatar rendered from a
#: same-origin URL would run it.
ALLOWED_AVATAR_TYPES = frozenset({"image/jpeg", "image/png", "image/webp", "image/gif"})

#: Cap on the bytes we will read. Avatars are displayed at 40px; anything
#: larger than this is a mistake or an attack, not a portrait.
MAX_AVATAR_BYTES = 5 * 1024 * 1024

#: Longest edge after resizing. Generous enough for retina display at the
#: largest size the UI uses, small enough that the file is a few tens of KB.
AVATAR_MAX_EDGE = 512

#: Guard against a "decompression bomb": a small file that expands to a
#: gigapixel image and exhausts memory during decode.
MAX_AVATAR_PIXELS = 50_000_000


class StorageError(Exception):
    """Raised when a file cannot be accepted or cannot be persisted."""


def _local_root() -> str:
    return os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "uploads")


def s3_enabled() -> bool:
    """True when a bucket and credentials are configured."""
    return bool(
        settings.AWS_S3_BUCKET
        and settings.AWS_ACCESS_KEY_ID
        and settings.AWS_SECRET_ACCESS_KEY
    )


def normalize_avatar(raw: bytes, content_type: Optional[str]) -> Tuple[bytes, str]:
    """
    Validate an uploaded avatar and return ``(webp_bytes, "image/webp")``.

    The declared content type is checked first as a cheap filter, but it is the
    *decode* that decides: a browser will happily send ``image/png`` for a zip
    file, so nothing is trusted until Pillow has parsed it.
    """
    if not raw:
        raise StorageError("The file is empty.")
    if len(raw) > MAX_AVATAR_BYTES:
        raise StorageError(
            f"Image is too large. Choose one under {MAX_AVATAR_BYTES // (1024 * 1024)}MB."
        )
    if content_type and content_type.lower() not in ALLOWED_AVATAR_TYPES:
        raise StorageError("Use a JPEG, PNG, WebP or GIF image.")

    original_limit = Image.MAX_IMAGE_PIXELS
    Image.MAX_IMAGE_PIXELS = MAX_AVATAR_PIXELS
    try:
        image = Image.open(io.BytesIO(raw))
        image.load()
    except Image.DecompressionBombError as exc:
        # Listed before the generic case: it is not an OSError, so without this
        # a bomb escapes as a 500 instead of telling the user the image is too big.
        raise StorageError("That image is too large to process.") from exc
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise StorageError("That file is not a readable image.") from exc
    finally:
        Image.MAX_IMAGE_PIXELS = original_limit

    # Flatten transparency onto white rather than dropping the alpha channel,
    # which would otherwise turn transparent corners black.
    if image.mode in ("RGBA", "LA", "P"):
        image = image.convert("RGBA")
        backdrop = Image.new("RGBA", image.size, (255, 255, 255, 255))
        image = Image.alpha_composite(backdrop, image).convert("RGB")
    else:
        image = image.convert("RGB")

    image.thumbnail((AVATAR_MAX_EDGE, AVATAR_MAX_EDGE), Image.Resampling.LANCZOS)

    out = io.BytesIO()
    # WebP, not PNG. These are photographs, and PNG is lossless: a 512px portrait
    # lands around 240KB as PNG versus ~25KB as WebP, on an image that loads in
    # the header of every page. Universally supported since 2020.
    #
    # save() on a fresh image built from pixels only — no EXIF, no ICC, no
    # trailing bytes from the original file survive this.
    image.save(out, format="WEBP", quality=85, method=6)
    return out.getvalue(), "image/webp"


def _store_s3(key: str, data: bytes, content_type: str) -> str:
    import boto3
    from botocore.config import Config

    client = boto3.client(
        "s3",
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_REGION,
        endpoint_url=settings.AWS_ENDPOINT_URL,
        config=Config(s3={'addressing_style': 'virtual'}),
    )
    client.put_object(
        Bucket=settings.AWS_S3_BUCKET,
        Key=key,
        Body=data,
        ContentType=content_type,
        # Avatars are shown on every page; a long max-age matters. The key
        # contains a fresh uuid on every upload, so a cached copy is never
        # stale — the URL changes instead of the content.
        CacheControl="public, max-age=31536000, immutable",
    )
    if settings.AWS_PUBLIC_URL:
        base = settings.AWS_PUBLIC_URL.rstrip("/")
        return f"{base}/{key}"
    return f"https://{settings.AWS_S3_BUCKET}.s3.{settings.AWS_REGION}.amazonaws.com/{key}"


def _store_local(key: str, data: bytes, public_base: Optional[str]) -> str:
    path = os.path.join(_local_root(), key)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as handle:
        handle.write(data)

    # Absolute, not "/uploads/...". The frontend is served from a different
    # origin than the API (:3000 vs :8001 in development, and separate
    # subdomains in the deployment), so a root-relative URL resolves against
    # the *frontend* and 404s — the image uploads fine and then renders broken.
    base = (public_base or settings.API_BASE_URL or "").rstrip("/")
    return f"{base}/uploads/{key}" if base else f"/uploads/{key}"


def store_avatar(
    user_id: uuid.UUID,
    raw: bytes,
    content_type: Optional[str],
    public_base: Optional[str] = None,
) -> str:
    """
    Validate, normalize and persist an avatar. Returns the URL to serve it from.

    ``public_base`` is this API's own externally-reachable origin, used only by
    the local-disk backend to build an absolute URL. S3 URLs are already
    absolute.
    """
    data, resolved_type = normalize_avatar(raw, content_type)
    # A new name every time, so a replaced avatar is never masked by a cached
    # copy of the old one at the same URL.
    key = f"avatars/{user_id}/{uuid.uuid4().hex}.webp"

    if s3_enabled():
        try:
            return _store_s3(key, data, resolved_type)
        except Exception as exc:  # noqa: BLE001 - surfaced to the caller as 502
            logger.error(f"Could not upload avatar to S3: {exc}")
            raise StorageError("Could not save the image. Please try again.") from exc

    return _store_local(key, data, public_base)


def delete_avatar(url: Optional[str]) -> None:
    """
    Best-effort removal of a previously stored avatar.

    Never raises: a leftover object costs a fraction of a cent, while a failure
    here must not block the user from changing their picture. URLs we did not
    write — an OAuth provider's CDN, for instance — are left alone.
    """
    if not url:
        return

    try:
        # Matches both the absolute form written now and the root-relative form
        # written before this was fixed.
        marker = "/uploads/avatars/"
        if marker in url:
            relative = url.split("/uploads/", 1)[1].split("?", 1)[0]
            path = os.path.join(_local_root(), relative)
            if os.path.isfile(path):
                os.remove(path)
            return

        is_aws_url = settings.AWS_S3_BUCKET and f"{settings.AWS_S3_BUCKET}.s3." in url
        is_custom_url = settings.AWS_PUBLIC_URL and url.startswith(settings.AWS_PUBLIC_URL.rstrip("/"))
        if s3_enabled() and (is_aws_url or is_custom_url):
            import boto3
            from botocore.config import Config

            if is_custom_url:
                base = settings.AWS_PUBLIC_URL.rstrip("/")
                key = url[len(base) + 1:]
            else:
                key = url.split(".amazonaws.com/", 1)[-1]
            boto3.client(
                "s3",
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=settings.AWS_REGION,
                endpoint_url=settings.AWS_ENDPOINT_URL,
                config=Config(s3={'addressing_style': 'virtual'}),
            ).delete_object(Bucket=settings.AWS_S3_BUCKET, Key=key)
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"Could not delete old avatar {url}: {exc}")
