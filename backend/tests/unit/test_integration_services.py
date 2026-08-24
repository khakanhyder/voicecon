"""
Unit tests for the integration plumbing: OAuth2 flow state, token exchange, and
credential encryption.

These two modules are the security boundary for third-party integrations. The
state store is the CSRF defence on the OAuth callback, and the credential
manager is the only thing standing between the database and plaintext customer
API keys — so the tests here lean on the failure paths, not just the happy one.

No network: `_get_http_client` is replaced with a stub that returns canned
responses.
"""
import json
import uuid
from datetime import datetime, timedelta

import httpx
import pytest

from app.services.integrations.credential_manager import (
    CredentialDecryptionError,
    CredentialManager,
    get_credential_manager,
)
from app.services.integrations.oauth_handler import (
    OAuth2Error,
    OAuth2Handler,
    get_oauth_handler,
)


def _stub_token_endpoint(handler, *, json_body=None, status_code=200):
    """
    Point `handler` at a fake token endpoint.

    Records every POST on `handler.posts` so tests can assert on the form body
    the handler actually sent (grant_type, client_secret, and so on).
    """
    handler.posts = []

    async def fake_post(url, data=None, headers=None):
        handler.posts.append({"url": url, "data": data, "headers": headers})
        request = httpx.Request("POST", url)
        return httpx.Response(
            status_code, json=json_body if json_body is not None else {}, request=request
        )

    class _Client:
        post = staticmethod(fake_post)

    async def fake_get_client():
        return _Client()

    handler._get_http_client = fake_get_client
    return handler


# ── OAuth2 state (CSRF protection) ──────────────────────────────────────────


class TestOAuth2State:
    """The state token is what ties a callback back to the request that began it."""

    def test_state_round_trips_its_metadata(self):
        handler = OAuth2Handler()

        state = handler.generate_state("connector-1", "user-1")
        ok, data = handler.verify_state(state)

        assert ok is True
        assert data["connector_id"] == "connector-1"
        assert data["user_id"] == "user-1"

    def test_state_is_single_use(self):
        """A replayed callback must not authorise a second connection."""
        handler = OAuth2Handler()
        state = handler.generate_state("connector-1", "user-1")

        assert handler.verify_state(state)[0] is True
        assert handler.verify_state(state) == (False, None)

    def test_unknown_state_is_rejected(self):
        """A state the server never issued is a forged callback."""
        handler = OAuth2Handler()

        assert handler.verify_state("never-issued") == (False, None)

    def test_expired_state_is_rejected_and_discarded(self):
        handler = OAuth2Handler()
        state = handler.generate_state("connector-1", "user-1")
        handler._state_store[state]["expires_at"] = 0  # already elapsed

        assert handler.verify_state(state) == (False, None)
        assert state not in handler._state_store

    def test_states_are_unique_per_request(self):
        """Two concurrent connect attempts must not collide."""
        handler = OAuth2Handler()

        states = {handler.generate_state("c", "u") for _ in range(50)}

        assert len(states) == 50

    def test_state_is_long_enough_to_be_unguessable(self):
        handler = OAuth2Handler()

        state = handler.generate_state("c", "u")

        # token_urlsafe(32) → 43 chars of base64url, ~256 bits of entropy.
        assert len(state) >= 40


# ── Authorization URL ───────────────────────────────────────────────────────


class TestAuthorizationUrl:
    def test_url_carries_the_required_oauth2_params(self):
        handler = OAuth2Handler()

        url = handler.build_authorization_url(
            authorize_url="https://provider.test/oauth/authorize",
            client_id="client-abc",
            redirect_uri="https://app.test/callback",
            state="state-xyz",
        )

        assert url.startswith("https://provider.test/oauth/authorize?")
        assert "response_type=code" in url
        assert "client_id=client-abc" in url
        assert "state=state-xyz" in url
        # The redirect URI must be percent-encoded, not pasted in raw.
        assert "redirect_uri=https%3A%2F%2Fapp.test%2Fcallback" in url

    def test_scopes_are_space_joined(self):
        """OAuth2 specifies a space-delimited scope list, encoded as `+` or %20."""
        handler = OAuth2Handler()

        url = handler.build_authorization_url(
            authorize_url="https://provider.test/authorize",
            client_id="c",
            redirect_uri="https://app.test/cb",
            state="s",
            scopes=["contacts.read", "contacts.write"],
        )

        assert "scope=contacts.read+contacts.write" in url

    def test_additional_params_are_merged(self):
        """Providers like Google need `access_type=offline` to return a refresh token."""
        handler = OAuth2Handler()

        url = handler.build_authorization_url(
            authorize_url="https://provider.test/authorize",
            client_id="c",
            redirect_uri="https://app.test/cb",
            state="s",
            additional_params={"access_type": "offline", "prompt": "consent"},
        )

        assert "access_type=offline" in url
        assert "prompt=consent" in url


# ── Token exchange ──────────────────────────────────────────────────────────


class TestTokenExchange:
    async def test_code_is_exchanged_for_tokens(self):
        handler = _stub_token_endpoint(
            OAuth2Handler(),
            json_body={
                "access_token": "at-1",
                "refresh_token": "rt-1",
                "expires_in": 3600,
                "token_type": "Bearer",
            },
        )

        tokens = await handler.exchange_code_for_token(
            token_url="https://provider.test/token",
            client_id="client-abc",
            client_secret="shhh",
            code="auth-code-1",
            redirect_uri="https://app.test/cb",
        )

        assert tokens["access_token"] == "at-1"
        assert tokens["refresh_token"] == "rt-1"

        sent = handler.posts[0]["data"]
        assert sent["grant_type"] == "authorization_code"
        assert sent["code"] == "auth-code-1"
        # The redirect_uri must match the one used to authorize, or providers
        # reject the exchange.
        assert sent["redirect_uri"] == "https://app.test/cb"

    async def test_response_without_an_access_token_is_an_error(self):
        """A 200 with no token is a failed exchange, not a successful connection."""
        handler = _stub_token_endpoint(
            OAuth2Handler(), json_body={"error": "invalid_grant"}
        )

        with pytest.raises(OAuth2Error):
            await handler.exchange_code_for_token(
                token_url="https://provider.test/token",
                client_id="c",
                client_secret="s",
                code="bad-code",
                redirect_uri="https://app.test/cb",
            )

    async def test_http_error_becomes_an_oauth_error(self):
        """Callers catch OAuth2Error; a raw httpx error would escape as a 500."""
        handler = _stub_token_endpoint(
            OAuth2Handler(), json_body={"error": "server_error"}, status_code=500
        )

        with pytest.raises(OAuth2Error):
            await handler.exchange_code_for_token(
                token_url="https://provider.test/token",
                client_id="c",
                client_secret="s",
                code="code",
                redirect_uri="https://app.test/cb",
            )

    async def test_refresh_sends_the_refresh_grant(self):
        handler = _stub_token_endpoint(
            OAuth2Handler(), json_body={"access_token": "at-2", "expires_in": 3600}
        )

        tokens = await handler.refresh_access_token(
            token_url="https://provider.test/token",
            client_id="c",
            client_secret="s",
            refresh_token="rt-1",
        )

        assert tokens["access_token"] == "at-2"
        sent = handler.posts[0]["data"]
        assert sent["grant_type"] == "refresh_token"
        assert sent["refresh_token"] == "rt-1"

    async def test_failed_refresh_raises(self):
        handler = _stub_token_endpoint(OAuth2Handler(), json_body={})

        with pytest.raises(OAuth2Error):
            await handler.refresh_access_token(
                token_url="https://provider.test/token",
                client_id="c",
                client_secret="s",
                refresh_token="expired",
            )


class TestTokenExpiry:
    def test_expiry_is_computed_with_a_refresh_buffer(self):
        """
        The stored expiry is deliberately early, so a refresh happens before the
        provider starts rejecting the token mid-call.
        """
        handler = OAuth2Handler()

        expiry = handler.calculate_token_expiry(3600)

        expected = datetime.utcnow() + timedelta(seconds=3600 - 300)
        assert abs((expiry - expected).total_seconds()) < 5

    def test_short_lived_token_does_not_expire_in_the_past(self):
        """A token shorter than the buffer must clamp to now, not go backwards."""
        handler = OAuth2Handler()

        expiry = handler.calculate_token_expiry(60)

        assert expiry >= datetime.utcnow() - timedelta(seconds=5)

    def test_missing_expiry_stays_missing(self):
        """Some providers issue non-expiring tokens; that is not an expiry of now."""
        handler = OAuth2Handler()

        assert handler.calculate_token_expiry(None) is None


# ── Credential encryption ───────────────────────────────────────────────────


class TestCredentialManager:
    # The encryption key these tests need is set suite-wide in tests/conftest.py,
    # alongside the rate-limit switch, for the reason documented there.

    def test_string_round_trips(self):
        manager = CredentialManager()

        encrypted = manager.encrypt("super-secret-api-key")

        assert encrypted != "super-secret-api-key"
        assert manager.decrypt(encrypted) == "super-secret-api-key"

    def test_ciphertext_does_not_leak_the_plaintext(self):
        manager = CredentialManager()

        encrypted = manager.encrypt("sk_live_1234567890")

        assert "sk_live" not in encrypted

    def test_same_plaintext_encrypts_differently_each_time(self):
        """
        Fernet includes a random IV, so identical secrets must not produce
        identical ciphertext — otherwise the database leaks which tenants share
        a key.
        """
        manager = CredentialManager()

        assert manager.encrypt("same") != manager.encrypt("same")

    def test_empty_values_pass_through(self):
        """Optional credentials are stored as "", and must not blow up."""
        manager = CredentialManager()

        assert manager.encrypt("") == ""
        assert manager.decrypt("") == ""

    def test_dict_round_trips_with_types_intact(self):
        manager = CredentialManager()
        original = {"api_key": "k", "region": "us-east-1", "port": 443, "tls": True}

        restored = manager.decrypt_dict(manager.encrypt_dict(original))

        assert restored == original

    def test_empty_ciphertext_decrypts_to_an_empty_dict(self):
        """A connection row with no auth data must read as {}, not raise."""
        manager = CredentialManager()

        assert manager.decrypt_dict("") == {}

    def test_garbage_ciphertext_is_rejected(self):
        """Tampered or truncated data must fail loudly, never return a partial key."""
        manager = CredentialManager()

        with pytest.raises(CredentialDecryptionError):
            manager.decrypt("not-a-real-fernet-token")

    def test_tampered_ciphertext_is_rejected(self):
        """Fernet is authenticated; flipping a byte must fail the MAC check."""
        manager = CredentialManager()
        encrypted = manager.encrypt("secret")

        tampered = encrypted[:-4] + ("AAAA" if not encrypted.endswith("AAAA") else "BBBB")

        with pytest.raises(CredentialDecryptionError):
            manager.decrypt(tampered)

    def test_a_different_key_cannot_decrypt(self):
        """Confirms the ciphertext is actually bound to the configured secret."""
        manager = CredentialManager()
        encrypted = manager.encrypt("secret")

        from cryptography.fernet import Fernet

        stranger = CredentialManager()
        stranger._fernet = Fernet(Fernet.generate_key())

        with pytest.raises(CredentialDecryptionError):
            stranger.decrypt(encrypted)

    def test_oauth_tokens_are_encrypted_under_their_storage_names(self):
        manager = CredentialManager()

        encrypted = manager.encrypt_oauth_tokens("at-1", "rt-1")

        assert set(encrypted) == {"access_token_encrypted", "refresh_token_encrypted"}
        assert "at-1" not in encrypted["access_token_encrypted"]

        restored = manager.decrypt_oauth_tokens(
            encrypted["access_token_encrypted"],
            encrypted["refresh_token_encrypted"],
        )
        assert restored == {"access_token": "at-1", "refresh_token": "rt-1"}

    def test_refresh_token_is_optional(self):
        """Client-credentials providers issue no refresh token."""
        manager = CredentialManager()

        encrypted = manager.encrypt_oauth_tokens("at-only")

        assert "refresh_token_encrypted" not in encrypted
        assert manager.decrypt_oauth_tokens(encrypted["access_token_encrypted"]) == {
            "access_token": "at-only"
        }

    def test_unicode_survives_the_round_trip(self):
        manager = CredentialManager()
        secret = "clé-très-sécurisée-🔐"

        assert manager.decrypt(manager.encrypt(secret)) == secret

    def test_key_derivation_is_deterministic_across_instances(self):
        """
        Two processes must derive the same key from the same secret, or a restart
        would orphan every stored credential.
        """
        first, second = CredentialManager(), CredentialManager()

        assert second.decrypt(first.encrypt("shared")) == "shared"


class TestSingletons:
    def test_credential_manager_is_shared(self):
        assert get_credential_manager() is get_credential_manager()

    def test_oauth_handler_is_shared(self):
        """
        The state store lives on the instance, so the callback must reach the
        same handler that issued the state.
        """
        assert get_oauth_handler() is get_oauth_handler()


# ── Test doubles for the integration manager ────────────────────────────────


class _FakeConnector:
    """Just enough connector for the OAuth paths."""

    def __init__(self, slug="fake-app", name="Fake App"):
        self.id = uuid.uuid4()
        self.slug = slug
        self.name = name
        self.auth_type = "oauth2"
        self.auth_config = {}


class _FakeConnection:
    """A stand-in for the IntegrationConnection row."""

    def __init__(self, **overrides):
        self.id = uuid.uuid4()
        self.user_id = uuid.uuid4()
        self.organization_id = uuid.uuid4()
        self.connector_id = None
        self.name = "Fake App Connection"
        self.status = "active"
        self.is_active = True
        self.last_error = None
        self.error_count = 0
        self.access_token_encrypted = None
        self.refresh_token_encrypted = None
        self.token_expires_at = None
        self.integration_metadata = {}
        self.updated_at = None
        self.created_at = datetime.utcnow()
        for key, value in overrides.items():
            setattr(self, key, value)


class _FakeResult:
    def __init__(self, row):
        self._row = row

    def scalars(self):
        return self

    def first(self):
        return self._row


class _FakeSession:
    """Async session double that returns one preloaded row."""

    def __init__(self, existing):
        self._existing = existing
        self.added = []
        self.committed = 0
        self.rolled_back = 0

    async def execute(self, *_args, **_kwargs):
        return _FakeResult(self._existing)

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        self.committed += 1

    async def rollback(self):
        self.rolled_back += 1

    async def refresh(self, *_args, **_kwargs):
        return None


def _stub_oauth_completion(manager, monkeypatch, connector, user_id):
    """Make complete_oauth_flow reach the connection-writing step offline."""
    monkeypatch.setattr(
        manager.oauth_handler, "verify_state",
        lambda state: (True, {"connector_id": str(connector.id), "user_id": user_id}),
    )

    async def fake_exchange(**_kwargs):
        return {"access_token": "new-access", "refresh_token": "new-refresh",
                "expires_in": 3600, "token_type": "Bearer"}

    monkeypatch.setattr(manager.oauth_handler, "exchange_code_for_token", fake_exchange)
    monkeypatch.setattr(
        "app.services.integrations.oauth_providers.resolve_client_credentials",
        lambda slug, config: {"token_url": "https://example.com/token",
                              "client_id": "id", "client_secret": "secret",
                              "token_style": "form"},
    )


def _stub_refresh_failure(manager, monkeypatch, detail):
    """Make refresh_token fail the way a provider rejection does."""
    monkeypatch.setattr(
        "app.services.integrations.oauth_providers.resolve_client_credentials",
        lambda slug, config: {"token_url": "https://example.com/token",
                              "client_id": "id", "client_secret": "secret",
                              "token_style": "form"},
    )
    monkeypatch.setattr(manager.credential_manager, "decrypt", lambda value: "plain-refresh")

    async def fake_refresh(**_kwargs):
        raise OAuth2Error(detail)

    monkeypatch.setattr(manager.oauth_handler, "refresh_access_token", fake_refresh)

# ── Reconnecting an app ─────────────────────────────────────────────────────


class TestReconnectKeepsTheSameConnection:
    """
    Reconnecting must land on the row the workflows already name.

    Every workflow step, tool and agent stores a connection *id*. Inserting a
    new row on reconnect left all of them pointing at the dead one, so the
    Integrations page read "Connected" while every call through the app failed.
    """

    @pytest.mark.asyncio
    async def test_reconnect_updates_the_existing_row(self, monkeypatch):
        from app.services.integrations.integration_manager import IntegrationManager

        manager = IntegrationManager()
        connector = _FakeConnector()
        existing = _FakeConnection(
            status="expired", last_error="dead", error_count=4,
            access_token_encrypted="old-access",
        )
        db = _FakeSession(existing)
        user_id = str(existing.user_id)
        _stub_oauth_completion(manager, monkeypatch, connector, user_id)

        result = await manager.complete_oauth_flow(
            connector=connector, code="c", state="s", redirect_uri="r",
            user_id=user_id, organization_id=str(existing.organization_id),
            db=db,
        )

        assert result is existing, "reconnect created a second connection"
        assert db.added == [], "nothing should be inserted on a reconnect"
        assert result.access_token_encrypted != "old-access"
        # A fresh authorisation clears whatever went wrong before it.
        assert result.status == "active"
        assert result.last_error is None
        assert result.error_count == 0

    @pytest.mark.asyncio
    async def test_first_connect_still_creates_a_row(self, monkeypatch):
        from app.services.integrations.integration_manager import IntegrationManager

        manager = IntegrationManager()
        connector = _FakeConnector()
        db = _FakeSession(None)
        user_id = str(uuid.uuid4())
        _stub_oauth_completion(manager, monkeypatch, connector, user_id)

        result = await manager.complete_oauth_flow(
            connector=connector, code="c", state="s", redirect_uri="r",
            user_id=user_id, organization_id=str(uuid.uuid4()), db=db,
        )

        assert db.added == [result]
        assert result.status == "active"

    @pytest.mark.asyncio
    async def test_re_entering_an_api_key_also_reuses_the_row(self, monkeypatch):
        """The same trap on the API-key path — Trello and Slack go through it."""
        from app.services.integrations.integration_manager import IntegrationManager

        manager = IntegrationManager()
        connector = _FakeConnector()
        connector.auth_type = "api_key"
        existing = _FakeConnection(status="error", last_error="bad key", error_count=2)
        db = _FakeSession(existing)

        async def fake_test(connection, connector, db=None):
            return {"success": True, "message": "ok"}

        monkeypatch.setattr(manager, "test_connection", fake_test)

        result = await manager.connect_with_api_key(
            connector=connector, api_key="new-key",
            user_id=str(existing.user_id),
            organization_id=str(existing.organization_id), db=db,
        )

        assert result is existing
        assert db.added == []
        assert result.status == "active"
        assert result.last_error is None
        assert result.error_count == 0


# ── A refresh the provider rejects ──────────────────────────────────────────


class TestExpiredAuthorisationIsVisible:
    """
    A dead refresh token has to show up on the connection, not only in a stack
    trace inside whatever workflow happened to run next.
    """

    @pytest.mark.asyncio
    async def test_invalid_grant_marks_the_connection_expired(self, monkeypatch):
        from app.services.integrations import integration_manager as im

        manager = im.IntegrationManager()
        connector = _FakeConnector()
        connection = _FakeConnection(refresh_token_encrypted="enc-refresh")
        db = _FakeSession(connection)
        _stub_refresh_failure(
            manager, monkeypatch,
            "HTTP 400: invalid_grant Token has been expired or revoked.")

        with pytest.raises(im.IntegrationError) as exc:
            await manager.refresh_token(connection=connection, connector=connector, db=db)

        assert connection.status == "expired"
        assert connection.error_count == 1
        assert "Integrations page" in connection.last_error
        # The message names the app, the fix, and the provider's own reason.
        assert "Fake App" in str(exc.value)
        assert "reconnect" in str(exc.value).lower()
        assert "invalid_grant" in str(exc.value)

    @pytest.mark.asyncio
    async def test_a_provider_outage_does_not_demand_a_reconnect(self, monkeypatch):
        """A bad minute at the provider is not a revoked authorisation."""
        from app.services.integrations import integration_manager as im

        manager = im.IntegrationManager()
        connector = _FakeConnector()
        connection = _FakeConnection(refresh_token_encrypted="enc-refresh")
        db = _FakeSession(connection)
        _stub_refresh_failure(manager, monkeypatch, "HTTP 503: service unavailable")

        with pytest.raises(im.IntegrationError):
            await manager.refresh_token(connection=connection, connector=connector, db=db)

        assert connection.status == "active", "a transient error must not expire the connection"
        assert connection.last_error is None


class TestProviderErrorIsReadable:
    """
    raise_for_status reports only "Client error '400 Bad Request'". The body is
    where the provider says *why*, and that is what tells a revoked token apart
    from a provider outage.
    """

    def test_the_providers_own_words_survive(self):
        from app.services.integrations.oauth_handler import _provider_error

        request = httpx.Request("POST", "https://oauth2.googleapis.com/token")
        response = httpx.Response(
            400,
            json={"error": "invalid_grant",
                  "error_description": "Token has been expired or revoked."},
            request=request,
        )

        detail = _provider_error(response)
        assert "invalid_grant" in detail
        assert "expired or revoked" in detail
        assert "400" in detail

    def test_a_non_json_body_still_reports_something(self):
        from app.services.integrations.oauth_handler import _provider_error

        request = httpx.Request("POST", "https://example.com/token")
        response = httpx.Response(500, text="upstream exploded", request=request)

        assert "500" in _provider_error(response)
        assert "upstream exploded" in _provider_error(response)

    @pytest.mark.asyncio
    async def test_a_rejected_refresh_reaches_the_caller_intact(self):
        """The message must not be re-wrapped on the way out."""
        handler = _stub_token_endpoint(
            OAuth2Handler(),
            json_body={"error": "invalid_grant", "error_description": "revoked"},
            status_code=400,
        )

        with pytest.raises(OAuth2Error) as exc:
            await handler.refresh_access_token(
                token_url="https://example.com/token", client_id="id",
                client_secret="secret", refresh_token="old",
            )

        assert "invalid_grant" in str(exc.value)
        # It used to arrive as "Token refresh failed: Token refresh failed: …"
        assert str(exc.value).count("Token refresh failed") <= 1
