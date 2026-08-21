"""
Seed database with pre-built templates.

Usage:
    python -m scripts.seed_templates
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select

# The app's own session factory, deliberately, rather than a second engine
# built here from `os.getenv("DATABASE_URL")`.
#
# `app.database` normalizes the URL — `postgresql://` becomes
# `postgresql+asyncpg://`, `postgres://` likewise — because that is the form
# deployments actually set. Building an async engine from the raw value fails
# with "The asyncio extension requires an async driver", which reads like a
# dependency problem rather than a URL scheme, and the old hardcoded fallback
# meant a *missing* variable seeded some other database instead of saying so.
from app.database import AsyncSessionLocal, DATABASE_URL
from app.models.template import AgentTemplate, WorkflowTemplate
from app.services.templates import AGENT_TEMPLATES, WORKFLOW_TEMPLATES


def _redacted(url: str) -> str:
    """The database URL with any password removed, for logging."""
    if "@" not in url:
        return url
    scheme, _, rest = url.partition("://")
    credentials, _, host = rest.rpartition("@")
    user = credentials.split(":", 1)[0]
    return f"{scheme}://{user}:***@{host}"


async def seed_templates():
    """Seed templates into database."""
    print(f"Connecting to database: {_redacted(DATABASE_URL)}")

    async with AsyncSessionLocal() as session:
        try:
            print("\n" + "=" * 80)
            print("SEEDING AGENT TEMPLATES")
            print("=" * 80 + "\n")

            # Seed agent templates
            for template_data in AGENT_TEMPLATES:
                # Check if template already exists
                result = await session.execute(
                    select(AgentTemplate).where(
                        AgentTemplate.slug == template_data["slug"]
                    )
                )
                existing = result.scalar_one_or_none()

                if existing:
                    print(f"⏭️  Skipping existing template: {template_data['name']}")
                    continue

                # Create new template
                template = AgentTemplate(**template_data)
                session.add(template)
                print(f"✅ Created agent template: {template_data['name']} ({template_data['slug']})")

            # Commit agent templates
            await session.commit()
            print(f"\n✅ Successfully seeded {len(AGENT_TEMPLATES)} agent templates!\n")

            print("\n" + "=" * 80)
            print("SEEDING WORKFLOW TEMPLATES")
            print("=" * 80 + "\n")

            # Seed workflow templates
            for template_data in WORKFLOW_TEMPLATES:
                # Check if template already exists
                result = await session.execute(
                    select(WorkflowTemplate).where(
                        WorkflowTemplate.slug == template_data["slug"]
                    )
                )
                existing = result.scalar_one_or_none()

                if existing:
                    print(f"⏭️  Skipping existing template: {template_data['name']}")
                    continue

                # Create new template
                template = WorkflowTemplate(**template_data)
                session.add(template)
                print(f"✅ Created workflow template: {template_data['name']} ({template_data['slug']})")

            # Commit workflow templates
            await session.commit()
            print(f"\n✅ Successfully seeded {len(WORKFLOW_TEMPLATES)} workflow templates!\n")

            # Print summary
            print("\n" + "=" * 80)
            print("SEEDING SUMMARY")
            print("=" * 80)
            print(f"✅ Agent Templates: {len(AGENT_TEMPLATES)}")
            print(f"✅ Workflow Templates: {len(WORKFLOW_TEMPLATES)}")
            print(f"✅ Total Templates: {len(AGENT_TEMPLATES) + len(WORKFLOW_TEMPLATES)}")
            print("=" * 80 + "\n")

        except Exception as e:
            print(f"\n❌ Error seeding templates: {e}")
            await session.rollback()
            raise
        finally:
            # The engine belongs to `app.database` and may be reused by
            # anything else importing it, so it is not disposed here.
            pass


def main():
    """Main entry point."""
    print("\n" + "=" * 80)
    print("VOICECON TEMPLATE SEEDER")
    print("=" * 80 + "\n")

    print("This script will seed the database with pre-built templates.")
    print("Existing templates will be skipped.\n")

    # Run seeding
    asyncio.run(seed_templates())

    print("\n🎉 Template seeding completed successfully!")
    print("\nYou can now view templates in the marketplace at:")
    print("  http://localhost:3000/marketplace\n")


if __name__ == "__main__":
    main()
