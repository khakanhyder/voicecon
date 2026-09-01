"""
The origin an outside browser actually reaches this API on.

``request.base_url`` is built from the connection the app sees. Behind a reverse
proxy that terminates TLS — Traefik on Dokploy, Railway's edge, an nginx in
front — that connection is plain HTTP on an internal address, so the scheme
comes back as ``http`` even though the user is on ``https``. Every absolute URL
built from it is then mixed content: an avatar stored as
``http://api.example.com/uploads/...`` uploads successfully and then renders as
a broken image on the HTTPS dashboard, because the browser refuses to fetch it.

Uvicorn can resolve this itself with ``--proxy-headers --forwarded-allow-ips``
(start.sh passes both), but that lives in a start command one deployment tweak
away from being lost, and the failure it causes is silent and persisted — the
wrong URL is written to the database. So the forwarded headers are also read
here, and any URL handed to a browser is correct either way.
"""
from fastapi import Request

from app.core.config import settings


def public_base_url(request: Request) -> str:
    """
    Return this API's externally-reachable origin, with no trailing slash.

    ``API_BASE_URL`` wins when it is configured: it is the operator stating the
    answer outright, and it is already what the telephony webhooks rely on.
    Otherwise the request is used, with ``X-Forwarded-Proto`` correcting the
    scheme when a proxy set it.
    """
    if settings.API_BASE_URL:
        return settings.API_BASE_URL.rstrip("/")

    base = str(request.base_url).rstrip("/")

    # A chain of proxies appends to this header; the first entry is the scheme
    # the client used.
    proto = (request.headers.get("x-forwarded-proto") or "").split(",")[0].strip().lower()
    if proto in ("http", "https") and "://" in base:
        base = f"{proto}://{base.split('://', 1)[1]}"

    return base
