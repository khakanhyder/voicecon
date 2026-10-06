"""marketing blog: posts, categories and blog roles

Revision ID: 0037_blog
Revises: 0036_payg_wallet
Create Date: 2026-10-06

* ``blog_categories`` and ``blog_posts`` — the blog written in the staff
  console and shown at voicecon.ai/blog.
* ``users.blog_role`` — ``editor`` or ``viewer`` for console users who are not
  platform admins; NULL for everyone else, so existing accounts are unchanged.

Guarded so it is safe on a database ``create_all`` already built, and safe to
rerun after a partial failure.
"""
from alembic import op
import sqlalchemy as sa


revision = "0037_blog"
down_revision = "0036_payg_wallet"
branch_labels = None
depends_on = None


def _tables() -> set:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _columns(table: str) -> set:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def _indexes(table: str) -> set:
    return {ix["name"] for ix in sa.inspect(op.get_bind()).get_indexes(table)}


def _index(name: str, table: str, columns: list, unique: bool = False) -> None:
    if name not in _indexes(table):
        op.create_index(name, table, columns, unique=unique)


def upgrade() -> None:
    if "blog_role" not in _columns("users"):
        op.add_column("users", sa.Column("blog_role", sa.String(20), nullable=True))

    tables = _tables()
    if "blog_categories" not in tables:
        op.create_table(
            "blog_categories",
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column("name", sa.String(80), nullable=False),
            sa.Column("slug", sa.String(100), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )
    _index("ix_blog_categories_slug", "blog_categories", ["slug"], unique=True)

    if "blog_posts" not in tables:
        op.create_table(
            "blog_posts",
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column("title", sa.String(200), nullable=False),
            sa.Column("slug", sa.String(200), nullable=False),
            sa.Column("excerpt", sa.Text(), nullable=True),
            sa.Column("content_html", sa.Text(), nullable=False),
            sa.Column("featured_image_url", sa.Text(), nullable=True),
            sa.Column("featured_image_alt", sa.String(255), nullable=True),
            sa.Column("social_image_url", sa.Text(), nullable=True),
            sa.Column(
                "category_id", sa.Uuid(),
                sa.ForeignKey("blog_categories.id", ondelete="SET NULL"), nullable=True,
            ),
            sa.Column("tags", sa.JSON(), nullable=False),
            sa.Column("author_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("author_name", sa.String(255), nullable=True),
            sa.Column("status", sa.String(20), nullable=False),
            sa.Column("published_at", sa.DateTime(), nullable=True),
            sa.Column("is_featured", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("seo_title", sa.String(200), nullable=True),
            sa.Column("seo_description", sa.String(320), nullable=True),
            sa.Column("reading_minutes", sa.Integer(), nullable=False),
            sa.Column("created_by_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("updated_by_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )
    _index("ix_blog_posts_slug", "blog_posts", ["slug"], unique=True)
    _index("ix_blog_posts_category_id", "blog_posts", ["category_id"])
    _index("ix_blog_posts_author_id", "blog_posts", ["author_id"])
    _index("ix_blog_posts_status_published_at", "blog_posts", ["status", "published_at"])


def downgrade() -> None:
    tables = _tables()
    if "blog_posts" in tables:
        op.drop_table("blog_posts")
    if "blog_categories" in tables:
        op.drop_table("blog_categories")
    if "blog_role" in _columns("users"):
        op.drop_column("users", "blog_role")
