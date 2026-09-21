"""System health and the admin audit trail."""
from __future__ import annotations

import time
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import runtime_settings
from app.core.admin import require_platform_admin
from app.core.config import MIN_SECRET_LENGTH, settings
from app.database import get_db
from app.models.platform import AdminAuditLog

from ._common import PageParams, iso, like, paginated
from .overview import provider_summary

router = APIRouter()


@router.get("/me")
async def admin_me(admin=Depends(require_platform_admin)):
    return {"id": str(admin.id), "email": admin.email, "full_name": admin.full_name}


async def _check_db(db: AsyncSession) -> dict:
    started = time.monotonic()
    try:
        await db.execute(text("SELECT 1"))
        return {"ok": True, "latency_ms": int((time.monotonic() - started) * 1000)}
    except Exception as exc:
        return {"ok": False, "error": type(exc).__name__}


async def _check_redis() -> dict:
    url = settings.REDIS_URL
    if not url:
        return {"ok": False, "configured": False, "error": "REDIS_URL is not set"}
    started = time.monotonic()
    try:
        import redis.asyncio as redis

        client = redis.from_url(url, socket_connect_timeout=2, socket_timeout=2)
        try:
            await client.ping()
        finally:
            await client.aclose() if hasattr(client, "aclose") else await client.close()
        return {"ok": True, "configured": True, "latency_ms": int((time.monotonic() - started) * 1000)}
    except Exception as exc:
        return {"ok": False, "configured": True, "error": type(exc).__name__}


async def _schedulers() -> list:
    out = []
    try:
        from app.services.billing.scheduler import get_billing_scheduler

        out.append({"name": "Billing reconciler", "running": bool(get_billing_scheduler().is_running)})
    except Exception:
        out.append({"name": "Billing reconciler", "running": False})
    try:
        from app.services.workflows.scheduler import get_scheduler as get_workflow_scheduler

        out.append({"name": "Workflow scheduler", "running": bool(getattr(get_workflow_scheduler(), "_running", False))})
    except Exception:
        out.append({"name": "Workflow scheduler", "running": False})
    try:
        from app.services.analytics.scheduler import get_scheduler as get_analytics_scheduler

        out.append({"name": "Analytics scheduler", "running": bool((await get_analytics_scheduler()).is_running)})
    except Exception:
        out.append({"name": "Analytics scheduler", "running": False})
    return out


def _secret_ok(value: Optional[str]) -> bool:
    return bool(value) and len(value) >= MIN_SECRET_LENGTH


@router.get("/system/health")
async def system_health(
    db: AsyncSession = Depends(get_db),
    _admin=Depends(require_platform_admin),
):
    return {
        "app": {
            "name": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "environment": settings.ENVIRONMENT,
            "debug": settings.DEBUG,
        },
        "database": await _check_db(db),
        "redis": await _check_redis(),
        "schedulers": await _schedulers(),
        "runtime_settings": runtime_settings.status(),
        "providers": provider_summary(),
        # Environment-only secrets: shown as present/absent, never as values.
        "bootstrap": [
            {"key": "SECRET_KEY", "ok": _secret_ok(settings.SECRET_KEY) and settings.SECRET_KEY != settings.DEFAULT_SECRET_KEY,
             "note": "Signs login tokens."},
            {"key": "ENCRYPTION_SECRET_KEY", "ok": _secret_ok(settings.ENCRYPTION_SECRET_KEY),
             "note": "Encrypts stored credentials, including keys saved in this dashboard."},
            {"key": "ENCRYPTION_SALT", "ok": bool(settings.ENCRYPTION_SALT), "note": "Must never change once set."},
            {"key": "EGRESS_ALLOW_PRIVATE", "ok": not settings.EGRESS_ALLOW_PRIVATE,
             "note": "Must be off outside tests."},
        ],
        "email_provider": settings.resolved_email_provider,
    }


@router.get("/audit-logs")
async def list_audit_logs(
    search: Optional[str] = Query(None, max_length=200),
    action: Optional[str] = Query(None, max_length=100),
    target_type: Optional[str] = Query(None, max_length=50),
    target_id: Optional[str] = Query(None, max_length=100),
    params: PageParams = Depends(),
    db: AsyncSession = Depends(get_db),
    _admin=Depends(require_platform_admin),
):
    query = select(AdminAuditLog)
    if search:
        term = like(search.strip())
        query = query.where(or_(AdminAuditLog.summary.ilike(term), AdminAuditLog.actor_email.ilike(term)))
    if action:
        query = query.where(AdminAuditLog.action.startswith(action))
    if target_type:
        query = query.where(AdminAuditLog.target_type == target_type)
    if target_id:
        query = query.where(AdminAuditLog.target_id == target_id)

    total = int((await db.execute(select(func.count()).select_from(query.subquery()))).scalar() or 0)
    rows = (
        await db.execute(query.order_by(AdminAuditLog.created_at.desc()).offset(params.offset).limit(params.page_size))
    ).scalars().all()
    items = [
        {
            "id": str(r.id),
            "actor_email": r.actor_email,
            "action": r.action,
            "target_type": r.target_type,
            "target_id": r.target_id,
            "summary": r.summary,
            "details": r.details,
            "ip_address": r.ip_address,
            "created_at": iso(r.created_at),
        }
        for r in rows
    ]
    return paginated(items, total, params)
