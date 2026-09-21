"""
Platform-level models: operator-managed settings and the admin audit trail.

Everything here belongs to Voicecon itself, not to any tenant. Nothing in this
module carries an ``organization_id``, and nothing outside the platform-admin
API reads or writes it — apart from ``app.core.runtime_settings``, which
overlays ``PlatformSetting`` rows onto the process's ``settings`` object.
"""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Index, JSON, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class PlatformSetting(Base):
    """One configuration value an operator set from the admin dashboard.

    A row *overrides* the environment variable of the same name; deleting the
    row falls back to the environment again. That is what makes it safe to
    adopt incrementally: a deployment with no rows behaves exactly as before.

    Secrets are stored encrypted with the integration credential key
    (``services/integrations/credential_manager``) and never leave the server in
    plaintext — the API only ever returns a masked hint.
    """

    __tablename__ = "platform_settings"

    #: The ``Settings`` attribute this row overrides, e.g. ``OPENAI_API_KEY``.
    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    #: Plain value for non-secret settings; NULL for secrets.
    value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    #: Fernet ciphertext for secret settings; NULL otherwise.
    value_encrypted: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_secret: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    #: Last four characters of a secret, kept so the UI can show which key is
    #: live without decrypting anything.
    hint: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)

    updated_by: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    def __repr__(self) -> str:
        return f"<PlatformSetting {self.key}>"


class AdminAuditLog(Base):
    """Append-only record of every change a platform admin made.

    ``details`` holds a before/after snapshot. Secret values are never written
    here — only the fact that one changed and its new masked hint.
    """

    __tablename__ = "admin_audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    actor_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid(as_uuid=True), nullable=True, index=True)
    #: Denormalised so the trail stays readable after the actor is deleted.
    actor_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    #: Dotted verb, e.g. ``setting.update``, ``organization.suspend``.
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    target_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    target_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    details: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    def __repr__(self) -> str:
        return f"<AdminAuditLog {self.action} {self.target_type}:{self.target_id}>"


Index("idx_admin_audit_target", AdminAuditLog.target_type, AdminAuditLog.target_id)
