"""index api_keys.key_prefix for authentication lookups

Revision ID: 0014_api_key_prefix_idx
Revises: 0013_active_workspace
Create Date: 2026-08-03

Authenticating an API key looks the row up by ``key_prefix`` — the non-secret
``vcon_xxxxxxx`` head of the key — and then bcrypt-verifies the presented
secret against the candidates' hashes. Until now nothing used that path, so the
column had no index; with API key auth live it is read on every machine-to-
machine request and a sequential scan over every key in the system is not
acceptable.

Non-unique on purpose. The prefix is only 7 secret characters, so a collision
is unlikely but possible, and a unique constraint would turn that coincidence
into a failed key creation for an unlucky customer. The authenticator handles
multiple candidates by hash-checking each, so duplicates are correct-but-slower
rather than an error.

Idempotent: skips when the index already exists, matching the other migrations
here (a dev DB may have been built by Base.metadata.create_all).

Note: the revision id is kept short (<=32 chars) to fit alembic_version.version_num.
"""
from alembic import op
import sqlalchemy as sa

revision = "0014_api_key_prefix_idx"
down_revision = "0013_active_workspace"
branch_labels = None
depends_on = None

TABLE = "api_keys"
COLUMN = "key_prefix"
INDEX_NAME = "ix_api_keys_key_prefix"


def _index_exists() -> bool:
    inspector = sa.inspect(op.get_bind())
    if TABLE not in inspector.get_table_names():
        return False
    return INDEX_NAME in {ix["name"] for ix in inspector.get_indexes(TABLE)}


def upgrade() -> None:
    if _index_exists():
        return
    op.create_index(INDEX_NAME, TABLE, [COLUMN])


def downgrade() -> None:
    if not _index_exists():
        return
    op.drop_index(INDEX_NAME, table_name=TABLE)
