"""Provider keys and platform tunables, managed from the dashboard.

Values written here override the environment variable of the same name (see
``app.core.runtime_settings``). Secrets are write-only: the API accepts them,
stores them encrypted, and only ever returns a masked hint.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import runtime_settings as rs
from app.core.admin import audit, require_platform_admin
from app.core.config import settings
from app.database import get_db
from app.models.platform import PlatformSetting
from app.models.user import User
from app.services.admin.provider_checks import run_check
from app.services.billing import providers

from ._common import iso

router = APIRouter()


class SettingUpdate(BaseModel):
    value: Any


def _encryption_ready() -> bool:
    try:
        rs.encrypt_secret("probe")
        return True
    except Exception:
        return False


def _entry(spec: rs.SettingSpec, row: Optional[PlatformSetting], editors: Dict[Any, str]) -> Dict[str, Any]:
    baseline = rs.baseline_value(spec.key)
    errors = rs.db_errors()
    if row is not None and spec.key not in errors:
        source = "database"
    elif baseline not in (None, ""):
        source = "environment"
    else:
        source = "unset"

    entry: Dict[str, Any] = {
        "key": spec.key,
        "label": spec.label,
        "kind": spec.kind,
        "description": spec.description,
        "placeholder": spec.placeholder,
        "choices": list(spec.choices),
        "is_secret": spec.is_secret,
        "source": source,
        "has_env_value": baseline not in (None, ""),
        "error": errors.get(spec.key),
        "updated_at": iso(row.updated_at) if row else None,
        "updated_by": editors.get(row.updated_by) if row and row.updated_by else None,
    }
    if spec.is_secret:
        entry["value"] = None
        entry["hint"] = row.hint if source == "database" and row else rs.mask(baseline)
    else:
        effective = getattr(settings, spec.key, None)
        entry["value"] = effective
        entry["hint"] = None
    return entry


async def _rows(db: AsyncSession) -> Dict[str, PlatformSetting]:
    return {r.key: r for r in (await db.execute(select(PlatformSetting))).scalars().all()}


async def _editors(db: AsyncSession, rows) -> Dict[Any, str]:
    ids = {r.updated_by for r in rows if r.updated_by}
    if not ids:
        return {}
    result = await db.execute(select(User.id, User.email).where(User.id.in_(ids)))
    return {uid: email for uid, email in result.all()}


async def _guard_payment_provider(db: AsyncSession, key: str, new_value: Any) -> None:
    """Keep checkout working across provider changes.

    * Switching ``PAYMENT_PROVIDER`` is refused until the target provider has
      every key it needs; otherwise every Upgrade button would start failing.
    * Removing a key the *active* provider needs is refused for the same
      reason: switch provider first, then remove it.

    ``new_value`` is the value the key would have afterwards (``None`` = unset).
    """
    if key != "PAYMENT_PROVIDER" and not any(key in keys for keys in providers.REQUIRED_KEYS.values()):
        return
    await rs.refresh_quietly(db)
    if key == "PAYMENT_PROVIDER":
        target = str(new_value or "stripe").strip().lower()
        problem = providers.problem(target)
        if problem:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Can't switch payments to {providers.LABELS.get(target, target)} yet. {problem} Add the missing keys under {providers.LABELS.get(target, target)} first.",
            )
        return
    active = providers.active_provider()
    if key in providers.REQUIRED_KEYS[active] and new_value in (None, ""):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"{providers.LABELS[active]} is the active payment provider and needs this key. "
                "Switch the payment provider first, then remove it."
            ),
        )


def _spec_or_404(key: str) -> rs.SettingSpec:
    spec = rs.SPEC_BY_KEY.get(key)
    if spec is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="This setting cannot be managed here.")
    return spec


@router.get("/settings")
async def list_settings(
    db: AsyncSession = Depends(get_db),
    _admin=Depends(require_platform_admin),
):
    # Make sure this process reflects any change another replica made.
    await rs.refresh_quietly(db)
    rows = await _rows(db)
    editors = await _editors(db, rows.values())
    groups = []
    for group in rs.GROUPS:
        specs = [s for s in rs.SPECS if s.group == group.id]
        groups.append(
            {
                "id": group.id,
                "label": group.label,
                "description": group.description,
                "icon": group.icon,
                "test": group.test,
                "docs_url": group.docs_url,
                "settings": [_entry(s, rows.get(s.key), editors) for s in specs],
            }
        )
    return {
        "groups": groups,
        "encryption_ready": _encryption_ready(),
        "runtime": rs.status(),
    }


@router.put("/settings/{key}")
async def update_setting(
    key: str,
    payload: SettingUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_platform_admin),
):
    spec = _spec_or_404(key)
    try:
        value = rs.normalise(spec, payload.value)
    except rs.InvalidSettingValue as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=exc.public_message)
    await _guard_payment_provider(db, key, value)

    row = await db.get(PlatformSetting, key)
    previous_value = None if spec.is_secret else getattr(settings, key, None)
    previous_source = "database" if row else "environment"

    if row is None:
        row = PlatformSetting(key=key, is_secret=spec.is_secret)
        db.add(row)

    if spec.is_secret:
        try:
            row.value_encrypted = rs.encrypt_secret(value)
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=(
                    "Secrets cannot be stored because ENCRYPTION_SECRET_KEY and ENCRYPTION_SALT "
                    "are not configured on the server."
                ),
            )
        row.value = None
        row.hint = rs.mask(value)
    else:
        row.value = value
        row.value_encrypted = None
        row.hint = None
    row.is_secret = spec.is_secret
    row.updated_by = admin.id

    details: Dict[str, Any] = {"key": key, "previous_source": previous_source}
    if spec.is_secret:
        details["hint"] = row.hint
        summary = f"Set {spec.label} ({key}) to {row.hint}"
    else:
        details["before"] = previous_value
        details["after"] = value
        summary = f"Changed {spec.label} ({key})"
    audit(db, admin, "setting.update", target_type="setting", target_id=key, summary=summary, details=details, request=request)
    await db.commit()
    await rs.refresh(db, force=True)

    rows = await _rows(db)
    return _entry(spec, rows.get(key), await _editors(db, rows.values()))


@router.delete("/settings/{key}")
async def reset_setting(
    key: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_platform_admin),
):
    """Remove the dashboard value so the environment variable applies again."""
    spec = _spec_or_404(key)
    row = await db.get(PlatformSetting, key)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="This setting has no dashboard value.")
    await _guard_payment_provider(db, key, rs.baseline_value(key))
    await db.delete(row)
    audit(
        db,
        admin,
        "setting.reset",
        target_type="setting",
        target_id=key,
        summary=f"Reset {spec.label} ({key}) to the environment value",
        request=request,
    )
    await db.commit()
    await rs.refresh(db, force=True)
    return _entry(spec, None, {})


@router.post("/settings/test/{provider}")
async def test_provider(
    provider: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_platform_admin),
):
    await rs.refresh_quietly(db)
    result = await run_check(provider)
    audit(
        db,
        admin,
        "setting.test",
        target_type="provider",
        target_id=provider,
        summary=f"Tested {provider}: {result.status}",
        request=request,
    )
    await db.commit()
    return result.as_dict()
