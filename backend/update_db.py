import asyncio
from app.database import AsyncSessionLocal
from app.models.subscription import SubscriptionPlan
from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified

async def main():
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(SubscriptionPlan))
        plans = result.scalars().all()
        for plan in plans:
            if plan.slug == 'sales-chatbot':
                plan.max_agents = 10
                plan.max_phone_numbers = 10
                plan.max_knowledge_bases = 10
                entit = dict(plan.entitlements)
                entit["limits"]["agents"] = 10
                entit["limits"]["phone_numbers"] = 10
                entit["limits"]["knowledge_bases"] = 10
                print(f"Old highlights: {plan.features}")
                features = dict(plan.features)
                for h in list(features.get("highlights", [])):
                    if "Scheduling" in h:
                        features["highlights"].remove(h)
                plan.features = features
                flag_modified(plan, "features")
                
                plan.entitlements = entit
                flag_modified(plan, "entitlements")
            elif plan.slug == 'voice-ai':
                plan.max_agents = 30
                plan.max_phone_numbers = 30
                plan.max_knowledge_bases = 30
                entit = dict(plan.entitlements)
                entit["limits"]["agents"] = 30
                entit["limits"]["phone_numbers"] = 30
                entit["limits"]["knowledge_bases"] = 30
                plan.entitlements = entit
                flag_modified(plan, "entitlements")
        await db.commit()
    print("Database updated!")

if __name__ == "__main__":
    asyncio.run(main())
