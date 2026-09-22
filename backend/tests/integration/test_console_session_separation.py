"""
The customer app and the staff console are two separate sign-ins.

Signing in at ``/login`` must not be a sign-in at ``/admin/login``, and the
reverse, *even for one person who is legitimately both* — which is the case
that matters, because it is the one where a shared session looks like it is
working.

These drive real tokens through the real dependency chain: nothing is
overridden except the database, so what is being tested is what a browser
would get.
"""
import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.security import (
    SCOPE_ADMIN,
    SCOPE_APP,
    SESSION_SCOPE_CLAIM,
    decode_token,
    get_password_hash,
)
from app.main import app
from app.models.user import Organization, OrganizationMember, User

PASSWORD = "admin-console-password-123"

APP_ENDPOINT = "/api/v1/users/me"
ADMIN_ENDPOINT = "/api/v1/admin/me"


async def _make_user(db, email: str, *, admin: bool = False) -> User:
    user = User(
        email=email,
        hashed_password=get_password_hash(PASSWORD),
        full_name=email.split("@")[0],
        is_active=True,
        is_verified=True,
        is_platform_admin=admin,
    )
    db.add(user)
    await db.flush()
    org = Organization(
        name=f"{email} workspace",
        slug=f"org-{uuid.uuid4().hex[:8]}",
        owner_id=user.id,
        is_active=True,
    )
    db.add(org)
    await db.flush()
    db.add(OrganizationMember(organization_id=org.id, user_id=user.id, role="owner"))
    await db.commit()
    await db.refresh(user)
    return user


@pytest_asyncio.fixture
async def staff(db_session) -> User:
    """One person who is both a platform admin and a customer."""
    return await _make_user(db_session, "staff@example.com", admin=True)


@pytest_asyncio.fixture
async def customer(db_session) -> User:
    return await _make_user(db_session, "customer@example.com")


def bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def sign_in(client: AsyncClient, user: User, *, console: bool) -> dict:
    """Sign in at one of the two front doors and return the token pair."""
    path = "/api/v1/auth/admin/login" if console else "/api/v1/auth/login"
    res = await client.post(path, json={"email": user.email, "password": PASSWORD})
    assert res.status_code == 200, res.text
    return res.json()


@pytest.mark.integration
@pytest.mark.auth
class TestScopeOfIssuedSessions:
    async def test_app_sign_in_is_app_scoped_even_for_staff(
        self, async_client, staff
    ):
        tokens = await sign_in(async_client, staff, console=False)

        for token in (tokens["access_token"], tokens["refresh_token"]):
            assert decode_token(token)[SESSION_SCOPE_CLAIM] == SCOPE_APP

    async def test_console_sign_in_is_admin_scoped(self, async_client, staff):
        tokens = await sign_in(async_client, staff, console=True)

        for token in (tokens["access_token"], tokens["refresh_token"]):
            assert decode_token(token)[SESSION_SCOPE_CLAIM] == SCOPE_ADMIN

    async def test_console_refuses_a_customer_account(self, async_client, customer):
        res = await async_client.post(
            "/api/v1/auth/admin/login",
            json={"email": customer.email, "password": PASSWORD},
        )

        # 401, not 403: whether an address is staff is not for an anonymous
        # caller to discover by comparing responses.
        assert res.status_code == 401, res.text

    async def test_console_refuses_a_wrong_password_for_an_admin(
        self, async_client, staff
    ):
        res = await async_client.post(
            "/api/v1/auth/admin/login",
            json={"email": staff.email, "password": "not-the-password"},
        )

        assert res.status_code == 401, res.text


@pytest.mark.integration
@pytest.mark.auth
class TestSessionsDoNotCarryOver:
    async def test_signing_into_the_app_does_not_open_the_console(
        self, async_client, staff
    ):
        """The heart of it: a platform admin signed into the product only."""
        tokens = await sign_in(async_client, staff, console=False)

        res = await async_client.get(
            ADMIN_ENDPOINT, headers=bearer(tokens["access_token"])
        )

        assert res.status_code == 403, res.text
        assert "admin console" in res.json()["detail"].lower()

    async def test_signing_into_the_console_does_not_open_the_app(
        self, async_client, staff
    ):
        tokens = await sign_in(async_client, staff, console=True)

        res = await async_client.get(
            APP_ENDPOINT, headers=bearer(tokens["access_token"])
        )

        assert res.status_code == 403, res.text

    async def test_the_console_session_still_works_on_the_console(
        self, async_client, staff
    ):
        tokens = await sign_in(async_client, staff, console=True)

        res = await async_client.get(
            ADMIN_ENDPOINT, headers=bearer(tokens["access_token"])
        )

        assert res.status_code == 200, res.text
        assert res.json()["email"] == staff.email

    async def test_the_app_session_still_works_on_the_app(self, async_client, staff):
        tokens = await sign_in(async_client, staff, console=False)

        res = await async_client.get(
            APP_ENDPOINT, headers=bearer(tokens["access_token"])
        )

        assert res.status_code == 200, res.text
        assert res.json()["email"] == staff.email

    async def test_a_customer_session_is_refused_by_the_admin_api(
        self, async_client, customer
    ):
        tokens = await sign_in(async_client, customer, console=False)

        res = await async_client.get(
            ADMIN_ENDPOINT, headers=bearer(tokens["access_token"])
        )

        assert res.status_code == 403, res.text


@pytest.mark.integration
@pytest.mark.auth
class TestRefreshKeepsItsScope:
    """A refresh must not be a way to trade one console's session for the other."""

    async def test_console_refresh_stays_admin_scoped(self, async_client, staff):
        tokens = await sign_in(async_client, staff, console=True)

        res = await async_client.post(
            "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
        )
        assert res.status_code == 200, res.text
        refreshed = res.json()["access_token"]

        assert decode_token(refreshed)[SESSION_SCOPE_CLAIM] == SCOPE_ADMIN
        assert (
            await async_client.get(APP_ENDPOINT, headers=bearer(refreshed))
        ).status_code == 403

    async def test_app_refresh_stays_app_scoped(self, async_client, staff):
        tokens = await sign_in(async_client, staff, console=False)

        res = await async_client.post(
            "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
        )
        assert res.status_code == 200, res.text
        refreshed = res.json()["access_token"]

        assert decode_token(refreshed)[SESSION_SCOPE_CLAIM] == SCOPE_APP
        assert (
            await async_client.get(ADMIN_ENDPOINT, headers=bearer(refreshed))
        ).status_code == 403


@pytest.mark.integration
@pytest.mark.auth
class TestSigningOut:
    async def test_a_console_session_can_sign_itself_out(self, async_client, staff):
        """Sign-out is the one endpoint both scopes share; it has to be."""
        tokens = await sign_in(async_client, staff, console=True)

        res = await async_client.post(
            "/api/v1/auth/logout", headers=bearer(tokens["access_token"])
        )

        assert res.status_code == 200, res.text
        assert (
            await async_client.get(
                ADMIN_ENDPOINT, headers=bearer(tokens["access_token"])
            )
        ).status_code == 401
