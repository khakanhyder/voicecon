"""
The origin the app hands to browsers.

This is the bug that turned a successful avatar upload into a broken image on
the live deployment: behind a TLS-terminating proxy the app's own connection is
plain http, so it wrote down an http:// URL that an https page then refused to
load. The scheme has to come from what the *browser* used.
"""
import pytest

from app.core import urls
from app.core.urls import public_base_url


class FakeRequest:
    """Only the two attributes public_base_url reads."""

    def __init__(self, base_url: str, headers: dict | None = None):
        self.base_url = base_url
        self.headers = {k.lower(): v for k, v in (headers or {}).items()}


@pytest.fixture(autouse=True)
def no_configured_base(monkeypatch):
    """Default to the unconfigured case; the API_BASE_URL test opts back in."""
    monkeypatch.setattr(urls.settings, "API_BASE_URL", None, raising=False)


def test_uses_the_forwarded_scheme_over_the_connections_own():
    request = FakeRequest(
        "http://backend.example.com/", {"X-Forwarded-Proto": "https"}
    )
    assert public_base_url(request) == "https://backend.example.com"


def test_reads_the_first_hop_of_a_proxy_chain():
    request = FakeRequest(
        "http://backend.example.com/", {"X-Forwarded-Proto": "https, http"}
    )
    assert public_base_url(request) == "https://backend.example.com"


def test_leaves_a_plain_http_deployment_alone():
    assert public_base_url(FakeRequest("http://localhost:8001/")) == "http://localhost:8001"


def test_ignores_a_nonsense_forwarded_scheme():
    request = FakeRequest("https://backend.example.com/", {"X-Forwarded-Proto": "gopher"})
    assert public_base_url(request) == "https://backend.example.com"


def test_configured_base_url_wins(monkeypatch):
    monkeypatch.setattr(urls.settings, "API_BASE_URL", "https://api.example.com/")
    request = FakeRequest("http://internal:8000/", {"X-Forwarded-Proto": "http"})
    assert public_base_url(request) == "https://api.example.com"


def test_never_returns_a_trailing_slash():
    assert not public_base_url(FakeRequest("https://backend.example.com/")).endswith("/")
