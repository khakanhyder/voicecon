"""
The public blog API, mounted at ``/api/v1/blog`` with no authentication.

Read by the marketing site (voicecon.ai/blog and the home page's blog section).
Only live posts exist here: published, with a publish time that has passed. A
draft or a scheduled post is a 404, the same as a slug that was never used.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import utc_iso
from app.database import get_db
from app.models.blog import POST_PUBLISHED, BlogCategory, BlogPost

from ..admin._common import like, utcnow
from ._views import category_view, public_card, public_detail

router = APIRouter()


def _live():
    return [BlogPost.status == POST_PUBLISHED, BlogPost.published_at <= utcnow()]


_NEWEST = (BlogPost.published_at.desc(), BlogPost.created_at.desc())


@router.get("/posts")
async def list_posts(
    page: int = Query(1, ge=1),
    page_size: int = Query(9, ge=1, le=24),
    category: Optional[str] = Query(None, max_length=100, description="Category slug"),
    tag: Optional[str] = Query(None, max_length=40),
    q: Optional[str] = Query(None, max_length=200),
    db: AsyncSession = Depends(get_db),
):
    filters = _live()
    if category:
        filters.append(BlogPost.category.has(BlogCategory.slug == category))
    if q and q.strip():
        term = like(q.strip())
        filters.append(or_(BlogPost.title.ilike(term, escape="\\"), BlogPost.excerpt.ilike(term, escape="\\")))

    query = select(BlogPost).where(*filters).order_by(*_NEWEST)
    if tag:
        # Tags are a small JSON list per post; filtering them in Python keeps
        # this portable across Postgres and the SQLite test database.
        wanted = tag.strip().lower()
        posts = [
            p for p in (await db.execute(query)).unique().scalars().all()
            if wanted in {t.lower() for t in (p.tags or [])}
        ]
        total = len(posts)
        rows = posts[(page - 1) * page_size: page * page_size]
    else:
        total = int((await db.execute(select(func.count(BlogPost.id)).where(*filters))).scalar() or 0)
        rows = (await db.execute(query.offset((page - 1) * page_size).limit(page_size))).unique().scalars().all()

    return {
        "items": [public_card(p) for p in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": max(1, -(-total // page_size)),
    }


@router.get("/highlights")
async def highlights(limit: int = Query(3, ge=1, le=12), db: AsyncSession = Depends(get_db)):
    """For the home page: featured posts first, then the newest, ``limit`` in all."""
    rows = (
        await db.execute(
            select(BlogPost).where(*_live()).order_by(BlogPost.is_featured.desc(), *_NEWEST).limit(limit)
        )
    ).unique().scalars().all()
    return [public_card(p) for p in rows]


@router.get("/categories")
async def list_categories(db: AsyncSession = Depends(get_db)):
    """Categories with at least one live post."""
    rows = (
        await db.execute(
            select(BlogCategory, func.count(BlogPost.id))
            .join(BlogPost, BlogPost.category_id == BlogCategory.id)
            .where(*_live())
            .group_by(BlogCategory.id)
            .order_by(func.lower(BlogCategory.name))
        )
    ).all()
    return [{**category_view(c), "description": c.description, "posts": int(n)} for c, n in rows]


@router.get("/sitemap")
async def sitemap(db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(BlogPost.slug, BlogPost.updated_at).where(*_live()).order_by(*_NEWEST))).all()
    return [{"slug": slug, "updated_at": utc_iso(updated)} for slug, updated in rows]


@router.get("/posts/{slug}")
async def get_post(slug: str, db: AsyncSession = Depends(get_db)):
    post = (await db.execute(select(BlogPost).where(BlogPost.slug == slug, *_live()))).unique().scalar_one_or_none()
    if post is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Article not found")

    # Related: same category first, then the newest of the rest.
    related = []
    if post.category_id:
        related = (
            await db.execute(
                select(BlogPost)
                .where(*_live(), BlogPost.category_id == post.category_id, BlogPost.id != post.id)
                .order_by(*_NEWEST).limit(3)
            )
        ).unique().scalars().all()
    if len(related) < 3:
        seen = [post.id, *(p.id for p in related)]
        related = [*related, *(
            await db.execute(
                select(BlogPost).where(*_live(), BlogPost.id.not_in(seen)).order_by(*_NEWEST).limit(3 - len(related))
            )
        ).unique().scalars().all()]

    return {**public_detail(post), "related": [public_card(p) for p in related]}
