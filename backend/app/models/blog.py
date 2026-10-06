"""
The marketing blog: posts and their categories.

Owned by Voicecon itself, not by any tenant, so nothing here carries an
``organization_id``. Posts are written in the staff console (``/admin/blog``)
by platform admins and blog editors, and read by anyone through the public
``/api/v1/blog`` endpoints once they are live.

A post has two stored states, ``draft`` and ``published``. "Scheduled" is not
stored: it is a published post whose ``published_at`` is still in the future.
The public API filters on ``published_at <= now``, so a scheduled post goes
live on its own at that moment, with no job to run.
"""
import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, JSON, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

POST_DRAFT = "draft"
POST_PUBLISHED = "published"
POST_STATUSES = (POST_DRAFT, POST_PUBLISHED)


class BlogCategory(Base):
    __tablename__ = "blog_categories"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    posts: Mapped[List["BlogPost"]] = relationship("BlogPost", back_populates="category")


class BlogPost(Base):
    __tablename__ = "blog_posts"
    __table_args__ = (Index("ix_blog_posts_status_published_at", "status", "published_at"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    #: The URL: voicecon.ai/blog/<slug>. Unique across drafts too, so publishing
    #: a draft can never collide with a live post.
    slug: Mapped[str] = mapped_column(String(200), unique=True, nullable=False, index=True)
    excerpt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    #: Rich-text body, already sanitised on the way in
    #: (services/blog/content.sanitize_html). Rendered as-is by the website.
    content_html: Mapped[str] = mapped_column(Text, nullable=False, default="")

    featured_image_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    featured_image_alt: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    #: Optional override for link previews; the featured image is used otherwise.
    social_image_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    category_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("blog_categories.id", ondelete="SET NULL"), nullable=True, index=True
    )
    tags: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    author_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    #: The byline as shown on the site, copied from the author when the post is
    #: saved. Kept so the byline survives the author's account being deleted
    #: (which erases the name from ``users``).
    author_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    status: Mapped[str] = mapped_column(String(20), nullable=False, default=POST_DRAFT)
    #: When the post is (or was, or will be) live. Set on first publish.
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    #: Picked for the home page's blog section ahead of the newest posts.
    is_featured: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")

    seo_title: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    seo_description: Mapped[Optional[str]] = mapped_column(String(320), nullable=True)
    reading_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    created_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    updated_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    category: Mapped[Optional[BlogCategory]] = relationship("BlogCategory", back_populates="posts", lazy="joined")
    author = relationship("User", foreign_keys=[author_id], lazy="joined")

    def display_status(self, now: datetime) -> str:
        """``draft``, ``scheduled`` or ``published`` — what the console shows."""
        if self.status != POST_PUBLISHED:
            return POST_DRAFT
        if self.published_at and self.published_at > now:
            return "scheduled"
        return POST_PUBLISHED

    def __repr__(self) -> str:
        return f"<BlogPost(slug={self.slug}, status={self.status})>"
