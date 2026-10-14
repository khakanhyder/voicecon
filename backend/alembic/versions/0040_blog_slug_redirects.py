"""blog_slug_redirects: old article URLs that 301 to the post's current one

Revision ID: 0040_blog_slug_redirects
Revises: 0038_chat_mobile_inbox
Create Date: 2026-10-14

Changing a published post's slug used to leave the old URL behind with no
redirect. The console now records the old slug here on every rename.

Also seeds the one rename made before this existed (2026-10-14):
/blog/outsource-receptionist-services-a-complete-guide-for-businesses-of-all-sizes
→ /blog/outsource-receptionist. Skipped when that post is not in the database.

Guarded so it is safe on a database ``create_all`` already built.
"""
from alembic import op
import sqlalchemy as sa


revision = "0040_blog_slug_redirects"
down_revision = "0038_chat_mobile_inbox"
branch_labels = None
depends_on = None

_SEED_FROM = "outsource-receptionist-services-a-complete-guide-for-businesses-of-all-sizes"
_SEED_TO = "outsource-receptionist"


def upgrade() -> None:
    tables = set(sa.inspect(op.get_bind()).get_table_names())
    if "blog_slug_redirects" not in tables:
        op.create_table(
            "blog_slug_redirects",
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column("old_slug", sa.String(200), nullable=False),
            sa.Column("post_id", sa.Uuid(), sa.ForeignKey("blog_posts.id", ondelete="CASCADE"), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )
        op.create_index("ix_blog_slug_redirects_old_slug", "blog_slug_redirects", ["old_slug"], unique=True)
        op.create_index("ix_blog_slug_redirects_post_id", "blog_slug_redirects", ["post_id"])

    op.execute(
        sa.text(
            """
            INSERT INTO blog_slug_redirects (id, old_slug, post_id, created_at)
            SELECT gen_random_uuid(), :old, p.id, now()
              FROM blog_posts p
             WHERE p.slug = :new
               AND NOT EXISTS (SELECT 1 FROM blog_slug_redirects WHERE old_slug = :old)
               AND NOT EXISTS (SELECT 1 FROM blog_posts WHERE slug = :old)
            """
        ).bindparams(old=_SEED_FROM, new=_SEED_TO)
    )


def downgrade() -> None:
    if "blog_slug_redirects" in set(sa.inspect(op.get_bind()).get_table_names()):
        op.drop_table("blog_slug_redirects")
