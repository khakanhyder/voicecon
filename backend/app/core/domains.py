"""
Does a domain someone typed actually exist?

A website can be well-formed and end in a real TLD and still be nothing:
"asdfqwe.com" passes every syntax rule. The only way to tell is to ask DNS.

The answer is deliberately lopsided. Only an authoritative "no such domain"
counts as a no. A timeout, a resolver that is down, or a host with no network
at all is *our* problem, and must not stop someone from saving a perfectly good
website, so everything else is treated as a yes.
"""
import logging

import dns.asyncresolver
import dns.resolver

logger = logging.getLogger(__name__)

#: Total time allowed for the lookup. It runs inside a form submit.
_LOOKUP_SECONDS = 3.0


async def domain_exists(host: str) -> bool:
    """Return False only when DNS says outright that `host` does not exist."""
    resolver = dns.asyncresolver.Resolver()
    resolver.lifetime = _LOOKUP_SECONDS
    try:
        # NoAnswer (the name exists but has no A record) is not raised: a
        # domain that is registered but IPv6-only or parked is still real.
        await resolver.resolve(host, "A", raise_on_no_answer=False)
    except dns.resolver.NXDOMAIN:
        return False
    except Exception as exc:  # noqa: BLE001 - any resolver failure is ours, not the user's
        logger.warning("Could not check whether %s exists (%s); accepting it", host, exc)
    return True
