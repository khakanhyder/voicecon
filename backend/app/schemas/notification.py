"""Pydantic schemas for in-app notifications."""
import uuid
from datetime import datetime
from typing import Any, Dict

from pydantic import BaseModel, ConfigDict


class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    type: str
    title: str
    body: str
    data: Dict[str, Any]
    is_read: bool
    is_actioned: bool
    created_at: datetime


class UnreadCountResponse(BaseModel):
    count: int
