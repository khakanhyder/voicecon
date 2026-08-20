"""
Guard for outbound HTTP requests whose destination a user chose.

Two features let a customer name a URL the server will then fetch: the workflow
"webhook" step, and the ``api_request`` tool type. Both are meant to reach the
customer's own systems on the public internet. Neither had any restriction
beyond requiring an ``http(s)`` scheme, so both could equally be pointed *inward*
— at the cloud metadata endpoint, at Redis or Postgres, at anything else the
container can route to but the internet cannot. The webhook step returns the
response body into the execution result, so it was a read primitive, not a blind
one: metadata credentials could be exfiltrated in a single run.

What this module does
---------------------
``assert_safe_url`` resolves the hostname and refuses any address that is not
publicly routable — loopback, private ranges, link-local (which is where
169.254.169.254 lives), and the various reserved blocks.

What it does not do
-------------------
Resolution happens here and the connection happens in the caller, so a name that
resolves differently between the two — DNS rebinding — is not closed by this
alone. Redirects are the same story, which is why callers should disable them
rather than trusting a second check. The durable fix is a network path that
cannot reach internal addresses at all; this is the application-layer floor
under that, not a substitute for it.
"""
from __future__ import annotations

import ipaddress
import socket
from typing import Iterable, List
from urllib.parse import urlparse

#: Schemes worth speaking to. ``file:``, ``gopher:`` and friends have no
#: business here and are historically how SSRF turns into file disclosure.
ALLOWED_SCHEMES = frozenset({"http", "https"})


class UnsafeURLError(ValueError):
    """The destination is not a publicly routable address."""


def _is_public(ip: ipaddress._BaseAddress) -> bool:
    """Whether ``ip`` is a normal internet address.

    ``is_global`` covers most of this, but it is checked alongside the specific
    flags so the intent stays readable and so an address that is somehow global
    yet loopback cannot slip through.
    """
    if (
        ip.is_loopback          # 127.0.0.0/8, ::1
        or ip.is_private        # 10/8, 172.16/12, 192.168/16, fc00::/7
        or ip.is_link_local     # 169.254.0.0/16 — cloud metadata lives here
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    ):
        return False

    # IPv4-mapped and 6to4 addresses can wrap a private v4 address in a v6 one;
    # unwrap before judging, or ::ffff:127.0.0.1 reads as public.
    mapped = getattr(ip, "ipv4_mapped", None)
    if mapped is not None:
        return _is_public(mapped)
    sixtofour = getattr(ip, "sixtofour", None)
    if sixtofour is not None:
        return _is_public(sixtofour)

    return ip.is_global


def _resolve(host: str) -> List[ipaddress._BaseAddress]:
    """Every address ``host`` resolves to.

    All of them are checked, not just the first: a name that returns one public
    and one private address must be refused, since the client may connect to
    either.
    """
    # A bare IP literal needs no lookup — and passing one to getaddrinfo would
    # happily return it, so handle it directly.
    try:
        return [ipaddress.ip_address(host)]
    except ValueError:
        pass

    try:
        infos = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise UnsafeURLError(f"Could not resolve host '{host}'") from exc

    resolved: List[ipaddress._BaseAddress] = []
    for info in infos:
        sockaddr = info[4]
        try:
            resolved.append(ipaddress.ip_address(sockaddr[0]))
        except ValueError:
            continue

    if not resolved:
        raise UnsafeURLError(f"Could not resolve host '{host}'")
    return resolved


def assert_safe_url(url: str) -> str:
    """Return ``url`` unchanged, or raise :class:`UnsafeURLError`.

    Raises rather than returning a boolean so a caller cannot forget to check
    the result — the failure mode of a predicate here is an open SSRF.
    """
    # Test-suite affordance only. The scheme check below still applies, so
    # file:// and gopher:// stay refused even here. Production cannot turn this
    # on — app.core.config.check_production_secrets fails the boot if it is set.
    from app.core.config import settings

    allow_private = settings.EGRESS_ALLOW_PRIVATE

    parsed = urlparse(url)

    if parsed.scheme.lower() not in ALLOWED_SCHEMES:
        raise UnsafeURLError(
            f"URL scheme '{parsed.scheme}' is not allowed; use http or https"
        )

    host = parsed.hostname
    if not host:
        raise UnsafeURLError("URL has no host")

    if allow_private:
        return url

    for ip in _resolve(host):
        if not _is_public(ip):
            # The address is deliberately named. An operator reading the log
            # needs to know which internal target was reached for, and the
            # caller needs to know why their URL was refused.
            raise UnsafeURLError(
                f"'{host}' resolves to {ip}, which is not a public address. "
                f"Outbound requests may only reach the public internet."
            )

    return url


def is_safe_url(url: str) -> bool:
    """Boolean form, for callers that genuinely want to branch."""
    try:
        assert_safe_url(url)
        return True
    except UnsafeURLError:
        return False
