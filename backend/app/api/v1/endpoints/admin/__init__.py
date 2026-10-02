"""
Platform admin API, mounted at ``/api/v1/admin``.

Every route here depends on :func:`app.core.admin.require_platform_admin`;
the router-level dependency below makes that the default for any route added
later, so an endpoint cannot be exposed by forgetting it.
"""
from fastapi import APIRouter, Depends

from app.core.admin import require_platform_admin

from . import (
    affiliate_applications,
    affiliates,
    billing,
    notifications,
    operations,
    organizations,
    overview,
    settings,
    system,
    users,
    wallet,
)

router = APIRouter(dependencies=[Depends(require_platform_admin)])
router.include_router(system.router)
router.include_router(overview.router)
router.include_router(settings.router)
router.include_router(organizations.router)
router.include_router(users.router)
router.include_router(billing.router)
router.include_router(wallet.router)
router.include_router(operations.router)
router.include_router(notifications.router)
# Before ``affiliates``: its ``/affiliates/{affiliate_id}`` would swallow ``/affiliates/applications``.
router.include_router(affiliate_applications.router)
router.include_router(affiliates.router)
