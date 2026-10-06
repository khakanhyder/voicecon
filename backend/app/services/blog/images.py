"""
Blog image uploads: featured images, social share images and pictures inside
an article.

Like avatars (services/storage.py), nothing is stored as sent. Each upload is
decoded, capped in size and re-encoded as WebP, which drops EXIF (camera GPS)
and anything smuggled after the image data. Images are not cropped: the site
shows featured images in a 16:9 frame (the recommended 1200 × 675 upload) and
the console warns when an upload is a different shape.
"""
from __future__ import annotations

import io
import uuid
from datetime import datetime
from typing import Optional, Tuple

from PIL import Image, UnidentifiedImageError

from app.services.storage import StorageError, store_public_file

ALLOWED_TYPES = frozenset({"image/jpeg", "image/jpg", "image/png", "image/webp"})
MAX_BYTES = 10 * 1024 * 1024
#: Retina-wide for a 1200px article column, without storing camera originals.
MAX_EDGE = 2400
MAX_PIXELS = 60_000_000

RECOMMENDED_WIDTH = 1200
RECOMMENDED_HEIGHT = 675


def normalize_blog_image(raw: bytes, content_type: Optional[str]) -> Tuple[bytes, int, int]:
    """Validate an upload; return ``(webp_bytes, width, height)``."""
    if not raw:
        raise StorageError("The file is empty.")
    if len(raw) > MAX_BYTES:
        raise StorageError(f"Image is too large. Choose one under {MAX_BYTES // (1024 * 1024)}MB.")
    if content_type and content_type.lower() not in ALLOWED_TYPES:
        raise StorageError("Use a JPG, PNG or WebP image.")

    original_limit = Image.MAX_IMAGE_PIXELS
    Image.MAX_IMAGE_PIXELS = MAX_PIXELS
    try:
        image = Image.open(io.BytesIO(raw))
        if image.format not in ("JPEG", "PNG", "WEBP"):
            raise StorageError("Use a JPG, PNG or WebP image.")
        image.load()
    except Image.DecompressionBombError as exc:
        raise StorageError("That image is too large to process.") from exc
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise StorageError("That file is not a readable image.") from exc
    finally:
        Image.MAX_IMAGE_PIXELS = original_limit

    # WebP keeps transparency, so a PNG logo stays transparent.
    has_alpha = image.mode in ("RGBA", "LA") or (image.mode == "P" and "transparency" in image.info)
    image = image.convert("RGBA" if has_alpha else "RGB")
    image.thumbnail((MAX_EDGE, MAX_EDGE), Image.Resampling.LANCZOS)

    out = io.BytesIO()
    image.save(out, format="WEBP", quality=86, method=6)
    return out.getvalue(), image.width, image.height


def store_blog_image(raw: bytes, content_type: Optional[str], public_base: Optional[str] = None) -> dict:
    data, width, height = normalize_blog_image(raw, content_type)
    now = datetime.utcnow()
    key = f"blog/{now:%Y/%m}/{uuid.uuid4().hex}.webp"
    url = store_public_file(key, data, "image/webp", public_base)
    return {"url": url, "width": width, "height": height}
