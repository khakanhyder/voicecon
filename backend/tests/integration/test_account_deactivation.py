"""
Account deactivation, recovery and permanent deletion.

  - the customer flow   (/api/v1/users/me/deactivation/*, /me/deactivate)
  - sign-in while deactivated
  - support recovery    (/api/v1/admin/users/{id}/reactivate)
  - the scheduled permanent deletion, and registering the freed address again

Same client pattern as ``test_settings_api.py``: an in-loop httpx client with a
fresh session per request, and ``get_current_user`` overridden to load the
acting user from that request's session.
"""
import re
import uuid
from datetime import datetime, timedelta

import httpx
import pytest
import pytest_asyncio
from fastapi import Depends
from httpx import ASGITransport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.admin import require_platform_admin
from app.core.config import settings
from app.core.dependencies import get_current_user
from app.core.security import get_password_hash
from app.database import get_db
from app.main import app
from app.models.user import ApiKey, Organization, OrganizationMember, User
from app.services import account_deletion
from app.services.auth import login_throttle

PASSWORD = "password123"
_ACTING: dict = {"id": None}


async def _make_user(db, email: str, *, password: str | None = PASSWORD, **extra) -> User:
    user = User(
        email=email,
        hashed_password=get_password_hash(password) if password else None,
        full_name=extra.pop("full_name", "Someone"),
        is_active=True,
        **extra,
    )
    db.add(user)
    await db.flush()
    return user


async def _make_org(db, owner: User, name: str = "Acme", *, is_active: bool = True) -> Organization:
    org = Organization(
        name=name, slug=f"org-{uuid.uuid4().hex[:8]}", owner_id=owner.id, is_active=is_active
    )
    db.add(org)
    await db.flush()
    db.add(OrganizationMember(organization_id=org.id, user_id=owner.id, role="owner"))
    return org


@pytest_asyncio.fixture
async def owner(db_session) -> User:
    user = await _make_user(
        db_session, "owner@example.com", full_name="Owner", phone_number="+14155552671"
    )
    await _make_org(db_session, user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def admin(db_session) -> User:
    user = await _make_user(db_session, "staff@example.com", is_platform_admin=True)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture(autouse=True)
def outbox(monkeypatch):
    """Capture email instead of sending it. The local .env may point at a real
    mail server, and a test must never deliver to it."""
    from app.services.email.service import email_service

    sent: list = []

    async def _capture(message, *, raise_on_error: bool = False) -> bool:
        sent.append(message)
        return True

    monkeypatch.setattr(email_service, "send", _capture)
    return sent


@pytest_asyncio.fixture
async def client(db_engine):
    sessionmaker = async_sessionmaker(db_engine, expire_on_commit=False)

    async def override_get_db():
        async with sessionmaker() as session:
            yield session

    async def _current_user(db=Depends(get_db)):
        return (await db.execute(select(User).where(User.id == _ACTING["id"]))).scalar_one()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = _current_user
    app.dependency_overrides[require_platform_admin] = _current_user
    login_throttle.reset_all()

    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
    login_throttle.reset_all()


def as_user(client, user: User):
    _ACTING["id"] = user.id
    return client


async def _terms(client, user: User, password: str = PASSWORD) -> dict:
    res = await as_user(client, user).post(
        "/api/v1/users/me/deactivation/verify", json={"password": password}
    )
    assert res.status_code == 200, res.text
    return res.json()


async def _deactivate(client, user: User) -> dict:
    terms = await _terms(client, user)
    res = await as_user(client, user).post(
        "/api/v1/users/me/deactivate", json={"deactivation_token": terms["deactivation_token"]}
    )
    assert res.status_code == 200, res.text
    return res.json()


async def _owned_orgs(db, user: User) -> list:
    owner_id = user.id
    db.expire_all()
    return list(
        (await db.execute(select(Organization).where(Organization.owner_id == owner_id))).scalars()
    )


@pytest.mark.integration
@pytest.mark.asyncio
class TestDeactivating:
    async def test_wrong_password_is_refused_and_changes_nothing(self, client, owner, db_session):
        res = await as_user(client, owner).post(
            "/api/v1/users/me/deactivation/verify", json={"password": "not-it"}
        )
        assert res.status_code == 400
        assert "password" in res.json()["detail"].lower()
        await db_session.refresh(owner)
        assert owner.is_active is True and owner.deactivated_at is None

    async def test_repeated_wrong_passwords_are_locked_out(self, client, owner, monkeypatch):
        monkeypatch.setattr(settings, "RATE_LIMIT_LOGIN_ATTEMPTS", 3)
        for _ in range(3):
            await as_user(client, owner).post(
                "/api/v1/users/me/deactivation/verify", json={"password": "nope"}
            )
        res = await as_user(client, owner).post(
            "/api/v1/users/me/deactivation/verify", json={"password": PASSWORD}
        )
        assert res.status_code == 429

    async def test_right_password_returns_the_terms_and_changes_nothing(self, client, owner, db_session):
        terms = await _terms(client, owner)
        assert terms["retention_days"] == 30
        assert terms["support_email"]
        assert terms["deactivation_token"]
        await db_session.refresh(owner)
        assert owner.is_active is True

    async def test_cannot_deactivate_without_passing_the_check(self, client, owner, db_session):
        res = await as_user(client, owner).post(
            "/api/v1/users/me/deactivate", json={"deactivation_token": "made-up"}
        )
        assert res.status_code == 400
        await db_session.refresh(owner)
        assert owner.is_active is True

    async def test_the_old_one_click_delete_is_gone(self, client, owner, db_session):
        res = await as_user(client, owner).delete("/api/v1/users/me")
        assert res.status_code == 405
        await db_session.refresh(owner)
        assert owner.is_active is True

    async def test_a_token_from_another_account_is_refused(self, client, owner, db_session):
        other = await _make_user(db_session, "other@example.com")
        await db_session.commit()
        terms = await _terms(client, other)
        res = await as_user(client, owner).post(
            "/api/v1/users/me/deactivate", json={"deactivation_token": terms["deactivation_token"]}
        )
        assert res.status_code == 400

    async def test_deactivating_keeps_the_account_and_schedules_deletion(self, client, owner, db_session, outbox):
        body = await _deactivate(client, owner)
        assert body["retention_days"] == 30
        (notice,) = outbox
        assert notice.to == "owner@example.com"
        assert "deactivated" in notice.subject and "30 days" in notice.text

        await db_session.refresh(owner)
        assert owner.is_active is False
        assert owner.deactivated_at is not None
        assert owner.deleted_at is None, "deactivated is not permanently deleted"
        assert owner.email == "owner@example.com", "nothing is erased yet"
        assert owner.full_name == "Owner"
        assert owner.token_version == 1, "signed out everywhere"
        kept = owner.deletion_scheduled_at - owner.deactivated_at
        assert kept == timedelta(days=30)

        (org,) = await _owned_orgs(db_session, owner)
        assert org.is_active is False
        assert org.owner_deactivated_at is not None

    async def test_the_admin_retention_setting_is_used(self, client, owner, db_session, monkeypatch):
        monkeypatch.setattr(settings, "ACCOUNT_DELETION_RETENTION_DAYS", 45)
        terms = await _terms(client, owner)
        assert terms["retention_days"] == 45
        await as_user(client, owner).post(
            "/api/v1/users/me/deactivate", json={"deactivation_token": terms["deactivation_token"]}
        )
        await db_session.refresh(owner)
        assert owner.deletion_scheduled_at - owner.deactivated_at == timedelta(days=45)

    async def test_staff_accounts_cannot_deactivate_themselves(self, client, admin):
        res = await as_user(client, admin).post(
            "/api/v1/users/me/deactivation/verify", json={"password": PASSWORD}
        )
        assert res.status_code == 409


@pytest.mark.integration
@pytest.mark.asyncio
class TestAccountsWithoutAPassword:
    """Google/Apple accounts have no password, so they confirm with an emailed code."""

    @pytest_asyncio.fixture
    async def social(self, db_session) -> User:
        user = await _make_user(
            db_session, "social@example.com", password=None, auth_provider="google", google_id="g-1"
        )
        await _make_org(db_session, user)
        await db_session.commit()
        await db_session.refresh(user)
        return user

    async def test_a_code_stands_in_for_the_password(self, client, social, db_session, outbox):
        sent = await as_user(client, social).post("/api/v1/users/me/deactivation/code")
        assert sent.status_code == 200, sent.text
        (message,) = outbox
        assert message.to == "social@example.com"
        code = re.search(r"\b(\d{6})\b", message.text).group(1)

        wrong = await as_user(client, social).post(
            "/api/v1/users/me/deactivation/verify", json={"code": "000000" if code != "000000" else "111111"}
        )
        assert wrong.status_code == 400

        ok = await as_user(client, social).post(
            "/api/v1/users/me/deactivation/verify", json={"code": code}
        )
        assert ok.status_code == 200, ok.text
        res = await as_user(client, social).post(
            "/api/v1/users/me/deactivate", json={"deactivation_token": ok.json()["deactivation_token"]}
        )
        assert res.status_code == 200
        await db_session.refresh(social)
        assert social.deactivated_at is not None

    async def test_an_account_with_a_password_cannot_use_the_code_route(self, client, owner):
        res = await as_user(client, owner).post("/api/v1/users/me/deactivation/code")
        assert res.status_code == 400


@pytest.mark.integration
@pytest.mark.asyncio
class TestSigningInWhileDeactivated:
    async def test_login_is_refused_with_a_way_back(self, client, owner):
        await _deactivate(client, owner)
        res = await client.post(
            "/api/v1/auth/login", json={"email": "owner@example.com", "password": PASSWORD}
        )
        assert res.status_code == 403
        detail = res.json()["detail"]
        assert "deactivated" in detail and "@" in detail

    async def test_a_wrong_password_learns_nothing_about_the_account(self, client, owner):
        await _deactivate(client, owner)
        res = await client.post(
            "/api/v1/auth/login", json={"email": "owner@example.com", "password": "wrong-one"}
        )
        assert res.status_code == 401

    async def test_the_address_cannot_be_registered_again_yet(self, client, owner, monkeypatch):
        monkeypatch.setattr(settings, "REQUIRE_EMAIL_VERIFICATION", False)
        await _deactivate(client, owner)
        res = await client.post(
            "/api/v1/auth/register",
            json={"email": "owner@example.com", "password": "Another!2345", "full_name": "New Person"},
        )
        assert res.status_code == 400


@pytest.mark.integration
@pytest.mark.asyncio
class TestReactivating:
    async def test_admin_sees_and_reactivates_a_deactivated_account(self, client, owner, admin, db_session):
        # A workspace the owner deleted themselves, earlier. It must stay deleted.
        await _make_org(db_session, owner, "Old one", is_active=False)
        await db_session.commit()
        await _deactivate(client, owner)

        listing = await as_user(client, admin).get("/api/v1/admin/users", params={"filter": "deactivated"})
        assert listing.status_code == 200, listing.text
        body = listing.json()
        assert body["retention_days"] == 30
        (row,) = body["items"]
        assert row["email"] == "owner@example.com"
        assert row["status"] == "deactivated"
        assert row["deactivated_at"] and row["deletion_scheduled_at"]

        res = await as_user(client, admin).post(f"/api/v1/admin/users/{owner.id}/reactivate")
        assert res.status_code == 200, res.text
        assert res.json()["status"] == "active"
        assert res.json()["workspaces_restored"] == ["Acme"]

        await db_session.refresh(owner)
        assert owner.is_active is True
        assert owner.deactivated_at is None and owner.deletion_scheduled_at is None

        orgs = {o.name: o for o in await _owned_orgs(db_session, owner)}
        assert orgs["Acme"].is_active is True and orgs["Acme"].owner_deactivated_at is None
        assert orgs["Old one"].is_active is False

        login = await client.post(
            "/api/v1/auth/login", json={"email": "owner@example.com", "password": PASSWORD}
        )
        assert login.status_code == 200, login.text

    async def test_a_reactivated_account_is_not_deleted_later(self, client, owner, admin, db_session):
        await _deactivate(client, owner)
        await as_user(client, admin).post(f"/api/v1/admin/users/{owner.id}/reactivate")
        purged = await account_deletion.purge_due_accounts(
            db_session, now=datetime.utcnow() + timedelta(days=400)
        )
        assert purged == 0
        await db_session.refresh(owner)
        assert owner.email == "owner@example.com"

    async def test_reactivating_an_account_that_is_not_deactivated_is_refused(self, client, owner, admin):
        res = await as_user(client, admin).post(f"/api/v1/admin/users/{owner.id}/reactivate")
        assert res.status_code == 409

    async def test_an_admin_disabled_account_is_never_deleted_automatically(self, client, owner, admin, db_session):
        res = await as_user(client, admin).patch(
            f"/api/v1/admin/users/{owner.id}", json={"is_active": False}
        )
        assert res.status_code == 200 and res.json()["status"] == "disabled"
        purged = await account_deletion.purge_due_accounts(
            db_session, now=datetime.utcnow() + timedelta(days=400)
        )
        assert purged == 0


@pytest.mark.integration
@pytest.mark.asyncio
class TestPermanentDeletion:
    async def test_nothing_is_deleted_before_the_date(self, client, owner, db_session):
        await _deactivate(client, owner)
        purged = await account_deletion.purge_due_accounts(
            db_session, now=datetime.utcnow() + timedelta(days=29)
        )
        assert purged == 0
        await db_session.refresh(owner)
        assert owner.email == "owner@example.com" and owner.deleted_at is None

    async def test_after_the_date_the_account_is_erased(self, client, owner, db_session):
        owner_id = owner.id
        # Things that must go with the account.
        (org,) = await _owned_orgs(db_session, owner)
        teammate = await _make_user(db_session, "boss@example.com")
        their_org = await _make_org(db_session, teammate, "Their workspace")
        db_session.add(OrganizationMember(organization_id=their_org.id, user_id=owner_id, role="member"))
        db_session.add(
            ApiKey(user_id=owner_id, organization_id=org.id, name="k", key_hash=uuid.uuid4().hex, key_prefix="vcon_ab")
        )
        await db_session.commit()
        await db_session.refresh(owner)
        their_org_id = their_org.id

        await _deactivate(client, owner)
        purged = await account_deletion.purge_due_accounts(
            db_session, now=datetime.utcnow() + timedelta(days=31)
        )
        assert purged == 1

        db_session.expire_all()
        gone = await db_session.get(User, owner_id)
        assert gone.deleted_at is not None
        assert gone.email.endswith("@deleted.invalid")
        assert gone.full_name is None and gone.phone_number is None
        assert gone.hashed_password is None
        assert gone.is_active is False

        keys = (await db_session.execute(select(ApiKey).where(ApiKey.user_id == owner_id))).scalars().all()
        assert keys == []
        memberships = (
            await db_session.execute(
                select(OrganizationMember).where(
                    OrganizationMember.user_id == owner_id,
                    OrganizationMember.organization_id == their_org_id,
                )
            )
        ).scalars().all()
        assert memberships == [], "removed from other people's workspaces"

        # Running again finds nothing left to do.
        assert await account_deletion.purge_due_accounts(
            db_session, now=datetime.utcnow() + timedelta(days=40)
        ) == 0

    async def test_the_address_registers_again_as_a_brand_new_account(self, client, owner, db_session, monkeypatch):
        monkeypatch.setattr(settings, "REQUIRE_EMAIL_VERIFICATION", False)
        old_id = owner.id
        await _deactivate(client, owner)
        assert await account_deletion.purge_due_accounts(
            db_session, now=datetime.utcnow() + timedelta(days=31)
        ) == 1

        res = await client.post(
            "/api/v1/auth/register",
            json={"email": "owner@example.com", "password": "Another!2345", "full_name": "New Person"},
        )
        assert res.status_code in (200, 201), res.text

        db_session.expire_all()
        fresh = (
            await db_session.execute(select(User).where(User.email == "owner@example.com"))
        ).scalar_one()
        assert fresh.id != old_id
        assert fresh.is_active is True and fresh.deactivated_at is None

        login = await client.post(
            "/api/v1/auth/login", json={"email": "owner@example.com", "password": "Another!2345"}
        )
        assert login.status_code == 200, login.text
        old = await client.post(
            "/api/v1/auth/login", json={"email": "owner@example.com", "password": PASSWORD}
        )
        assert old.status_code == 401, "the old password belongs to an account that no longer exists"

    async def test_the_freed_address_gets_a_signup_code_like_any_new_one(self, client, owner, db_session, outbox):
        """Sign-up starts by emailing a code, and that step refuses addresses
        that already have an account."""
        refused = await client.post("/api/v1/auth/email/send-code", json={"email": "owner@example.com"})
        assert refused.status_code in (400, 409)

        await _deactivate(client, owner)
        still = await client.post("/api/v1/auth/email/send-code", json={"email": "owner@example.com"})
        assert still.status_code in (400, 409), "a deactivated account still holds its address"

        await account_deletion.purge_due_accounts(
            db_session, now=datetime.utcnow() + timedelta(days=31)
        )
        outbox.clear()
        res = await client.post("/api/v1/auth/email/send-code", json={"email": "owner@example.com"})
        assert res.status_code == 200, res.text
        (message,) = outbox
        assert message.to == "owner@example.com" and re.search(r"\b\d{6}\b", message.text)

    async def test_the_owner_is_told_when_the_account_is_deleted(self, client, owner, db_session, outbox):
        await _deactivate(client, owner)
        outbox.clear()
        await account_deletion.purge_due_accounts(
            db_session, now=datetime.utcnow() + timedelta(days=31)
        )
        (message,) = outbox
        assert message.to == "owner@example.com", "sent to the real address, not the tombstone"
        assert "permanently deleted" in message.subject

    async def test_an_admin_can_delete_a_deactivated_account_early(self, client, owner, admin, db_session):
        owner_id = owner.id
        await _deactivate(client, owner)
        res = await as_user(client, admin).delete(f"/api/v1/admin/users/{owner_id}")
        assert res.status_code == 200, res.text
        db_session.expire_all()
        gone = await db_session.get(User, owner_id)
        assert gone.deleted_at is not None and gone.email.endswith("@deleted.invalid")
