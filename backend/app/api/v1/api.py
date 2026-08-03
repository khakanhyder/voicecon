"""
API v1 router aggregator.

Organization-scoped routers carry a blanket :func:`workspace_guard`, so every
endpoint under them resolves the caller's current workspace and checks a
permission before the handler runs — reads need the ``:read`` permission,
anything else the ``:write`` one. Authorization is therefore the default for a
newly added endpoint rather than something each author must remember.

Routes that genuinely have no workspace (carrier webhooks, Stripe webhooks, the
public chat widget, the marketplace catalogue) live on a separate
``public_router`` in their module and are mounted without the guard.
"""
from fastapi import APIRouter, Depends

from app.core import permissions as perms
from app.core.dependencies import workspace_guard
from app.api.v1.endpoints import (
    agents,
    analytics,
    api_keys,
    auth,
    billing,
    calls,
    chat,
    integrations,
    invitations,
    knowledge_base,
    marketplace,
    notifications,
    onboarding,
    phone_numbers,
    team,
    telephony,
    tools,
    users,
    voice_stream,
    waitlist,
    workflows,
    workspaces,
)

api_router = APIRouter()


def _guard(read_permission: str, write_permission: str):
    return [Depends(workspace_guard(read_permission, write_permission))]


# ---- No workspace context: auth, the personal account, public surfaces ----
api_router.include_router(auth.router, tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(notifications.router, prefix="/notifications", tags=["notifications"])
api_router.include_router(invitations.router, prefix="/invitations", tags=["invitations"])
api_router.include_router(waitlist.router, prefix="/waitlist", tags=["waitlist"])
api_router.include_router(voice_stream.router, prefix="/voice", tags=["voice-stream"])

# ---- Workspace management: finer, per-endpoint checks live in the module ----
api_router.include_router(workspaces.router, prefix="/workspaces", tags=["workspaces"])
api_router.include_router(team.router, prefix="/team", tags=["team"])
api_router.include_router(onboarding.router, prefix="/onboarding", tags=["onboarding"])

# ---- Workspace-scoped resources ----
api_router.include_router(
    agents.router, prefix="/agents", tags=["agents"],
    dependencies=_guard(perms.AGENTS_READ, perms.AGENTS_WRITE),
)
api_router.include_router(
    calls.router, prefix="/calls", tags=["calls"],
    dependencies=_guard(perms.CALLS_READ, perms.CALLS_WRITE),
)
api_router.include_router(
    phone_numbers.router, prefix="/phone-numbers", tags=["phone-numbers"],
    dependencies=_guard(perms.PHONE_NUMBERS_READ, perms.PHONE_NUMBERS_WRITE),
)
api_router.include_router(
    workflows.router, prefix="/workflows", tags=["workflows"],
    dependencies=_guard(perms.WORKFLOWS_READ, perms.WORKFLOWS_WRITE),
)
api_router.include_router(
    tools.router, prefix="/tools", tags=["tools"],
    dependencies=_guard(perms.TOOLS_READ, perms.TOOLS_WRITE),
)
api_router.include_router(
    knowledge_base.router, prefix="/knowledge", tags=["knowledge-base"],
    dependencies=_guard(perms.KNOWLEDGE_READ, perms.KNOWLEDGE_WRITE),
)
api_router.include_router(
    integrations.router, prefix="/integrations", tags=["integrations"],
    dependencies=_guard(perms.INTEGRATIONS_READ, perms.INTEGRATIONS_WRITE),
)
api_router.include_router(
    analytics.router, prefix="/analytics", tags=["analytics"],
    dependencies=_guard(perms.ANALYTICS_READ, perms.ANALYTICS_READ),
)
api_router.include_router(
    chat.router, prefix="/chat", tags=["chat-widget"],
    dependencies=_guard(perms.AGENTS_READ, perms.AGENTS_WRITE),
)
api_router.include_router(
    marketplace.router, prefix="/marketplace", tags=["marketplace"],
    dependencies=_guard(perms.AGENTS_READ, perms.AGENTS_WRITE),
)
api_router.include_router(
    telephony.router, prefix="/telephony", tags=["telephony"],
    dependencies=_guard(perms.CALLS_READ, perms.CALLS_WRITE),
)
# An API key grants programmatic access to the whole workspace, so minting one
# is an admin act even though reading the list is not.
api_router.include_router(
    api_keys.router, prefix="/api-keys", tags=["api-keys"],
    dependencies=_guard(perms.API_KEYS_READ, perms.API_KEYS_MANAGE),
)
# Money: admins may look at the plan and invoices, only the owner may change them.
api_router.include_router(
    billing.router, prefix="/billing", tags=["billing"],
    dependencies=_guard(perms.BILLING_READ, perms.BILLING_MANAGE),
)

# ---- Public: provider webhooks and unauthenticated surfaces ----
api_router.include_router(telephony.public_router, prefix="/telephony", tags=["telephony"])
api_router.include_router(billing.public_router, prefix="/billing", tags=["billing"])
api_router.include_router(chat.public_router, prefix="/chat", tags=["chat-widget"])
api_router.include_router(marketplace.public_router, prefix="/marketplace", tags=["marketplace"])
api_router.include_router(workflows.public_router, prefix="/workflows", tags=["workflows"])
