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

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select

from app.database import Base
from app.models.template import AgentTemplate, WorkflowTemplate
from app.services.templates import AGENT_TEMPLATES, WORKFLOW_TEMPLATES
import os


async def seed_templates():
    """Seed templates into database."""

    # Get database URL from environment
    database_url = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://postgres:postgres@localhost:5432/voicecon"
    )

    print(f"Connecting to database: {database_url}")

    # Create engine and session
    engine = create_async_engine(database_url, echo=True)
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session() as session:
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
            await engine.dispose()


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
