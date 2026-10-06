"""
The staff console's blog section, mounted at ``/api/v1/admin``.

Unlike the rest of the admin API this router is open to blog users as well as
platform admins, so it is mounted *outside* the platform-admin router and every
route names its own guard:

* ``require_blog_reader`` — any console user (admin, blog editor, blog viewer).
* ``require_blog_editor`` — admins and blog editors: anything that writes.
* ``require_platform_admin`` — the blog team page: who gets a blog role.

``/admin/me`` lives here too, because blog users need it to load the console.
"""
from __future__ import annotations

import re
import uuid
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import extract, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.admin import (
    BLOG_ROLES,
    audit,
    console_permissions,
    console_role,
    require_blog_editor,
    require_blog_reader,
    require_console_user,
    require_platform_admin,
)
from app.core.passwords import PasswordPolicyError, validate_password
from app.core.security import get_password_hash
from app.core.time import utc_iso
from app.core.urls import public_base_url
from app.database import get_db
from app.models.blog import POST_DRAFT, POST_PUBLISHED, BlogCategory, BlogPost
from app.models.user import User
from app.services.auth.verification import normalize_email
from app.services.blog.content import excerpt_from, normalize_tags, reading_minutes, sanitize_html, slugify
from app.services.blog.images import MAX_BYTES as MAX_IMAGE_BYTES, store_blog_image
from app.services.storage import StorageError

from ..admin._common import PageParams, like, paginated, parse_uuid, utcnow
from ._views import console_detail, console_row

router = APIRouter()

_URL_RE = re.compile(r"^https?://", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Who is signed in
# ---------------------------------------------------------------------------


@router.get("/me")
async def console_me(user=Depends(require_console_user)):
    """The signed-in console user and what they may do; the console builds its menu from this."""
    return {
        "id": str(user.id),
        "email": user.email,
        "full_name": user.full_name,
        "avatar_url": user.avatar_url,
        "role": console_role(user),
        "permissions": console_permissions(user),
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _naive_utc(value: Optional[datetime]) -> Optional[datetime]:
    """The database stores naive UTC; the console sends ISO with an offset."""
    if value is None:
        return None
    if value.tzinfo is not None:
        value = value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def _clean_url(value: Optional[str], what: str) -> Optional[str]:
    value = (value or "").strip()
    if not value:
        return None
    if not _URL_RE.match(value) or len(value) > 2000:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"The {what} must be an http(s) link.")
    return value


def _display_name(user: User) -> str:
    return user.full_name or user.email.split("@", 1)[0]


async def _post_or_404(db: AsyncSession, post_id: str) -> BlogPost:
    post = await db.get(BlogPost, parse_uuid(post_id, "post"))
    if post is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    return post


async def _slug_taken(db: AsyncSession, slug: str, exclude_id: Optional[uuid.UUID] = None) -> bool:
    query = select(BlogPost.id).where(BlogPost.slug == slug)
    if exclude_id is not None:
        query = query.where(BlogPost.id != exclude_id)
    return (await db.execute(query.limit(1))).first() is not None


async def _free_slug(db: AsyncSession, base: str, exclude_id: Optional[uuid.UUID] = None) -> str:
    """``base``, or ``base-2``, ``base-3``… whichever is free."""
    base = base or "post"
    candidate, n = base, 2
    while await _slug_taken(db, candidate, exclude_id):
        candidate = f"{base[:190]}-{n}"
        n += 1
    return candidate


async def _console_author(db: AsyncSession, author_id: str) -> User:
    user = await db.get(User, parse_uuid(author_id, "author"))
    if user is None or user.deleted_at is not None or console_role(user) is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The author must be an admin or a member of the blog team.",
        )
    return user


async def _category_or_422(db: AsyncSession, category_id: Optional[str]) -> Optional[BlogCategory]:
    if not category_id:
        return None
    category = await db.get(BlogCategory, parse_uuid(category_id, "category"))
    if category is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="That category no longer exists.")
    return category


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------


@router.get("/blog/overview")
async def blog_overview(db: AsyncSession = Depends(get_db), _=Depends(require_blog_reader)):
    now = utcnow()
    posts = (await db.execute(select(BlogPost))).unique().scalars().all()

    counts = Counter(p.display_status(now) for p in posts)
    month_start = datetime(now.year, now.month, 1)
    live = [p for p in posts if p.display_status(now) == POST_PUBLISHED]

    # Published per month for the last 12 months, oldest first.
    months: List[dict] = []
    year, month = now.year, now.month
    for _ in range(12):
        months.append({"year": year, "month": month, "posts": 0})
        year, month = (year, month - 1) if month > 1 else (year - 1, 12)
    months.reverse()
    index = {(m["year"], m["month"]): m for m in months}
    for p in live:
        bucket = index.get((p.published_at.year, p.published_at.month))
        if bucket:
            bucket["posts"] += 1

    by_category = Counter(p.category.name if p.category else "Uncategorised" for p in posts)
    by_author = Counter(console_row(p, now)["author"]["name"] for p in posts)

    recent = sorted(posts, key=lambda p: p.updated_at or p.created_at, reverse=True)[:6]
    upcoming = sorted(
        (p for p in posts if p.display_status(now) == "scheduled"), key=lambda p: p.published_at
    )[:5]

    return {
        "counts": {
            "total": len(posts),
            "published": counts.get(POST_PUBLISHED, 0),
            "scheduled": counts.get("scheduled", 0),
            "draft": counts.get(POST_DRAFT, 0),
            "featured": sum(1 for p in live if p.is_featured),
            "published_this_month": sum(1 for p in live if p.published_at >= month_start),
        },
        "monthly": months,
        "by_category": [{"name": k, "posts": v} for k, v in by_category.most_common(8)],
        "by_author": [{"name": k, "posts": v} for k, v in by_author.most_common(5)],
        "recent": [console_row(p, now) for p in recent],
        "upcoming": [console_row(p, now) for p in upcoming],
        "generated_at": utc_iso(now),
    }


# ---------------------------------------------------------------------------
# Posts
# ---------------------------------------------------------------------------

_DATE_COLUMNS = {
    "created": BlogPost.created_at,
    "updated": BlogPost.updated_at,
    "published": BlogPost.published_at,
}


@router.get("/blog/posts")
async def list_posts(
    page: PageParams = Depends(),
    q: Optional[str] = Query(None, max_length=200),
    status_filter: Optional[Literal["draft", "published", "scheduled"]] = Query(None, alias="status"),
    author_id: Optional[str] = None,
    category_id: Optional[str] = None,
    date_field: Literal["created", "updated", "published"] = "created",
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    year: Optional[int] = Query(None, ge=2000, le=2100),
    month: Optional[int] = Query(None, ge=1, le=12),
    sort: Literal["newest", "oldest", "title", "updated"] = "newest",
    db: AsyncSession = Depends(get_db),
    _=Depends(require_blog_reader),
):
    now = utcnow()
    column = _DATE_COLUMNS[date_field]
    filters = []
    if q and q.strip():
        term = like(q.strip())
        filters.append(or_(BlogPost.title.ilike(term, escape="\\"), BlogPost.slug.ilike(term, escape="\\")))
    if status_filter == "draft":
        filters.append(BlogPost.status != POST_PUBLISHED)
    elif status_filter == "published":
        filters.append(BlogPost.status == POST_PUBLISHED)
        filters.append(BlogPost.published_at <= now)
    elif status_filter == "scheduled":
        filters.append(BlogPost.status == POST_PUBLISHED)
        filters.append(BlogPost.published_at > now)
    if author_id:
        filters.append(BlogPost.author_id == parse_uuid(author_id, "author"))
    if category_id == "none":
        filters.append(BlogPost.category_id.is_(None))
    elif category_id:
        filters.append(BlogPost.category_id == parse_uuid(category_id, "category"))
    # Days are UTC days, like every other date filter in the console.
    if date_from:
        filters.append(column >= datetime.combine(date_from, datetime.min.time()))
    if date_to:
        filters.append(column < datetime.combine(date_to + timedelta(days=1), datetime.min.time()))
    if year:
        filters.append(extract("year", column) == year)
    if month:
        filters.append(extract("month", column) == month)

    order = {
        "newest": [column.desc().nulls_last(), BlogPost.created_at.desc()],
        "oldest": [column.asc().nulls_last(), BlogPost.created_at.asc()],
        "title": [func.lower(BlogPost.title).asc()],
        "updated": [BlogPost.updated_at.desc()],
    }[sort]

    total = int((await db.execute(select(func.count(BlogPost.id)).where(*filters))).scalar() or 0)
    rows = (
        await db.execute(select(BlogPost).where(*filters).order_by(*order).offset(page.offset).limit(page.page_size))
    ).unique().scalars().all()
    return paginated([console_row(p, now) for p in rows], total, page)


@router.get("/blog/posts/{post_id}")
async def get_post(post_id: str, db: AsyncSession = Depends(get_db), _=Depends(require_blog_reader)):
    return console_detail(await _post_or_404(db, post_id), utcnow())


class PostBody(BaseModel):
    """Every field is optional so the same body serves create and update."""

    title: Optional[str] = Field(None, max_length=200)
    slug: Optional[str] = Field(None, max_length=200)
    excerpt: Optional[str] = Field(None, max_length=400)
    content_html: Optional[str] = Field(None, max_length=500_000)
    featured_image_url: Optional[str] = None
    featured_image_alt: Optional[str] = Field(None, max_length=255)
    social_image_url: Optional[str] = None
    category_id: Optional[str] = None
    tags: Optional[List[str]] = None
    author_id: Optional[str] = None
    status: Optional[Literal["draft", "published"]] = None
    published_at: Optional[datetime] = None
    is_featured: Optional[bool] = None
    seo_title: Optional[str] = Field(None, max_length=200)
    seo_description: Optional[str] = Field(None, max_length=320)

    @field_validator("title", "excerpt", "featured_image_alt", "seo_title", "seo_description", "slug")
    @classmethod
    def _strip(cls, value: Optional[str]) -> Optional[str]:
        return value.strip() if isinstance(value, str) else value


def _check_publishable(post: BlogPost) -> None:
    if not (post.title or "").strip():
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Add a title before publishing.")
    if not (post.content_html or "").strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Write the article before publishing it."
        )


async def _apply(db: AsyncSession, post: BlogPost, body: PostBody, actor: User, creating: bool) -> List[str]:
    """Copy ``body`` onto ``post``; returns the names of the fields that changed."""
    fields = body.model_dump(exclude_unset=True)
    changed: List[str] = []

    def put(name: str, value) -> None:
        if getattr(post, name) != value:
            setattr(post, name, value)
            changed.append(name)

    if "title" in fields:
        if not body.title:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="The title cannot be empty.")
        put("title", body.title)

    if "slug" in fields or creating:
        wanted = slugify(body.slug or "") if body.slug else ""
        if wanted:
            if await _slug_taken(db, wanted, post.id):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Another post already uses that URL. Choose a different slug.",
                )
            put("slug", wanted)
        elif creating or not post.slug:
            put("slug", await _free_slug(db, slugify(post.title), post.id))

    if "content_html" in fields:
        html = sanitize_html(body.content_html)
        put("content_html", html)
        put("reading_minutes", reading_minutes(html))
    if "excerpt" in fields:
        put("excerpt", body.excerpt or None)
    for name, what in (("featured_image_url", "featured image"), ("social_image_url", "share image")):
        if name in fields:
            put(name, _clean_url(fields[name], what))
    for name in ("featured_image_alt", "seo_title", "seo_description"):
        if name in fields:
            put(name, fields[name] or None)
    if "tags" in fields:
        put("tags", normalize_tags(body.tags))
    if "is_featured" in fields and body.is_featured is not None:
        put("is_featured", body.is_featured)
    if "category_id" in fields:
        category = await _category_or_422(db, body.category_id)
        put("category_id", category.id if category else None)
        post.category = category

    if "author_id" in fields and body.author_id:
        author = await _console_author(db, body.author_id)
    elif creating or post.author_id is None:
        author = actor
    else:
        author = None
    if author is not None:
        put("author_id", author.id)
        put("author_name", _display_name(author))
        post.author = author

    if "published_at" in fields:
        put("published_at", _naive_utc(body.published_at))
    if body.status is not None:
        put("status", body.status)
    if post.status == POST_PUBLISHED:
        _check_publishable(post)
        if post.published_at is None:
            put("published_at", utcnow())

    # The card needs a summary; fall back to the article's opening lines.
    if not post.excerpt and post.content_html:
        post.excerpt = excerpt_from(post.content_html)

    post.updated_by_id = actor.id
    return changed


@router.post("/blog/posts", status_code=status.HTTP_201_CREATED)
async def create_post(
    body: PostBody,
    request: Request,
    db: AsyncSession = Depends(get_db),
    editor=Depends(require_blog_editor),
):
    if not body.title:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Add a title.")
    post = BlogPost(title=body.title, content_html="", tags=[], status=POST_DRAFT, created_by_id=editor.id)
    # Added only once it has a slug: the uniqueness checks in _apply query the
    # table, and autoflush would otherwise insert a row without one.
    await _apply(db, post, body, editor, creating=True)
    db.add(post)
    await db.flush()
    audit(db, editor, "blog.post.create", target_type="blog_post", target_id=post.id,
          summary=f"Created “{post.title}” ({post.status})", request=request)
    await db.commit()
    await db.refresh(post)
    return console_detail(post, utcnow())


@router.put("/blog/posts/{post_id}")
async def update_post(
    post_id: str,
    body: PostBody,
    request: Request,
    db: AsyncSession = Depends(get_db),
    editor=Depends(require_blog_editor),
):
    post = await _post_or_404(db, post_id)
    was = post.display_status(utcnow())
    changed = await _apply(db, post, body, editor, creating=False)
    if changed:
        now_status = post.display_status(utcnow())
        note = f" ({was} → {now_status})" if was != now_status else ""
        audit(db, editor, "blog.post.update", target_type="blog_post", target_id=post.id,
              summary=f"Edited “{post.title}”{note}",
              details={"fields": [c for c in changed if c != "content_html"] + (["content"] if "content_html" in changed else [])},
              request=request)
    await db.commit()
    await db.refresh(post)
    return console_detail(post, utcnow())


class PublishBody(BaseModel):
    #: Omit to publish now (or keep the date already set); a future time schedules it.
    published_at: Optional[datetime] = None


@router.post("/blog/posts/{post_id}/publish")
async def publish_post(
    post_id: str,
    request: Request,
    body: Optional[PublishBody] = None,
    db: AsyncSession = Depends(get_db),
    editor=Depends(require_blog_editor),
):
    post = await _post_or_404(db, post_id)
    _check_publishable(post)
    when = _naive_utc(body.published_at) if body and body.published_at else None
    if when is not None:
        post.published_at = when
    elif post.published_at is None or (post.status != POST_PUBLISHED and post.published_at > utcnow()):
        # Publishing a draft that had a future date saved means "now"; the
        # date field (or the body) is how to schedule deliberately.
        post.published_at = utcnow()
    post.status = POST_PUBLISHED
    post.updated_by_id = editor.id
    state = post.display_status(utcnow())
    audit(db, editor, "blog.post.publish", target_type="blog_post", target_id=post.id,
          summary=(f"Scheduled “{post.title}” for {utc_iso(post.published_at)}"
                   if state == "scheduled" else f"Published “{post.title}”"),
          request=request)
    await db.commit()
    await db.refresh(post)
    return console_detail(post, utcnow())


@router.post("/blog/posts/{post_id}/unpublish")
async def unpublish_post(
    post_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    editor=Depends(require_blog_editor),
):
    post = await _post_or_404(db, post_id)
    post.status = POST_DRAFT
    post.updated_by_id = editor.id
    audit(db, editor, "blog.post.unpublish", target_type="blog_post", target_id=post.id,
          summary=f"Unpublished “{post.title}”", request=request)
    await db.commit()
    await db.refresh(post)
    return console_detail(post, utcnow())


@router.delete("/blog/posts/{post_id}")
async def delete_post(
    post_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    editor=Depends(require_blog_editor),
):
    post = await _post_or_404(db, post_id)
    audit(db, editor, "blog.post.delete", target_type="blog_post", target_id=post.id,
          summary=f"Deleted “{post.title}” (/{post.slug})", request=request)
    await db.delete(post)
    await db.commit()
    return {"ok": True}


@router.get("/blog/slug-check")
async def slug_check(
    slug: str = Query(..., max_length=200),
    exclude_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_blog_reader),
):
    """Whether a slug is free, and the free form of it if not."""
    clean = slugify(slug)
    exclude = parse_uuid(exclude_id, "post") if exclude_id else None
    if not clean:
        return {"slug": "", "available": False, "suggestion": None}
    taken = await _slug_taken(db, clean, exclude)
    return {
        "slug": clean,
        "available": not taken,
        "suggestion": await _free_slug(db, clean, exclude) if taken else clean,
    }


@router.post("/blog/images", status_code=status.HTTP_201_CREATED)
async def upload_image(
    request: Request,
    file: UploadFile = File(...),
    _=Depends(require_blog_editor),
):
    """Store a featured, share or in-article image; returns its public URL and size."""
    raw = await file.read(MAX_IMAGE_BYTES + 1)
    try:
        return store_blog_image(raw, file.content_type, public_base=public_base_url(request))
    except StorageError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=exc.public_message) from exc


@router.get("/blog/authors")
async def list_authors(db: AsyncSession = Depends(get_db), _=Depends(require_blog_reader)):
    """Everyone who can be credited on a post: platform admins and the blog team."""
    users = (
        await db.execute(
            select(User)
            .where(User.deleted_at.is_(None), or_(User.is_platform_admin.is_(True), User.blog_role.in_(BLOG_ROLES)))
            .order_by(func.lower(func.coalesce(User.full_name, User.email)))
        )
    ).scalars().all()
    return [
        {"id": str(u.id), "name": _display_name(u), "email": u.email, "role": console_role(u), "is_active": u.is_active}
        for u in users
    ]


# ---------------------------------------------------------------------------
# Categories
# ---------------------------------------------------------------------------


class CategoryBody(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    slug: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = Field(None, max_length=500)


async def _category_or_404(db: AsyncSession, category_id: str) -> BlogCategory:
    category = await db.get(BlogCategory, parse_uuid(category_id, "category"))
    if category is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
    return category


async def _category_slug(db: AsyncSession, body: CategoryBody, exclude: Optional[uuid.UUID]) -> str:
    slug = slugify(body.slug or body.name, max_length=100)
    if not slug:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Use letters or numbers in the name.")
    query = select(BlogCategory.id).where(BlogCategory.slug == slug)
    if exclude is not None:
        query = query.where(BlogCategory.id != exclude)
    if (await db.execute(query.limit(1))).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A category with that name already exists.")
    return slug


def _category_out(category: BlogCategory, posts: int = 0) -> dict:
    return {
        "id": str(category.id),
        "name": category.name,
        "slug": category.slug,
        "description": category.description,
        "posts": posts,
        "created_at": utc_iso(category.created_at),
    }


@router.get("/blog/categories")
async def list_categories(db: AsyncSession = Depends(get_db), _=Depends(require_blog_reader)):
    counts = dict(
        (await db.execute(select(BlogPost.category_id, func.count(BlogPost.id)).group_by(BlogPost.category_id))).all()
    )
    categories = (await db.execute(select(BlogCategory).order_by(func.lower(BlogCategory.name)))).scalars().all()
    return [_category_out(c, int(counts.get(c.id, 0))) for c in categories]


@router.post("/blog/categories", status_code=status.HTTP_201_CREATED)
async def create_category(
    body: CategoryBody,
    request: Request,
    db: AsyncSession = Depends(get_db),
    editor=Depends(require_blog_editor),
):
    category = BlogCategory(
        name=body.name.strip(), slug=await _category_slug(db, body, None), description=(body.description or "").strip() or None
    )
    db.add(category)
    await db.flush()
    audit(db, editor, "blog.category.create", target_type="blog_category", target_id=category.id,
          summary=f"Created blog category {category.name}", request=request)
    await db.commit()
    return _category_out(category)


@router.put("/blog/categories/{category_id}")
async def update_category(
    category_id: str,
    body: CategoryBody,
    request: Request,
    db: AsyncSession = Depends(get_db),
    editor=Depends(require_blog_editor),
):
    category = await _category_or_404(db, category_id)
    category.name = body.name.strip()
    category.slug = await _category_slug(db, body, category.id)
    category.description = (body.description or "").strip() or None
    audit(db, editor, "blog.category.update", target_type="blog_category", target_id=category.id,
          summary=f"Edited blog category {category.name}", request=request)
    await db.commit()
    count = int((await db.execute(select(func.count(BlogPost.id)).where(BlogPost.category_id == category.id))).scalar() or 0)
    return _category_out(category, count)


@router.delete("/blog/categories/{category_id}")
async def delete_category(
    category_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    editor=Depends(require_blog_editor),
):
    """Delete a category. Its posts stay, uncategorised."""
    category = await _category_or_404(db, category_id)
    audit(db, editor, "blog.category.delete", target_type="blog_category", target_id=category.id,
          summary=f"Deleted blog category {category.name}", request=request)
    # Explicit, not left to ON DELETE SET NULL: SQLite test databases do not enforce it.
    for post in (await db.execute(select(BlogPost).where(BlogPost.category_id == category.id))).unique().scalars():
        post.category_id = None
    await db.delete(category)
    await db.commit()
    return {"ok": True}


# ---------------------------------------------------------------------------
# Blog team (platform admins only)
# ---------------------------------------------------------------------------


def _member_out(user: User, posts: int = 0) -> dict:
    return {
        "id": str(user.id),
        "email": user.email,
        "full_name": user.full_name,
        "role": console_role(user),
        "is_active": user.is_active,
        "posts": posts,
        "last_login_at": utc_iso(user.last_login_at),
        "created_at": utc_iso(user.created_at),
    }


async def _member_or_404(db: AsyncSession, user_id: str) -> User:
    user = await db.get(User, parse_uuid(user_id, "user"))
    if user is None or user.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


@router.get("/blog/team")
async def list_team(db: AsyncSession = Depends(get_db), _=Depends(require_platform_admin)):
    users = (
        await db.execute(
            select(User)
            .where(User.deleted_at.is_(None), or_(User.is_platform_admin.is_(True), User.blog_role.in_(BLOG_ROLES)))
            .order_by(User.is_platform_admin.desc(), func.lower(User.email))
        )
    ).scalars().all()
    counts = dict(
        (await db.execute(select(BlogPost.author_id, func.count(BlogPost.id)).group_by(BlogPost.author_id))).all()
    )
    return [_member_out(u, int(counts.get(u.id, 0))) for u in users]


class TeamMemberCreate(BaseModel):
    email: str = Field(..., min_length=3, max_length=255)
    full_name: Optional[str] = Field(None, max_length=255)
    role: Literal["editor", "viewer"]
    #: Required for a new account; ignored for an existing one, which keeps its own.
    password: Optional[str] = Field(None, max_length=200)


@router.post("/blog/team", status_code=status.HTTP_201_CREATED)
async def add_team_member(
    body: TeamMemberCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_platform_admin),
):
    """Give a blog role to an existing account, or create an account with one."""
    email = normalize_email(body.email)
    if "@" not in email or "." not in email.rsplit("@", 1)[-1]:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Enter a valid email address.")
    full_name = (body.full_name or "").strip() or None

    user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
    created = user is None
    if user is not None:
        if user.deleted_at is not None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="That account has been deleted.")
        if user.is_platform_admin:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="That person is a platform admin and already has full blog access.",
            )
        if not user.hashed_password:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"That account signs in with {user.auth_provider.title()} and has no password, "
                    "so it cannot sign in to the console. Ask them to set a password first."
                ),
            )
        if full_name and not user.full_name:
            user.full_name = full_name
    else:
        if not body.password:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Set a password for the new account.",
            )
        try:
            validate_password(body.password, email=email, full_name=full_name)
        except PasswordPolicyError as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
        now = utcnow()
        user = User(
            email=email,
            full_name=full_name,
            hashed_password=get_password_hash(body.password),
            auth_provider="email",
            is_active=True,
            # An admin vouched for the address by creating it.
            is_verified=True,
            email_verified_at=now,
        )
        db.add(user)

    user.blog_role = body.role
    await db.flush()
    audit(db, admin, "blog.team.add", target_type="user", target_id=user.id,
          summary=f"{'Created' if created else 'Added'} {email} as blog {body.role}",
          details={"role": body.role, "new_account": created}, request=request)
    await db.commit()
    await db.refresh(user)
    return {**_member_out(user), "created": created}


class TeamMemberPatch(BaseModel):
    role: Literal["editor", "viewer"]


@router.patch("/blog/team/{user_id}")
async def change_team_role(
    user_id: str,
    body: TeamMemberPatch,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_platform_admin),
):
    user = await _member_or_404(db, user_id)
    if user.is_platform_admin:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Platform admins always have full blog access.")
    before = user.blog_role
    user.blog_role = body.role
    audit(db, admin, "blog.team.role", target_type="user", target_id=user.id,
          summary=f"{user.email}: blog {before or 'none'} → {body.role}", request=request)
    await db.commit()
    await db.refresh(user)
    return _member_out(user)


@router.delete("/blog/team/{user_id}")
async def remove_team_member(
    user_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_platform_admin),
):
    """Take the blog role away. The account itself is kept, and so are its posts.

    Takes effect on the person's next request: roles are read from the database
    every time, not from the token.
    """
    user = await _member_or_404(db, user_id)
    if user.is_platform_admin:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Platform admins always have full blog access.")
    before = user.blog_role
    user.blog_role = None
    audit(db, admin, "blog.team.remove", target_type="user", target_id=user.id,
          summary=f"Removed blog {before} access from {user.email}", request=request)
    await db.commit()
    return {"ok": True}
