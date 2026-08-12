import asyncio
from app.database import AsyncSessionLocal
from app.models.subscription import SubscriptionPlan
from sqlalchemy import select

async def main():
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(SubscriptionPlan))
        plans = result.scalars().all()
        for plan in plans:
            print(f"{plan.slug} max_agents: {plan.max_agents}, features: {plan.features}")
if __name__ == "__main__":
    asyncio.run(main())
