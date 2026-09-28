"""chatbots: standalone, named, linked to (not owned by) an agent

Revision ID: 0025_standalone_chatbots
Revises: 0024_custom_voices
Create Date: 2026-09-28

The chat widget moved out of the agent screen into its own Chatbot section.
A chatbot is now its own object:

- ``name`` — shown in the Chatbot list; backfilled as "<agent name> chatbot".
- ``agent_id`` — no longer unique (one agent can answer several chatbots) and
  nullable (a chatbot can exist before an agent is chosen).
- the agent foreign key is ``ON DELETE SET NULL`` instead of ``CASCADE``, so
  deleting an agent no longer deletes the chatbot, its embed key and its
  conversation history.

Existing rows keep their id, public_key, config and agent, so every installed
embed snippet keeps working unchanged. Guarded, so it is safe on a database
``create_all`` built from the new models.
"""
from alembic import op
import sqlalchemy as sa


revision = "0025_standalone_chatbots"
down_revision = "0024_custom_voices"
branch_labels = None
depends_on = None

_TABLE = "chat_widgets"


def _inspector():
    return sa.inspect(op.get_bind())


def upgrade() -> None:
    inspector = _inspector()
    if _TABLE not in inspector.get_table_names():
        return

    columns = {c["name"]: c for c in inspector.get_columns(_TABLE)}
    if "name" not in columns:
        op.add_column(_TABLE, sa.Column("name", sa.String(length=255), nullable=True))
        op.execute(
            """
            UPDATE chat_widgets AS w
            SET name = LEFT(COALESCE(a.name, 'Website') || ' chatbot', 255)
            FROM agents AS a
            WHERE a.id = w.agent_id AND w.name IS NULL
            """
        )
        op.execute("UPDATE chat_widgets SET name = 'Website chatbot' WHERE name IS NULL")

    # One agent may now answer several chatbots: replace the unique index.
    for index in inspector.get_indexes(_TABLE):
        if index["column_names"] == ["agent_id"] and index.get("unique"):
            op.drop_index(index["name"], table_name=_TABLE)
            op.create_index("ix_chat_widgets_agent_id", _TABLE, ["agent_id"], unique=False)
    for constraint in inspector.get_unique_constraints(_TABLE):
        if constraint["column_names"] == ["agent_id"]:
            op.drop_constraint(constraint["name"], _TABLE, type_="unique")

    if not columns["agent_id"]["nullable"]:
        op.alter_column(_TABLE, "agent_id", existing_type=sa.Uuid(), nullable=True)

    # Deleting an agent unlinks its chatbots instead of deleting them.
    for fk in inspector.get_foreign_keys(_TABLE):
        if fk["constrained_columns"] == ["agent_id"] and (fk.get("options") or {}).get("ondelete", "").upper() != "SET NULL":
            op.drop_constraint(fk["name"], _TABLE, type_="foreignkey")
            op.create_foreign_key(
                "chat_widgets_agent_id_fkey", _TABLE, "agents",
                ["agent_id"], ["id"], ondelete="SET NULL",
            )


def downgrade() -> None:
    # Restoring the unique, required, cascading link would delete or reject
    # chatbots that no longer fit it (unlinked ones, or several per agent), so
    # only the added column is removed.
    if _TABLE in _inspector().get_table_names():
        if "name" in {c["name"] for c in _inspector().get_columns(_TABLE)}:
            op.drop_column(_TABLE, "name")
