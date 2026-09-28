"""
Integration tests for changing the account email
(/api/v1/users/me/email/change-request and /change-confirm).

The point of the flow is that the account moves to a new address only after
the person proves they receive mail there, so most of these tests are about
what must *not* change.
"""
import uuid
from datetime import datetime, timedelta

import httpx
import pytest
import pytest_asyncio
from fastapi import Depends
from httpx import ASGITransport
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.dependencies import get_current_user
from app.core.security import decode_token, get_password_hash
from app.database import get_db
from app.main import app
from app.models.user import Organization, OrganizationMember, User
from app.models.verification import VerificationCode
from app.services.email.service import email_service

PASSWORD = "Correct-horse-42"
OLD = "owner@example.com"
NEW = "new.address@example.com"
REQUEST = "/api/v1/users/me/email/change-request"
CONFIRM = "/api/v1/users/me/email/change-confirm"

_ACTING: dict = {"id": None}


async def _user(db_session, email: str, password: "str | None" = PASSWORD, **fields) -> User:
    user = User(
        email=email,
        hashed_password=get_password_hash(password) if password else None,
        full_name="Owner",
        is_active=True,
        is_verified=True,
        **fields,
    )
    db_session.add(user)
    await db_session.flush()
    org = Organization(
        name="Acme", slug=f"acme-{uuid.uuid4().hex[:8]}", owner_id=user.id,
        is_active=True, billing_email=email,
    )
    db_session.add(org)
    await db_session.flush()
    db_session.add(OrganizationMember(organization_id=org.id, user_id=user.id, role="owner"))
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def owner(db_session) -> User:
    return await _user(db_session, OLD)


@pytest_asyncio.fixture
async def client(db_engine):
    sessionmaker = async_sessionmaker(db_engine, expire_on_commit=False)

    async def override_get_db():
        async with sessionmaker() as session:
            yield session

    async def _current_user(db=Depends(get_db)):
        result = await db.execute(select(User).where(User.id == _ACTING["id"]))
        return result.scalar_one()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = _current_user
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


def acting(client, user: User):
    _ACTING["id"] = user.id
    return client


@pytest.fixture
def outbox(monkeypatch):
    """Everything the app tried to email, instead of sending it."""
    sent = {"codes": [], "notices": []}

    async def send_verification_code(**kwargs):
        sent["codes"].append(kwargs)
        return True

    async def send_email_changed_notice(**kwargs):
        sent["notices"].append(kwargs)
        return True

    monkeypatch.setattr(email_service, "send_verification_code", send_verification_code)
    monkeypatch.setattr(email_service, "send_email_changed_notice", send_email_changed_notice)
    return sent


async def _email_of(db_session, user: User) -> str:
    # A column select reads the row as it is now, not the session's copy.
    return (await db_session.execute(select(User.email).where(User.id == user.id))).scalar_one()


async def _request(client, new_email=NEW, password=PASSWORD):
    return await client.post(REQUEST, json={"new_email": new_email, "current_password": password})


@pytest.mark.integration
@pytest.mark.asyncio
class TestEmailChange:
    async def test_the_address_changes_only_after_the_code_is_confirmed(
        self, client, owner, outbox, db_session
    ):
        before_version = owner.token_version or 0

        asked = await _request(acting(client, owner))
        assert asked.status_code == 200, asked.text
        assert await _email_of(db_session, owner) == OLD

        mail = outbox["codes"][0]
        assert mail["to_email"] == NEW
        assert mail["purpose"] == "email_change"
        assert mail["code"] not in asked.text

        done = await client.post(CONFIRM, json={"new_email": NEW, "code": mail["code"]})
        assert done.status_code == 200, done.text
        assert await _email_of(db_session, owner) == NEW

        body = done.json()
        assert body["user"]["email"] == NEW
        # The caller stays signed in on tokens for the new version; every other
        # session, still on the old version, is signed out.
        claims = decode_token(body["access_token"])
        assert claims["sub"] == str(owner.id)
        version, verified = (
            await db_session.execute(
                select(User.token_version, User.is_verified).where(User.id == owner.id)
            )
        ).one()
        assert version == before_version + 1
        assert verified is True

    async def test_the_previous_address_is_told(self, client, owner, outbox):
        await _request(acting(client, owner))
        await client.post(CONFIRM, json={"new_email": NEW, "code": outbox["codes"][0]["code"]})
        assert outbox["notices"] == [
            {"old_email": OLD, "new_email": NEW, "recipient_name": "Owner"}
        ]

    async def test_billing_follows_the_owner_to_the_new_address(
        self, client, owner, outbox, db_session
    ):
        await _request(acting(client, owner))
        await client.post(CONFIRM, json={"new_email": NEW, "code": outbox["codes"][0]["code"]})
        billing_email = (
            await db_session.execute(
                select(Organization.billing_email).where(Organization.owner_id == owner.id)
            )
        ).scalar_one()
        assert billing_email == NEW

    async def test_the_new_address_is_stored_lowercased(self, client, owner, outbox, db_session):
        await _request(acting(client, owner), new_email="New.Address@Example.COM")
        done = await client.post(
            CONFIRM, json={"new_email": "NEW.address@example.com", "code": outbox["codes"][0]["code"]}
        )
        assert done.status_code == 200
        assert await _email_of(db_session, owner) == NEW

    async def test_a_wrong_password_sends_nothing(self, client, owner, outbox, db_session):
        res = await _request(acting(client, owner), password="not-my-password")
        assert res.status_code == 400
        assert outbox["codes"] == []
        assert (await db_session.execute(select(VerificationCode))).first() is None

    async def test_a_password_is_required_when_the_account_has_one(self, client, owner, outbox):
        res = await acting(client, owner).post(REQUEST, json={"new_email": NEW})
        assert res.status_code == 400
        assert outbox["codes"] == []

    async def test_an_account_without_a_password_can_still_change(
        self, client, outbox, db_session
    ):
        social = await _user(
            db_session, "social@example.com", password=None,
            auth_provider="google", google_id="google-sub-1",
        )
        asked = await acting(client, social).post(REQUEST, json={"new_email": NEW})
        assert asked.status_code == 200
        done = await client.post(CONFIRM, json={"new_email": NEW, "code": outbox["codes"][0]["code"]})
        assert done.status_code == 200
        # Google signs them in by its own id, so the link survives the change.
        google_id = (
            await db_session.execute(select(User.google_id).where(User.id == social.id))
        ).scalar_one()
        assert google_id == "google-sub-1"

    async def test_an_address_another_account_uses_is_refused(
        self, client, owner, outbox, db_session
    ):
        await _user(db_session, NEW)
        res = await _request(acting(client, owner))
        assert res.status_code == 409
        assert "already used" in res.json()["detail"]
        assert outbox["codes"] == []

    async def test_an_address_taken_while_the_code_was_in_the_inbox_is_refused(
        self, client, owner, outbox, db_session
    ):
        await _request(acting(client, owner))
        await _user(db_session, NEW)
        res = await client.post(CONFIRM, json={"new_email": NEW, "code": outbox["codes"][0]["code"]})
        assert res.status_code == 409
        assert await _email_of(db_session, owner) == OLD

    async def test_the_current_address_is_refused(self, client, owner, outbox):
        res = await _request(acting(client, owner), new_email="OWNER@example.com")
        assert res.status_code == 400
        assert outbox["codes"] == []

    async def test_a_wrong_code_changes_nothing(self, client, owner, outbox, db_session):
        await _request(acting(client, owner))
        real = outbox["codes"][0]["code"]
        wrong = "000000" if real != "000000" else "111111"

        res = await client.post(CONFIRM, json={"new_email": NEW, "code": wrong})

        assert res.status_code == 400
        assert await _email_of(db_session, owner) == OLD
        assert outbox["notices"] == []

    async def test_a_code_stops_working_after_too_many_wrong_guesses(
        self, client, owner, outbox, db_session
    ):
        await _request(acting(client, owner))
        real = outbox["codes"][0]["code"]
        wrong = "000000" if real != "000000" else "111111"
        for _ in range(5):
            await client.post(CONFIRM, json={"new_email": NEW, "code": wrong})

        res = await client.post(CONFIRM, json={"new_email": NEW, "code": real})

        assert res.status_code == 400
        assert await _email_of(db_session, owner) == OLD

    async def test_confirming_without_asking_first_changes_nothing(
        self, client, owner, outbox, db_session
    ):
        res = await acting(client, owner).post(CONFIRM, json={"new_email": NEW, "code": "123456"})
        assert res.status_code == 400
        assert await _email_of(db_session, owner) == OLD

    async def test_an_expired_code_is_refused(self, client, owner, outbox, db_session):
        await _request(acting(client, owner))
        await db_session.execute(
            update(VerificationCode).values(expires_at=datetime.utcnow() - timedelta(minutes=1))
        )
        await db_session.commit()

        res = await client.post(CONFIRM, json={"new_email": NEW, "code": outbox["codes"][0]["code"]})

        assert res.status_code == 400
        assert "expired" in res.json()["detail"]
        assert await _email_of(db_session, owner) == OLD

    async def test_a_code_works_once(self, client, owner, outbox, db_session):
        await _request(acting(client, owner))
        code = outbox["codes"][0]["code"]
        await client.post(CONFIRM, json={"new_email": NEW, "code": code})

        # Moving on to a third address cannot reuse the code for the second.
        again = await client.post(CONFIRM, json={"new_email": "third@example.com", "code": code})
        assert again.status_code == 400
        assert await _email_of(db_session, owner) == NEW

    async def test_a_code_only_works_for_the_address_it_was_sent_to(
        self, client, owner, outbox, db_session
    ):
        await _request(acting(client, owner))
        res = await client.post(
            CONFIRM, json={"new_email": "attacker@example.com", "code": outbox["codes"][0]["code"]}
        )
        assert res.status_code == 400
        assert await _email_of(db_session, owner) == OLD

    async def test_a_code_only_works_for_the_account_that_asked(
        self, client, owner, outbox, db_session
    ):
        other = await _user(db_session, "other@example.com")
        await _request(acting(client, owner))
        code = outbox["codes"][0]["code"]

        res = await acting(client, other).post(CONFIRM, json={"new_email": NEW, "code": code})

        assert res.status_code == 400
        assert await _email_of(db_session, other) == "other@example.com"
        assert await _email_of(db_session, owner) == OLD

    async def test_resending_waits_out_the_cooldown_then_replaces_the_code(
        self, client, owner, outbox, db_session
    ):
        await _request(acting(client, owner))
        first = outbox["codes"][0]["code"]

        too_soon = await _request(client)
        assert too_soon.status_code == 429
        assert too_soon.headers["retry-after"]
        assert len(outbox["codes"]) == 1

        await db_session.execute(
            update(VerificationCode).values(created_at=datetime.utcnow() - timedelta(minutes=2))
        )
        await db_session.commit()
        resent = await _request(client)
        assert resent.status_code == 200
        second = outbox["codes"][1]["code"]

        if first != second:
            stale = await client.post(CONFIRM, json={"new_email": NEW, "code": first})
            assert stale.status_code == 400
        done = await client.post(CONFIRM, json={"new_email": NEW, "code": second})
        assert done.status_code == 200
        assert await _email_of(db_session, owner) == NEW

    async def test_the_profile_update_cannot_be_used_to_skip_verification(
        self, client, owner, db_session
    ):
        res = await acting(client, owner).patch(
            "/api/v1/users/me", json={"email": NEW, "full_name": "Renamed"}
        )
        assert res.status_code == 200
        assert res.json()["email"] == OLD
        assert await _email_of(db_session, owner) == OLD

    async def test_an_address_that_is_not_an_email_is_refused(self, client, owner, outbox):
        res = await _request(acting(client, owner), new_email="not-an-email")
        assert res.status_code == 422
        assert outbox["codes"] == []
