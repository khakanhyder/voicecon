#!/bin/bash

# Database Seed Script for Voicecon
# Populates database with sample data for development

set -e

echo "🌱 Voicecon Database Seed Script"
echo "================================="

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Navigate to backend directory
cd "$(dirname "$0")/../backend"

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo -e "${RED}❌ Virtual environment not found!${NC}"
    echo "Run ./scripts/setup.sh first"
    exit 1
fi

# Activate virtual environment
source venv/bin/activate

# Check if Python seed script exists, if not create it
if [ ! -f "scripts/seed_data.py" ]; then
    echo -e "${BLUE}📝 Creating seed data script...${NC}"
    mkdir -p scripts

    cat > scripts/seed_data.py << 'PYTHON_SCRIPT'
"""
Database seed script - populates development data
"""
import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import AsyncSessionLocal
from app.models.user import User, Organization, OrganizationMember
from app.models.agent import Agent
from app.models.integration import IntegrationConnector
from app.core.security import get_password_hash
from sqlalchemy import select


async def seed_database():
    """Seed the database with sample data"""
    print("🌱 Seeding database...")

    async with AsyncSessionLocal() as session:
        # Check if data already exists
        result = await session.execute(select(User))
        existing_users = result.scalars().all()

        if existing_users:
            print("⚠️  Database already has data. Skipping seed.")
            print(f"Found {len(existing_users)} existing users.")
            return

        # Create demo user
        print("👤 Creating demo user...")
        demo_user = User(
            email="demo@voicecon.com",
            hashed_password=get_password_hash("demo123456"),
            full_name="Demo User",
            company_name="Voicecon Demo",
            is_active=True,
            is_verified=True,
        )
        session.add(demo_user)
        await session.flush()

        # Create demo organization
        print("🏢 Creating demo organization...")
        demo_org = Organization(
            name="Voicecon Demo Organization",
            slug="demo-org",
            owner_id=demo_user.id,
            plan_type="professional",
            is_active=True,
        )
        session.add(demo_org)
        await session.flush()

        # Add user as organization owner
        print("👥 Adding organization membership...")
        membership = OrganizationMember(
            organization_id=demo_org.id,
            user_id=demo_user.id,
            role="owner",
        )
        session.add(membership)

        # Create sample agent
        print("🤖 Creating sample agent...")
        sample_agent = Agent(
            user_id=demo_user.id,
            organization_id=demo_org.id,
            name="Customer Support Agent",
            description="AI agent for handling customer support calls",
            type="assistant",
            system_prompt="You are a helpful customer support agent. Be polite, professional, and solve customer issues efficiently.",
            first_message="Hello! How can I help you today?",
            llm_provider="openai",
            llm_model="gpt-4",
            llm_temperature=0.7,
            tts_provider="elevenlabs",
            stt_provider="deepgram",
            stt_language="en",
            is_active=True,
            tags=["support", "customer-service"],
        )
        session.add(sample_agent)

        # Seed popular integration connectors
        print("🔌 Seeding integration connectors...")
        connectors = [
            # CRM
            IntegrationConnector(
                name="Salesforce",
                slug="salesforce",
                category="crm",
                description="Connect with Salesforce CRM to manage leads and opportunities",
                auth_type="oauth2",
                supports_triggers=True,
                supports_actions=True,
                is_active=True,
            ),
            IntegrationConnector(
                name="HubSpot",
                slug="hubspot",
                category="crm",
                description="Integrate with HubSpot CRM for contact and deal management",
                auth_type="oauth2",
                supports_triggers=True,
                supports_actions=True,
                is_active=True,
            ),
            # Communication
            IntegrationConnector(
                name="Slack",
                slug="slack",
                category="communication",
                description="Send messages and notifications to Slack channels",
                auth_type="oauth2",
                supports_triggers=True,
                supports_actions=True,
                is_active=True,
            ),
            IntegrationConnector(
                name="Microsoft Teams",
                slug="microsoft_teams",
                category="communication",
                description="Post messages to Microsoft Teams channels",
                auth_type="oauth2",
                supports_triggers=False,
                supports_actions=True,
                is_active=True,
            ),
            # Calendar
            IntegrationConnector(
                name="Google Calendar",
                slug="google_calendar",
                category="calendar",
                description="Create and manage calendar events",
                auth_type="oauth2",
                supports_triggers=True,
                supports_actions=True,
                is_active=True,
            ),
            IntegrationConnector(
                name="Calendly",
                slug="calendly",
                category="calendar",
                description="Schedule appointments with Calendly",
                auth_type="oauth2",
                supports_triggers=True,
                supports_actions=True,
                is_active=True,
            ),
            # Email
            IntegrationConnector(
                name="Gmail",
                slug="gmail",
                category="email",
                description="Send and receive emails via Gmail",
                auth_type="oauth2",
                supports_triggers=True,
                supports_actions=True,
                is_active=True,
            ),
            IntegrationConnector(
                name="SendGrid",
                slug="sendgrid",
                category="email",
                description="Send transactional emails",
                auth_type="api_key",
                supports_triggers=False,
                supports_actions=True,
                is_active=True,
            ),
            # Productivity
            IntegrationConnector(
                name="Notion",
                slug="notion",
                category="productivity",
                description="Create and update Notion pages and databases",
                auth_type="oauth2",
                supports_triggers=False,
                supports_actions=True,
                is_active=True,
            ),
            IntegrationConnector(
                name="Airtable",
                slug="airtable",
                category="productivity",
                description="Manage records in Airtable bases",
                auth_type="api_key",
                supports_triggers=True,
                supports_actions=True,
                is_active=True,
            ),
        ]

        for connector in connectors:
            session.add(connector)

        # Commit all changes
        await session.commit()

        print("✅ Database seeded successfully!")
        print("\n📊 Summary:")
        print(f"  • 1 demo user created (email: demo@voicecon.com, password: demo123456)")
        print(f"  • 1 organization created")
        print(f"  • 1 sample agent created")
        print(f"  • {len(connectors)} integration connectors added")
        print("\n🎉 You can now login with demo@voicecon.com / demo123456")


async def clear_database():
    """Clear all data from database (use with caution!)"""
    print("⚠️  WARNING: This will delete ALL data from the database!")
    response = input("Type 'yes' to confirm: ")

    if response.lower() != 'yes':
        print("Cancelled.")
        return

    print("🗑️  Clearing database...")

    async with AsyncSessionLocal() as session:
        # Delete in reverse order of dependencies
        from app.models.integration import WorkflowExecution, Workflow, IntegrationConnection, IntegrationConnector
        from app.models.call import CallLog, Call, PhoneNumber
        from app.models.agent import AgentFlow, KnowledgeBaseDocument, SquadMember, Squad, AgentFunction, Agent
        from app.models.user import ApiKey, OrganizationMember, Organization, User

        # Delete all records
        for model in [
            WorkflowExecution, Workflow, IntegrationConnection, IntegrationConnector,
            CallLog, Call, PhoneNumber,
            AgentFlow, KnowledgeBaseDocument, SquadMember, Squad, AgentFunction, Agent,
            ApiKey, OrganizationMember, Organization, User
        ]:
            await session.execute(f"DELETE FROM {model.__tablename__}")

        await session.commit()
        print("✅ Database cleared")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "clear":
        asyncio.run(clear_database())
    else:
        asyncio.run(seed_database())
PYTHON_SCRIPT

    echo -e "${GREEN}✅ Seed script created${NC}"
fi

# Run the seed script
echo -e "${BLUE}🚀 Running seed script...${NC}"

if [ "$1" == "clear" ]; then
    python scripts/seed_data.py clear
else
    python scripts/seed_data.py
fi

echo ""
echo -e "${GREEN}Done! 🎉${NC}"
