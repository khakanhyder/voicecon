"""
The blog: console API (/api/v1/admin/blog), public API (/api/v1/blog) and roles.

What matters most:

* Roles are enforced by the API, not the menu: a blog viewer can read but not
  write, and neither blog role reaches any other admin endpoint.
* Customers (no console role) are refused everywhere in the console.
* Only live posts are public: drafts and scheduled posts are 404 / not listed.
* Post bodies are sanitised on the way in.

Same harness as ``test_admin_api``: in-loop httpx client, per-request DB
sessions, and ``get_current_user`` loading the acting user from that session.
"""
from datetime import datetime, timedelta, timezone

import httpx
import pytest
import pytest_asyncio
from fastapi import Depends
from httpx import ASGITransport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.dependencies import get_current_user
from app.core.security import get_password_hash
from app.database import get_db
from app.main import app
from app.models.blog import BlogPost
from app.models.platform import AdminAuditLog
from app.models.user import User

_ACTING: dict = {"id": None}
PASSWORD = "Blog-Console-Pass-2026"


async def _make_user(db, email, *, admin=False, blog_role=None) -> User:
    user = User(
        email=email,
        hashed_password=get_password_hash(PASSWORD),
        full_name=email.split("@")[0].title(),
        is_active=True,
        is_verified=True,
        is_platform_admin=admin,
        blog_role=blog_role,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest_asyncio.fixture
async def admin(db_session) -> User:
    return await _make_user(db_session, "admin@example.com", admin=True)


@pytest_asyncio.fixture
async def editor(db_session) -> User:
    return await _make_user(db_session, "editor@example.com", blog_role="editor")


@pytest_asyncio.fixture
async def viewer(db_session) -> User:
    return await _make_user(db_session, "viewer@example.com", blog_role="viewer")


@pytest_asyncio.fixture
async def customer(db_session) -> User:
    return await _make_user(db_session, "customer@example.com")


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
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


def as_user(client, user):
    _ACTING["id"] = user.id
    return client


async def _create(client, **fields):
    body = {"title": "Hello voice agents", "content_html": "<p>Body text here.</p>", **fields}
    res = await client.post("/api/v1/admin/blog/posts", json=body)
    assert res.status_code == 201, res.text
    return res.json()


# ---------- Roles ----------
@pytest.mark.integration
@pytest.mark.asyncio
class TestRoles:
    async def test_me_reports_role_and_permissions(self, client, admin, editor, viewer):
        me = (await as_user(client, viewer).get("/api/v1/admin/me")).json()
        assert me["role"] == "blog_viewer" and me["permissions"] == ["blog:read"]
        me = (await as_user(client, editor).get("/api/v1/admin/me")).json()
        assert me["role"] == "blog_editor" and "blog:write" in me["permissions"]
        me = (await as_user(client, admin).get("/api/v1/admin/me")).json()
        assert me["role"] == "admin" and "admin" in me["permissions"]

    async def test_customer_is_refused_everywhere(self, client, customer):
        as_user(client, customer)
        assert (await client.get("/api/v1/admin/me")).status_code == 403
        assert (await client.get("/api/v1/admin/blog/posts")).status_code == 403
        assert (await client.post("/api/v1/admin/blog/posts", json={"title": "x"})).status_code == 403

    async def test_blog_roles_cannot_reach_other_admin_endpoints(self, client, editor, viewer):
        for user in (editor, viewer):
            as_user(client, user)
            for path in ("/api/v1/admin/overview", "/api/v1/admin/users", "/api/v1/admin/settings",
                         "/api/v1/admin/blog/team"):
                res = await client.get(path)
                assert res.status_code == 403, (user.email, path, res.status_code)

    async def test_viewer_reads_but_cannot_write(self, client, editor, viewer):
        post = await _create(as_user(client, editor))
        as_user(client, viewer)
        assert (await client.get("/api/v1/admin/blog/posts")).json()["total"] == 1
        assert (await client.get(f"/api/v1/admin/blog/posts/{post['id']}")).status_code == 200
        assert (await client.get("/api/v1/admin/blog/overview")).status_code == 200
        writes = [
            client.post("/api/v1/admin/blog/posts", json={"title": "x"}),
            client.put(f"/api/v1/admin/blog/posts/{post['id']}", json={"title": "x"}),
            client.post(f"/api/v1/admin/blog/posts/{post['id']}/publish"),
            client.post(f"/api/v1/admin/blog/posts/{post['id']}/unpublish"),
            client.delete(f"/api/v1/admin/blog/posts/{post['id']}"),
            client.post("/api/v1/admin/blog/categories", json={"name": "News"}),
        ]
        for request in writes:
            assert (await request).status_code == 403

    async def test_revoking_a_role_applies_on_the_next_request(self, client, admin, viewer):
        as_user(client, viewer)
        assert (await client.get("/api/v1/admin/blog/posts")).status_code == 200
        res = await as_user(client, admin).delete(f"/api/v1/admin/blog/team/{viewer.id}")
        assert res.status_code == 200
        assert (await as_user(client, viewer).get("/api/v1/admin/blog/posts")).status_code == 403

    async def test_blog_user_can_sign_in_to_the_console_but_customer_cannot(self, client, viewer, customer):
        res = await client.post("/api/v1/auth/admin/login", json={"email": viewer.email, "password": PASSWORD})
        assert res.status_code == 200, res.text
        res = await client.post("/api/v1/auth/admin/login", json={"email": customer.email, "password": PASSWORD})
        assert res.status_code == 401


# ---------- Team ----------
@pytest.mark.integration
@pytest.mark.asyncio
class TestTeam:
    async def test_admin_creates_a_blog_editor_account(self, client, admin, db_session):
        res = await as_user(client, admin).post(
            "/api/v1/admin/blog/team",
            json={"email": "New.Writer@Example.com", "full_name": "New Writer", "role": "editor", "password": PASSWORD},
        )
        assert res.status_code == 201, res.text
        assert res.json()["created"] is True and res.json()["role"] == "blog_editor"
        user = (await db_session.execute(select(User).where(User.email == "new.writer@example.com"))).scalar_one()
        assert user.blog_role == "editor" and not user.is_platform_admin
        actions = (await db_session.execute(select(AdminAuditLog.action))).scalars().all()
        assert "blog.team.add" in actions

    async def test_new_account_needs_a_password(self, client, admin):
        res = await as_user(client, admin).post(
            "/api/v1/admin/blog/team", json={"email": "x@example.com", "role": "viewer"}
        )
        assert res.status_code == 422

    async def test_existing_account_keeps_its_password(self, client, admin, customer, db_session):
        before = customer.hashed_password
        res = await as_user(client, admin).post(
            "/api/v1/admin/blog/team", json={"email": customer.email, "role": "viewer", "password": "Other-Pass-9911"}
        )
        assert res.status_code == 201 and res.json()["created"] is False
        await db_session.refresh(customer)
        assert customer.blog_role == "viewer" and customer.hashed_password == before

    async def test_editor_cannot_manage_the_team(self, client, editor):
        res = await as_user(client, editor).post(
            "/api/v1/admin/blog/team", json={"email": "y@example.com", "role": "editor", "password": PASSWORD}
        )
        assert res.status_code == 403


# ---------- Posts ----------
@pytest.mark.integration
@pytest.mark.asyncio
class TestPosts:
    async def test_create_sanitises_and_fills_defaults(self, client, editor):
        post = await _create(
            as_user(client, editor),
            title="GEO Services: A Guide!",
            content_html='<p onclick="x()">Hi</p><script>alert(1)</script><a href="javascript:alert(1)">bad</a>',
        )
        assert post["slug"] == "geo-services-a-guide"
        assert "script" not in post["content_html"] and "onclick" not in post["content_html"]
        assert "javascript:" not in post["content_html"]
        assert post["status"] == "draft"
        assert post["author"]["name"] == "Editor"
        assert post["excerpt"]  # generated from the body

    async def test_tables_survive_sanitising(self, client, editor):
        post = await _create(
            as_user(client, editor),
            title="Comparison",
            content_html=(
                '<table style="min-width:50px"><colgroup><col style="min-width:25px"></colgroup><tbody>'
                '<tr><th colspan="1" rowspan="1" onclick="x()"><p>Capability</p></th><th colspan="2"><p>AI</p></th></tr>'
                '<tr><td rowspan="2"><p>Yes</p></td></tr></tbody></table>'
            ),
        )
        html = post["content_html"]
        assert "<table>" in html and "<tbody>" in html and "<th colspan=\"2\">" in html
        assert "<td rowspan=\"2\">" in html
        assert "onclick" not in html and "min-width" not in html
        assert post["excerpt"] == ""  # cell text is not used as a summary

    async def test_duplicate_titles_get_distinct_slugs_but_explicit_clash_is_409(self, client, editor):
        as_user(client, editor)
        first = await _create(client)
        second = await _create(client)
        assert second["slug"] == f"{first['slug']}-2"
        res = await client.put(f"/api/v1/admin/blog/posts/{second['id']}", json={"slug": first["slug"]})
        assert res.status_code == 409

    async def test_publish_requires_content(self, client, editor):
        as_user(client, editor)
        res = await client.post("/api/v1/admin/blog/posts", json={"title": "Empty", "status": "published"})
        assert res.status_code == 422

    async def test_status_filters_and_scheduled(self, client, editor):
        as_user(client, editor)
        draft = await _create(client, title="Draft one")
        live = await _create(client, title="Live one")
        await client.post(f"/api/v1/admin/blog/posts/{live['id']}/publish")
        future = (datetime.now(timezone.utc) + timedelta(days=3)).isoformat()
        sched = await _create(client, title="Later one", status="published", published_at=future)
        assert sched["status"] == "scheduled"

        async def ids(status):
            body = (await client.get("/api/v1/admin/blog/posts", params={"status": status})).json()
            return {p["id"] for p in body["items"]}

        assert await ids("draft") == {draft["id"]}
        assert await ids("published") == {live["id"]}
        assert await ids("scheduled") == {sched["id"]}
        counts = (await client.get("/api/v1/admin/blog/overview")).json()["counts"]
        assert counts == {**counts, "total": 3, "draft": 1, "published": 1, "scheduled": 1}

    async def test_search_and_author_filter(self, client, editor, admin):
        await _create(as_user(client, editor), title="Voice agents for dentists")
        await _create(as_user(client, admin), title="Workflow tips")
        body = (await client.get("/api/v1/admin/blog/posts", params={"q": "dentist"})).json()
        assert [p["title"] for p in body["items"]] == ["Voice agents for dentists"]
        body = (await client.get("/api/v1/admin/blog/posts", params={"author_id": str(admin.id)})).json()
        assert [p["title"] for p in body["items"]] == ["Workflow tips"]

    async def test_deleting_a_category_keeps_its_posts(self, client, editor, db_session):
        as_user(client, editor)
        category = (await client.post("/api/v1/admin/blog/categories", json={"name": "Guides"})).json()
        post = await _create(client, category_id=category["id"])
        assert post["category"]["slug"] == "guides"
        assert (await client.delete(f"/api/v1/admin/blog/categories/{category['id']}")).status_code == 200
        again = (await client.get(f"/api/v1/admin/blog/posts/{post['id']}")).json()
        assert again["category"] is None

    async def test_delete(self, client, editor, db_session):
        post = await _create(as_user(client, editor))
        assert (await client.delete(f"/api/v1/admin/blog/posts/{post['id']}")).status_code == 200
        assert (await db_session.execute(select(BlogPost))).first() is None


# ---------- Public ----------
@pytest.mark.integration
@pytest.mark.asyncio
class TestPublic:
    async def test_only_live_posts_are_public(self, client, editor):
        as_user(client, editor)
        draft = await _create(client, title="Secret draft")
        live = await _create(client, title="Live post")
        await client.post(f"/api/v1/admin/blog/posts/{live['id']}/publish")
        future = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
        sched = await _create(client, title="Future post", status="published", published_at=future)

        listing = (await client.get("/api/v1/blog/posts")).json()
        assert [p["slug"] for p in listing["items"]] == [live["slug"]]
        assert (await client.get(f"/api/v1/blog/posts/{live['slug']}")).status_code == 200
        assert (await client.get(f"/api/v1/blog/posts/{draft['slug']}")).status_code == 404
        assert (await client.get(f"/api/v1/blog/posts/{sched['slug']}")).status_code == 404

        await client.post(f"/api/v1/admin/blog/posts/{live['id']}/unpublish")
        assert (await client.get(f"/api/v1/blog/posts/{live['slug']}")).status_code == 404

    async def test_highlights_put_featured_first_and_related_excludes_self(self, client, editor):
        as_user(client, editor)
        slugs = []
        for i, featured in enumerate((True, False, False)):
            post = await _create(client, title=f"Post {i}", is_featured=featured)
            await client.post(f"/api/v1/admin/blog/posts/{post['id']}/publish")
            slugs.append(post["slug"])
        highlights = (await client.get("/api/v1/blog/highlights", params={"limit": 3})).json()
        assert highlights[0]["slug"] == slugs[0]
        detail = (await client.get(f"/api/v1/blog/posts/{slugs[1]}")).json()
        assert slugs[1] not in {p["slug"] for p in detail["related"]}
        assert len(detail["related"]) == 2
        assert "content_html" not in highlights[0]
