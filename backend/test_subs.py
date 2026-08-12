import asyncio
from app.database import AsyncSessionLocal
from app.models.subscription import Subscription
from sqlalchemy import select

async def main():
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Subscription))
        subs = result.scalars().all()
        stripe_subs = [s for s in subs if s.source == 'stripe']
        print(f"Stripe subscriptions found: {len(stripe_subs)}")

if __name__ == "__main__":
    asyncio.run(main())
