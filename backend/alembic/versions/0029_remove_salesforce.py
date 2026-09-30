"""remove the Salesforce integration

Revision ID: 0029_remove_salesforce
Revises: 0028_voice_ai_to_agency
Create Date: 2026-09-30

Salesforce was taken out of the product: its connector class, OAuth provider,
actions and catalog entries are gone from the code. Startup seeding upserts
connectors but never deletes one, so the ``integration_connectors`` row would
otherwise stay listed in the catalog on every existing database, offering an
app that can no longer connect.

This removes:

* **Agent tools bound to Salesforce** (``config.connector_slug``, or a
  ``config.connection_id`` of a Salesforce connection). Left in
  place they would still be offered to the model during calls and fail every
  time. Their agent assignments go with them (ON DELETE CASCADE).
* **The connector row.** Its connections, and their logs and metrics, go with
  it through ON DELETE CASCADE; phone numbers pointing at a connection are set
  to NULL. The ``integration_changes`` audit trail has no foreign key and is
  kept.
* **Salesforce in the agent templates'** ``required_integrations`` and setup
  guide text, matching the updated seed data.

Workflow steps that used a Salesforce connection are left as they are: they
belong to the user, and the step now fails with "connection not found" rather
than silently vanishing from a workflow someone relies on.

The downgrade is a no-op: deleted connections and tools cannot be restored.
"""
import json

from alembic import op
import sqlalchemy as sa

revision = "0029_remove_salesforce"
down_revision = "0028_voice_ai_to_agency"
branch_labels = None
depends_on = None

SLUG = "salesforce"

# Same substitutions as app/services/templates/agent_templates.py.
SETUP_GUIDE_EDITS = (
    ("- CRM system (Salesforce, HubSpot, or similar)", "- CRM system (HubSpot, Pipedrive, or similar)"),
    ("   - Integrate with Salesforce or HubSpot", "   - Integrate with HubSpot or Pipedrive"),
    ("- CRM system (HubSpot, Salesforce, etc.)", "- CRM system (HubSpot, Pipedrive, etc.)"),
)


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())

    if {"tools", "integration_connections", "integration_connectors"} <= tables:
        removed = bind.execute(
            sa.text(
                "DELETE FROM tools WHERE CAST(config AS JSONB) ->> 'connector_slug' = :slug "
                "OR CAST(config AS JSONB) ->> 'connection_id' IN ("
                "  SELECT CAST(c.id AS TEXT) FROM integration_connections c "
                "  JOIN integration_connectors k ON k.id = c.connector_id WHERE k.slug = :slug)"
            ),
            {"slug": SLUG},
        ).rowcount
        print(f"Removed {removed} Salesforce agent tool(s)")

    if "integration_connectors" in tables:
        if "integration_connections" in tables:
            connections = bind.execute(
                sa.text(
                    "SELECT COUNT(*) FROM integration_connections c "
                    "JOIN integration_connectors k ON k.id = c.connector_id WHERE k.slug = :slug"
                ),
                {"slug": SLUG},
            ).scalar()
            print(f"Removing {connections} Salesforce connection(s)")
        bind.execute(sa.text("DELETE FROM integration_connectors WHERE slug = :slug"), {"slug": SLUG})

    if "agent_templates" in tables:
        rows = bind.execute(
            sa.text(
                "SELECT id, required_integrations, setup_guide FROM agent_templates "
                "WHERE CAST(required_integrations AS TEXT) LIKE '%salesforce%' "
                "OR setup_guide LIKE '%Salesforce%'"
            )
        ).fetchall()
        for row_id, required, guide in rows:
            if isinstance(required, list):
                required = [slug for slug in required if slug != SLUG]
            for old, new in SETUP_GUIDE_EDITS:
                guide = guide.replace(old, new) if guide else guide
            bind.execute(
                sa.text(
                    "UPDATE agent_templates SET required_integrations = CAST(:required AS JSON), "
                    "setup_guide = :guide WHERE id = :id"
                ),
                {"required": json.dumps(required), "guide": guide, "id": row_id},
            )


def downgrade() -> None:
    pass
