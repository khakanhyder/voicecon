"""The admin console's bell.

Staff notifications (``ADMIN_NOTIFICATION_TYPES``) are rows in the same
``notifications`` table as the customer app's, but a console session cannot
reach ``/notifications`` and the app's bell never lists these types — so each
bell shows only what belongs to its own front door.
"""
from __future__ import annotations

import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.admin import require_platform_admin
from app.database import get_db
from app.models.notification import ADMIN_NOTIFICATION_TYPES, Notification
from app.schemas.notification import NotificationResponse, UnreadCountResponse

router = APIRouter(prefix="/notifications")


def _mine(admin):
    return (Notification.user_id == admin.id, Notification.type.in_(ADMIN_NOTIFICATION_TYPES))


@router.get("", response_model=List[NotificationResponse])
async def list_notifications(
    limit: int = Query(30, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_platform_admin),
):
    """This admin's notifications, unread first then newest."""
    result = await db.execute(
        select(Notification)
        .where(*_mine(admin))
        .order_by(Notification.is_read.asc(), Notification.created_at.desc())
        .limit(limit)
    )
    return result.scalars().all()


@router.get("/unread-count", response_model=UnreadCountResponse)
async def unread_count(db: AsyncSession = Depends(get_db), admin=Depends(require_platform_admin)):
    count = await db.scalar(
        select(func.count(Notification.id)).where(*_mine(admin), Notification.is_read.is_(False))
    )
    return UnreadCountResponse(count=count or 0)


@router.post("/read-all", status_code=status.HTTP_204_NO_CONTENT)
async def mark_all_read(db: AsyncSession = Depends(get_db), admin=Depends(require_platform_admin)):
    await db.execute(
        update(Notification).where(*_mine(admin), Notification.is_read.is_(False)).values(is_read=True)
    )
    await db.commit()


@router.post("/{notification_id}/read", response_model=NotificationResponse)
async def mark_read(
    notification_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_platform_admin),
):
    notification = await db.scalar(
        select(Notification).where(Notification.id == notification_id, *_mine(admin))
    )
    if notification is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    notification.is_read = True
    await db.commit()
    await db.refresh(notification)
    return notification
