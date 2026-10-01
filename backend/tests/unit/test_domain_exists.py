"""
`domain_exists` only says no when DNS says no.

Any other failure is ours — a resolver that is down must not stop someone
saving a real website — so it has to come back as a yes.
"""
import dns.asyncresolver
import dns.exception
import dns.resolver
import pytest

from app.core.domains import domain_exists


def _resolver_that(monkeypatch, outcome):
    async def resolve(self, host, rdtype, **kwargs):
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    monkeypatch.setattr(dns.asyncresolver.Resolver, "resolve", resolve)


@pytest.mark.asyncio
async def test_a_domain_that_resolves_exists(monkeypatch):
    _resolver_that(monkeypatch, object())
    assert await domain_exists("acme.com") is True


@pytest.mark.asyncio
async def test_a_domain_dns_has_never_heard_of_does_not(monkeypatch):
    _resolver_that(monkeypatch, dns.resolver.NXDOMAIN())
    assert await domain_exists("asdfqwe-not-registered.com") is False


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "failure",
    [dns.exception.Timeout(), dns.resolver.NoNameservers(), OSError("network unreachable")],
)
async def test_a_lookup_we_could_not_make_is_not_held_against_the_user(monkeypatch, failure):
    _resolver_that(monkeypatch, failure)
    assert await domain_exists("acme.com") is True
