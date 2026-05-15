"""
Create organization and membership for demo user
"""
import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import AsyncSessionLocal
from app.models.user import User, Organization, OrganizationMember
from sqlalchemy import select

async def create_org_membership():
    async with AsyncSessionLocal() as session:
        # Get demo user
        result = await session.execute(
            select(User).where(User.email == "demo@voicecon.com")
        )
        user = result.scalar_one_or_none()
        
        if not user:
            print("ERROR: Demo user not found!")
            return
        
        print(f"Found user: {user.email} (ID: {user.id})")
        
        # Check for existing org
        org_result = await session.execute(
            select(Organization).where(Organization.owner_id == user.id)
        )
        org = org_result.scalar_one_or_none()
        
        if not org:
            print("Creating organization...")
            org = Organization(
                name="Demo Organization",
                slug="demo-org",
                owner_id=user.id,
                plan_type="professional",
                is_active=True
            )
            session.add(org)
            await session.flush()
            print(f"Created organization: {org.name} (ID: {org.id})")
        else:
            print(f"Organization exists: {org.name} (ID: {org.id})")
        
        # Check for membership
        member_result = await session.execute(
            select(OrganizationMember).where(
                OrganizationMember.user_id == user.id,
                OrganizationMember.organization_id == org.id
            )
        )
        member = member_result.scalar_one_or_none()
        
        if not member:
            print("Creating organization membership...")
            member = OrganizationMember(
                organization_id=org.id,
                user_id=user.id,
                role="owner"
            )
            session.add(member)
            print("Created membership with role: owner")
        else:
            print(f"Membership exists with role: {member.role}")
        
        await session.commit()
        print("\n✅ SUCCESS: Organization membership verified!")
        print(f"User: {user.email}")
        print(f"Organization: {org.name}")
        print(f"Role: owner")

if __name__ == "__main__":
    asyncio.run(create_org_membership())
