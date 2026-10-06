"""JSON shapes for blog posts, shared by the console and the public API."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from app.core.time import utc_iso
from app.models.blog import BlogCategory, BlogPost


def category_view(category: Optional[BlogCategory]) -> Optional[Dict[str, Any]]:
    if category is None:
        return None
    return {"id": str(category.id), "name": category.name, "slug": category.slug}


def author_view(post: BlogPost) -> Dict[str, Any]:
    user = post.author
    # The live account's name wins, so renaming yourself updates your bylines;
    # the stored copy covers a deleted account (whose name is erased).
    live_name = user.full_name if user is not None and user.deleted_at is None else None
    return {
        "id": str(post.author_id) if post.author_id else None,
        "name": live_name or post.author_name or "Voicecon Team",
        "avatar_url": user.avatar_url if user is not None and user.deleted_at is None else None,
    }


def public_card(post: BlogPost) -> Dict[str, Any]:
    """What a blog card needs: no body."""
    return {
        "slug": post.slug,
        "title": post.title,
        "excerpt": post.excerpt or "",
        "featured_image_url": post.featured_image_url,
        "featured_image_alt": post.featured_image_alt or post.title,
        "category": category_view(post.category),
        "tags": list(post.tags or []),
        "author": author_view(post),
        "published_at": utc_iso(post.published_at),
        "updated_at": utc_iso(post.updated_at),
        "reading_minutes": post.reading_minutes,
        "is_featured": bool(post.is_featured),
    }


def public_detail(post: BlogPost) -> Dict[str, Any]:
    return {
        **public_card(post),
        "content_html": post.content_html or "",
        "social_image_url": post.social_image_url,
        "seo_title": post.seo_title,
        "seo_description": post.seo_description,
    }


def console_row(post: BlogPost, now: datetime) -> Dict[str, Any]:
    """A row in the console's post table."""
    return {
        "id": str(post.id),
        **public_card(post),
        "status": post.display_status(now),
        "stored_status": post.status,
        "created_at": utc_iso(post.created_at),
    }


def console_detail(post: BlogPost, now: datetime) -> Dict[str, Any]:
    return {
        **console_row(post, now),
        **public_detail(post),
        "category_id": str(post.category_id) if post.category_id else None,
        "author_id": str(post.author_id) if post.author_id else None,
    }
