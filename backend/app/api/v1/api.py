"""
API v1 router aggregator.
"""
from fastapi import APIRouter

from app.api.v1.endpoints import auth, calls, telephony, phone_numbers, voice_stream, analytics, agents, integrations, workflows, knowledge_base, billing, marketplace, tools

api_router = APIRouter()

# Include all endpoint routers
api_router.include_router(auth.router, tags=["auth"])
api_router.include_router(calls.router, prefix="/calls", tags=["calls"])
api_router.include_router(telephony.router, prefix="/telephony", tags=["telephony"])
api_router.include_router(phone_numbers.router, prefix="/phone-numbers", tags=["phone-numbers"])
api_router.include_router(voice_stream.router, prefix="/voice", tags=["voice-stream"])
api_router.include_router(analytics.router, prefix="/analytics", tags=["analytics"])
api_router.include_router(agents.router, prefix="/agents", tags=["agents"])
api_router.include_router(integrations.router, prefix="/integrations", tags=["integrations"])
api_router.include_router(workflows.router, prefix="/workflows", tags=["workflows"])
api_router.include_router(knowledge_base.router, prefix="/knowledge", tags=["knowledge-base"])
api_router.include_router(billing.router, prefix="/billing", tags=["billing"])
api_router.include_router(marketplace.router, prefix="/marketplace", tags=["marketplace"])
api_router.include_router(tools.router, prefix="/tools", tags=["tools"])

# Add more routers as they are created
# api_router.include_router(users.router, prefix="/users", tags=["users"])
