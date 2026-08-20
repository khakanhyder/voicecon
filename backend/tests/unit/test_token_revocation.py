"""
Session revocation via ``User.token_version``.

A JWT is valid until it expires, whatever the server thinks — so revocation has
to be a claim the server re-checks at use time. Every token carries the version
its account held when issued; bumping the column strands everything already out
there.

What these tests pin down is not the mechanism but the *consequences*, because
the mechanism is trivial and the consequences are what was broken:

* logout ends sessions on machines you no longer have,
* changing a password ends the sessions the old password opened,
* resetting a password evicts whoever prompted the reset,
* and a refresh token — which outlives an access token by weeks — cannot be
  used to mint new access tokens after any of those.

The last one is the point. Everything else is cosmetic if a 30-day refresh
token still works after a password reset.
"""
from types import SimpleNamespace

import pytest

from app.core.security import (
    TOKEN_VERSION_CLAIM,
    create_access_token,
    create_refresh_token,
    decode_token,
    token_version_matches,
)


def user_at(version: int) -> SimpleNamespace:
    return SimpleNamespace(id="user-1", token_version=version)


class TestTokensCarryTheVersion:
    def test_access_token_records_the_issuing_version(self):
        token = create_access_token(subject="user-1", token_version=7)
        assert decode_token(token)[TOKEN_VERSION_CLAIM] == 7

    def test_refresh_token_records_the_issuing_version(self):
        token = create_refresh_token(subject="user-1", token_version=7)
        assert decode_token(token)[TOKEN_VERSION_CLAIM] == 7

    def test_version_defaults_to_zero(self):
        """A caller that forgets to pass one must not mint an unrevokable token."""
        assert decode_token(create_access_token(subject="user-1"))[TOKEN_VERSION_CLAIM] == 0


class TestRevocation:
    def test_a_token_is_valid_while_the_version_holds(self):
        user = user_at(3)
        token = create_access_token(subject="user-1", token_version=3)

        assert token_version_matches(decode_token(token), user)

    def test_bumping_the_version_invalidates_an_access_token(self):
        user = user_at(3)
        token = create_access_token(subject="user-1", token_version=3)

        user.token_version = 4  # logout / password change / reset

        assert not token_version_matches(decode_token(token), user)

    def test_bumping_the_version_invalidates_a_refresh_token(self):
        """
        The one that matters. A refresh token lasts 30 days; if it survived a
        password reset it would keep issuing access tokens for a month to
        exactly the person the reset was meant to lock out.
        """
        user = user_at(3)
        token = create_refresh_token(subject="user-1", token_version=3)

        user.token_version = 4

        assert not token_version_matches(decode_token(token), user)

    def test_a_token_from_a_future_version_is_refused(self):
        """Not a real flow — but a mismatch in either direction is a mismatch."""
        assert not token_version_matches({TOKEN_VERSION_CLAIM: 9}, user_at(3))


class TestDeployingThisDoesNotSignEveryoneOut:
    def test_a_token_issued_before_the_claim_existed_still_works(self):
        """
        Tokens already in the wild carry no ``tv``. They are read as version 0,
        which is what the migration backfills, so the deploy is not a mass
        logout — users keep working until they do something that revokes.
        """
        legacy = {"sub": "user-1", "type": "access"}

        assert token_version_matches(legacy, user_at(0))

    def test_but_a_legacy_token_is_still_revocable(self):
        """The grandfathering must not be a permanent bypass."""
        legacy = {"sub": "user-1", "type": "access"}

        assert not token_version_matches(legacy, user_at(1))


class TestMalformedInput:
    def test_a_non_numeric_version_claim_is_refused(self):
        """Not something we issue, so it is not something we accept."""
        assert not token_version_matches({TOKEN_VERSION_CLAIM: "abc"}, user_at(3))

    @pytest.mark.parametrize("stored", [None, 0])
    def test_a_missing_or_null_column_reads_as_zero(self, stored):
        """Rows predating the column, and the column default, agree on 0."""
        assert token_version_matches({TOKEN_VERSION_CLAIM: 0}, SimpleNamespace(token_version=stored))
