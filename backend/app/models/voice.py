"""
Custom voice model.

A CustomVoice is a voice a workspace brought from its own TTS provider account
(an ElevenLabs cloned voice, say) and added to its voice library. Agents keep
referring to a voice by ``tts_provider`` + ``tts_voice_id``; this row is what
gives that id a name in the UI and, when the voice lives in the customer's own
provider account, the key needed to speak with it.
"""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class CustomVoice(Base):
    """A provider voice saved to a workspace's voice library."""

    __tablename__ = "custom_voices"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "provider", "voice_id", name="uq_custom_voice_org_provider_voice"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    voice_id: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # What the provider calls this kind of voice ("cloned", "professional", ...).
    category: Mapped[Optional[str]] = mapped_column(String(50))
    description: Mapped[Optional[str]] = mapped_column(Text)
    labels: Mapped[dict] = mapped_column(JSON, default=dict)

    # The customer's own provider key, Fernet-encrypted. NULL means the voice is
    # reachable with the platform's key. Never serialised to a response.
    api_key_encrypted: Mapped[Optional[str]] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    def __repr__(self) -> str:
        return f"<CustomVoice(org={self.organization_id}, {self.provider}:{self.voice_id})>"
