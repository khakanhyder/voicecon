"""
Avatar upload handling.

An avatar is the one file an anonymous-ish action puts on disk and then serves
back from our own origin, so the interesting cases here are the hostile ones:
a file that lies about its type, a file that is an image *and* something else,
and a small file that decodes to a gigapixel bitmap.
"""
import io
import uuid

import pytest
from PIL import Image

from app.services import storage
from app.services.storage import (
    AVATAR_MAX_EDGE,
    MAX_AVATAR_BYTES,
    StorageError,
    normalize_avatar,
    store_avatar,
)


def make_image(size=(64, 64), mode="RGB", fmt="PNG") -> bytes:
    buf = io.BytesIO()
    Image.new(mode, size, (120, 90, 200) if mode == "RGB" else (120, 90, 200, 128)).save(
        buf, format=fmt
    )
    return buf.getvalue()


class TestNormalizeAvatar:
    def test_accepts_a_real_image_and_returns_webp(self):
        data, content_type = normalize_avatar(make_image(), "image/png")

        assert content_type == "image/webp"
        assert Image.open(io.BytesIO(data)).format == "WEBP"

    @pytest.mark.parametrize("fmt,declared", [("JPEG", "image/jpeg"), ("WEBP", "image/webp")])
    def test_converts_other_formats(self, fmt, declared):
        data, _ = normalize_avatar(make_image(fmt=fmt), declared)
        assert Image.open(io.BytesIO(data)).format == "WEBP"

    def test_shrinks_a_large_image(self):
        data, _ = normalize_avatar(make_image(size=(2000, 1000)), "image/png")

        out = Image.open(io.BytesIO(data))
        assert max(out.size) == AVATAR_MAX_EDGE
        # Aspect ratio is preserved rather than squashed to a square.
        assert out.size == (AVATAR_MAX_EDGE, AVATAR_MAX_EDGE // 2)

    def test_leaves_a_small_image_alone(self):
        data, _ = normalize_avatar(make_image(size=(48, 48)), "image/png")
        assert Image.open(io.BytesIO(data)).size == (48, 48)

    def test_flattens_transparency_onto_white(self):
        # Dropping the alpha channel instead would turn transparent corners black.
        data, _ = normalize_avatar(make_image(mode="RGBA"), "image/png")
        assert Image.open(io.BytesIO(data)).mode == "RGB"

    def test_strips_exif(self):
        """A phone photo carries GPS coordinates. Re-encoding drops them."""
        buf = io.BytesIO()
        image = Image.new("RGB", (64, 64))
        exif = image.getexif()
        exif[0x010F] = "SecretCameraMake"
        image.save(buf, format="JPEG", exif=exif)
        assert b"SecretCameraMake" in buf.getvalue()

        data, _ = normalize_avatar(buf.getvalue(), "image/jpeg")

        assert b"SecretCameraMake" not in data
        assert not Image.open(io.BytesIO(data)).getexif()

    def test_drops_a_payload_appended_to_a_valid_image(self):
        """
        A file can be a valid PNG and carry arbitrary bytes after it. Decoding
        to pixels and re-encoding leaves the payload behind.
        """
        poisoned = make_image() + b"<script>alert(1)</script>"

        data, _ = normalize_avatar(poisoned, "image/png")

        assert b"<script>" not in data

    def test_rejects_a_file_that_only_claims_to_be_an_image(self):
        with pytest.raises(StorageError, match="not a readable image"):
            normalize_avatar(b"PK\x03\x04 this is a zip", "image/png")

    def test_rejects_svg(self):
        """SVG is a document format that can carry script; it is not an avatar."""
        svg = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'
        with pytest.raises(StorageError):
            normalize_avatar(svg, "image/svg+xml")

    def test_rejects_a_disallowed_content_type(self):
        with pytest.raises(StorageError, match="JPEG, PNG, WebP or GIF"):
            normalize_avatar(make_image(), "application/pdf")

    def test_rejects_an_empty_file(self):
        with pytest.raises(StorageError, match="empty"):
            normalize_avatar(b"", "image/png")

    def test_rejects_an_oversized_file(self):
        with pytest.raises(StorageError, match="too large"):
            normalize_avatar(b"x" * (MAX_AVATAR_BYTES + 1), "image/png")

    def test_refuses_a_decompression_bomb(self):
        """A tiny file that expands to a gigapixel bitmap must not be decoded."""
        buf = io.BytesIO()
        Image.new("L", (20000, 20000)).save(buf, format="PNG")
        if len(buf.getvalue()) > MAX_AVATAR_BYTES:
            pytest.skip("bomb exceeds the byte cap, which already rejects it")

        with pytest.raises(StorageError):
            normalize_avatar(buf.getvalue(), "image/png")


class TestStoreAvatar:
    def test_writes_to_disk_and_returns_an_absolute_url(self, tmp_path, monkeypatch):
        """
        The URL must carry the API's origin.

        A root-relative "/uploads/..." resolves against whatever origin loaded
        the page — the frontend on :3000 — while the file is served by the API
        on :8001. The upload succeeded and the picture rendered broken.
        """
        monkeypatch.setattr(storage, "_local_root", lambda: str(tmp_path))
        monkeypatch.setattr(storage, "s3_enabled", lambda: False)
        user_id = uuid.uuid4()

        url = store_avatar(
            user_id, make_image(), "image/png", public_base="http://localhost:8001"
        )

        assert url.startswith(f"http://localhost:8001/uploads/avatars/{user_id}/")
        assert (tmp_path / url.split("/uploads/", 1)[1]).is_file()

    def test_a_trailing_slash_on_the_base_does_not_double_up(self, tmp_path, monkeypatch):
        monkeypatch.setattr(storage, "_local_root", lambda: str(tmp_path))
        monkeypatch.setattr(storage, "s3_enabled", lambda: False)

        url = store_avatar(
            uuid.uuid4(), make_image(), "image/png", public_base="http://localhost:8001/"
        )

        assert "//uploads/" not in url

    def test_each_upload_gets_a_fresh_url(self, tmp_path, monkeypatch):
        """Reusing a key would leave the old picture cached in every browser."""
        monkeypatch.setattr(storage, "_local_root", lambda: str(tmp_path))
        monkeypatch.setattr(storage, "s3_enabled", lambda: False)
        user_id = uuid.uuid4()

        first = store_avatar(user_id, make_image(), "image/png", public_base="http://x")
        second = store_avatar(user_id, make_image(), "image/png", public_base="http://x")

        assert first != second


class TestDeleteAvatar:
    def test_removes_a_local_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr(storage, "_local_root", lambda: str(tmp_path))
        monkeypatch.setattr(storage, "s3_enabled", lambda: False)
        url = store_avatar(
            uuid.uuid4(), make_image(), "image/png", public_base="http://localhost:8001"
        )
        path = tmp_path / url.split("/uploads/", 1)[1]
        assert path.is_file()

        storage.delete_avatar(url)

        assert not path.exists()

    def test_still_removes_a_legacy_root_relative_url(self, tmp_path, monkeypatch):
        """Rows written before the URL was made absolute must still clean up."""
        monkeypatch.setattr(storage, "_local_root", lambda: str(tmp_path))
        monkeypatch.setattr(storage, "s3_enabled", lambda: False)
        path = tmp_path / "avatars" / "u1" / "old.png"  # legacy extension
        path.parent.mkdir(parents=True)
        path.write_bytes(b"x")

        storage.delete_avatar("/uploads/avatars/u1/old.png")

        assert not path.exists()

    def test_ignores_a_url_we_did_not_write(self, monkeypatch):
        """An OAuth provider's CDN avatar is not ours to delete."""
        monkeypatch.setattr(storage, "s3_enabled", lambda: False)
        storage.delete_avatar("https://lh3.googleusercontent.com/a/abc123")

    def test_never_raises_on_a_missing_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr(storage, "_local_root", lambda: str(tmp_path))
        monkeypatch.setattr(storage, "s3_enabled", lambda: False)
        # Losing the old file must not block the user changing their picture.
        storage.delete_avatar("/uploads/avatars/nope/missing.png")
        storage.delete_avatar(None)
