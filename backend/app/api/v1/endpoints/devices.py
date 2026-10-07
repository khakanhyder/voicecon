"""
Mobile devices: register a phone for chat push notifications.

Account-level, not workspace-level: one phone gets pushes for every workspace
its user can read chatbots in, and each push says which workspace it is for.
"""
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_active_user
from app.database import get_db
from app.models.chat import DeviceToken
from app.models.user import User
from app.services.chat.push import push_configured

logger = logging.getLogger(__name__)

router = APIRouter()


class DeviceRegister(BaseModel):
    token: str = Field(..., min_length=10, max_length=512, description="FCM registration token")
    platform: str = Field(..., pattern="^(android|ios)$")
    device_name: Optional[str] = Field(default=None, max_length=255)
    app_version: Optional[str] = Field(default=None, max_length=50)


class DeviceUnregister(BaseModel):
    token: str = Field(..., min_length=10, max_length=512)


@router.post("")
async def register_device(
    payload: DeviceRegister,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Register (or refresh) this phone's FCM token for the signed-in user.

    Call after every sign-in and whenever FCM rotates the token. Idempotent; a
    token previously registered to another account moves to this one.
    """
    device = (
        await db.execute(select(DeviceToken).where(DeviceToken.token == payload.token))
    ).scalar_one_or_none()
    if device is None:
        device = DeviceToken(token=payload.token)
        db.add(device)
    device.user_id = current_user.id
    device.platform = payload.platform
    device.device_name = payload.device_name
    device.app_version = payload.app_version
    device.token_version = current_user.token_version or 0
    device.last_seen_at = datetime.utcnow()
    await db.commit()
    return {"registered": True, "push_enabled": push_configured()}


@router.post("/unregister")
async def unregister_device(
    payload: DeviceUnregister,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Stop pushes to this phone (call on sign-out, before dropping the token)."""
    await db.execute(
        delete(DeviceToken).where(
            DeviceToken.token == payload.token, DeviceToken.user_id == current_user.id
        )
    )
    await db.commit()
    return {"registered": False}
